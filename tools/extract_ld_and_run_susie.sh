#!/bin/bash
# Extracts the LD matrix for a region using PLINK, then runs SuSiE fine-mapping.
# Usage: bash extract_ld_and_run_susie.sh <sumstats_region_csv> <plink_bfile_ref> <sample_size> <output_prefix>

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 <sumstats_region_csv> <plink_bfile_ref> <sample_size> <output_prefix>"
    echo "Note: sumstats_region_csv must have a 'SNP' column for PLINK extraction, and 'beta', 'se' columns for SuSiE."
    exit 1
fi

SUMSTATS=$1
BFILE_REF=$2
N=$3
OUT_PREFIX=$4

mkdir -p "$(dirname "${OUT_PREFIX}")"

echo "=========================================="
echo "SuSiE Fine-mapping Pipeline"
echo "Target Region Sumstats: $SUMSTATS"
echo "LD Reference: $BFILE_REF"
echo "Sample Size: $N"
echo "Output Prefix: $OUT_PREFIX"
echo "=========================================="

# 1. Extract SNP list
SNP_LIST="${OUT_PREFIX}_snps.txt"
echo "Extracting SNP list..."
python3 -c "
import pandas as pd
sep = '\t' if '${SUMSTATS}'.endswith('.tsv') else ','
df = pd.read_csv('${SUMSTATS}', sep=sep, engine='python')
df['SNP'].to_csv('${SNP_LIST}', index=False, header=False)
"

# 2. Extract LD Matrix using PLINK
echo "Computing LD matrix using PLINK..."
plink --bfile "${BFILE_REF}" \
      --extract "${SNP_LIST}" \
      --r square \
      --make-just-bim \
      --allow-extra-chr \
      --out "${OUT_PREFIX}"

if [ ! -f "${OUT_PREFIX}.ld" ]; then
    echo "Error: PLINK LD extraction failed. Ensure your SNPs overlap with the reference panel."
    exit 1
fi

# 3. Align Summary Statistics
# The order of SNPs in the LD matrix (.ld) matches the order in the output .bim file.
# We must reorder the sumstats to match the PLINK .bim order exactly.
ALIGNED_SUMSTATS="${OUT_PREFIX}_aligned_sumstats.csv"
echo "Aligning summary stats to LD matrix order..."
python3 -c "
import pandas as pd
sep = '\t' if '${SUMSTATS}'.endswith('.tsv') else ','
sumstats = pd.read_csv('${SUMSTATS}', sep=sep, engine='python')
# Some upstream GWAS files (e.g. meta-analyses) carry duplicate rows for the
# same SNP ID from incompletely merged cohorts. Keep the row with the larger
# N (the more complete meta-analysis estimate) so the merge below stays 1:1.
dup_mask = sumstats['SNP'].duplicated(keep=False)
if dup_mask.any():
    print('Dropping', dup_mask.sum() - sumstats.loc[dup_mask, \"SNP\"].nunique(), 'duplicate SNP row(s):', sorted(sumstats.loc[dup_mask, 'SNP'].unique()))
    sumstats = sumstats.sort_values('N', ascending=False).drop_duplicates('SNP', keep='first')
bim = pd.read_csv('${OUT_PREFIX}.bim', sep='\t', header=None, names=['chr', 'SNP', 'cm', 'bp', 'a1', 'a2'])
aligned = bim[['SNP']].merge(sumstats, on='SNP', how='inner')
aligned.to_csv('${ALIGNED_SUMSTATS}', index=False)
"

# 4. Run SuSiE Fine-mapping
echo "Running SuSiE..."
Rscript "${SCRIPT_DIR}/susie_finemap.R" "${ALIGNED_SUMSTATS}" "${OUT_PREFIX}.ld" "${N}" "${OUT_PREFIX}"

echo "=========================================="
echo "Fine-mapping pipeline complete."
echo "Results saved to: ${OUT_PREFIX}_susie_results.csv"
