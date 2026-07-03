"""GWAS-domain tool schemas and dispatch table (V2G / MR / Drug stages).

Design: every heavy step is started via start_job and polled via
check_job_status / get_job_result -- the model is never blocked on a long
subprocess. Checkpointing happens automatically inside the job completion
callback.

This module is self-contained: it does not import from `agentcore.tools`
or from the bio domain. `agentcore/tools.py` imports the pieces it needs
from here (one direction only) to assemble the unified Planner's tool list.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from agentcore import REPO_ROOT, jobs, state

from .steps import cojo, format_gwas, graph, prs, smr_eqtl, susie, two_sample_mr, visualize, druggability

STEP_FUNCS = {
    "format_gwas":    format_gwas.run,
    "cojo":           cojo.run,
    "susie_locus":    susie.run_locus,
    "susie_batch":    susie.run_batch,
    "smr_eqtl":       smr_eqtl.run,
    "two_sample_mr":  two_sample_mr.run,
    "extract_graph":  graph.run,
    "visualize":      visualize.run,
    "druggability":   druggability.run,
    "prs":            prs.run,
}

_STEP_LIST = ", ".join(STEP_FUNCS)

INSPECT_GWAS_INPUT: dict[str, Any] = {
    "name": "inspect_gwas_input",
    "description": (
        "Inspect a GWAS summary-statistics file and return detected metadata: "
        "file format, column names in the header, row count, minimum p-value, "
        "and any genome-build hints (e.g. 'chr' prefix, rs-ID presence, hg19 vs hg38). "
        "Call this when the input is a single tabular file (.tsv/.csv/.ma, optionally .gz) "
        "rather than a directory or sequencing-data file. "
        "Use this before format_gwas_to_ma to confirm column names are correct."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the GWAS file (.tsv/.csv, optionally .gz)."},
        },
        "required": ["path"],
    },
}

DISPATCH_STAGE_TOOL: dict[str, Any] = {
    "name": "dispatch_stage",
    "description": (
        "Dispatch a post-GWAS pipeline stage to its dedicated sub-agent and wait for it to complete. "
        "Stages run sequentially: v2g first, then mr (using V2G outputs), then drug (using gene list). "
        "prs is an optional stage that builds a polygenic risk score from the V2G-formatted .ma; "
        "run it after v2g (it needs only the .ma and a PLINK bfile, not mr/drug outputs). "
        "stage must be one of: 'v2g', 'mr', 'drug', 'prs'. "
        "context is a free-form dict passed to the sub-agent as additional context "
        "(e.g. {trait, plink_bfile_ref, eqtl_path, sample_size, outcome_gwas_csv, target_bfile})."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "stage": {"type": "string", "enum": ["v2g", "mr", "drug", "prs"]},
            "context": {"type": "object", "description": "Stage-specific parameters and file paths."},
        },
        "required": ["stage"],
    },
}

_LIST_ASSETS: dict[str, Any] = {
    "name": "list_available_assets",
    "description": "List files matching a glob pattern under a directory, with size and mtime.",
    "input_schema": {
        "type": "object",
        "properties": {
            "root": {"type": "string"},
            "pattern": {"type": "string", "default": "*"},
            "limit": {"type": "integer", "default": 30},
        },
        "required": ["root"],
    },
}

_READ_CHECKPOINT: dict[str, Any] = {
    "name": "read_checkpoint",
    "description": "Return a summary of all steps already recorded for this run (for resuming or reading prior stage outputs).",
    "input_schema": {"type": "object", "properties": {}},
}

_REQUEST_CONFIRMATION: dict[str, Any] = {
    "name": "request_confirmation",
    "description": (
        "Ask the user for confirmation before a long or irreversible action "
        "(e.g. a full-genome COJO run, an eQTL dataset download). "
        "Returns 'approved' or 'deferred'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "reason": {"type": "string"},
            "estimated_cost": {"type": "string", "description": "e.g. '~30 min runtime, 2 GB output'"},
        },
        "required": ["action", "reason"],
    },
}

_WRITE_JSON_CONFIG: dict[str, Any] = {
    "name": "write_json_config",
    "description": (
        "Write a small JSON config file (e.g. for susie_batch's --config or "
        "extract_graph's trait_trait_mr_config). data must match the schema documented "
        "on the consuming tool. This is the only way the agent may write to disk."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "data": {"type": ["object", "array"]},
        },
        "required": ["path", "data"],
    },
}

_START_JOB: dict[str, Any] = {
    "name": "start_job",
    "description": (
        f"Start a pipeline step asynchronously and return a job_id immediately. Never blocks. "
        f"step must be one of: {_STEP_LIST}. args is a free-form object whose fields depend on the step:\n"
        "  format_gwas(input_file, output_file, chr_col, pos_col, effect_allele_col, other_allele_col, "
        "eaf_col, se_col, pval_col, [beta_col|or_col], [n|n_col], [snp_id_col], [sep])\n"
        "  cojo(gwas_ma_file, plink_bfile_ref, output_prefix, [orig_sig_csv, phenotype])\n"
        "  susie_locus(sumstats_region_csv, plink_bfile_ref, sample_size, output_prefix)\n"
        "  susie_batch(config_path)\n"
        "  smr_eqtl(comparison_path, eqtl_path, output, [comparison_sheet], [traits], ...)\n"
        "  two_sample_mr(cojo_jma_file, outcome_gwas_csv, outcome_name, output_dir)\n"
        "  extract_graph(input_path, output_edges, output_nodes, [trait_trait_mr_config], ...)\n"
        "  visualize(nodes, edges, output_png, output_html, [pip_threshold], [smr_p_threshold])\n"
        "  druggability(gene_symbols: list[str], output_tsv)\n"
        "  prs(gwas_ma_file, plink_bfile_ref, output_prefix, [target_bfile], "
        "[p_threshold], [clump_r2], [clump_kb], [extract_snps]) -- Clumping+Thresholding "
        "polygenic risk score: LD-clump the .ma against plink_bfile_ref, then plink --score "
        "target_bfile (defaults to plink_bfile_ref). Pass extract_snps (a SNP-list file) for a "
        "pathway/gene-restricted score. Writes <output_prefix>.profile"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "step": {"type": "string", "enum": list(STEP_FUNCS)},
            "args": {"type": "object"},
        },
        "required": ["step", "args"],
    },
}

_CHECK_JOB: dict[str, Any] = {
    "name": "check_job_status",
    "description": "Poll a job started via start_job. Returns status: running | done | failed.",
    "input_schema": {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    },
}

_GET_RESULT: dict[str, Any] = {
    "name": "get_job_result",
    "description": "Fetch the result of a job once check_job_status reports 'done'.",
    "input_schema": {
        "type": "object",
        "properties": {"job_id": {"type": "string"}},
        "required": ["job_id"],
    },
}

_WORKER_TOOLS = [_START_JOB, _CHECK_JOB, _GET_RESULT, _READ_CHECKPOINT,
                 _LIST_ASSETS, _REQUEST_CONFIRMATION, _WRITE_JSON_CONFIG]

V2G_TOOLS: list[dict[str, Any]] = _WORKER_TOOLS
MR_TOOLS: list[dict[str, Any]] = _WORKER_TOOLS
PRS_TOOLS: list[dict[str, Any]] = _WORKER_TOOLS
DRUG_TOOLS: list[dict[str, Any]] = [_START_JOB, _CHECK_JOB, _GET_RESULT, _READ_CHECKPOINT, _LIST_ASSETS]

# Whitelist of external data sources this domain may query (configs/external_sources.json).
# Exposed for agentcore.tools's shared fetch_external_data tool description.
_SOURCES_CONFIG_PATH = REPO_ROOT / "configs" / "external_sources.json"


def _load_sources() -> dict[str, Any]:
    try:
        return json.loads(_SOURCES_CONFIG_PATH.read_text())
    except Exception:
        return {}


EXTERNAL_SOURCES: dict[str, Any] = {k: v for k, v in _load_sources().items() if not k.startswith("_")}


def _job_on_complete(run_id: str, step_name: str, phase: str | None, args: dict[str, Any]):
    def _callback(job_id: str, result: dict[str, Any] | None, error: str | None) -> None:
        state.record_step(
            run_id,
            step=step_name,
            phase=phase,
            status="done" if error is None else "failed",
            inputs=args,
            outputs=result,
            job_id=job_id,
            error=error,
        )
    return _callback


def inspect_gwas_input(path: str) -> dict[str, Any]:
    import csv, gzip, re
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    if not p.exists():
        return {"error": f"file not found: {p}"}

    opener = gzip.open if str(p).endswith(".gz") else open
    try:
        with opener(p, "rt", encoding="utf-8", errors="replace") as fh:  # type: ignore[call-overload]
            sample = fh.read(8192)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    lines = sample.splitlines()
    if not lines:
        return {"error": "file is empty"}

    # detect separator
    header = lines[0]
    sep = "\t" if header.count("\t") >= 3 else ","
    cols = [c.strip().strip('"') for c in header.split(sep)]

    # count rows quickly
    try:
        with opener(p, "rt", encoding="utf-8", errors="replace") as fh:  # type: ignore[call-overload]
            n_rows = sum(1 for _ in fh) - 1
    except Exception:  # noqa: BLE001
        n_rows = None

    # sniff genome build
    build_hints: list[str] = []
    for line in lines[1:6]:
        fields = line.split(sep)
        if fields:
            chr_val = fields[0].strip().strip('"')
            if chr_val.startswith("chr"):
                build_hints.append("chr-prefixed chromosomes (consistent with GRCh38)")
            m = re.search(r"\brs\d+\b", line)
            if m:
                build_hints.append("rsIDs present")

    # sniff min p-value
    p_col_idx = None
    for i, c in enumerate(cols):
        if re.search(r"p.?val|pvalue|p_value|pval", c, re.I):
            p_col_idx = i
            break
    min_pval = None
    if p_col_idx is not None:
        pvals = []
        for line in lines[1:]:
            parts = line.split(sep)
            if len(parts) > p_col_idx:
                try:
                    pvals.append(float(parts[p_col_idx]))
                except ValueError:
                    pass
        if pvals:
            min_pval = min(pvals)

    return {
        "path": str(p),
        "format": "gz" if str(p).endswith(".gz") else p.suffix.lstrip("."),
        "separator": "tab" if sep == "\t" else "comma",
        "columns": cols,
        "n_columns": len(cols),
        "n_rows_approx": n_rows,
        "build_hints": build_hints or ["no clear build indicator in first rows"],
        "min_pval_in_sample": min_pval,
    }


def dispatch(run_id: str, name: str, tool_input: dict[str, Any], auto_approve: bool, phase: str | None = None) -> dict[str, Any]:
    """Execute a single gwas-domain tool call and return the result dict.

    `phase` identifies which stage ("v2g", "mr", "drug") is making this call.
    """

    if name == "inspect_gwas_input":
        return inspect_gwas_input(tool_input["path"])

    if name == "list_available_assets":
        root = Path(tool_input["root"])
        if not root.is_absolute():
            root = REPO_ROOT / root
        pattern = tool_input.get("pattern", "*")
        limit = tool_input.get("limit", 30)
        if not root.exists():
            return {"error": f"directory does not exist: {root}"}
        matches = sorted(root.glob(pattern))[:limit]
        return {
            "root": str(root),
            "pattern": pattern,
            "count": len(matches),
            "files": [
                {"path": str(m.relative_to(root)), "size_bytes": m.stat().st_size if m.is_file() else None}
                for m in matches
            ],
        }

    if name == "read_checkpoint":
        return {"summary": state.summarize_state(run_id)}

    if name == "request_confirmation":
        if auto_approve:
            return {"decision": "approved", "note": "auto-approve is enabled for this session"}
        return {"decision": "deferred", "note": "no interactive confirmation available; treat as not approved"}

    if name == "write_json_config":
        path = Path(tool_input["path"])
        if not path.is_absolute():
            path = REPO_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(tool_input["data"], indent=2), encoding="utf-8")
        return {"written": str(path)}

    if name == "start_job":
        step = tool_input["step"]
        args = tool_input.get("args", {})
        if step not in STEP_FUNCS:
            return {"error": f"unknown step '{step}'; valid: {_STEP_LIST}"}
        job_id = jobs.start_job(
            step, STEP_FUNCS[step], args,
            on_complete=_job_on_complete(run_id, step, phase, args),
        )
        state.record_step(run_id, step=step, phase=phase, status="started", inputs=args, job_id=job_id)
        return {"job_id": job_id, "step": step, "status": "started"}

    if name == "check_job_status":
        return jobs.check_job_status(tool_input["job_id"])

    if name == "get_job_result":
        return jobs.get_job_result(tool_input["job_id"])

    return {"error": f"unknown tool: {name}"}
