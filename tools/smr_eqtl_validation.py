#!/usr/bin/env python3
"""SMR (Summary-based Mendelian Randomization) validation of SNP -> gene
expression links, using GWAS independent-signal stats (COJO/SuSiE) against
an eQTL summary table (e.g. GTEx, any tissue).

Generalizes the old 19_run_smr_validation.py: trait list and the eQTL
source path/columns are CLI args instead of being hardcoded to a 3-trait
liver project, and the eQTL source isn't assumed to be GTEx liver
specifically (any GTEx-formatted, or column-compatible, eQTL parquet works).

SMR estimator: b_SMR = b_GWAS / b_eQTL (Wald ratio), with
Z_SMR = Z_GWAS / Z_eQTL and p_SMR from the standard normal.
"""
import argparse
import os

import numpy as np
import pandas as pd
import scipy.stats as stats


def load_eqtl(eqtl_path, variant_col, gene_col, beta_col, se_col, pval_col, variant_id_format):
    print(f"Loading eQTL data from {eqtl_path}...")
    if eqtl_path.endswith(".parquet"):
        eqtl = pd.read_parquet(eqtl_path)
    else:
        eqtl = pd.read_csv(eqtl_path, sep="\t" if eqtl_path.endswith((".tsv", ".txt")) else ",")

    eqtl = eqtl.rename(columns={
        variant_col: "variant_id_raw",
        gene_col: "phenotype_id",
        beta_col: "slope",
        se_col: "slope_se",
        pval_col: "pval_nominal",
    })

    if variant_id_format == "gtex":
        # GTEx variant_id convention: chrCHR_POS_REF_ALT_build, e.g. chr1_12345_A_G_b38
        print("Formatting GTEx-style variant IDs (chr_pos_ref_alt_build) to CHR:POS:REF:ALT...")
        parts = eqtl["variant_id_raw"].str.split("_")
        chr_num = parts.str[0].str.replace("chr", "")
        pos = parts.str[1]
        ref = parts.str[2]
        alt = parts.str[3]
        eqtl["SNP_match"] = chr_num + ":" + pos + ":" + ref + ":" + alt
        eqtl["SNP_match_flip"] = chr_num + ":" + pos + ":" + alt + ":" + ref
    elif variant_id_format == "passthrough":
        # variant_id already matches the GWAS SNP id convention (CHR:POS:REF:ALT)
        eqtl["SNP_match"] = eqtl["variant_id_raw"]
        eqtl["SNP_match_flip"] = None
    else:
        raise ValueError(f"Unknown variant_id_format: {variant_id_format}")

    keep_cols = ["phenotype_id", "slope", "slope_se", "pval_nominal"]
    exact = eqtl[["SNP_match"] + keep_cols].rename(columns={"SNP_match": "SNP"})
    if eqtl["SNP_match_flip"].notna().any():
        flip = eqtl[["SNP_match_flip"] + keep_cols].rename(columns={"SNP_match_flip": "SNP"})
        flip["slope"] = -flip["slope"]
        combined = pd.concat([exact, flip]).drop_duplicates(subset=["SNP", "phenotype_id"])
    else:
        combined = exact.drop_duplicates(subset=["SNP", "phenotype_id"])
    return combined


