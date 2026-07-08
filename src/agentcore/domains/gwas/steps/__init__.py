"""Shared subprocess runner for all GWAS pipeline steps.

Execution backends
------------------
The heavy GWAS tools (gcta64, plink, R + susieR/TwoSampleMR, and the pure-Python
tool scripts) run in two conda envs -- ``finemap`` and ``gwasagent``. On the
primary dev machine those envs, and the copied reference data, live only inside
WSL: the Windows repo sits on a Google Drive drive that WSL cannot mount, so the
tools cannot run on the Windows side at all. The agent orchestration still runs
on Windows and shells every command out to WSL via ``wsl.exe -e bash -lc``.

Two backends, selected automatically (override with ``AGENTCORE_EXEC_BACKEND``):

- ``wsl``    (default on Windows): commands are wrapped in ``wsl.exe`` and run
  inside the distro. Every file-path argument a step receives -- reference
  panels, ``.ma`` files, ``output_prefix``, config JSONs -- must therefore be a
  *WSL* path (e.g. ``/home/<user>/agentCore/...``), not a Windows path, because
  WSL cannot see the Windows ``H:`` drive.
- ``native`` (default elsewhere): commands run in-process on the host exactly as
  before this WSL split was introduced (``sys.executable`` + ``conda`` on PATH).

Env-var overrides (all optional):
    AGENTCORE_EXEC_BACKEND   "wsl" | "native"
    AGENTCORE_WSL_DISTRO     distro name for ``wsl.exe -d`` (default: default distro)
    AGENTCORE_WSL_TOOLS_DIR  WSL path to the copied ``tools/`` dir
    AGENTCORE_CONDA_SH       WSL path to ``conda.sh`` sourced before each command
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import PurePosixPath
from typing import Any

from agentcore import FINEMAP_CONDA_ENV, GWASAGENT_CONDA_ENV
from agentcore import TOOLS_DIR as _REPO_TOOLS_DIR

MAX_OUTPUT_CHARS = 8000

_BACKEND = os.environ.get("AGENTCORE_EXEC_BACKEND") or ("wsl" if os.name == "nt" else "native")
_WSL_DISTRO = os.environ.get("AGENTCORE_WSL_DISTRO", "")
# conda is not on PATH in a non-interactive WSL shell (Ubuntu's ~/.bashrc returns
# early before the conda-init block), so we source conda.sh ourselves. This also
# makes `conda activate` work inside scripts that self-activate (run_mr_pipeline.sh).
_CONDA_SH = os.environ.get("AGENTCORE_CONDA_SH", "$HOME/miniconda3/etc/profile.d/conda.sh")
_WSL_CD = os.environ.get("AGENTCORE_WSL_CD", "~")

if _BACKEND == "wsl":
    # Shadow agentcore.TOOLS_DIR so step modules that do `from . import TOOLS_DIR`
    # build WSL-side (POSIX) script paths, not Windows ones. PurePosixPath keeps
    # `/`-joins forward-slashed even though this code runs on Windows.
    TOOLS_DIR: Any = PurePosixPath(
        os.environ.get("AGENTCORE_WSL_TOOLS_DIR", "/home/weizhilin/agentCore/tools")
    )
    _PY_PREFIX = ["conda", "run", "-n", GWASAGENT_CONDA_ENV, "python"]
else:
    TOOLS_DIR = _REPO_TOOLS_DIR
    _PY_PREFIX = [sys.executable]


def _run(cmd: list[str], timeout: int = 21600) -> dict[str, Any]:
    argv = [str(c) for c in cmd]
    if _BACKEND == "wsl":
        inner = f"source {_CONDA_SH} && " + shlex.join(argv)
        # --cd starts the command in a WSL dir; without it wsl.exe inherits the
        # Windows CWD (on the unmountable H: drive) and emits a noisy
        # "Failed to translate" warning to stderr before falling back.
        prefix = ["wsl.exe"] + (["-d", _WSL_DISTRO] if _WSL_DISTRO else [])
        argv = prefix + ["--cd", _WSL_CD, "-e", "bash", "-lc", inner]
    try:
        # UTF-8 forced: WSL tool output carries β/≥/→ etc. and the dev host runs a
        # cp950 locale that would otherwise crash the default text decode.
        result = subprocess.run(
            argv, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return {"success": False, "exit_code": -1, "stdout": "", "stderr": "", "error": f"timed out after {e.timeout}s"}
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": (result.stdout or "")[-MAX_OUTPUT_CHARS:],
        "stderr": (result.stderr or "")[-MAX_OUTPUT_CHARS:],
    }


def _py(script: str) -> list[str]:
    return _PY_PREFIX + [str(TOOLS_DIR / script)]


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
