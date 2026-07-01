# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single Planner agent inspects an input and routes it to one of two
translational pipelines:

- **Bio** — a WES/scRNA bioinformatics pipeline (cell annotation, clustering,
  differential expression, GSEA; germline/somatic variant calling), merged
  in from the former `agent1poc` project.
- **GWAS** — a post-GWAS translational pipeline: Stage V2G (format_gwas →
  COJO → SuSiE) → Stage MR (SMR eQTL → two-sample MR → causal network) →
  Stage Drug (Open Targets druggability), merged in from the former
  `agnet2postGWAS` (AgentGWAS) project.

Both pipelines share one core (`src/agentcore/`): LLM provider abstraction,
async job queue, checkpoint persistence, and the web chat GUI. Domain-specific
agents, steps, and prompts live under `src/agentcore/domains/{bio,gwas}/`.
Runnable from a browser chat UI (`server.py`) or the CLI (`run_pipeline.py`,
`test_dispatch.py`). Providers: Claude (Anthropic), Gemini, Grok, and any
OpenAI-compatible endpoint.

This merge (agent1poc + agnet2postGWAS → this repo) intentionally kept both
domains' pipeline logic, prompts, and tool schemas unchanged in substance —
only the shared infrastructure was unified. See `docs/todo.md` for
pre-merge status notes (partially stale — verify against code before acting)
and the git history for the merge itself.

## Commands

```bash
# Install (core is always needed; add the extras for the domain(s) you use)
pip install -r requirements.txt
pip install -r requirements-bio.txt      # WES/scRNA
pip install -r requirements-gwas.txt     # post-GWAS
pip install pertpy                       # only for the bio multimodal demo download

# Download bio demo data
python download_demo_data.py                 # Kang 2018 multimodal (~100 MB) -> data/bio/demo_multimodal
python download_demo_data.py --demo scrna     # PBMC 3k single sample (~7 MB) -> data/bio/demo/pbmc3k.h5ad

# Full LLM pipeline (needs an API key via env var or --api-key)
export ANTHROPIC_API_KEY=sk-ant-...
python run_pipeline.py --input data/bio/demo_multimodal --run-id kang-demo
python run_pipeline.py --input smoketest/MASLD_chr1_slice.ma --trait MASLD --run-id masld-run1

# Web GUI (serves both domains through one page)
python server.py                   # http://127.0.0.1:8000  (--port to change)

# No-API-key test of the step/job/checkpoint layer (bypasses the LLM loop)
python test_dispatch.py --data data/bio/demo/pbmc3k.h5ad --run-id demo
python test_dispatch.py --gwas-file smoketest/MASLD_chr1_slice.ma --run-id gwas-demo
```

There is no formal test suite or linter. `test_dispatch.py` is the closest
thing to an integration test: it drives each domain's `tools.dispatch`
directly with deterministic Python branch logic instead of an LLM,
exercising the step → job-queue → checkpoint path without an API key. Use it
to verify changes to `steps/`, `jobs.py`, `state.py`, or either domain's
`tools.py`. GWAS steps that shell out to the `finemap`/`gwasagent` conda
envs are not covered by `test_dispatch.py` — see `smoketest/` for validated
real-run artifacts on those instead.

## Architecture

Three cooperating LLM agent layers, all defined once in `src/agentcore/agents/`
and shared by both domains:

- **Layer 1 — Planner** (`agentcore/agents/planner.py`, prompt
  `agentcore/prompts/planner.py`): inspects the input, detects which domain
  applies (`inspect_data_source` for bio, `inspect_gwas_input` for gwas —
  both tools are always available; the system prompt tells the model which
  to try first), presents a plan, dispatches workers/stages, then triggers
  the Reporter. Records the detected domain via `state.set_domain()` as soon
  as classification succeeds. Owns the main agent loop (`run()`) and an
  augmented `dispatch` that intercepts `dispatch_worker` (bio) /
  `dispatch_stage` (gwas) / `generate_report` and forwards everything else
  to `agentcore.tools.dispatch`.
- **Layer 2 — Workers/Stages** (`agentcore/domains/bio/agents/{wes,scrna}_agent.py`,
  `agentcore/domains/gwas/agents/{v2g,mr,drug}_agent.py`): each runs its
  branch's steps via `start_job`/`check_job_status`/`get_job_result` and
  returns a findings summary. Bio: WES = QC → alignment → mutation_calling;
  scRNA = cell_annotation → clustering → differential_expression → gsea.
  GWAS stages run sequentially: v2g → mr → drug.
- **Layer 3 — Reporter** (`agentcore/agents/reporter.py`): one shared agent
  loop and Markdown→HTML renderer for both domains. Reads `state.json`,
  synthesizes a report via the LLM, then branches on `checkpoint["domain"]`
  for domain-specific content: bio calls `domains/bio/figures.py` (PNG
  gallery) and `domains/bio/export.py` (`reproduce.sh`/`Snakefile`/
  `methods.md`); gwas links to the `network.png`/`network.html` already
  produced by the gwas `visualize` step.

### Core contracts

- **Every heavy step goes through `agentcore/jobs.py`** (`start_job` →
  `check_job_status` → `get_job_result`), even in bio's mock mode, so the
  model's tool-calling contract is identical when real mode is enabled
  later. Jobs run on a shared `ThreadPoolExecutor`.
- **Checkpointing is automatic, not agent-driven.** Each domain's `tools.py`
  wires a `state.record_step` callback into `start_job`'s `on_complete`;
  completion persists to `results/<run_id>/state.json`. A restarted run
  reads this back via `state.summarize_state` so finished steps aren't
  redone. `state.py` is thread-safe (module-level lock). `agent_log.jsonl`
  holds the full transcript.
