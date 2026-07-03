#!/usr/bin/env python3
"""Fetch GWAS summary statistics from the GWAS Catalog by study accession.

Given a GWAS Catalog study accession (GCST...), this resolves and downloads the
*harmonised* full summary-statistics file (``*.h.tsv.gz``) — the same GRCh38,
consistently-columned format the rest of this pipeline expects — into an output
directory, ready for ``format_gwas_to_ma.py``.

Two-step resolution, both against public GWAS Catalog endpoints (no key needed):

  1. REST metadata  https://www.ebi.ac.uk/gwas/rest/api/studies/<accession>
     Confirms the study exists and that ``fullPvalueSet`` is true (i.e. full
     summary statistics were deposited, not just top hits). Also records the
     trait for provenance.
  2. Harmonised FTP  https://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics/
                     <range>/<accession>/harmonised/
     Accessions are grouped into range folders of 1000
     (e.g. GCST90011885 -> GCST90011001-GCST90012000). The harmonised dir is an
     autoindex HTML listing; we parse it for the one ``*.h.tsv.gz`` (ignoring the
     ``.tbi`` index and ``-meta.yaml`` sidecar) and stream it to disk.

Search mode (``--trait``) instead lists candidate studies that have full summary
statistics, so a caller can pick an accession — it does not download anything.

Usage:
    python fetch_gwas_catalog.py --accession GCST90011885 --output-dir data/gwas/GCST90011885
    python fetch_gwas_catalog.py --trait "nonalcoholic fatty liver disease" --search-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REST_BASE = "https://www.ebi.ac.uk/gwas/rest/api"
FTP_BASE = "https://ftp.ebi.ac.uk/pub/databases/gwas/summary_statistics"
_UA = {"User-Agent": "agentcore-gwas-catalog/1.0"}


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_json(url: str, timeout: int = 60) -> dict:
    return json.loads(_get(url, timeout).decode("utf-8", errors="replace"))


def _range_dir(accession: str) -> str:
    """GCST90011885 -> 'GCST90011001-GCST90012000' (folders of 1000)."""
    m = re.fullmatch(r"GCST(\d+)", accession)
    if not m:
        raise ValueError(f"not a GCST accession: {accession!r}")
    n = int(m.group(1))
    width = len(m.group(1))
    lower = ((n - 1) // 1000) * 1000 + 1
    upper = lower + 999
    return f"GCST{lower:0{width}d}-GCST{upper:0{width}d}"


def study_metadata(accession: str) -> dict:
    data = _get_json(f"{REST_BASE}/studies/{accession}")
    trait = (data.get("diseaseTrait") or {}).get("trait")
    return {
        "accession": data.get("accessionId", accession),
        "trait": trait,
        "full_pvalue_set": bool(data.get("fullPvalueSet")),
        "initial_sample": data.get("initialSampleSize"),
    }


def harmonised_url(accession: str) -> str:
    listing_url = f"{FTP_BASE}/{_range_dir(accession)}/{accession}/harmonised/"
    html = _get(listing_url).decode("utf-8", errors="replace")
    hrefs = re.findall(r'href="([^"]+)"', html)
    candidates = [
        h for h in hrefs
        if h.endswith(".h.tsv.gz") and not h.endswith(".tbi")
    ]
    if not candidates:
        raise FileNotFoundError(
            f"no *.h.tsv.gz in {listing_url} (study may not have harmonised "
            f"summary statistics; found: {hrefs})"
        )
    # If several, prefer the accession-named one, else the first.
    chosen = next((c for c in candidates if accession in c), candidates[0])
    return urllib.parse.urljoin(listing_url, chosen)


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=_UA)
    total = 0
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as fh:
        length = resp.headers.get("Content-Length")
        length = int(length) if length else None
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
            if length:
                pct = 100 * total / length
                print(f"\r  downloaded {total/1e6:.1f} / {length/1e6:.1f} MB ({pct:.0f}%)",
                      end="", file=sys.stderr, flush=True)
    print("", file=sys.stderr)
    tmp.replace(dest)
    return total


def search_studies(trait: str, size: int = 10) -> list[dict]:
    q = urllib.parse.quote(trait)
    url = f"{REST_BASE}/studies/search/findByDiseaseTrait?diseaseTrait={q}&size={size}"
    try:
        data = _get_json(url)
    except Exception:
        # fall back to the generic full-text study search
        data = _get_json(f"{REST_BASE}/studies/search?q={q}&size={size}")
    studies = (data.get("_embedded") or {}).get("studies", [])
    out = []
    for s in studies:
        out.append({
            "accession": s.get("accessionId"),
            "trait": (s.get("diseaseTrait") or {}).get("trait"),
            "full_pvalue_set": bool(s.get("fullPvalueSet")),
            "sample": s.get("initialSampleSize"),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--accession", help="GWAS Catalog study accession, e.g. GCST90011885")
    ap.add_argument("--trait", help="Trait text to search for candidate studies (search mode).")
    ap.add_argument("--output-dir", default=None, help="Directory to write the downloaded .h.tsv.gz into.")
    ap.add_argument("--search-only", action="store_true", help="With --trait: list studies, download nothing.")
    ap.add_argument("--size", type=int, default=10, help="Max studies to return in search mode.")
    args = ap.parse_args()

    if args.trait and (args.search_only or not args.accession):
        results = search_studies(args.trait, args.size)
        with_stats = [r for r in results if r["full_pvalue_set"]]
        print(json.dumps({
            "mode": "search",
            "query": args.trait,
            "n_studies": len(results),
            "n_with_summary_stats": len(with_stats),
            "studies_with_summary_stats": with_stats,
            "studies_metadata_only": [r for r in results if not r["full_pvalue_set"]],
        }, indent=2))
        return

    if not args.accession:
        ap.error("provide --accession to download, or --trait --search-only to search")

    meta = study_metadata(args.accession)
    if not meta["full_pvalue_set"]:
        print(json.dumps({
            "mode": "download",
            "accession": args.accession,
            "success": False,
            "error": "study has no full summary statistics (fullPvalueSet is false); "
                     "only top associations are available via the REST API",
            "metadata": meta,
        }, indent=2))
        sys.exit(2)

    url = harmonised_url(args.accession)
    out_dir = Path(args.output_dir or f"data/gwas/{args.accession}")
    dest = out_dir / url.rsplit("/", 1)[-1]
    print(f"Downloading {url}\n  -> {dest}", file=sys.stderr)
    n_bytes = download(url, dest)

    print(json.dumps({
        "mode": "download",
        "accession": args.accession,
        "success": True,
        "trait": meta["trait"],
        "source_url": url,
        "output_file": str(dest),
        "bytes": n_bytes,
        "metadata": meta,
    }, indent=2))


if __name__ == "__main__":
    main()