def run_smr_validation(args):
    print("Starting COJO + SuSiE + SMR Validation...")

    print(f"Loading COJO + SuSiE comparison table from {args.comparison_path}...")
    df_stats = pd.read_excel(args.comparison_path, sheet_name=args.comparison_sheet)

    if args.cojo_locus_map_template and args.traits:
        cojo_details = []
        for trait in args.traits.split(","):
            trait = trait.strip()
            f = args.cojo_locus_map_template.format(trait=trait)
            if os.path.exists(f):
                df = pd.read_excel(f, sheet_name="Results")
                cols = [c for c in ["Independent_SNP_ID", "Indep_pJ", "Interpretation", "Priority"] if c in df.columns]
                cojo_details.append(df[cols].drop_duplicates())
        if cojo_details:
            df_cojo_ext = pd.concat(cojo_details, ignore_index=True).drop_duplicates(subset=["Independent_SNP_ID"])
            df_stats = pd.merge(df_stats, df_cojo_ext, left_on="SNP", right_on="Independent_SNP_ID", how="left")

    eqtl_combined = load_eqtl(
        args.eqtl_path, args.eqtl_variant_col, args.eqtl_gene_col,
        args.eqtl_beta_col, args.eqtl_se_col, args.eqtl_pval_col, args.variant_id_format,
    )

    print("Intersecting GWAS statistics with eQTLs...")
    validated = pd.merge(df_stats, eqtl_combined, on="SNP", how="inner")
    print(f"Found {len(validated)} SNP-gene overlaps.")
    if validated.empty:
        print("No overlaps between GWAS instruments and eQTL data - nothing to validate.")
        return

    print("Calculating SMR statistics...")
    p_for_z = validated["Indep_pJ"].fillna(validated["Indep_p"]) if "Indep_pJ" in validated.columns else validated["Indep_p"]
    validated["Z_GWAS"] = np.sign(validated["Indep_bJ"]) * np.abs(stats.norm.ppf(p_for_z / 2.0))
    validated["Z_eQTL"] = validated["slope"] / validated["slope_se"]

    validated["SMR_b"] = validated["Indep_bJ"] / validated["slope"]
    validated["SMR_Z"] = validated["Z_GWAS"] / validated["Z_eQTL"]
    validated["SMR_p"] = 2 * stats.norm.sf(np.abs(validated["SMR_Z"]))

    validated = validated.rename(columns={"slope": "eQTL_beta", "pval_nominal": "eQTL_p"})
    cols_order = [
        "Source", "SNP", "phenotype_id", "SMR_p", "SMR_b", "PIP", "CS",
        "Indep_bJ", "Indep_pJ", "P_Value_Improvement", "Interpretation", "Priority",
        "eQTL_beta", "eQTL_p", "Locus_Source", "LD_Indep_vs_Lead_r2", "Indep_b", "Indep_p",
    ]
    sort_cols = [c for c in ["Source", "SMR_p"] if c in validated.columns]
    final_df = validated[[c for c in cols_order if c in validated.columns]].sort_values(sort_cols)

    info_data = [
        ["Source", "[METADATA]", "The trait/disease source for this signal."],
        ["SNP", "[METADATA]", "The coordinate-based Variant ID (CHR:POS:REF:ALT)."],
        ["phenotype_id", "[SMR]", "The gene whose expression is tested against the eQTL source."],
        ["SMR_p", "[SMR]", "Significance of the causal link between gene expression and trait. P < 0.05 is significant."],
        ["SMR_b", "[SMR]", "Causal effect size of gene expression on the trait (Wald ratio)."],
        ["PIP", "[SuSiE]", "Bayesian probability (0-1) that the SNP is causal."],
        ["CS", "[SuSiE]", "The 95% Credible Set membership."],
        ["Indep_bJ", "[COJO]", "Joint effect size of the variant after conditioning."],
        ["Indep_pJ", "[COJO]", "Joint P-value of the variant after conditioning."],
        ["P_Value_Improvement", "[COJO]", "Significance revealed by the pipeline (-log10P gain)."],
        ["Interpretation", "[COJO]", "Discovery type (Masked, Refined, or Confirmed)."],
        ["Priority", "[COJO]", "Follow-up priority ranking."],
        ["eQTL_beta", "[eQTL]", "The effect size of the SNP on gene expression in the chosen eQTL source/tissue."],
        ["eQTL_p", "[eQTL]", "The significance of the SNP-gene association in the eQTL source."],
        ["Locus_Source", "[METADATA]", "The genomic region identifier."],
        ["LD_Indep_vs_Lead_r2", "[COJO]", "Correlation between the causal driver and the original lead hit."],
    ]
    info_df = pd.DataFrame(info_data, columns=["Column", "Method", "Explanation"])

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="SMR_Validation", index=False)
        info_df.to_excel(writer, sheet_name="Info", index=False)

    print(f"Validation complete. File saved to: {args.output}")


def main():
    parser = argparse.ArgumentParser(description="SMR validation of SNP->gene links against an eQTL source")
    parser.add_argument("--comparison_path", required=True, help="XLSX with merged COJO+SuSiE stats (needs SNP, Indep_bJ, Indep_p[/pJ] columns)")
    parser.add_argument("--comparison_sheet", default="Stats_Comparison")
    parser.add_argument("--cojo_locus_map_template", default=None,
                         help="Optional path template (e.g. 'results/COJO/COJO_{trait}_Locus_Map.xlsx') to enrich with Indep_pJ/Interpretation/Priority")
    parser.add_argument("--traits", default=None, help="Comma-separated trait names to substitute into --cojo_locus_map_template")
    parser.add_argument("--eqtl_path", required=True, help="eQTL summary table (GTEx-format parquet, or TSV/CSV)")
    parser.add_argument("--eqtl_variant_col", default="variant_id")
    parser.add_argument("--eqtl_gene_col", default="phenotype_id")
    parser.add_argument("--eqtl_beta_col", default="slope")
    parser.add_argument("--eqtl_se_col", default="slope_se")
    parser.add_argument("--eqtl_pval_col", default="pval_nominal")
    parser.add_argument("--variant_id_format", default="gtex", choices=["gtex", "passthrough"],
                         help="'gtex' parses chr_pos_ref_alt_build IDs; 'passthrough' assumes variant_id already matches the GWAS SNP id (CHR:POS:REF:ALT)")
    parser.add_argument("--output", required=True, help="Output XLSX path")
    args = parser.parse_args()

    run_smr_validation(args)


if __name__ == "__main__":
    main()
