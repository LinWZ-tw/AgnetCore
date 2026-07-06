#!/usr/bin/env python3
"""Model Context Protocol (MCP) server exposing agentCore's pipeline steps.

This lets any MCP-capable LLM client -- Claude Code / the `claude` CLI,
Codex, Antigravity, Cursor, etc. -- drive this repo's bio (WES/scRNA) and
GWAS (V2G/MR/Drug/PRS) steps directly as tool calls, *without* going through
the project's own Planner LLM loop or needing a provider API key.

It is a thin façade over each domain's self-contained `dispatch()` (see
`agentcore.domains.{bio,gwas}.tools`). Routing through `dispatch` -- rather
than calling `STEP_FUNCS` directly -- preserves the repo's core contract:
every heavy step runs on the shared job queue (`agentcore.jobs`) and its
completion is checkpointed to `results/<run_id>/state.json`
(`agentcore.state`). So an MCP-launched step is indistinguishable, on disk,
from one launched by the Planner.

Transport: stdio (the default every MCP client speaks). Run it directly for
a quick self-test, or register it with a client (see the block at the bottom
of this file for ready-to-paste config).

    pip install "mcp[cli]"          # one extra dependency, see src/requirements.txt
    python mcp_server.py --selftest # exercise the tools without an MCP client
    python mcp_server.py            # serve over stdio (what a client launches)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

# Force UTF-8 regardless of OS locale (cp950 on this repo's dev machine would
# otherwise crash on step output containing beta / >= / arrow glyphs). Same
# convention as run_pipeline.py / server.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agentcore import jobs  # noqa: E402
from agentcore.domains.bio import tools as bio_tools  # noqa: E402
from agentcore.domains.gwas import tools as gwas_tools  # noqa: E402

# One domain -> its self-contained dispatch()/STEP_FUNCS. Both share the same
# dispatch signature: dispatch(run_id, name, tool_input, auto_approve, phase).
_DOMAINS = {"bio": bio_tools, "gwas": gwas_tools}

# Archive/matrix-shaped inputs are bio; a lone tabular file is GWAS summary
# stats. Used only by inspect_input(domain="auto") as a best-effort guess --
# callers can always pass an explicit domain.
_BIO_SUFFIXES = {".h5", ".h5ad", ".zip", ".tar", ".loom", ".mtx"}


def _resolve_domain(domain: str, path: str | None = None) -> str:
    domain = (domain or "auto").lower()
    if domain in _DOMAINS:
        return domain
    if domain != "auto":
        raise ValueError(f"domain must be one of {sorted(_DOMAINS)} or 'auto', got {domain!r}")
    if path:
        p = Path(path)
        if p.is_dir() or p.suffix.lower() in _BIO_SUFFIXES:
            return "bio"
    return "gwas"


def _dispatch(domain: str, name: str, tool_input: dict[str, Any], run_id: str, phase: str | None = None) -> dict[str, Any]:
    mod = _DOMAINS[domain]
    # auto_approve=True: an MCP client has no interactive confirmation channel,
    # so treat gated actions as approved. Keep this in mind before wiring in
    # genuinely destructive steps.
    return mod.dispatch(run_id, name, tool_input, True, phase)


# ---------------------------------------------------------------------------
# Plain-Python tool implementations (also used by --selftest, no MCP needed)
# ---------------------------------------------------------------------------

def _list_capabilities() -> dict[str, Any]:
    return {
        "domains": {
            "bio": {
                "description": "WES + scRNA bioinformatics (mock mode by default; real mode shells out to the `wes` conda env).",
                "steps": list(bio_tools.STEP_FUNCS),
            },
            "gwas": {
                "description": "Post-GWAS translational pipeline (V2G/MR/Drug/PRS); heavy steps need the `finemap` conda env.",
                "steps": list(gwas_tools.STEP_FUNCS),
            },
        },
        "notes": [
            "Call run_step with wait=true for a blocking run, or start_step + check_job + get_job_result to poll.",
            "bio steps accept args.mode = 'mock' (default) or 'real'.",
            "Every completed step is checkpointed to results/<run_id>/state.json; read_checkpoint reports progress.",
        ],
    }


def _inspect_input(path: str, domain: str = "auto") -> dict[str, Any]:
    dom = _resolve_domain(domain, path)
    name = "inspect_gwas_input" if dom == "gwas" else "inspect_data_source"
    result = _dispatch(dom, name, {"path": path}, run_id="mcp-inspect")
    return {"domain": dom, "result": result}


def _list_assets(root: str, pattern: str = "*", limit: int = 30) -> dict[str, Any]:
    return _dispatch("bio", "list_available_assets", {"root": root, "pattern": pattern, "limit": limit}, run_id="mcp")


def _start_step(domain: str, step: str, args: dict[str, Any] | None = None, run_id: str = "mcp") -> dict[str, Any]:
    dom = _resolve_domain(domain)
    args = args or {}
    if step not in _DOMAINS[dom].STEP_FUNCS:
        return {"error": f"unknown {dom} step '{step}'; valid: {list(_DOMAINS[dom].STEP_FUNCS)}"}
    return _dispatch(dom, "start_job", {"step": step, "args": args}, run_id=run_id, phase=dom)


def _check_job(job_id: str) -> dict[str, Any]:
    return jobs.check_job_status(job_id)


def _get_job_result(job_id: str) -> dict[str, Any]:
    return jobs.get_job_result(job_id)


def _run_step(domain: str, step: str, args: dict[str, Any] | None = None,
              run_id: str = "mcp", timeout_s: int = 900) -> dict[str, Any]:
    started = _start_step(domain, step, args, run_id)
    job_id = started.get("job_id")
    if not job_id:
        return started  # error dict (unknown step, etc.)
    deadline = time.time() + max(1, timeout_s)
    while time.time() < deadline:
        status = jobs.check_job_status(job_id)
        if status.get("status") in ("done", "failed", "unknown"):
            break
        time.sleep(0.5)
    else:
        return {"job_id": job_id, "status": "timeout", "step": step,
                "note": f"still running after {timeout_s}s; poll with check_job({job_id!r})"}
    result = jobs.get_job_result(job_id)
    return {"job_id": job_id, "step": step, "domain": _resolve_domain(domain), **result}


def _read_checkpoint(run_id: str) -> dict[str, Any]:
    return _dispatch("bio", "read_checkpoint", {}, run_id=run_id)


# ---------------------------------------------------------------------------
# MCP server registration
# ---------------------------------------------------------------------------

def build_server():
    """Construct the FastMCP server, wiring each _fn above as an MCP tool."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "The 'mcp' package is required to serve. Install it with:\n"
            "    pip install \"mcp[cli]\"\n"
            f"(import error: {exc})"
        )

    mcp = FastMCP("agentcore")

    @mcp.tool()
    def list_capabilities() -> dict[str, Any]:
        """List the available domains (bio, gwas) and every step each one exposes."""
        return _list_capabilities()

    @mcp.tool()
    def inspect_input(path: str, domain: str = "auto") -> dict[str, Any]:
        """Classify an input path. domain: 'bio' (WES/scRNA), 'gwas' (summary stats), or 'auto'."""
        return _inspect_input(path, domain)

    @mcp.tool()
    def list_assets(root: str, pattern: str = "*", limit: int = 30) -> dict[str, Any]:
        """List files under `root` matching a glob `pattern`, with sizes -- to discover data instead of guessing paths."""
        return _list_assets(root, pattern, limit)

    @mcp.tool()
    def run_step(domain: str, step: str, args: dict[str, Any] | None = None,
                 run_id: str = "mcp", timeout_s: int = 900) -> dict[str, Any]:
        """Run one pipeline step to completion (blocking) and return its result.

        domain: 'bio' or 'gwas'. step: one of that domain's steps (see list_capabilities).
        args: step inputs (bio accepts mode='mock'|'real'). run_id: checkpoint bucket.
        """
        return _run_step(domain, step, args, run_id, timeout_s)

    @mcp.tool()
    def start_step(domain: str, step: str, args: dict[str, Any] | None = None,
                   run_id: str = "mcp") -> dict[str, Any]:
        """Start a step asynchronously and return a job_id immediately (poll with check_job / get_job_result)."""
        return _start_step(domain, step, args, run_id)

    @mcp.tool()
    def check_job(job_id: str) -> dict[str, Any]:
        """Return the status (running/done/failed) of a job started by start_step."""
        return _check_job(job_id)

    @mcp.tool()
    def get_job_result(job_id: str) -> dict[str, Any]:
        """Return the result payload of a completed job started by start_step."""
        return _get_job_result(job_id)

    @mcp.tool()
    def read_checkpoint(run_id: str) -> dict[str, Any]:
        """Summarize the steps already recorded for a run (from results/<run_id>/state.json)."""
        return _read_checkpoint(run_id)

    return mcp


def _selftest() -> int:
    import json

    print("== list_capabilities ==")
    caps = _list_capabilities()
    print(json.dumps(caps, indent=2, ensure_ascii=False))

    root = Path(__file__).resolve().parent

    print("\n== inspect_input (gwas summary stats) ==")
    sample = root / "smoketest" / "MASLD_chr1_slice.ma"
    if sample.exists():
        print(json.dumps(_inspect_input(str(sample)), indent=2, ensure_ascii=False)[:1200])
    else:
        print(f"(skipped: {sample} not present)")

    print("\n== run_step bio/qc (mock mode -- deterministic, no external tools) ==")
    out = _run_step("bio", "qc",
                    {"sample_id": "selftest", "input_path": str(sample), "mode": "mock"},
                    run_id="mcp-selftest", timeout_s=120)
    print(json.dumps(out, indent=2, ensure_ascii=False)[:1500])

    print("\n== read_checkpoint (proves the run was persisted to state.json) ==")
    print(json.dumps(_read_checkpoint("mcp-selftest"), indent=2, ensure_ascii=False)[:1000])
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    build_server().run()  # stdio transport
