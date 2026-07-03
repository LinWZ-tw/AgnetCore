"""Step: Clumping + Thresholding polygenic risk score (plink --clump/--score)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import TOOLS_DIR, _conda, _run


def run(
    *,
    gwas_ma_file: str,
    plink_bfile_ref: str,
    output_prefix: str,
    target_bfile: str | None = None,
    p_threshold: float | str = 5e-8,
    clump_r2: float | str = 0.1,
    clump_kb: int | str = 250,
    extract_snps: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    # C+T PRS: LD-clump the GWAS .ma against plink_bfile_ref, then score the
    # target cohort's genotypes with the retained betas. target_bfile defaults
    # to the LD reference itself (scores the reference samples -- a runnable
    # demo, but circular for a real risk estimate; supply a genuine target
    # cohort's bfile for that). extract_snps optionally restricts the clumped
    # set to a supplied SNP list (e.g. variants mapping to candidate genes),
    # giving a pathway-restricted PRS.
    positional = [
        gwas_ma_file,
        plink_bfile_ref,
        target_bfile or plink_bfile_ref,
        output_prefix,
        str(p_threshold),
        str(clump_r2),
        str(clump_kb),
    ]
    if extract_snps:
        positional.append(extract_snps)
    cmd = _conda(["bash", str(TOOLS_DIR / "prs_clump_score.sh")] + positional)
    result = _run(cmd)
    profile = f"{output_prefix}.profile"
    result["profile_file"] = profile
    result["profile_exists"] = Path(profile).exists()
    return result
