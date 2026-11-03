#!/usr/bin/env bash
# Run the simulated SoC with the firmware preloaded into main RAM.
set -e
cd "$(dirname "$0")/.."
source scripts/sim_args.sh
python3 soc/gemm_sim.py $SIM_ARGS --ram-init=build/gemm_fw.bin "$@"
