#!/usr/bin/env python3
"""Cheap, no-API-key regression check for agentcore/state.py's `phase`/
`exec_mode` split and `set_domain` -- the one file that got a real
behavioral change (not just an import-path rename) during the agent1poc +
agnet2postGWAS merge. Run directly: `python test_state.py`.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agentcore import state  # noqa: E402


def _fresh_run_id() -> str:
    return f"test-state-{uuid.uuid4().hex[:8]}"


def test_phase_and_exec_mode_round_trip() -> None:
    run_id = _fresh_run_id()
    record = state.record_step(
        run_id, step="qc", status="done", phase="wes", exec_mode="mock",
        inputs={"sample_id": "s1"}, outputs={"pass_rate": 0.98}, job_id="job_0001",
    )
    assert record["phase"] == "wes", record
    assert record["exec_mode"] == "mock", record
    assert "mode" not in record, "the old overloaded `mode` key must not resurface"

    loaded = state.load_state(run_id)
    assert loaded["steps"][0]["phase"] == "wes"
    assert loaded["steps"][0]["exec_mode"] == "mock"

    summary = state.summarize_state(run_id)
    assert "phase=wes" in summary, summary
    assert "exec_mode=mock" in summary, summary
    print(f"[ok] test_phase_and_exec_mode_round_trip (run_id={run_id})")


def test_gwas_phase_values() -> None:
    run_id = _fresh_run_id()
    for phase in ("v2g", "mr", "drug"):
        state.record_step(run_id, step=f"{phase}_step", status="done", phase=phase)
    loaded = state.load_state(run_id)
    phases = [s["phase"] for s in loaded["steps"]]
    assert phases == ["v2g", "mr", "drug"], phases
    print(f"[ok] test_gwas_phase_values (run_id={run_id})")


def test_set_domain() -> None:
    run_id = _fresh_run_id()
    assert state.load_state(run_id)["domain"] is None
    state.set_domain(run_id, "bio")
    assert state.load_state(run_id)["domain"] == "bio"
    state.set_domain(run_id, "gwas")
    assert state.load_state(run_id)["domain"] == "gwas", "set_domain must be overwritable, not append-only"
    print(f"[ok] test_set_domain (run_id={run_id})")


def test_provenance_popped_from_outputs() -> None:
    run_id = _fresh_run_id()
    record = state.record_step(
        run_id, step="clustering", status="done", phase="scrna",
        outputs={"n_clusters": 5, "_provenance": {"tool": "leidenalg", "version": "0.10.2"}},
    )
    assert "_provenance" not in record["outputs"], record["outputs"]
    assert record["provenance"] == {"tool": "leidenalg", "version": "0.10.2"}, record["provenance"]
    print(f"[ok] test_provenance_popped_from_outputs (run_id={run_id})")


if __name__ == "__main__":
    test_phase_and_exec_mode_round_trip()
    test_gwas_phase_values()
    test_set_domain()
    test_provenance_popped_from_outputs()
    print("\nAll state.py checks passed.")
