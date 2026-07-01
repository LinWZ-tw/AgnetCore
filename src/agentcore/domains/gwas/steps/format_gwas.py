"""Step: convert GWAS summary statistics to GCTA .ma format."""

from __future__ import annotations

from typing import Any

from . import _kv_args, _py, _run


def run(
    *,
    input_file: str,
    output_file: str,
    chr_col: str,
    pos_col: str,
    effect_allele_col: str,
    other_allele_col: str,
    eaf_col: str,
    se_col: str,
    pval_col: str,
    beta_col: str | None = None,
    or_col: str | None = None,
    n: int | None = None,
    n_col: str | None = None,
    snp_id_col: str | None = None,
    sep: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    kwargs = {
        "input": input_file, "output": output_file,
        "chr_col": chr_col, "pos_col": pos_col,
        "effect_allele_col": effect_allele_col, "other_allele_col": other_allele_col,
        "eaf_col": eaf_col, "se_col": se_col, "pval_col": pval_col,
        "beta_col": beta_col, "or_col": or_col, "n": n, "n_col": n_col,
        "snp_id_col": snp_id_col, "sep": sep,
    }
    cmd = _py("format_gwas_to_ma.py") + _kv_args(
        kwargs,
        ["input", "output", "sep", "chr_col", "pos_col", "effect_allele_col",
         "other_allele_col", "eaf_col", "se_col", "pval_col",
         "beta_col", "or_col", "n", "n_col", "snp_id_col"],
    )
    result = _run(cmd)
    result["output_file"] = output_file
    return result
