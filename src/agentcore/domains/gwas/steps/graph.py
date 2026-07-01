"""Step: extract causal-network node/edge tables."""

from __future__ import annotations

from typing import Any

from . import _kv_args, _py, _run


def run(
    *,
    input_path: str,
    output_edges: str,
    output_nodes: str,
    sheet_name: str | None = None,
    snp_col: str | None = None,
    gene_col: str | None = None,
    rsid_col: str | None = None,
    pip_col: str | None = None,
    smr_p_col: str | None = None,
    source_col: str | None = None,
    interaction_prob_col: str | None = None,
    trait_trait_mr_config: str | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    kwargs = {
        "input_path": input_path, "output_edges": output_edges, "output_nodes": output_nodes,
        "sheet_name": sheet_name, "snp_col": snp_col, "gene_col": gene_col,
        "rsid_col": rsid_col, "pip_col": pip_col, "smr_p_col": smr_p_col,
        "source_col": source_col, "interaction_prob_col": interaction_prob_col,
        "trait_trait_mr_config": trait_trait_mr_config,
    }
    cmd = _py("extract_graph_table.py") + _kv_args(kwargs, [
        "input_path", "sheet_name", "snp_col", "gene_col", "rsid_col", "pip_col",
        "smr_p_col", "source_col", "interaction_prob_col", "trait_trait_mr_config",
        "output_edges", "output_nodes",
    ])
    result = _run(cmd)
    result["output_edges"] = output_edges
    result["output_nodes"] = output_nodes
    return result
