#!/usr/bin/env bash
# Run the simulated SoC with a firmware image preloaded into main RAM.
# Usage: [FW_BIN=path/to/image.bin] scripts/run_sim.sh [extra litex_sim args]
set -e
cd "$(dirname "$0")/.."
source scripts/sim_args.sh
BIN="${FW_BIN:-build/gemm_fw.bin}"
python3 soc/gemm_sim.py $SIM_ARGS --ram-init="$BIN" "$@"
