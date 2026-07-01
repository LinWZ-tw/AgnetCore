#!/usr/bin/env python3
"""Build a causal-network node/edge table from validated SNP-gene (SMR) links
and, optionally, real trait-to-trait MR results.

Generalizes the old 20_extract_graph_table.py. Two changes from the original:
1. Trait list, input path, and column names are CLI args instead of being
   hardcoded to a 3-trait liver project.
2. Trait->Trait edges are read from the actual two_sample_mr.R output
   (via --trait_trait_mr_config) instead of hand-coded literal weights.
   If no MR config is given, no trait-to-trait edges are added - that step
   is skipped, which is the correct behavior when trait-to-trait MR isn't
   applicable rather than synthesizing fake numbers.

--trait_trait_mr_config is a JSON list, one entry per trait->trait edge:
[
  {"source": "MASLD", "target": "Cirrhosis",
   "mr_results_csv": "results/MR/Cirrhosis_MR_results.csv",
   "method": "Inverse variance weighted"}
]
Each mr_results_csv is the *_MR_results.csv produced by two_sample_mr.R,
which has columns: exposure, outcome, method, b, se, pval, OR, OR_lower, OR_upper.
"""
import argparse
import json
import os

import pandas as pd


def load_table(path, sheet_name):
    if path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_csv(path)


def build_snp_gene_and_gene_trait_edges(df, args):
    df = df[df[args.smr_p_col].notna()].copy()

    gene_col = args.gene_col if args.gene_col in df.columns else "phenotype_id"
    snp_label_col = args.rsid_col if (args.rsid_col and args.rsid_col in df.columns) else args.snp_col

    df["node_gene"] = df[gene_col]
    df["node_snp"] = df[snp_label_col]
    if args.rsid_col and args.rsid_col in df.columns:
        df["node_snp"] = df[args.rsid_col].fillna(df[args.snp_col])

    has_prob = args.interaction_prob_col and args.interaction_prob_col in df.columns

    edges = []
    for _, row in df.iterrows():
        edges.append({
            "source": row["node_snp"],
            "target": row["node_gene"],
            "type": "SNP-Gene (Validated)",
            "weight": row[args.pip_col],
            "smr_p": row[args.smr_p_col],
            "prob": row[args.interaction_prob_col] if has_prob else 1.0,
        })
    for _, row in df.iterrows():
        edges.append({
            "source": row["node_gene"],
            "target": row[args.source_col],
            "type": "Gene-Trait (Discovery)",
            "weight": 1.0,
            "smr_p": row[args.smr_p_col],
            "prob": 1.0,
        })
    return df, edges


def build_trait_trait_edges(mr_config_path):
    with open(mr_config_path) as f:
        entries = json.load(f)
    if isinstance(entries, dict):
        entries = entries.get("edges", entries.get("entries", []))

    edges = []
    for entry in entries:
        csv_path = entry["mr_results_csv"]
        if not os.path.exists(csv_path):
            print(f"Warning: {csv_path} not found, skipping {entry['source']} -> {entry['target']}")
            continue
        mr_res = pd.read_csv(csv_path)
        method = entry.get("method", "Inverse variance weighted")
        row = mr_res[mr_res["method"] == method]
        if row.empty:
            print(f"Warning: method '{method}' not found in {csv_path}, skipping")
            continue
        row = row.iloc[0]
        edges.append({
            "source": entry["source"],
            "target": entry["target"],
            "type": "Disease Progression",
            "weight": row.get("OR", abs(row["b"])),
            "smr_p": row["pval"],
            "prob": 1.0,
        })
    return edges


def main():
    parser = argparse.ArgumentParser(description="Extract causal-network nodes/edges from validated SMR results and (optionally) trait-to-trait MR")
    parser.add_argument("--input_path", required=True, help="Validated SMR table (xlsx or csv), e.g. SMR_eQTL_Validation.xlsx")
    parser.add_argument("--sheet_name", default="SMR_Validation")
    parser.add_argument("--snp_col", default="SNP")
    parser.add_argument("--gene_col", default="phenotype_id")
    parser.add_argument("--rsid_col", default=None, help="Optional column with rsIDs to use as SNP node labels instead of --snp_col")
    parser.add_argument("--pip_col", default="PIP")
    parser.add_argument("--smr_p_col", default="SMR_p")
    parser.add_argument("--source_col", default="Source", help="Column naming the trait each row belongs to")
    parser.add_argument("--interaction_prob_col", default=None, help="Optional ML interaction-probability column (e.g. from EPFinder)")
    parser.add_argument("--trait_trait_mr_config", default=None,
                         help="JSON list of {source,target,mr_results_csv,method} - see module docstring. Omit to skip trait-to-trait edges entirely.")
    parser.add_argument("--output_edges", required=True)
    parser.add_argument("--output_nodes", required=True)
    args = parser.parse_args()

    print(f"Loading data from {args.input_path}...")
    df = load_table(args.input_path, args.sheet_name)

    df_validated, edges = build_snp_gene_and_gene_trait_edges(df, args)

    if args.trait_trait_mr_config:
        print(f"Adding trait-to-trait edges from {args.trait_trait_mr_config}...")
        edges.extend(build_trait_trait_edges(args.trait_trait_mr_config))
    else:
        print("No --trait_trait_mr_config given; skipping trait-to-trait edges.")

    df_edges = pd.DataFrame(edges).drop_duplicates(subset=["source", "target", "type"])
    os.makedirs(os.path.dirname(args.output_edges) or ".", exist_ok=True)
    df_edges.to_csv(args.output_edges, index=False)

    print("Extracting node metadata...")
    nodes = []
    for t in df_validated[args.source_col].unique():
        nodes.append({"id": t, "label": t, "group": "Trait", "color": "red"})
    unique_genes = df_validated["node_gene"].unique()
    for g in unique_genes:
        nodes.append({"id": g, "label": g, "group": "Gene", "color": "blue"})
    unique_snps = df_validated["node_snp"].unique()
    for s in unique_snps:
        nodes.append({"id": s, "label": s, "group": "SNP", "color": "gray"})

    df_nodes = pd.DataFrame(nodes)
    os.makedirs(os.path.dirname(args.output_nodes) or ".", exist_ok=True)
    df_nodes.to_csv(args.output_nodes, index=False)

    print("\nSuccess! Created:")
    print(f"  - Edges Table: {args.output_edges}")
    print(f"  - Nodes Table: {args.output_nodes}")
    print(f"Total Unique Validated SNPs in Graph: {len(unique_snps)}")
    print(f"Total Unique Genes in Graph: {len(unique_genes)}")


if __name__ == "__main__":
    main()
