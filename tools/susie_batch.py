#!/usr/bin/env python3
"""Batch-run SuSiE fine-mapping across every COJO-independent locus listed in
a locus-master file, for one or more traits.

Generalizes the old 18_run_batch_susie.py: trait names, sumstats paths,
sample sizes, and the LD reference panel are all supplied via --config
instead of being hardcoded, so this works for any set of traits/loci.

Config JSON schema:
{
  "locus_master_file": "path/to/locus_master.csv",   # columns: Source, Independent_SNP_ID, Independent_SNP_Pos
  "sumstats_map": {
    "<Source value>": {"file": "path/to/trait.ma", "N": 123456}
  },
  "window_size": 500000,
  "out_base_dir": "results/SuSiE",
  "bfile": "path/to/1000G_reference",
  "conda_env": "finemap",                              # optional, default "finemap"
  "cojo_locus_map_template": "results/COJO/COJO_{trait}_Locus_Map.xlsx"  # optional
}
"""
import argparse
import json
import os
import subprocess

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_susie_batch(config):
    locus_master_file = config["locus_master_file"]
    sumstats_map = config["sumstats_map"]
    window_size = config.get("window_size", 500000)
    out_base_dir = config["out_base_dir"]
    bfile = config["bfile"]
    conda_env = config.get("conda_env", "finemap")
    cojo_template = config.get("cojo_locus_map_template")

    if not os.path.exists(locus_master_file):
        print(f"Error: {locus_master_file} not found.")
        return

    df_loci = pd.read_csv(locus_master_file)
    print(f"Found {len(df_loci)} loci to process.")

    for idx, row in df_loci.iterrows():
        trait = row["Source"]
        snp_id = row["Independent_SNP_ID"]
        snp_pos = int(row["Independent_SNP_Pos"])

        try:
            chrom = snp_id.split(":")[0]
        except Exception:
            print(f"Skipping malformed SNP ID: {snp_id}")
            continue

        if trait not in sumstats_map:
            print(f"Skipping {trait}: not present in sumstats_map.")
            continue

        locus_name = f"{trait}_{chrom}_{snp_pos}"
        locus_dir = os.path.join(out_base_dir, locus_name)
        os.makedirs(locus_dir, exist_ok=True)

        regional_csv = os.path.join(locus_dir, "regional_sumstats.csv")
        final_xlsx = os.path.join(locus_dir, f"SuSiE_{locus_name}_Results.xlsx")

        print(f"[{idx + 1}/{len(df_loci)}] Processing {locus_name}...")

        # A. Extract dense summary stats for the region
        if not os.path.exists(regional_csv):
            ma_file = sumstats_map[trait]["file"]
            start = snp_pos - window_size
            end = snp_pos + window_size

            print(f"   - Extracting dense region {chrom}:{start}-{end}...")
            # SNP column is field 1, format CHR:POS:REF:ALT
            awk_cmd = (
                f"awk 'NR==1 || ($1 ~ /^{chrom}:/ && "
                f"(split($1,a,\":\") && a[2] >= {start} && a[2] <= {end}))' "
                f"{ma_file} > {regional_csv}.tmp"
            )
            subprocess.run(awk_cmd, shell=True, check=True)

            df_reg = pd.read_csv(f"{regional_csv}.tmp", sep="\t")
            df_reg = df_reg.rename(columns={"b": "beta"})
            df_reg.to_csv(regional_csv, index=False)
            os.remove(f"{regional_csv}.tmp")
            print(f"   - Found {len(df_reg)} SNPs.")

            if len(df_reg) < 10:
                print("   - Warning: Too few SNPs in region. Skipping.")
                continue

        # B. Run SuSiE pipeline (LD extraction + fine-mapping)
        susie_results_csv = os.path.join(locus_dir, "susie_run_susie_results.csv")
        if not os.path.exists(susie_results_csv):
            print("   - Running SuSiE...")
            susie_cmd = [
                "bash", os.path.join(SCRIPT_DIR, "extract_ld_and_run_susie.sh"),
                regional_csv,
                bfile,
                str(sumstats_map[trait]["N"]),
                os.path.join(locus_dir, "susie_run"),
            ]
            full_cmd = ["conda", "run", "-n", conda_env] + susie_cmd
            result = subprocess.run(full_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                err_log = os.path.join(locus_dir, "susie_error.log")
                with open(err_log, "w") as f:
                    f.write(result.stdout)
                    f.write(result.stderr)
                print(f"   - SuSiE command failed (exit {result.returncode}). See {err_log}")
        else:
            print("   - SuSiE results found. Skipping computation.")

        # C. Export merged Excel result (optionally joined with the COJO locus map)
        if os.path.exists(susie_results_csv):
            print("   - Exporting to XLSX...")
            df_res = pd.read_csv(susie_results_csv)

            df_cojo_locus = pd.DataFrame()
            if cojo_template:
                cojo_master = cojo_template.format(trait=trait)
                try:
                    df_cojo_all = pd.read_excel(cojo_master, sheet_name="Results")
                    df_cojo_locus = df_cojo_all[df_cojo_all["Independent_SNP_Pos"] == snp_pos].copy()
                except Exception:
                    pass

            info_data = [
                ["SNP", "Variant ID", "Unique identifier (CHR:POS:REF:ALT)."],
                ["PIP", "Causal Probability", "The Bayesian probability (0.0-1.0) that this specific SNP is causal. 1.0 is highest certainty."],
                ["CS", "95% Credible Set", "Groups SNPs into independent causal signals (1, 2, 3...). 0 means not causal."],
                ["beta / se", "GWAS Statistics", "The effect size and standard error from the input GWAS."],
                ["p", "P-value", "Original marginal P-value."],
                ["--- Note ---", "", "SuSiE reveals multiple independent causal signals within a single locus that COJO may miss."],
            ]
            info_df = pd.DataFrame(info_data, columns=["Column", "Full Name", "Explanation"])

            with pd.ExcelWriter(final_xlsx, engine="openpyxl") as writer:
                if not df_cojo_locus.empty:
                    cojo_cols = [c for c in [
                        "Independent_SNP_ID", "Indep_bJ", "Indep_pJ", "LD_Indep_vs_Lead_r2",
                        "Interpretation", "Priority", "P_Value_Improvement",
                    ] if c in df_cojo_locus.columns]
                    cojo_stats = df_cojo_locus[cojo_cols].drop_duplicates()
                    merged_df = pd.merge(df_res, cojo_stats, left_on="SNP", right_on="Independent_SNP_ID", how="left")
                    cols_order = ["SNP", "PIP", "Indep_pJ", "CS", "P_Value_Improvement", "Interpretation", "Priority", "LD_Indep_vs_Lead_r2", "beta", "se", "p"]
                    merged_df = merged_df[[c for c in cols_order if c in merged_df.columns] + [c for c in merged_df.columns if c not in cols_order]]
                    merged_df.sort_values("PIP", ascending=False).to_excel(writer, sheet_name="Integrated_Results", index=False)
                    df_cojo_locus.to_excel(writer, sheet_name="COJO_Hit_Mapping", index=False)
                else:
                    df_res.sort_values("PIP", ascending=False).to_excel(writer, sheet_name="SuSiE_Results", index=False)

                info_df.to_excel(writer, sheet_name="Info", index=False)

            print(f"   - Completed: {final_xlsx}")
        else:
            print(f"   - Error: SuSiE run failed for {locus_name}. Check logs in folder.")


def main():
    parser = argparse.ArgumentParser(description="Batch SuSiE fine-mapping across COJO-independent loci")
    parser.add_argument("--config", required=True, help="Path to JSON config (see module docstring for schema)")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    run_susie_batch(config)


if __name__ == "__main__":
    main()
