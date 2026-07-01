#!/bin/bash
# Usage: bash cojo.sh <gwas_ma_file> <plink_bfile_ref> <output_prefix> [orig_sig_csv] [phenotype]
#
# Runs GCTA-COJO to identify statistically independent signals within GWAS loci.
# If orig_sig_csv and phenotype are provided, also generates a Locus Map
# (maps each original genome-wide-significant hit to its nearest COJO-independent
# driver and computes LD between them).
#
# The GWAS .ma file must have columns: SNP, A1, A2, freq, b, se, p, N
# (produced by format_gwas_to_ma.py)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -lt 3 ]; then
    echo "Usage: $0 <gwas_ma_file> <plink_bfile_ref> <output_prefix> [orig_sig_csv] [phenotype]"
    exit 1
fi

GWAS_MA=$1
BFILE_REF=$2
OUT_PREFIX=$3
ORIG_SIG=${4:-}
PHENOTYPE=${5:-}

mkdir -p "$(dirname "${OUT_PREFIX}")"

echo "=========================================="
echo "Running GCTA-COJO"
echo "GWAS Data: $GWAS_MA"
echo "LD Reference: $BFILE_REF"
echo "Output Prefix: $OUT_PREFIX"
echo "=========================================="

gcta64 --bfile "${BFILE_REF}" \
       --cojo-file "${GWAS_MA}" \
       --cojo-slct \
       --out "${OUT_PREFIX}"

if [ ! -f "${OUT_PREFIX}.jma.cojo" ]; then
    echo "Error: COJO analysis failed (no independent signals, or all SNPs collinear). Check the log file: ${OUT_PREFIX}.log"
    exit 1
fi

echo "COJO analysis complete."
echo "Independent signals saved to: ${OUT_PREFIX}.jma.cojo"

# Optional Locus Map step
if [ -n "${ORIG_SIG}" ] && [ -n "${PHENOTYPE}" ]; then
    echo "=========================================="
    echo "Generating Locus Map"
    echo "Original Sig File: ${ORIG_SIG}"
    echo "Phenotype: ${PHENOTYPE}"

    TRAIT_CLEAN=$(echo "${PHENOTYPE}" | cut -d',' -f1 | sed 's/EUR//g')
    OUT_DIR=$(dirname "${OUT_PREFIX}")
    XLSX_OUT="${OUT_DIR}/COJO_${TRAIT_CLEAN}_Locus_Map.xlsx"

    python3 "${SCRIPT_DIR}/map_cojo_to_loci.py" \
        --cojo_jma "${OUT_PREFIX}.jma.cojo" \
        --original_sig "${ORIG_SIG}" \
        --phenotype "${PHENOTYPE}" \
        --bfile "${BFILE_REF}" \
        --output "${XLSX_OUT}"

    echo "Locus Map saved to: ${XLSX_OUT}"
fi
