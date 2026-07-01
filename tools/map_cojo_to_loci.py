#!/usr/bin/env python3
"""Map original genome-wide-significant hits to their nearest GCTA-COJO
independent signal and compute LD between them.

Trait-agnostic: --phenotype is just a filter string applied to the
"Phenotype" column of --original_sig, so this works for any trait.
"""
import pandas as pd
import numpy as np
import argparse
import os
import subprocess

def get_bim_ids(bim_file, coord_list):
    """
    Looks up real SNP IDs from the .bim file based on a list of (Chr, Pos).
    Returns a dictionary of (Chr, Pos) -> Real_ID.
    """
    coords = set(coord_list)
    id_map = {}
    print(f"Scanning {bim_file} for {len(coords)} unique coordinates...")

    try:
        with open(bim_file, 'r') as f:
            for line in f:
                parts = line.split()
                if not parts: continue
                # Handle cases where chromosome is 'chr1' or just '1'
                raw_chr = parts[0]
                chrom = int(raw_chr) if raw_chr.isdigit() else raw_chr
                pos = int(parts[3])
                if (chrom, pos) in coords:
                    id_map[(chrom, pos)] = parts[1]
                    # Optimization: if we found all, we can stop
                    if len(id_map) == len(coords):
                        break
    except Exception as e:
        print(f"Warning: Error reading BIM file: {e}")
    return id_map

