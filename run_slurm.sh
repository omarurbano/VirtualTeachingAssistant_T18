#!/bin/bash
#SBATCH --job-name=synth_data_pipeline
#SBATCH --output=slurm_out/%x_%j.out
#SBATCH --error=slurm_out/%x_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64GB
#SBATCH --gres=gpu:1
#SBATCH --time=04:00:00
#SBATCH --partition=gpu

# ── Synthetic Data Generation Pipeline ─────────────────────────────────────────
# Run on NVIDIA GPU node. Requires: .env, credentials.json in working directory.
# Usage:
#   sbatch run_slurm.sh <drive_folder_id>
#   sbatch run_slurm.sh --local /path/to/course/files/
#   sbatch run_slurm.sh --seeds seeds.json --variants 5
# ────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

echo "=== SLURM Job ${SLURM_JOB_ID} started at $(date) ==="
echo "Node: $(hostname)"
echo "GPU:  ${CUDA_VISIBLE_DEVICES:-n/a}"

# Load Conda / module env if your cluster uses it (uncomment as needed):
# source /opt/conda/etc/profile.d/conda.sh
# conda activate synth-data

# Ensure output directory exists
mkdir -p slurm_out Synthetic_Data_Generation/output

# Run the pipeline
PIPELINE_ARGS=""
if [ $# -ge 1 ]; then
    PIPELINE_ARGS="$@"
fi

echo "Running: python Synthetic_Data_Generation/gen_data.py $PIPELINE_ARGS"
python Synthetic_Data_Generation/gen_data.py $PIPELINE_ARGS

echo "=== SLURM Job ${SLURM_JOB_ID} finished at $(date) ==="
