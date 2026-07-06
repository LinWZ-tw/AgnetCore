#!/bin/bash
# Usage: bash cojo_by_chr.sh <gwas_ma_file> <plink_bfile_base> <output_prefix> <chroms> [orig_sig_csv] [phenotype]
#   <chroms>: "1-22" | "1,2,19" | "19"
#
# Per-chromosome GCTA-COJO for memory-limited hosts. gcta64 loads the WHOLE
# --bfile panel into RAM regardless of how few SNPs the .ma has, so a
# genome-wide all-variants panel (~75M SNPs) OOMs on <=15GB machines, and
# gcta64 --chr does NOT help (it still loads the full panel before filtering).
# Instead we run COJO one chromosome at a time against per-chromosome reference
# bfiles (<plink_bfile_base>_chr<N>, created on demand with plink2 and cached),
# then concatenate the per-chr .jma.cojo into <output_prefix>.jma.cojo.
#
# This is statistically IDENTICAL to a genome-wide run: COJO never conditions
# across chromosomes, so the union of per-chromosome independent signals equals
# the genome-wide result. Peak RAM is ~one chromosome's worth of the panel.
#
# The GWAS .ma must have columns: SNP A1 A2 freq b se p N (format_gwas_to_ma.py).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <gwas_ma_file> <plink_bfile_base> <output_prefix> <chroms> [orig_sig_csv] [phenotype]"
    exit 1
fi

GWAS_MA=$1
BFILE_BASE=$2
OUT_PREFIX=$3
CHROMS_SPEC=$4
ORIG_SIG=${5:-}
PHENOTYPE=${6:-}

mkdir -p "$(dirname "${OUT_PREFIX}")"

expand_chroms() {
    local spec="$1"
    if [[ "$spec" == *-* ]]; then
        seq "${spec%-*}" "${spec#*-}"
    else
        echo "$spec" | tr ',' '\n'
    fi
}

echo "=========================================="
echo "Per-chromosome GCTA-COJO"
echo "GWAS Data:     $GWAS_MA"
echo "Base panel:    $BFILE_BASE"
echo "Chromosomes:   $CHROMS_SPEC"
echo "Output Prefix: $OUT_PREFIX"
echo "=========================================="

produced=()
for N in $(expand_chroms "$CHROMS_SPEC"); do
    chr_bfile="${BFILE_BASE}_chr${N}"

    # Lazily create the per-chromosome reference (cached next to the base panel).
    if [ ! -f "${chr_bfile}.bed" ]; then
        echo "--- Splitting reference chr${N} (one-time) -> ${chr_bfile} ---"
        if ! plink2 --bfile "${BFILE_BASE}" --chr "${N}" --make-bed --out "${chr_bfile}" >/dev/null 2>&1; then
            echo "Warning: plink2 split failed for chr${N}; skipping."
            continue
        fi
    fi
    if [ ! -f "${chr_bfile}.bed" ]; then
        echo "Warning: no reference bfile for chr${N}; skipping."
        continue
    fi

    echo "--- COJO chr${N} ---"
    chr_out="${OUT_PREFIX}_chr${N}"
    # A chromosome with no genome-wide-significant signal produces no .jma.cojo
    # (and gcta may exit non-zero) -- must not abort the whole loop.
    gcta64 --bfile "${chr_bfile}" \
           --cojo-file "${GWAS_MA}" \
           --cojo-slct \
           --out "${chr_out}" || true

    if [ -f "${chr_out}.jma.cojo" ]; then
        produced+=("${chr_out}.jma.cojo")
        echo "chr${N}: independent signal(s) found."
    else
        echo "chr${N}: no independent signals."
    fi
done

if [ "${#produced[@]}" -eq 0 ]; then
    echo "Error: COJO selected no independent signals on any requested chromosome."
    exit 1
fi

echo "=== Concatenating ${#produced[@]} per-chr result(s) -> ${OUT_PREFIX}.jma.cojo ==="
awk 'FNR==1 && NR!=1 {next} {print}' "${produced[@]}" > "${OUT_PREFIX}.jma.cojo"
echo "Combined independent signals: $(( $(wc -l < "${OUT_PREFIX}.jma.cojo") - 1 ))"

# Optional Locus Map -- uses the FULL base panel (.bim scan + pairwise plink
# --ld are both low-memory, so no per-chr split needed here).
if [ -n "${ORIG_SIG}" ] && [ -n "${PHENOTYPE}" ]; then
    echo "=========================================="
    echo "Generating Locus Map"
    TRAIT_CLEAN=$(echo "${PHENOTYPE}" | cut -d',' -f1 | sed 's/EUR//g')
    OUT_DIR=$(dirname "${OUT_PREFIX}")
    XLSX_OUT="${OUT_DIR}/COJO_${TRAIT_CLEAN}_Locus_Map.xlsx"

    python3 "${SCRIPT_DIR}/map_cojo_to_loci.py" \
        --cojo_jma "${OUT_PREFIX}.jma.cojo" \
        --original_sig "${ORIG_SIG}" \
        --phenotype "${PHENOTYPE}" \
        --bfile "${BFILE_BASE}" \
        --output "${XLSX_OUT}"

    echo "Locus Map saved to: ${XLSX_OUT}"
fi

echo "Per-chromosome COJO complete."
