"""Step: two-sample Mendelian Randomization (trait -> trait)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import FINEMAP_CONDA_ENV, TOOLS_DIR, _run


def run(
    *,
    cojo_jma_file: str,
    outcome_gwas_csv: str,
    outcome_name: str,
    output_dir: str,
    **_ignored: Any,
) -> dict[str, Any]:
    cmd = [
        "bash", str(TOOLS_DIR / "run_mr_pipeline.sh"),
        cojo_jma_file, outcome_gwas_csv, outcome_name, output_dir, FINEMAP_CONDA_ENV,
    ]
    result = _run(cmd)
    result["output_dir"] = output_dir
    mr_csv = str(Path(output_dir) / f"{outcome_name}_MR_results.csv")
    result["mr_results_csv"] = mr_csv
    result["mr_results_exists"] = Path(mr_csv).exists()
    return result
