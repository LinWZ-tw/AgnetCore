# Translational Agent Framework

A single LLM-orchestrated **Planner** agent routes between two translational
bioinformatics pipelines depending on what data you hand it — you never have
to say which one you want:

- **Bio** — whole-exome sequencing (WES) and single-cell RNA-seq (scRNA)
  analysis: QC → alignment → mutation-calling (WES), or cell-annotation →
  clustering → differential-expression → GSEA (scRNA).
- **GWAS** — a post-GWAS translational pipeline ("AgentGWAS"): Stage V2G
  (format_gwas → COJO → SuSiE fine-mapping) → Stage MR (SMR eQTL validation
  → optional two-sample MR → causal network) → Stage Drug (Open Targets
  druggability lookup).

Drive it from a browser chat UI (`server.py`) or an interactive CLI
(`run_pipeline.py`). Both talk to the same Planner/Worker/Reporter agent
stack and write to the same `results/<run_id>/` checkpoint, so a run started
on one can be resumed from the other. Supports Claude (Anthropic), Google
Gemini, xAI Grok, and any OpenAI-compatible endpoint (OpenAI, Ollama, vLLM,
Groq, etc.).

This repository merges two formerly-separate projects (`agent1poc` and
`agnet2postGWAS`/AgentGWAS) that shared nearly identical infrastructure
(provider abstraction, job queue, checkpointing, chat session, report
rendering) into one framework, with the domain-specific pipeline code kept
cleanly separated under `agentcore/domains/`. See `CLAUDE.md` for the
merge-specific rationale behind individual design decisions.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r requirements-bio.txt      # for the WES/scRNA pipeline
pip install -r requirements-gwas.txt     # for the post-GWAS pipeline
pip install pertpy                       # only needed for the bio multimodal demo download

# 2. Set your API key
export ANTHROPIC_API_KEY=sk-ant-...   # Claude (default provider)
# export GEMINI_API_KEY=AIza...       # Gemini
# export GROK_API_KEY=xai-...         # Grok
# export OPENAI_API_KEY=sk-...        # OpenAI / OpenAI-compatible
```

### Option A — Web GUI

```bash
python server.py    # open http://127.0.0.1:8000
```

Fill in the sidebar: provider, API key, and an **Input path** — a data
directory / `.h5ad` / `.h5` file for bio, or a GWAS summary-statistics file
(`.tsv`/`.csv`/`.ma`, optionally `.gz`) for gwas. Optionally add free-text
notes (study design, trait name, sample metadata) — these are appended to
the agent's first message as extra context. The Planner inspects the input
itself and picks the right pipeline. A green **"Open report"** button
appears in the sidebar once `report.html` exists; you can also type follow-up
messages into the chat at any time, even while the agent is mid-run.

### Option B — CLI

```bash
# Bio demo (downloads a Kang 2018 case-control scRNA + mock WES cohort)
python download_demo_data.py
python run_pipeline.py --input data/bio/demo_multimodal --run-id kang-demo