- **`state.record_step` takes `phase=` and `exec_mode=`, not `mode=`.**
  Pre-merge, bio used `mode=` for mock/real execution mode and gwas used
  `stage=` for which stage (v2g/mr/drug) was running. Both are now separate,
  explicitly-named kwargs: `phase` is the domain branch/stage
  (`"wes"`/`"scrna"`/`"v2g"`/`"mr"`/`"drug"`), `exec_mode` is bio's
  mock/real execution mode. Reusing `mode` for both would have been
  ambiguous once a single `state.py` serves both domains.
- **`dispatch_worker` (bio) and `dispatch_stage` (gwas) are intentionally
  kept as two separate Planner tools**, not merged into one schema. Their
  input shapes don't collapse cleanly — bio's tool carries rich
  scenario/groups/paired-normal fields, gwas's carries a free-form `context`
  dict — and routing is already done by tool name, so forcing a single
  schema would only add risk (a higher chance of the model misusing
  fields across domains) for no simplification. Don't "fix" this into one
  tool later without re-reading this rationale.
- **Domain `tools.py` files are self-contained.** `agentcore/domains/bio/tools.py`
  and `agentcore/domains/gwas/tools.py` do not import from each other or
  from `agentcore/tools.py` — only the reverse (`agentcore/tools.py` imports
  the pieces it needs from both, one direction, no cycle). This is what lets
  each domain be read, tested, and extended independently.
- **Per-agent tool subsets**: `agentcore/tools.py` assembles the unified
  `PLANNER_TOOLS` (both domains' inspect + dispatch tools, plus shared
  `list_available_assets`/`read_checkpoint`/`request_confirmation`/
  `fetch_external_data`/`generate_report`) and `REPORTER_TOOLS`. Each
  domain's own `tools.py` defines its own `WORKER_TOOLS`/`V2G_TOOLS`/
  `MR_TOOLS`/`DRUG_TOOLS` and `STEP_FUNCS` (step name → `steps/*.run`).
- **Provider abstraction** (`agentcore/providers.py`): agents only use
  `send_user_text`/`send_tool_results`/`step() -> TurnResult`. Gemini and
  Grok route through `OpenAIProvider` with fixed base URLs. On a 503/429/529
  the provider automatically retries down a per-vendor fallback model list.
  Default Anthropic model is `claude-opus-4-8`. SDKs (`anthropic`, `openai`)
  are imported lazily so only the chosen provider's package needs to be
  installed. `providers.py` never imports tool schemas — callers always pass
  their own `tools=` list explicitly.

### Step modules

**Bio** (`domains/bio/steps/*.py`): each exposes
`run(*, mode="mock", **kwargs) -> dict` with two paths — **mock** (default):
synthetic-but-plausible metrics, seeded deterministically from the input
path via `seeded_random`/`compute_seed`, so repeated mock runs on the same
input agree; this is the demo path. **real**: shells out to the actual tool
(fastp, bwa, GATK4, scanpy, harmonypy, leidenalg, gseapy) in the `wes` conda
env (WES) or the base env (scRNA). Raises a clear error naming exactly
what's missing rather than faking success. `domains/bio/steps/detect.py`
classifies inputs by file *content*, never by name.

**GWAS** (`domains/gwas/steps/*.py`): thin Python wrappers around the
standalone scripts in `tools/` (`cojo.sh`, `*.R`, python wrapper scripts),
run as subprocesses — no mock/real distinction, they either run for real or
fail with a clear missing-dependency/missing-file error. Real execution of
`cojo.sh`/`extract_ld_and_run_susie.sh`/`susie_finemap.R`/`run_mr_pipeline.sh`
needs the `finemap` conda env (`gcta64`, `plink`, R + `susieR`,
`TwoSampleMR`); the rest need only the `gwasagent` env (this repo's own
Python deps). Stage agents shell out to `finemap` via `conda run -n finemap ...`.

## Domains

Adding a third domain means adding a third `agentcore/domains/<name>/`
package (agents/prompts/steps/tools.py, self-contained per the contract
above) and a third dispatch tool the Planner routes to — not touching the
shared core (`providers.py`, `jobs.py`, `session.py`, `state.py`) unless the
new domain needs a genuinely new checkpoint field.

## Conventions

- **UTF-8 is forced explicitly.** Entrypoints call
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` and all file
  I/O passes `encoding="utf-8"`, because the primary dev machine runs a
  cp950 (Traditional Chinese Windows) locale where LLM output containing
  `β`, `≥`, `→` etc. would otherwise crash. Preserve this when adding file
  reads/writes or print paths.
- `results/` and `data/` are git-ignored (large outputs and machine-specific
  symlinks); `smoketest/` and `configs/` are deliberately tracked. Never
  commit run output into `results/`.
- Bio's pre-merge legacy shims (`orchestrator.py`, top-level `prompts.py`)
  were **not** ported into this merge — they were already marked
  do-not-extend in agent1poc's own CLAUDE.md, so there was no benefit to
  carrying them forward.

## Outstanding work

See `docs/todo.md` for the pre-merge bio status audit (stale in parts —
verify against the code before acting). Merge-specific follow-ups:
- GWAS-side `test_dispatch.py` coverage is limited to pure-Python steps
  (`format_gwas`, `extract_graph`); conda-env-dependent steps rely on
  `smoketest/` fixtures instead of a deterministic no-API-key test.
- The merged Planner system prompt concatenates both domains' full
  scenario-routing instructions into one static prompt (~300+ lines). If
  token cost becomes an issue, consider loading the domain-specific block
  dynamically once `inspect_data_source`/`inspect_gwas_input` returns,
  instead of including both from turn 1.
