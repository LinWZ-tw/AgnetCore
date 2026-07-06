#!/bin/bash
# Usage: bash split_reference_by_chr.sh <plink_bfile_base> <chroms>
#   <chroms>: "1-22" | "1,2,19" | "19"
#
# One-time creation of per-chromosome PLINK bfiles (<base>_chr<N>) from a
# genome-wide panel, using plink2 (streams at low memory, unlike gcta64/plink1.9
# which load the whole panel into RAM). Idempotent: skips chromosomes whose
# output already exists. Used by cojo_by_chr.sh for memory-limited
# per-chromosome COJO; can also be run ahead of time to pre-warm the cache.

set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <plink_bfile_base> <chroms>   (chroms: '1-22' | '1,2,19' | '19')"
    exit 1
fi

BFILE_BASE=$1
CHROMS_SPEC=$2

expand_chroms() {
    local spec="$1"
    if [[ "$spec" == *-* ]]; then
        seq "${spec%-*}" "${spec#*-}"
    else
        echo "$spec" | tr ',' '\n'
    fi
}

for N in $(expand_chroms "$CHROMS_SPEC"); do
    out="${BFILE_BASE}_chr${N}"
    if [ -f "${out}.bed" ]; then
        echo "chr${N}: already exists, skipping."
        continue
    fi
    echo "=== Splitting chr${N} -> ${out} ==="
    plink2 --bfile "${BFILE_BASE}" --chr "${N}" --make-bed --out "${out}"
done

echo "Per-chromosome reference split complete."