# GWAS demo (uses the tracked MASLD chr1 smoketest slice)
python run_pipeline.py --input smoketest/MASLD_chr1_slice.ma --trait MASLD --run-id masld-run1
```

**The CLI is fully interactive.** Whenever the model finishes a turn without
calling a tool (e.g. it just presented an analysis plan and is waiting), the
agent pauses at a `You:` prompt and waits for your reply — correct the
scenario, add metadata, adjust the plan, or just press <kbd>Enter</kbd> to
accept and let it proceed. <kbd>Ctrl-C</kbd> stops the wait and lets the run
finish with whatever the model last produced. Pass `--no-interactive` to
disable the pause entirely (useful for scripted/batch runs). The full
turn-by-turn transcript is saved to `results/<run_id>/agent_log.jsonl`
either way.

`--data` and `--gwas-file` are accepted as deprecated aliases for `--input`,
kept for anyone used to the pre-merge flag names from `agent1poc` /
`agnet2postGWAS` respectively; supplying either also sets an implicit domain
hint (bio / gwas) that nudges (but does not force) which inspection tool the
Planner tries first.

### Resuming a run

Both entrypoints are checkpoint-aware. Re-running `run_pipeline.py` with the
same `--run-id` (or reconnecting to the same `run_id` in the GUI) loads
`results/<run_id>/state.json`, summarizes what is already recorded, and
tells the model to skip completed steps — this is what lets a long GWAS run
or an interrupted GUI session pick back up instead of restarting from
scratch.

## Architecture

Three agent layers sit on top of a small set of shared infrastructure
modules. The same Planner, dispatch tools, job queue, and checkpoint format
serve both domains; only the Layer-2 workers/stages and their step libraries
are domain-specific.

```
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 0 — Entrypoints                                                  │
│  server.py (+ static/index.html, browser chat)   or   run_pipeline.py   │
│  server.py wraps each run in a long-lived agentcore.session.AgentSession│
│  (background thread); run_pipeline.py drives agentcore.agents.planner   │
│  .run() directly, once, to completion.                                  │
└────────────────────────────┬─────────────────────────────────────────-─┘
                              │ goal + input_path (+ optional domain hint)
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 1 — Planner   agentcore/agents/planner.py                        │
│  • Calls inspect_data_source or inspect_gwas_input to classify the input│
│  • Records the domain on the checkpoint (state.set_domain)              │
│  • Presents an analysis plan in chat, waits for approval / corrections  │
│  • dispatch_worker (bio) / dispatch_stage (gwas) to run Layer 2         │
│  • generate_report calls the Reporter (Layer 3) once all steps are done │
└──────────┬───────────────────────────────┬───────────────────────────-─┘
           │ dispatch_worker(branch=...)   │ dispatch_stage(stage=...)
           ▼                               ▼
