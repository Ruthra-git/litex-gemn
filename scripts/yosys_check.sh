#!/usr/bin/env bash
# Structural gate: elaboration, multiple drivers, combinational loops, latches.
set -e
cd "$(dirname "$0")/.."
mkdir -p build
for L in 4 8 16; do
  yosys -q -l build/yosys_check_L$L.log -p "read_verilog -sv rtl/gemm_core.v rtl/gemm_dma.v rtl/gemm_wb.v; chparam -set LANES $L gemm_wb; hierarchy -check -top gemm_wb; proc; opt_clean; check -assert"
  echo "LANES=$L: structural check passed"
done
if grep -l "Latch inferred" build/yosys_check_L*.log; then
  echo "FAIL: latch inferred (see files above)"; exit 1
fi
echo "STRUCTURAL OK"
