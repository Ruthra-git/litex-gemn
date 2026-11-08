#!/usr/bin/env bash

# Run LiteX simulation with a selectable firmware image.
set -e

cd "$(dirname "$0")/.."

source scripts/sim_args.sh

# Use Zephyr firmware if FW_BIN is supplied;
# otherwise fall back to the original bare-metal firmware.
FW_BIN="${FW_BIN:-build/gemm_fw.bin}"

# Convert relative path to absolute path.
if [[ "$FW_BIN" != /* ]]; then
    FW_BIN="$PWD/$FW_BIN"
fi

# Check that the firmware exists.
if [[ ! -f "$FW_BIN" ]]; then
    echo "ERROR: Firmware not found: $FW_BIN"
    exit 1
fi

echo "======================================"
echo "LiteX GEMM Simulation"
echo "Firmware: $FW_BIN"
echo "======================================"

python3 soc/gemm_sim.py $SIM_ARGS --ram-init="$FW_BIN" "$@"
