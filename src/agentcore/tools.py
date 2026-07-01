"""Shared, cross-domain tool schemas and the Planner's top-level dispatch table.

Domain-specific tool schemas and dispatch logic live in
`agentcore.domains.bio.tools` and `agentcore.domains.gwas.tools` -- fully
self-contained modules that this file imports from (one direction only, no
cycle). Worker/Stage agents (wes_agent, scrna_agent, v2g_agent, mr_agent,
drug_agent) import their tool list and dispatch() directly from their own
domain's tools module, not from here.

This module assembles the single unified `PLANNER_TOOLS` list -- both
domains' input-inspection and dispatch tools are always present; the
Planner's system prompt decides which one applies based on what the input
looks like (see agentcore/prompts/planner.py). `dispatch_worker` and
`dispatch_stage` are intentionally kept as two separate tools rather than
one merged schema: their input shapes don't collapse cleanly (bio's rich
scenario/groups/paired-normal fields vs. gwas's free-form context dict),
and routing is already done by tool name, so a forced merge would only add
risk for no simplification. `dispatch_worker`/`dispatch_stage`/
`generate_report` are intercepted by the Planner's own dispatch wrapper
(agentcore/agents/planner.py::make_dispatch) before reaching this module's
`dispatch()` -- see that file for the actual worker/stage/reporter calls.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .domains.bio import tools as bio_tools
from .domains.gwas import tools as gwas_tools

_LIST_ASSETS: dict[str, Any] = {
    "name": "list_available_assets",
    "description": (
        "List files under a directory matching a glob pattern, with size and mtime. Use this to "
        "discover existing data instead of guessing file paths."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "root": {"type": "string", "description": "Directory to list, relative to repo root or absolute."},
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '*.h5' or '**/*.h5ad'.", "default": "*"},
            "limit": {"type": "integer", "default": 30},
        },
        "required": ["root"],
    },
}

_READ_CHECKPOINT: dict[str, Any] = {
    "name": "read_checkpoint",
    "description": "Return a summary of steps already recorded for this run (for resuming a previous session).",
    "input_schema": {"type": "object", "properties": {}},
}

_REQUEST_CONFIRMATION: dict[str, Any] = {
    "name": "request_confirmation",
    "description": (
        "Ask for human confirmation before an expensive or irreversible action "
        "(e.g. extracting a multi-hundred-GB archive, a full-genome COJO run). "
        "Returns 'approved' or 'deferred'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "reason": {"type": "string"},
            "estimated_cost": {"type": "string", "description": "e.g. '~1TB disk, ~6h runtime'"},
        },
        "required": ["action", "reason"],
    },
}

_FETCH_EXTERNAL: dict[str, Any] = {
    "name": "fetch_external_data",
    "description": (
        "Make an HTTP GET request to a whitelisted external data source and return the parsed JSON response. "
        "Only sources declared in configs/external_sources.json are allowed. "
        f"Currently whitelisted sources: {', '.join(gwas_tools.EXTERNAL_SOURCES.keys())}. "
        "Use this to look up eQTL associations (gtex), find existing GWAS (gwas_catalog), "
        "annotate variants/genes (ensembl), retrieve V2G scores (open_targets_platform), "
        "or search MR outcome datasets. Not relevant to bio (WES/scRNA) runs. "
        "path is the API endpoint path (e.g. '/lookup/symbol/homo_sapiens/PCSK9'). "
        "params is an optional dict of query-string parameters."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "enum": list(gwas_tools.EXTERNAL_SOURCES.keys()),
                "description": "Name of the whitelisted data source.",
            },
            "path": {
                "type": "string",
                "description": "API endpoint path, starting with '/'.",
            },
            "params": {
                "type": "object",
                "description": "Optional query-string parameters as key-value pairs.",
            },
        },
        "required": ["source", "path"],
    },
}

_GENERATE_REPORT: dict[str, Any] = {
    "name": "generate_report",
    "description": (
        "Trigger the Reporter agent (Layer 3) to synthesize all completed step/stage results "
        "into a Markdown + HTML report written to results/<run_id>/report/. "
        "Call this after all dispatch_worker (bio) or dispatch_stage (gwas) calls have "
        "returned successfully."
    ),
    "input_schema": {"type": "object", "properties": {}},
}

# ---------------------------------------------------------------------------
# Per-agent tool subsets
# ---------------------------------------------------------------------------

PLANNER_TOOLS: list[dict[str, Any]] = [
    bio_tools.INSPECT_DATA_SOURCE,
    gwas_tools.INSPECT_GWAS_INPUT,
    _LIST_ASSETS,
    _READ_CHECKPOINT,
    _REQUEST_CONFIRMATION,
    _FETCH_EXTERNAL,
    bio_tools.DISPATCH_WORKER_TOOL,
    gwas_tools.DISPATCH_STAGE_TOOL,
    _GENERATE_REPORT,
]

REPORTER_TOOLS: list[dict[str, Any]] = [_READ_CHECKPOINT, _LIST_ASSETS]


def _fetch_external(tool_input: dict[str, Any]) -> dict[str, Any]:
    source_name = tool_input.get("source", "")
    if source_name not in gwas_tools.EXTERNAL_SOURCES:
        return {"error": f"source '{source_name}' is not in the whitelist; allowed: {list(gwas_tools.EXTERNAL_SOURCES)}"}

    source = gwas_tools.EXTERNAL_SOURCES[source_name]
    base_url = source["base_url"].rstrip("/")
    path = tool_input.get("path", "")
    if not path.startswith("/"):
        path = "/" + path
    params = tool_input.get("params") or {}

    url = base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "agentcore/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code} from {url}", "source": source_name}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "source": source_name}

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"raw_text": body[:4096]}

    return {"source": source_name, "url": url, "status": status, "data": data}


def dispatch(run_id: str, name: str, tool_input: dict[str, Any], auto_approve: bool) -> dict[str, Any]:
    """Execute a single Planner-level tool call. Returns the dict to JSON-encode as tool_result content.

    `dispatch_worker`, `dispatch_stage`, and `generate_report` are handled
    upstream by the Planner's own dispatch wrapper and never reach here.
    """
    if name in ("inspect_data_source", "locate_fastq_pairs"):
        return bio_tools.dispatch(run_id, name, tool_input, auto_approve)

    if name == "inspect_gwas_input":
        return gwas_tools.dispatch(run_id, name, tool_input, auto_approve)

    if name in ("list_available_assets", "read_checkpoint", "request_confirmation"):
        # Identical implementation in both domain modules; either works.
        return bio_tools.dispatch(run_id, name, tool_input, auto_approve)

    if name == "fetch_external_data":
        return _fetch_external(tool_input)

    return {"error": f"unknown tool: {name}"}
