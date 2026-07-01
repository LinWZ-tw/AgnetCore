#!/usr/bin/env python3
"""Convert an arbitrary GWAS summary-stats file to GCTA-COJO .ma format.

GCTA .ma columns: SNP A1 A2 freq b se p N
(A1 = effect allele, A2 = other allele)

Generalizes the old per-trait format_gwas_to_ma.py: instead of one
hardcoded column mapping per trait, every column is supplied on the
command line so any GWAS-SSF-style or custom summary-stats file works.
"""
import argparse
import sys

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Convert GWAS summary stats to GCTA .ma format")
    parser.add_argument("--input", required=True, help="Input summary-stats file (.tsv/.csv, optionally .gz)")
    parser.add_argument("--output", required=True, help="Output .ma file")
    parser.add_argument("--sep", default=None, help="Field separator (default: inferred from file extension)")
    parser.add_argument("--chr_col", required=True)
    parser.add_argument("--pos_col", required=True)
    parser.add_argument("--effect_allele_col", required=True)
    parser.add_argument("--other_allele_col", required=True)
    parser.add_argument("--eaf_col", required=True, help="Effect allele frequency column")
    parser.add_argument("--se_col", required=True)
    parser.add_argument("--pval_col", required=True)
    effect = parser.add_mutually_exclusive_group(required=True)
    effect.add_argument("--beta_col", help="Column already on the log/beta scale")
    effect.add_argument("--or_col", help="Column on the odds-ratio scale (will be log-transformed)")
    n_group = parser.add_mutually_exclusive_group(required=True)
    n_group.add_argument("--n", type=float, help="Fixed total sample size for every row")
    n_group.add_argument("--n_col", help="Per-row sample size column")
    parser.add_argument("--snp_id_col", default=None,
                         help="Use this column verbatim as the SNP id instead of building CHR:POS:A2:A1")
    args = parser.parse_args()

    sep = args.sep
    if sep is None:
        sep = "\t" if (".tsv" in args.input or args.input.endswith(".txt")) else ","

    print(f"Reading {args.input}...")
    df = pd.read_csv(args.input, sep=sep, low_memory=False)

    ma_df = pd.DataFrame()
    if args.snp_id_col:
        ma_df["SNP"] = df[args.snp_id_col].astype(str)
    else:
        ma_df["SNP"] = (
            df[args.chr_col].astype(str) + ":" + df[args.pos_col].astype(str) + ":"
            + df[args.other_allele_col].astype(str) + ":" + df[args.effect_allele_col].astype(str)
        )
    ma_df["A1"] = df[args.effect_allele_col]
    ma_df["A2"] = df[args.other_allele_col]
    ma_df["freq"] = pd.to_numeric(df[args.eaf_col], errors="coerce")
    if args.beta_col:
        ma_df["b"] = pd.to_numeric(df[args.beta_col], errors="coerce")
    else:
        odds_ratio = pd.to_numeric(df[args.or_col], errors="coerce")
        ma_df["b"] = np.log(odds_ratio)
    ma_df["se"] = pd.to_numeric(df[args.se_col], errors="coerce")
    ma_df["p"] = pd.to_numeric(df[args.pval_col], errors="coerce")
    ma_df["N"] = args.n if args.n is not None else pd.to_numeric(df[args.n_col], errors="coerce")

    n_before = len(ma_df)
    ma_df = ma_df.dropna(subset=["SNP", "A1", "A2", "freq", "b", "se", "p", "N"])
    n_dropped = n_before - len(ma_df)
    if n_dropped:
        print(f"Dropped {n_dropped} row(s) with missing required values.")

    print(f"Saving {len(ma_df)} rows to {args.output}...")
    ma_df.to_csv(args.output, sep="\t", index=False)
    print("Done.")


if __name__ == "__main__":
    sys.exit(main())
