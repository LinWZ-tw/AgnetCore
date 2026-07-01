#!/bin/bash
# Usage: bash run_mr_pipeline.sh <cojo_jma_file> <outcome_gwas_csv> <outcome_name> <output_dir> [conda_env]

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <cojo_jma_file> <outcome_gwas_csv> <outcome_name> <output_dir> [conda_env]"
    echo "Example: bash run_mr_pipeline.sh results/COJO/12_cojo.jma.cojo data/Outcome_GWAS.csv 'LipidLevels' results/MR"
    exit 1
fi

COJO_FILE=$1
OUTCOME_FILE=$2
OUTCOME_NAME=$3
OUT_DIR=$4
CONDA_ENV=${5:-finemap}

mkdir -p "${OUT_DIR}"
OUT_PREFIX="${OUT_DIR}/${OUTCOME_NAME}"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV}"

echo "Running Mendelian Randomization..."
echo "Exposure (Instruments): $COJO_FILE"
echo "Outcome Data: $OUTCOME_FILE"

Rscript "${SCRIPT_DIR}/two_sample_mr.R" "${COJO_FILE}" "${OUTCOME_FILE}" "${OUTCOME_NAME}" "${OUT_PREFIX}"
