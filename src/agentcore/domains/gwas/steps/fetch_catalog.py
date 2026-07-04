"""Step: fetch GWAS summary statistics from the GWAS Catalog.

Wraps tools/fetch_gwas_catalog.py. Two modes:
  - download (accession given): resolve + stream the harmonised .h.tsv.gz into
    output_dir, ready for format_gwas.
  - search (trait given, no accession or search_only=True): list candidate
    studies that have full summary statistics, so the caller can pick one.

Runs in the gwasagent env / WSL backend like the other pure-Python gwas tools,
so the download lands where COJO/SuSiE can read it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import TOOLS_DIR, _py, _run


def run(
    *,
    accession: str | None = None,
    trait: str | None = None,
    output_dir: str | None = None,
    search_only: bool = False,
    size: int = 10,
    **_ignored: Any,
) -> dict[str, Any]:
    cmd = _py("fetch_gwas_catalog.py")
    if accession and not search_only:
        cmd += ["--accession", accession]
        if output_dir:
            cmd += ["--output-dir", output_dir]
    elif trait:
        cmd += ["--trait", trait, "--search-only", "--size", str(size)]
    else:
        return {
            "success": False,
            "error": "provide 'accession' to download, or 'trait' (with search_only) to search",
        }
    # This step can shell a large file download; give it a generous timeout.
    result = _run(cmd, timeout=3600)
    if accession and not search_only and output_dir:
        # Best-effort provenance; existence check is only meaningful on the
        # native backend (see cojo.py for the same caveat under the WSL split).
        result["output_dir"] = output_dir
    return result
