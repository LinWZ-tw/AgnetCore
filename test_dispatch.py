#!/usr/bin/env python3
"""Free, no-API-key test of both domains' step library + job queue + checkpointing.

This drives each domain's `tools.dispatch` directly with deterministic
Python branch logic (mirroring what the system prompt asks the model to do)
instead of an actual LLM tool-use loop -- no API key needed for the
pipeline steps themselves. It exercises the shared dispatch/job/state.py
plumbing (including the `phase`/`exec_mode` fields and `state.set_domain`)
that both domains' `tools.py` route through.

The Reporter Agent (Layer 3) does need an LLM to synthesise the final
report. Pass --api-key (or set ANTHROPIC_API_KEY) to generate it; omit to
skip it.

Bio examples:
    python test_dispatch.py --data data/bio/demo/pbmc3k.h5ad --run-id demo
    python test_dispatch.py --data data/bio/demo/pbmc3k.h5ad --run-id demo --api-key sk-ant-...
    python test_dispatch.py --data data/bio/scRNA_AML --all --limit 5
    python test_dispatch.py --data data/bio/WES_OC_fasta

GWAS example (pure-Python step only -- format_gwas; steps that shell out to
the `finemap` conda env are not covered here, see smoketest/ instead):
    python test_dispatch.py --gwas-format-test --run-id gwas-demo
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agentcore import state  # noqa: E402
from agentcore.domains.bio.tools import dispatch as bio_dispatch  # noqa: E402
from agentcore.domains.gwas.tools import dispatch as gwas_dispatch  # noqa: E402


def show(label: str, result: dict) -> None:
    print(f"\n--- {label} ---")
    print(json.dumps(result, indent=2, default=str)[:1500])


def run_job(dispatch, run_id: str, phase: str | None, step: str, args: dict) -> dict:
    started = dispatch(run_id, "start_job", {"step": step, "args": args}, True, phase)
    job_id = started["job_id"]
    status = dispatch(run_id, "check_job_status", {"job_id": job_id}, True, phase)
    while status["status"] == "running":
        time.sleep(0.2)
        status = dispatch(run_id, "check_job_status", {"job_id": job_id}, True, phase)
    result = dispatch(run_id, "get_job_result", {"job_id": job_id}, True, phase)
    show(f"{step}", result)
    if result["status"] != "ok":
        raise RuntimeError(f"step '{step}' failed: {result}")
    return result["result"]


def run_scrna_branch(run_id: str, sample_id: str, input_path: str, n_cells: int | None) -> None:
    run_job(bio_dispatch, run_id, "scrna", "cell_annotation", {"sample_id": sample_id, "input_path": input_path, "mode": "mock", "n_cells": n_cells})
    clu = run_job(bio_dispatch, run_id, "scrna", "clustering", {"sample_id": sample_id, "input_path": input_path, "mode": "mock", "n_cells": n_cells})
    de = run_job(
        bio_dispatch, run_id, "scrna", "differential_expression",
        {"sample_id": sample_id, "input_path": input_path, "mode": "mock", "groups": list(clu["cluster_sizes"])},
    )
    run_job(bio_dispatch, run_id, "scrna", "gsea", {"sample_id": sample_id, "mode": "mock", "group": next(iter(de["top_de_genes"]))})


def run_wes_branch(run_id: str, sample_id: str, input_path: str) -> None:
    run_job(bio_dispatch, run_id, "wes", "qc", {"sample_id": sample_id, "input_path": input_path, "mode": "mock"})
    run_job(bio_dispatch, run_id, "wes", "alignment", {"sample_id": sample_id, "input_path": input_path, "mode": "mock"})
    run_job(bio_dispatch, run_id, "wes", "mutation_calling", {"sample_id": sample_id, "input_path": input_path, "mode": "mock"})


def run_gwas_format_test(run_id: str) -> None:
    """Deterministic coverage for the gwas domain's shared dispatch/job/state
    path, using format_gwas -- the one step that is pure Python (shells out
    to tools/format_gwas_to_ma.py via sys.executable, no `finemap` conda env
    needed). A tiny synthetic summary-stats CSV is generated on the fly so
    this test doesn't depend on smoketest/'s fixture column layout."""
    rdir = state.run_dir(run_id)
    input_csv = rdir / "synthetic_gwas_input.csv"
    output_ma = rdir / "synthetic_gwas_output.ma"

    rows = [
        {"snp": "rs1", "chr": "1", "pos": "1000", "a1": "A", "a2": "G", "eaf": "0.30", "beta": "0.05", "se": "0.02", "p": "0.01", "n": "50000"},
        {"snp": "rs2", "chr": "1", "pos": "2000", "a1": "C", "a2": "T", "eaf": "0.45", "beta": "-0.03", "se": "0.015", "p": "0.04", "n": "50000"},
        {"snp": "rs3", "chr": "2", "pos": "1500", "a1": "G", "a2": "A", "eaf": "0.10", "beta": "0.12", "se": "0.03", "p": "0.001", "n": "50000"},
    ]
    with input_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=> synthetic GWAS summary-stats fixture written to {input_csv}")

    inspected = gwas_dispatch(run_id, "inspect_gwas_input", {"path": str(input_csv)}, True)
    show("inspect_gwas_input", inspected)

    result = run_job(
        gwas_dispatch, run_id, "v2g", "format_gwas",
        {
            "input_file": str(input_csv), "output_file": str(output_ma),
            "chr_col": "chr", "pos_col": "pos",
            "effect_allele_col": "a1", "other_allele_col": "a2",
            "eaf_col": "eaf", "se_col": "se", "pval_col": "p",
            "beta_col": "beta", "n_col": "n", "snp_id_col": "snp", "sep": ",",
        },
    )
    if not output_ma.exists():
        raise RuntimeError(f"format_gwas reported success but {output_ma} was not written: {result}")
    print(f"\n=> format_gwas OK, wrote {output_ma}")


def run_reporter(run_id: str, api_key: str, provider: str, model: str | None) -> None:
    print("\n=== Reporter Agent (Layer 3) ===")
    from agentcore.agents.reporter import run as reporter_run
    result = reporter_run(
        run_id=run_id,
        provider_name=provider,
        api_key=api_key,
        model=model or None,
        auto_approve=True,
    )
    print(f"  report.md  : {result['report_md']}")
    print(f"  report.html: {result['report_html']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=None, help="Bio: path to inspect (relative to repo root or absolute).")
    parser.add_argument("--gwas-format-test", action="store_true", help="Run the gwas domain's format_gwas dispatch/job/state test on a synthetic fixture.")
    parser.add_argument("--run-id", default="test", help="results/<run-id>/ holds state.json for this run.")
    parser.add_argument("--sample", default=None, help="For a scrna_matrix_directory: filename of the one sample to use (default: first found).")
    parser.add_argument("--all", action="store_true", help="For a scrna_matrix_directory: run every sample found, not just the first.")
    parser.add_argument("--limit", type=int, default=None, help="With --all: cap how many samples to run (default: no cap).")
    # Reporter options
    parser.add_argument("--api-key", default="", help="LLM API key for the Reporter Agent. Falls back to ANTHROPIC_API_KEY env var.")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"], help="LLM provider for the Reporter (default: anthropic).")
    parser.add_argument("--model", default="", help="Model name for the Reporter (default: provider default).")
    parser.add_argument("--no-report", action="store_true", help="Skip the Reporter Agent even if an API key is available.")
    args = parser.parse_args()

    if not args.data and not args.gwas_format_test:
        parser.error("pass --data (bio) or --gwas-format-test (gwas)")

    if args.gwas_format_test:
        state.set_domain(args.run_id, "gwas")
        run_gwas_format_test(args.run_id)
        print(f"\n=== GWAS format_gwas test done. Checkpoint: results/{args.run_id}/state.json ===")
    else:
        state.set_domain(args.run_id, "bio")
        profile = bio_dispatch(args.run_id, "inspect_data_source", {"path": args.data}, True)
        show("inspect_data_source", profile)
        data_type = profile["data_type"]

        if data_type == "dna_exome_fastq_archive":
            sample_id = Path(profile["details"]["sample_entry_peeked"]).parent.name
            print(f"\n=> WES branch (sample_id={sample_id})")
            run_wes_branch(args.run_id, sample_id, args.data)

        elif data_type in ("scrna_count_matrix", "scrna_h5ad"):
            sample_id = Path(args.data).stem
            n_cells = profile["details"].get("n_cells") or profile["details"].get("n_obs_cells")
            print(f"\n=> scRNA branch (sample_id={sample_id}, n_cells={n_cells})")
            run_scrna_branch(args.run_id, sample_id, args.data, n_cells)

        elif data_type == "scrna_matrix_directory":
            # profile["details"]["sample_files"] is capped at 10 for display by
            # inspect_data_source -- get the full list via list_available_assets.
            assets = bio_dispatch(args.run_id, "list_available_assets", {"root": args.data, "pattern": "*.h5", "limit": 1000}, True)
            all_samples = [f["path"] for f in assets["files"]]
            if not all_samples:
                print("\n=> no .h5 sample files found via list_available_assets")
                return

            if args.all:
                chosen_list = all_samples[: args.limit] if args.limit else all_samples
            elif args.sample:
                chosen_list = [args.sample]
            else:
                chosen_list = all_samples[:1]

            print(f"\n=> scRNA branch on {len(chosen_list)} of {len(all_samples)} sample(s) found in {args.data}")
            for i, chosen in enumerate(chosen_list, 1):
                sample_path = str(Path(args.data) / chosen)
                sub_profile = bio_dispatch(args.run_id, "inspect_data_source", {"path": sample_path}, True)
                show(f"[{i}/{len(chosen_list)}] inspect_data_source({sample_path})", sub_profile)
                sample_id = Path(chosen).stem
                n_cells = sub_profile["details"]["n_cells"]
                print(f"\n=> running scRNA branch on {chosen} (sample_id={sample_id}, n_cells={n_cells})")
                run_scrna_branch(args.run_id, sample_id, sample_path, n_cells)

        else:
            print(f"\n=> data_type '{data_type}' has no test branch wired up here -- inspect manually.")
            return

        print(f"\n=== Pipeline steps done. Checkpoint: results/{args.run_id}/state.json ===")

    # --- Reporter Agent ---
    if args.no_report:
        print("\n(Reporter skipped via --no-report)")
        return

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print(
            "\n(Reporter skipped — no API key found. "
            "Pass --api-key sk-... or set ANTHROPIC_API_KEY to generate the report.)\n"
            f"  Report can be generated later by running the GUI (python server.py) "
            f"and resuming run '{args.run_id}'."
        )
        return

    run_reporter(args.run_id, api_key, args.provider, args.model or None)
    print(f"\n=== All done. Open results/{args.run_id}/report/report.html ===")


if __name__ == "__main__":
    main()
