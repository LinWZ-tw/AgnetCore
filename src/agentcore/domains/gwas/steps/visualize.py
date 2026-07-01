"""Step: render causal network as PNG + interactive HTML."""

from __future__ import annotations

from typing import Any

from . import _kv_args, _py, _run


def run(
    *,
    nodes: str,
    edges: str,
    output_png: str,
    output_html: str,
    pip_threshold: float | None = None,
    smr_p_threshold: float | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    kwargs = {
        "nodes": nodes, "edges": edges,
        "output_png": output_png, "output_html": output_html,
        "pip_threshold": pip_threshold, "smr_p_threshold": smr_p_threshold,
    }
    cmd = _py("visualize_causal_network.py") + _kv_args(
        kwargs, ["nodes", "edges", "output_png", "output_html", "pip_threshold", "smr_p_threshold"]
    )
    result = _run(cmd)
    result["output_png"] = output_png
    result["output_html"] = output_html
    return result
