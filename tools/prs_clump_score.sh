#!/bin/bash
# Usage: bash prs_clump_score.sh <gwas_ma_file> <ld_bfile_ref> <target_bfile> \
#            <output_prefix> [p_threshold] [clump_r2] [clump_kb] [extract_snps]
#
# Clumping + Thresholding (C+T) polygenic risk score, built on plink 1.9.
#   1. plink --clump on the LD reference -> LD-independent index SNPs at p < p_threshold
#   2. build a weight file (SNP, effect allele A1, beta b) from the GWAS .ma
#   3. plink --score on the target genotypes -> per-individual PRS (.profile)
#
# The GWAS .ma file must have columns: SNP A1 A2 freq b se p N
# (produced by format_gwas_to_ma.py). A1 is the effect allele that b refers to,
# so it is the allele plink scores on.
#
# <ld_bfile_ref>  PLINK bfile prefix used only for LD clumping (e.g. 1000G panel).
# <target_bfile>  PLINK bfile prefix of the cohort to score. For a demo with no
#                 separate target cohort, pass the same prefix as <ld_bfile_ref>
#                 (scores the reference samples themselves -- fine to prove the
#                 pipeline runs, but circular for a real risk estimate).
# [extract_snps]  Optional file with one SNP id per line. The clumped index set
#                 is intersected with it, giving a variant-restricted PRS (e.g.
#                 only SNPs mapping to a candidate pathway's genes).
set -euo pipefail

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <gwas_ma_file> <ld_bfile_ref> <target_bfile> <output_prefix> [p_threshold] [clump_r2] [clump_kb] [extract_snps]"
    exit 1
fi

GWAS_MA=$1
LD_REF=$2
TARGET=$3
OUT_PREFIX=$4
P_THRESH=${5:-5e-8}
CLUMP_R2=${6:-0.1}
CLUMP_KB=${7:-250}
EXTRACT_SNPS=${8:-}

mkdir -p "$(dirname "${OUT_PREFIX}")"

echo "=========================================="
echo "Polygenic Risk Score (Clumping + Thresholding)"
echo "GWAS weights : $GWAS_MA"
echo "LD reference : $LD_REF"
echo "Target cohort: $TARGET"
echo "p<${P_THRESH}, r2<${CLUMP_R2}, ${CLUMP_KB}kb window"
echo "=========================================="

# 1. LD clumping -> independent index SNPs below the p-value threshold.
plink --bfile "${LD_REF}" \
      --clump "${GWAS_MA}" \
      --clump-snp-field SNP \
      --clump-field p \
      --clump-p1 "${P_THRESH}" \
      --clump-p2 "${P_THRESH}" \
      --clump-r2 "${CLUMP_R2}" \
      --clump-kb "${CLUMP_KB}" \
      --out "${OUT_PREFIX}_clump"

if [ ! -f "${OUT_PREFIX}_clump.clumped" ]; then
    echo "Error: no clumps formed -- no SNP passed p < ${P_THRESH} in the LD reference," \
         "or none of the GWAS SNP ids matched the reference .bim. Try a looser p_threshold" \
         "or confirm the .ma SNP ids use the same convention as the bfile." >&2
    exit 1
fi

# .clumped column 3 is the index SNP id.
awk 'NR>1 && $3 != "" {print $3}' "${OUT_PREFIX}_clump.clumped" > "${OUT_PREFIX}.valid.snp"

# Optional pathway/gene restriction: keep only clumped SNPs also in the supplied list.
if [ -n "${EXTRACT_SNPS}" ]; then
    if [ ! -f "${EXTRACT_SNPS}" ]; then
        echo "Error: extract_snps file not found: ${EXTRACT_SNPS}" >&2
        exit 1
    fi
    grep -Fxf "${EXTRACT_SNPS}" "${OUT_PREFIX}.valid.snp" > "${OUT_PREFIX}.valid.restricted.snp" || true
    mv "${OUT_PREFIX}.valid.restricted.snp" "${OUT_PREFIX}.valid.snp"
fi

N_SNP=$(wc -l < "${OUT_PREFIX}.valid.snp" | tr -d ' ')
if [ "${N_SNP}" -eq 0 ]; then
    echo "Error: no SNPs remained after clumping/restriction; nothing to score." >&2
    exit 1
fi

# 2. Weight file: SNP (col1), effect allele A1 (col2), beta b (col5) from the .ma.
awk 'NR>1 {print $1, $2, $5}' "${GWAS_MA}" > "${OUT_PREFIX}.weights.txt"

# 3. Score the target cohort on the clumped variant set.
plink --bfile "${TARGET}" \
      --extract "${OUT_PREFIX}.valid.snp" \
      --score "${OUT_PREFIX}.weights.txt" 1 2 3 \
      --out "${OUT_PREFIX}"

if [ ! -f "${OUT_PREFIX}.profile" ]; then
    echo "Error: PRS scoring failed; no ${OUT_PREFIX}.profile written. Check ${OUT_PREFIX}.log." >&2
    exit 1
fi

# .profile columns: FID IID PHENO CNT CNT2 SCORE  (SCORE is column 6).
awk 'NR>1 {s+=$6; ss+=$6*$6; n++} END {
        if (n>0) { m=s/n; sd=(n>1)?sqrt((ss-n*m*m)/(n-1)):0;
        printf "PRS_SUMMARY n_individuals=%d score_mean=%.6g score_sd=%.6g\n", n, m, sd } }' \
    "${OUT_PREFIX}.profile"
echo "PRS_SUMMARY n_snps=${N_SNP}"
echo "Per-individual scores written to: ${OUT_PREFIX}.profile"
