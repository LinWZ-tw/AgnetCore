"""Steps: SuSiE fine-mapping (single locus and batch)."""

from __future__ import annotations

from typing import Any

from . import TOOLS_DIR, _conda, _py, _run


def run_locus(
    *,
    sumstats_region_csv: str,
    plink_bfile_ref: str,
    sample_size: int,
    output_prefix: str,
    **_ignored: Any,
) -> dict[str, Any]:
    cmd = _conda([
        "bash", str(TOOLS_DIR / "extract_ld_and_run_susie.sh"),
        sumstats_region_csv, plink_bfile_ref, str(sample_size), output_prefix,
    ])
    result = _run(cmd)
    result["output_prefix"] = output_prefix
    return result


def run_batch(*, config_path: str, **_ignored: Any) -> dict[str, Any]:
    cmd = _py("susie_batch.py") + ["--config", config_path]
    return _run(cmd)
