#!/usr/bin/env bash
# Generate the SoC and its software headers/libs (no gateware compile), for firmware builds.
set -e
cd "$(dirname "$0")/.."
source scripts/sim_args.sh
python3 soc/gemm_sim.py $SIM_ARGS --no-compile-gateware
