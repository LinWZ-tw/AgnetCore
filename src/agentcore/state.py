"""Checkpoint persistence for a pipeline run.

Each run gets a `results/<run_id>/state.json` containing an ordered list of
step records plus a top-level `domain` field ("bio" or "gwas") set once the
Planner classifies the input. This is what makes a run resumable: a
restarted Planner loads this file and tells the model what's already done
so it isn't redone, and tells the Reporter which domain's report to build.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import RESULT_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_dir(run_id: str) -> Path:
    d = RESULT_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(run_id: str) -> Path:
    return run_dir(run_id) / "state.json"


def log_path(run_id: str) -> Path:
    return run_dir(run_id) / "agent_log.jsonl"


def report_dir(run_id: str) -> Path:
    d = run_dir(run_id) / "report"
    d.mkdir(parents=True, exist_ok=True)
    return d


_lock = threading.Lock()


def load_state(run_id: str) -> dict[str, Any]:
    path = state_path(run_id)
    if not path.exists():
        return {"run_id": run_id, "created_at": _now(), "domain": None, "steps": []}
    with path.open(encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("domain", None)
    return state


def save_state(run_id: str, state: dict[str, Any]) -> None:
    with _lock:
        state_path(run_id).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def set_domain(run_id: str, domain: str) -> None:
    """Record which domain ("bio" or "gwas") this run belongs to.

    Called once by the Planner right after it classifies the input. The
    Reporter and CLI/server read this back to decide which domain-specific
    report/summary logic to run.
    """
    with _lock:
        state = load_state(run_id)
        state["domain"] = domain
        state_path(run_id).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def record_step(
    run_id: str,
    *,
    step: str,
    status: str,
    phase: str | None = None,
    exec_mode: str | None = None,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    job_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Append a step record and persist it. Thread-safe.

    `phase` is the domain-specific branch/stage this step belongs to
    ("wes"/"scrna" for bio, "v2g"/"mr"/"drug" for gwas) — kept distinct from
    `exec_mode` (bio's "mock" vs "real" execution mode) since the two are
    independent axes and conflating them under one `mode=` kwarg (as the
    pre-merge bio codebase did) becomes ambiguous once both domains share
    this function.
    """
    with _lock:
        state = load_state(run_id)
        provenance = None
        if isinstance(outputs, dict):
            provenance = outputs.pop("_provenance", None)
        record = {
            "step": step,
            "status": status,
            "phase": phase,
            "exec_mode": exec_mode,
            "job_id": job_id,
            "inputs": inputs,
            "outputs": outputs,
            "provenance": provenance,
            "error": error,
            "timestamp": _now(),
        }
        state["steps"].append(record)
        state_path(run_id).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        return record


def append_log(run_id: str, entry: dict[str, Any]) -> None:
    entry = {"timestamp": _now(), **entry}
    with _lock:
        with log_path(run_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")


def summarize_state(run_id: str) -> str:
    """Human/LLM-readable summary of what's already been done in this run."""
    state = load_state(run_id)
    steps = state.get("steps", [])
    if not steps:
        return "No steps have been recorded yet for this run."
    lines = [f"Run '{run_id}' (domain={state.get('domain')}) has {len(steps)} recorded step event(s) so far:"]
    for s in steps:
        outs = s.get("outputs")
        outs_brief = json.dumps(outs)[:300] if outs else None
        lines.append(
            f"- [{s['timestamp']}] step={s['step']} status={s['status']} "
            f"phase={s.get('phase')} exec_mode={s.get('exec_mode')} job_id={s.get('job_id')}"
            + (f" outputs={outs_brief}" if outs_brief else "")
            + (f" error={s['error']}" if s.get("error") else "")
        )
    return "\n".join(lines)
