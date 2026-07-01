"""Step: GCTA-COJO conditional/joint analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import TOOLS_DIR, _conda, _run


def run(
    *,
    gwas_ma_file: str,
    plink_bfile_ref: str,
    output_prefix: str,
    orig_sig_csv: str | None = None,
    phenotype: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    positional = [gwas_ma_file, plink_bfile_ref, output_prefix]
    if orig_sig_csv and phenotype:
        positional += [orig_sig_csv, phenotype]
    cmd = _conda(["bash", str(TOOLS_DIR / "cojo.sh")] + positional)
    result = _run(cmd)
    jma_file = f"{output_prefix}.jma.cojo"
    result["jma_file"] = jma_file
    result["jma_exists"] = Path(jma_file).exists()
    return result