def get_ld_r2(bfile, snp1, snp2):
    """
    Uses PLINK to calculate the LD (r2) between two SNPs.
    """
    if snp1 == snp2: return 1.0
    if not snp1 or not snp2 or pd.isna(snp1) or pd.isna(snp2): return np.nan

    # Check if positions are same
    try:
        if snp1.split(':')[1] == snp2.split(':')[1]: return 1.0
    except:
        pass

    out_file = f"temp_ld_{os.getpid()}"
    cmd = [
        "plink", "--bfile", bfile,
        "--ld", snp1, snp2,
        "--allow-extra-chr",
        "--out", out_file
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        log_file = f"{out_file}.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in f:
                    if "R-sq =" in line:
                        r2 = line.split("R-sq =")[1].strip().split()[0]
                        return float(r2)
    except:
        pass
    finally:
        for ext in ['.log', '.nosex', '.ld']:
            if os.path.exists(out_file + ext):
                os.remove(out_file + ext)
    return np.nan

def main():
    parser = argparse.ArgumentParser(description="Map original hits to COJO signals and calculate LD")
    parser.add_argument("--cojo_jma", required=True, help="Path to .jma.cojo result file")
    parser.add_argument("--original_sig", required=True,
                         help="CSV of genome-wide-significant hits with columns: Phenotype, chr, pos, rsID, gwasP_min")
    parser.add_argument("--phenotype", required=True, help="Phenotype string to filter --original_sig by")
    parser.add_argument("--output", required=True, help="Output XLSX path")
    parser.add_argument("--bfile", required=True, help="Path to PLINK bfile used as the LD reference panel")
    args = parser.parse_args()

    # 1. Load COJO Independent Signals
    print(f"Loading COJO results from {args.cojo_jma}...")
    sep = '\t' if args.cojo_jma.endswith('.cojo') else ','
    indeps = pd.read_csv(args.cojo_jma, sep=sep)
    indeps['Chr'] = pd.to_numeric(indeps['Chr'], errors='coerce')
    indeps['bp'] = pd.to_numeric(indeps['bp'], errors='coerce')

    # 2. Load Original Significant SNPs
    print(f"Loading original significant SNPs...")
    orig = pd.read_csv(args.original_sig)
    mask = orig['Phenotype'].str.contains(args.phenotype, na=False)
    orig_filtered = orig[mask].copy()

    if orig_filtered.empty:
        print(f"Warning: No hits found for '{args.phenotype}'")
        return

    # 3. Initial Mapping and Coordination Collection
    results = []
    needed_coords = []

    # Pre-add all COJO positions to needed coords
    for _, row in indeps.iterrows():
        needed_coords.append((row['Chr'], int(row['bp'])))

    for idx, row in orig_filtered.iterrows():
        chrom = row['chr']
        pos = int(row['pos'])
        chrom_indeps = indeps[indeps['Chr'] == chrom]
        if chrom_indeps.empty: continue

        distances = (chrom_indeps['bp'] - pos).abs()
        min_dist = distances.min()
        if min_dist > 1000000: continue

        nearest_indep = chrom_indeps.loc[distances.idxmin()]

        res_row = {
            'Original_rsID': row['rsID'],
            'Original_Chr': chrom,
            'Original_Pos': pos,
            'Original_P': row['gwasP_min'],
            'Independent_SNP_Pos': int(nearest_indep['bp']),
            'Dist_to_Independent': int(min_dist)
        }
        needed_coords.append((chrom, pos))

        for col in ['SNP', 'bJ', 'pJ', 'LD_r', 'b', 'p', 'freq']:
            val_col = f'Indep_{col}' if col != 'SNP' else 'Independent_SNP_ID_Raw'
            res_row[val_col] = nearest_indep[col] if col in nearest_indep else nearest_indep.get(col.upper(), np.nan)

        results.append(res_row)

    if not results:
        print("No matches found within 1Mb threshold.")
        return

    df_results = pd.DataFrame(results)

    # 4. Lookup Real IDs from Reference Panel
    bim_file = args.bfile + ".bim"
    id_map = get_bim_ids(bim_file, needed_coords)

    # 5. Finalize Locus Leads and Calculate LD
    print("Identifying Locus Lead SNPs and calculating LD...")
    locus_info = []

    for indep_pos, group in df_results.groupby('Independent_SNP_Pos'):
        lead_idx = group['Original_P'].idxmin()
        lead_row = group.loc[lead_idx]

        chrom = lead_row['Original_Chr']
        # Lookup the ID string PLINK actually uses in the reference panel
        indep_real_id = id_map.get((chrom, int(indep_pos)))
        lead_real_id = id_map.get((chrom, int(lead_row['Original_Pos'])))

        ld_r2 = np.nan
        if indep_real_id and lead_real_id:
            ld_r2 = get_ld_r2(args.bfile, indep_real_id, lead_real_id)

        locus_data = {
            'Independent_SNP_Pos': indep_pos,
            'Independent_SNP_ID': indep_real_id if indep_real_id else "Not_in_Reference",
            'Locus_Lead_rsID': lead_row['Original_rsID'],
            'Locus_Lead_Pos': int(lead_row['Original_Pos']),
            'Locus_Lead_P': lead_row['Original_P'],
            'LD_Indep_vs_Lead_r2': ld_r2
        }
        locus_info.append(locus_data)

    df_locus = pd.DataFrame(locus_info)
    final_df = pd.merge(df_results, df_locus, on='Independent_SNP_Pos', how='left')

    # Calculate P-value Improvement and Categories
    final_df['P_Value_Improvement'] = (-np.log10(final_df['Indep_pJ'].astype(float)) - (-np.log10(final_df['Indep_p'].astype(float)))).round(2)

    def get_interp(row):
        if float(row['Indep_p']) > 5e-8:
            return "Masked / Hidden Variant"
        elif float(row['P_Value_Improvement']) > 1.0:
            return "Refined Causal Driver"
        else:
            return "Confirmed Signal"

    def get_priority(row):
        mapping = {
            "Masked / Hidden Variant": "Extreme",
            "Refined Causal Driver": "High",
            "Confirmed Signal": "Medium"
        }
        return mapping[row['Interpretation']]

    final_df['Interpretation'] = final_df.apply(get_interp, axis=1)
    final_df['Priority'] = final_df.apply(get_priority, axis=1)

    # Organize columns
    cols = ['Original_rsID', 'Original_Pos', 'Original_P',
            'Locus_Lead_rsID', 'Locus_Lead_Pos', 'Locus_Lead_P', 'LD_Indep_vs_Lead_r2',
            'Independent_SNP_ID', 'Independent_SNP_Pos', 'Dist_to_Independent',
            'Indep_bJ', 'Indep_pJ', 'P_Value_Improvement', 'Interpretation', 'Priority',
            'Indep_LD_r', 'Indep_b', 'Indep_p', 'Indep_freq']
    final_df = final_df[[c for c in cols if c in final_df.columns]].sort_values(['Independent_SNP_Pos', 'Original_Pos'])

    # 6. Info Sheet
    info_data = [
        ["Original_rsID", "Initial Hit", "The SNP from your significant hit list."],
        ["Original_Pos / P", "Initial Stats", "Genomic position and marginal P-value of the initial hit."],
        ["Locus_Lead_rsID", "Most Significant Hit", "The SNP with the lowest marginal P-value in this genomic locus."],
        ["Locus_Lead_Pos / P", "Lead Stats", "Genomic position and P-value of the strongest hit in the locus."],
        ["LD_Indep_vs_Lead_r2", "LD Correlation", "The r-squared correlation between the COJO Independent SNP and the Locus Lead SNP."],
        ["Independent_SNP_ID", "COJO Driver", "The statistically independent causal driver identified by COJO."],
        ["Independent_SNP_Pos", "COJO Pos", "Genomic position of the independent driver."],
        ["Indep_bJ / pJ", "Joint Statistics", "The effect size and P-value of the Independent SNP AFTER conditioning on other signals."],
        ["P_Value_Improvement", "Significance Improvement", "The increase in -log10(P) from the Independent SNP's original marginal P-value to its joint P-value."],
        ["Interpretation", "Biological Interpretation", "Categorization of the discovery: Masked/Hidden (originally p>5e-8), Refined (p improved by >1 order of magnitude), or Confirmed."],
        ["Priority", "Validation Priority", "Ranking for biological validation: Extreme (Masked), High (Refined), or Medium (Confirmed)."],
        ["Indep_b / p", "Marginal Stats", "The original GWAS effect and P-value for the Independent SNP."],
        ["Indep_freq", "GWAS Frequency", "The frequency of the effect allele in the original GWAS study."]
    ]
    info_df = pd.DataFrame(info_data, columns=["Column", "Full Name", "Explanation"])

    print(f"Exporting to Excel: {args.output}...")
    with pd.ExcelWriter(args.output, engine='openpyxl') as writer:
        final_df.to_excel(writer, sheet_name='Results', index=False)
        info_df.to_excel(writer, sheet_name='Info', index=False)
    print("Done.")

if __name__ == "__main__":
    main()
