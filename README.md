# Translational Agent Framework

A single LLM-orchestrated Planner routes between two translational
pipelines depending on what you give it:

- **Bio** — whole-exome sequencing (WES) and single-cell RNA-seq (scRNA)
  analysis: QC/alignment/mutation-calling, or cell-annotation/clustering/
  differential-expression/GSEA.
- **GWAS** — a post-GWAS translational pipeline (AgentGWAS): Stage V2G
  (format_gwas → COJO → SuSiE) → Stage MR (SMR eQTL → two-sample MR →
  causal network) → Stage Drug (Open Targets druggability).

Drive it from a browser chat UI (`server.py`) or the CLI
(`run_pipeline.py`, `test_dispatch.py`). Supports Claude (Anthropic),
Google Gemini, xAI Grok, and any OpenAI-compatible endpoint (OpenAI,
Ollama, vLLM, Groq, etc.).

This repository merges two formerly-separate projects (`agent1poc` and
`agnet2postGWAS`/AgentGWAS) that shared nearly identical infrastructure
into one framework — see `CLAUDE.md` for the architecture and the
rationale behind specific merge decisions.

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
# export OPENAI_API_KEY=sk-...        # OpenAI / OpenAI-compatible
```

### Option A — Web GUI

```bash
python server.py    # open http://127.0.0.1:8000
```

Fill in the sidebar: provider, API key, and an **Input path** — a data
directory / `.h5ad` / `.h5` file for bio, or a GWAS summary-statistics file
(`.tsv`/`.csv`/`.ma`, optionally `.gz`) for gwas. The Planner inspects the
input itself and picks the right pipeline; you don't need to tell it which
domain you're in. A green **"Open report"** button appears in the sidebar
when done.

### Option B — CLI

```bash
# Bio demo (downloads a Kang 2018 case-control scRNA + mock WES cohort)
python download_demo_data.py
python run_pipeline.py --input data/bio/demo_multimodal --run-id kang-demo

# GWAS demo (uses the tracked MASLD chr1 smoketest slice)
python run_pipeline.py --input smoketest/MASLD_chr1_slice.ma --trait MASLD --run-id masld-run1
```

**The CLI is fully interactive.** The agent pauses at each decision point
and waits for your reply at a `You:` prompt — correct the scenario, add
metadata, adjust the plan, or just press Enter to accept and proceed
(Ctrl-C to stop). The full transcript is saved to
`results/<run_id>/agent_log.jsonl` regardless of how you interact.

`--data` and `--gwas-file` are accepted as deprecated aliases for
`--input`, for anyone used to the pre-merge flag names.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 0 — GUI / CLI                                              │
│  server.py + static/index.html   or   run_pipeline.py             │
└─────────────────────────┬────────────────────────────────────────┘
                          │ goal + input path
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1 — Planner    agentcore/agents/planner.py                 │
│  • Detects domain (inspect_data_source vs inspect_gwas_input)     │
│  • Presents an analysis plan, waits for approval                  │
│  • Dispatches Layer-2 workers/stages                              │
│  • Hands the completed checkpoint to the Reporter (Layer 3)       │
└──────────┬───────────────────────────────┬───────────────────────┘
           │ bio: dispatch_worker          │ gwas: dispatch_stage
           ▼                               ▼
┌──────────────────────┐       ┌───────────────────────────────────┐
│  Bio Workers          │       │  GWAS Stage Agents                │
│  domains/bio/agents/  │       │  domains/gwas/agents/              │
│  wes_agent, scrna_agent│      │  v2g_agent, mr_agent, drug_agent   │
└──────────┬───────────┘       └──────────────────┬────────────────┘
           │  step results                        │
           └──────────────────┬───────────────────┘
                              │ full checkpoint (results/<run_id>/state.json)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3 — Reporter    agentcore/agents/reporter.py                │
│  • Shared Markdown→HTML synthesis for both domains                 │
│  • Bio: figure gallery (domains/bio/figures.py) + reproducibility  │
│    artifacts (domains/bio/export.py)                                │
│  • GWAS: links the causal-network diagram produced by the           │
│    `visualize` step                                                 │
└──────────────────────────────────────────────────────────────────┘
```

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
configs/                        external_sources.json -- gwas fetch_external_data whitelist
tools/                          gwas standalone scripts (cojo.sh, *.R, python wrappers)
smoketest/                      tracked validated gwas run artifacts (MASLD chr19 dry run)
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
    reporter.py                   merged reporter prompt (domain-conditional sections)
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
directly to the chosen SDK, and never logged or written to disk.

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
