"""Shared subprocess runner for all pipeline steps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from agentcore import FINEMAP_CONDA_ENV, GWASAGENT_CONDA_ENV, TOOLS_DIR

MAX_OUTPUT_CHARS = 8000


def _run(cmd: list[str], timeout: int = 21600) -> dict[str, Any]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        return {"success": False, "exit_code": -1, "stdout": "", "stderr": "", "error": f"timed out after {e.timeout}s"}
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-MAX_OUTPUT_CHARS:],
        "stderr": result.stderr[-MAX_OUTPUT_CHARS:],
    }


def _py(script: str) -> list[str]:
    return [sys.executable, str(TOOLS_DIR / script)]


def _conda(script_args: list[str]) -> list[str]:
    return ["conda", "run", "-n", FINEMAP_CONDA_ENV] + script_args


def _kv_args(kwargs: dict[str, Any], keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        v = kwargs.get(k)
        if v is None:
            continue
        out.extend([f"--{k}", str(v)])
    return out
