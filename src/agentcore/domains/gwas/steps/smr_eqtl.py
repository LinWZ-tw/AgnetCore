"""Step: SMR eQTL validation (SNP -> gene evidence)."""

from __future__ import annotations

from typing import Any

from . import _kv_args, _py, _run


def run(
    *,
    comparison_path: str,
    eqtl_path: str,
    output: str,
    comparison_sheet: str | None = None,
    cojo_locus_map_template: str | None = None,
    traits: str | None = None,
    eqtl_variant_col: str | None = None,
    eqtl_gene_col: str | None = None,
    eqtl_beta_col: str | None = None,
    eqtl_se_col: str | None = None,
    eqtl_pval_col: str | None = None,
    variant_id_format: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    kwargs = {
        "comparison_path": comparison_path, "eqtl_path": eqtl_path, "output": output,
        "comparison_sheet": comparison_sheet, "cojo_locus_map_template": cojo_locus_map_template,
        "traits": traits, "eqtl_variant_col": eqtl_variant_col, "eqtl_gene_col": eqtl_gene_col,
        "eqtl_beta_col": eqtl_beta_col, "eqtl_se_col": eqtl_se_col, "eqtl_pval_col": eqtl_pval_col,
        "variant_id_format": variant_id_format,
    }
    cmd = _py("smr_eqtl_validation.py") + _kv_args(kwargs, [
        "comparison_path", "comparison_sheet", "cojo_locus_map_template", "traits",
        "eqtl_path", "eqtl_variant_col", "eqtl_gene_col", "eqtl_beta_col",
        "eqtl_se_col", "eqtl_pval_col", "variant_id_format", "output",
    ])
    result = _run(cmd)
    result["output_file"] = output
    return result