┌───────────────────────┐       ┌────────────────────────────────────────┐
│  Bio Workers           │       │  GWAS Stage Agents                     │
│  domains/bio/agents/   │       │  domains/gwas/agents/                  │
│  wes_agent  (per WES   │       │  v2g_agent  (format_gwas→COJO→SuSiE)   │
│   sample: qc→alignment │       │  mr_agent   (SMR eQTL→2-sample MR      │
│   →mutation_calling)   │       │              →causal network)          │
│  scrna_agent (per scRNA│       │  drug_agent (Open Targets              │
│   sample: annotation→  │       │              druggability)             │
│   clustering→diffexp→  │       │  Stages run sequentially: v2g → mr →   │
│   gsea)                │       │  drug, each reading prior stage output │
└──────────┬─────────────┘       │  from the checkpoint via read_checkpoint│
           │                     └──────────────────┬─────────────────────┘
           │  each step: start_job → poll → checkpointed via state.record_step
           └──────────────────┬───────────────────────────────────────────
                              │ full checkpoint (results/<run_id>/state.json)
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 3 — Reporter   agentcore/agents/reporter.py                      │
│  • Shared agent loop + Markdown→HTML rendering for both domains          │
│  • Reads checkpoint["domain"] to pick the domain-specific extra section: │
│    - bio:  domains/bio/figures.py (PNG/Plotly gallery) +                 │
│            domains/bio/export.py (reproduce.sh, Snakefile, methods.md)   │
│    - gwas: links network.png/network.html already produced by the        │
│            `visualize` step (run earlier, inside the mr_agent stage)     │
│  • Writes report/report.md + report/report.html                         │
└────────────────────────────────────────────────────────────────────────┘
```

**Shared infrastructure** (`src/agentcore/`, used identically by both
domains):

| Module | Role |
|---|---|
| `providers.py` | Normalizes Claude/OpenAI/Gemini/Grok into one `send_user_text` / `send_tool_results` / `step()` interface, with automatic model-fallback on 429/503/529. |
| `jobs.py` | Thread-pool background job queue (`start_job` / `check_job_status` / `get_job_result`) so no agent ever blocks on a long-running step. |
| `state.py` | Checkpoint persistence — `results/<run_id>/state.json` (ordered step records + `domain` field) and `agent_log.jsonl` (full transcript). |
| `session.py` | `AgentSession` — wraps the Planner in a background thread with an inbox queue, for the GUI's long-lived, interruptible chat. |
| `tools.py` | Assembles the Planner's unified tool list from both domains' tool modules; hosts the domain-agnostic tools (`list_available_assets`, `read_checkpoint`, `request_confirmation`, `fetch_external_data`). |

## Data flow

Concretely, here is what happens end to end for one run, using the CLI as
the example (the GUI follows the identical sequence, just event-driven
through `AgentSession` instead of a blocking loop):

1. **You provide** `--input <path>` (+ optional `--trait`, `--goal`,
   `--provider`, notes). `run_pipeline.py` resolves the API key/model and
   calls `agentcore.agents.planner.run()`.
2. **Planner turn 1 — classify.** The Planner is given both domains'
   inspection tools at once (`inspect_data_source`, `inspect_gwas_input`)
   and tries the one the domain hint (or the path's shape) suggests first.
   Whichever succeeds is recorded via `state.set_domain(run_id, "bio"|"gwas")`
   — this single write is what lets a later Reporter (or a resumed session)
   know which domain's logic to use, even if the run is interrupted right
   after classification.
3. **Planner turn 2 — plan.** Using the inspection result (data type,
   evidence, detected columns/read-lengths/sample counts...), the Planner
   drafts a concrete step-by-step plan and prints it. In interactive mode
   (CLI default, or GUI chat) it stops here and waits for you to approve,
   correct, or add metadata before continuing.
4. **Dispatch to Layer 2.** For bio, the Planner calls `dispatch_worker`
   once per sample (`branch="wes"` or `branch="scrna"`, plus `scenario`,
   `groups`, etc.), which imports and runs `wes_agent.run()` /
   `scrna_agent.run()` synchronously (each is its own short-lived LLM
   agent with its own tool loop). For gwas, it calls `dispatch_stage`
   sequentially for `"v2g"`, then `"mr"`, then `"drug"`, passing a
   free-form `context` dict (trait name, PLINK bfile, eQTL path, sample
   size, outcome GWAS file, ...) — each stage reads the prior stage's
   recorded outputs back out of the checkpoint via `read_checkpoint`
   rather than receiving them directly as arguments.
5. **Step execution (both domains, identical contract).** Inside a
   worker/stage agent, every heavy step is: `start_job(step, args)` →
   `jobs.start_job()` submits the actual step function
   (`domains/<x>/steps/*.py::run`) to a background thread pool and returns
   a `job_id` immediately → the agent polls `check_job_status(job_id)` →
   once `"done"`, `get_job_result(job_id)`. The instant a job finishes, its
   completion callback calls `state.record_step(...)`, so the checkpoint is
   always current on disk without the model having to remember to save
   anything. `mode="mock"` (the default) runs a deterministic,
   seed-from-input-hash synthetic step instead of shelling out to the real
   tool — same function signature, same output shape, so nothing else in
   the pipeline needs to know which mode ran.
6. **Worker/stage returns a summary.** `wes_agent`/`scrna_agent`/
   `v2g_agent`/`mr_agent`/`drug_agent` each end their own tool loop with a
   short natural-language findings summary, which `dispatch_worker`/
   `dispatch_stage` hands back to the Planner as the tool result.
7. **Report.** Once all dispatches return, the Planner calls
   `generate_report`, which runs `agentcore.agents.reporter.run()`: a
   fresh short agent loop that calls `read_checkpoint`, writes a full
   Markdown report, then (in Python, not the LLM) branches on
   `checkpoint["domain"]` to attach the bio figure gallery +
   reproducibility artifacts, or the gwas causal-network diagram link.
   `report.md` and `report.html` are written to `results/<run_id>/report/`.
8. **You read the result.** CLI prints the output paths and exits; the GUI
   polls `/api/sessions/<run_id>/report_ready` and lights up the "Open
   report" button once `report.html` exists on disk.

## Tool reference

Every LLM agent in this framework only ever sees tool schemas — it never
calls Python directly. The table below is the full toolbox, grouped by
which agent layer holds it.

| Tool | Used by | Purpose |
|---|---|---|
| `inspect_data_source` | Planner | Classify a bio input path (fastq archive/dir, `.h5`, `.h5ad`, multimodal cohort) without extracting anything. |
| `inspect_gwas_input` | Planner | Sniff a GWAS summary-stats file: separator, columns, row count, min p-value, genome-build hints. |
| `dispatch_worker` | Planner | Hand one bio sample off to `wes_agent` or `scrna_agent`. |
| `dispatch_stage` | Planner | Hand off to `v2g_agent` / `mr_agent` / `drug_agent`, in order. |
| `generate_report` | Planner | Trigger the Reporter once all dispatches are done. |
| `fetch_external_data` | Planner | Whitelisted GET against `configs/external_sources.json` sources (GTEx, GWAS Catalog, Open Targets, Ensembl, IEU OpenGWAS) — used e.g. to look up eQTL tissues or annotate a gene before dispatching. |
| `list_available_assets` | all agents | Glob a directory (size + mtime) instead of guessing paths. |
| `read_checkpoint` | all agents | Summarize what's already recorded for this run — how workers/stages see each other's prior outputs, and how a resumed run avoids redoing steps. |
| `request_confirmation` | all agents | Gate on expensive/irreversible real-mode actions; auto-approved (mock-only) unless `auto_approve=False`. |
| `start_job` / `check_job_status` / `get_job_result` | worker & stage agents | Non-blocking execution of one step (see Data flow §5). |
| `locate_fastq_pairs` | wes_agent | Pair up `R1`/`R2` fastq.gz files in a directory before a real-mode `qc`/`alignment` call. |
| `write_json_config` | v2g_agent, mr_agent | The only disk-write tool available to gwas stage agents — used for `susie_batch`'s `--config` and `extract_graph`'s `trait_trait_mr_config`. |

## File layout

```
requirements.txt              core deps (anthropic, openai)
requirements-bio.txt          bio extras (matplotlib, scanpy, anndata, h5py)
requirements-gwas.txt         gwas extras (pandas, numpy, scipy, networkx, pyvis, ...)
download_demo_data.py         downloads bio demo datasets
run_pipeline.py                CLI entrypoint: goal + input -> planner, runs to completion
server.py                      web server: GUI <-> planner agent session
static/index.html              browser GUI (provider picker, API key, input path, chat panel)
test_dispatch.py                no-LLM step-library test harness for both domains
test_state.py                   unit tests for checkpoint persistence
configs/
  external_sources.json         whitelist of external APIs for fetch_external_data
  example_run.md                worked example transcript
tools/                          gwas standalone scripts (cojo.sh, *.R, python wrappers)
smoketest/                      tracked validated gwas run artifacts (MASLD dry runs)
docs/                           grant/planning docs (CommonFundDataPilotProject_R03), docs/todo.md
data/{bio,gwas}/                 gitignored local input data
results/                        gitignored run outputs
src/agentcore/
  __init__.py                   REPO_ROOT, RESULT_DIR, TOOLS_DIR, conda env constants
  providers.py                   LLM provider abstraction (Anthropic/OpenAI/Gemini/Grok)
  jobs.py                        background async job queue
  session.py                     web chat session wrapper
  state.py                       checkpoint persistence (results/<run_id>/state.json)
  tools.py                       shared tool schemas + unified Planner dispatch
  agents/
    planner.py                   Layer 1: domain detection, plan, dispatch, report trigger
    reporter.py                  Layer 3: shared report synthesis + rendering
  prompts/
    planner.py                   merged system prompt (bio + gwas routing sections)
    reporter.py                  merged reporter prompt (domain-conditional sections)
  domains/
    bio/
      agents/wes_agent.py, scrna_agent.py
      steps/  detect.py, qc.py, alignment.py, mutation.py,
              annotation.py, clustering.py, diffexp.py, gsea.py
      prompts/ wes.py, scrna.py
      tools.py, figures.py, export.py
    gwas/
      agents/v2g_agent.py, mr_agent.py, drug_agent.py
      steps/  format_gwas.py, cojo.py, susie.py, smr_eqtl.py,
              two_sample_mr.py, graph.py, visualize.py, druggability.py
      prompts/ v2g.py, mr.py, druggability.py
      tools.py
```

## Requirements

### LLM providers

| Provider | API key source | Default model |
|---|---|---|
| Claude (Anthropic) | console.anthropic.com | `claude-opus-4-8` |
| Google Gemini | aistudio.google.com/apikey | `gemini-2.5-flash` |
| xAI Grok | console.x.ai | `grok-3` |
| OpenAI | platform.openai.com/api-keys | `gpt-4o` |
| OpenAI-compatible (Ollama, vLLM, Groq, ...) | varies | set model explicitly |

Keys are sent from the browser to the local server process only, forwarded
directly to the chosen SDK, and never logged or written to disk. Each
provider also has a fixed fallback model list (`providers.py`) that is
tried automatically if the chosen model returns HTTP 429/503/529.

### Bio real-mode tools (not in requirements-bio.txt)

`bwa`, `gatk4`, `picard`, `samtools`, `bcftools`, `fastp` in a `wes` conda
env; `harmonypy`, `leidenalg`, `gseapy` for scRNA real-mode steps. Mock mode
(the default) only needs `requirements-bio.txt`.

### GWAS conda environments

| Environment | Purpose |
|---|---|
| `gwasagent` | Python pipeline: `run_pipeline.py`, `server.py`, pure-Python tools (`requirements-gwas.txt`) |
| `finemap` | `gcta64`, `plink`, R + `susieR`, `TwoSampleMR` — used by `cojo.sh`, `extract_ld_and_run_susie.sh`, `susie_finemap.R`, `run_mr_pipeline.sh` |

Stage agents shell out to `finemap` automatically via `conda run -n finemap ...`.

### External data sources (`configs/external_sources.json`)

The Planner's `fetch_external_data` tool is restricted to a whitelist of
base URLs: GTEx (`gtex`), GWAS Catalog (`gwas_catalog`), Open Targets
Platform (`open_targets_platform`), Ensembl (`ensembl`), and IEU OpenGWAS
(`ieu_opengwas`). Add new sources by editing that file — no code changes
needed, `agentcore/domains/gwas/tools.py` loads it at import time.

## Outputs

All runs write to `results/<run_id>/`:

```
state.json                     ordered checkpoint (status, inputs, outputs per step; domain field)
agent_log.jsonl                full turn-by-turn transcript for audit/debugging
report/report.md               narrative Markdown report
report/report.html             HTML report with sticky sidebar TOC
report/figures/<id>_*.png      bio only: matplotlib PNGs (one set per sample)
report/network.png/.html       gwas only: causal network diagram (static + interactive)
reproduce.sh, Snakefile,
methods.md                     bio only: reproducibility artifacts
<output_prefix>.ma, .jma.cojo,
edges.tsv, nodes.tsv, ...       gwas only: intermediate/output files, see CLAUDE.md
```

## Known limitations

| Feature | Status |
|---|---|
| Somatic mutation calling (Mutect2, paired tumour/normal) | Planned — germline pipeline used as approximation |
| Pseudotime / trajectory (PAGA, Monocle3, RNA velocity) | Planned — clustering + DE used as proxy |
| Cell–cell communication (CellChat, NicheNet) | Planned |
| Mutational signature analysis (SigProfiler) | Planned |
| Copy number variation (CNV) | Planned |
| GWAS deterministic (no-API-key) test coverage | Limited to pure-Python steps; conda-env-dependent steps covered by `smoketest/` only |

See `CLAUDE.md` for architecture details and merge-specific rationale, and
`docs/todo.md` for pre-merge bio status notes (partially stale).
