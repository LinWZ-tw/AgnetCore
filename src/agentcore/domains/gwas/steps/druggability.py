"""Step: druggability assessment via Open Targets Platform REST API.

Accepts a list of gene symbols, queries the Open Targets GraphQL API for
tractability scores and known drugs, and writes a TSV summary.
Falls back to a stub result if the network is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_OT_GRAPHQL = "https://api.platform.opentargets.org/api/v4/graphql"

_SEARCH_QUERY = """
query searchTarget($q: String!) {
  search(queryString: $q, entityNames: ["target"]) {
    hits { id name entity }
  }
}
"""

_TARGET_QUERY = """
query targetDruggability($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    approvedName
    tractability { label modality value }
    knownDrugs(size: 10) {
      rows {
        drug { id name maximumClinicalTrialPhase isApproved }
        mechanismOfAction
      }
    }
  }
}
"""


def _post(query: str, variables: dict) -> dict:
    import urllib.request
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        _OT_GRAPHQL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _query_gene(symbol: str) -> dict[str, Any]:
    try:
        search = _post(_SEARCH_QUERY, {"q": symbol})
        hits = search.get("data", {}).get("search", {}).get("hits", [])
        ensembl_id = None
        for h in hits:
            if h.get("entity") == "target" and h.get("name", "").upper() == symbol.upper():
                ensembl_id = h["id"]
                break
        if ensembl_id is None and hits:
            ensembl_id = hits[0]["id"]
        if ensembl_id is None:
            return {"symbol": symbol, "status": "not_found"}

        detail = _post(_TARGET_QUERY, {"ensemblId": ensembl_id})
        t = detail.get("data", {}).get("target", {})
        if not t:
            return {"symbol": symbol, "ensembl_id": ensembl_id, "status": "no_data"}

        tractability = {
            r["modality"]: r["value"]
            for r in (t.get("tractability") or [])
            if r.get("label") in ("High Confidence", "Medium to Low Confidence")
        }
        drugs = [
            {
                "name": row["drug"]["name"],
                "phase": row["drug"]["maximumClinicalTrialPhase"],
                "approved": row["drug"]["isApproved"],
                "mechanism": row.get("mechanismOfAction"),
            }
            for row in (t.get("knownDrugs", {}).get("rows") or [])
        ]
        return {
            "symbol": symbol,
            "ensembl_id": ensembl_id,
            "approved_name": t.get("approvedName"),
            "tractability": tractability,
            "known_drugs": drugs,
            "status": "ok",
        }
    except Exception as exc:  # noqa: BLE001
        return {"symbol": symbol, "status": "error", "error": str(exc)}


def run(
    *,
    gene_symbols: list[str],
    output_tsv: str,
    **_ignored: Any,
) -> dict[str, Any]:
    results = [_query_gene(g) for g in gene_symbols]

    out = Path(output_tsv)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["gene_symbol\tensembl_id\tapproved_name\ttractability_SM\ttractability_AB\tmax_drug_phase\tapproved_drug\tstatus"]
    for r in results:
        tract = r.get("tractability", {})
        drugs = r.get("known_drugs", [])
        max_phase = max((d["phase"] or 0 for d in drugs), default=0) if drugs else 0
        approved = any(d["approved"] for d in drugs) if drugs else False
        lines.append("\t".join([
            r.get("symbol", ""),
            r.get("ensembl_id", ""),
            r.get("approved_name", ""),
            str(tract.get("SmallMolecule", "")),
            str(tract.get("Antibody", "")),
            str(max_phase),
            str(approved),
            r.get("status", ""),
        ]))
    out.write_text("\n".join(lines), encoding="utf-8")

    n_ok = sum(1 for r in results if r.get("status") == "ok")
    n_with_drugs = sum(1 for r in results if r.get("known_drugs"))
    return {
        "success": True,
        "output_tsv": output_tsv,
        "n_genes_queried": len(gene_symbols),
        "n_genes_found": n_ok,
        "n_genes_with_known_drugs": n_with_drugs,
        "results": results,
    }
