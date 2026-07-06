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
    per_chromosome: bool = False,
    chromosomes: str = "1-22",
    **_ignored: Any,
) -> dict[str, Any]:
    # per_chromosome=True runs COJO one chromosome at a time (gcta64 --chr N) and
    # concatenates the per-chr .jma.cojo into <output_prefix>.jma.cojo. This is
    # statistically identical to a genome-wide run (COJO never conditions across
    # chromosomes) but caps peak RAM at ~one chromosome's worth of the reference
    # panel -- required for large all-variants panels on memory-limited hosts.
    if per_chromosome:
        script = "cojo_by_chr.sh"
        positional = [gwas_ma_file, plink_bfile_ref, output_prefix, chromosomes]
    else:
        script = "cojo.sh"
        positional = [gwas_ma_file, plink_bfile_ref, output_prefix]
    if orig_sig_csv and phenotype:
        positional += [orig_sig_csv, phenotype]
    cmd = _conda(["bash", str(TOOLS_DIR / script)] + positional)
    result = _run(cmd)
    jma_file = f"{output_prefix}.jma.cojo"
    result["jma_file"] = jma_file
    result["jma_exists"] = Path(jma_file).exists()
    return result
