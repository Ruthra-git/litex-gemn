# Build log

## Day 1
- Environment: WSL2 Ubuntu, LiteX in a venv, apt-installed riscv64-unknown-elf GCC 13.2.0.
- Issue: litex_setup.py --gcc=riscv tried apt without sudo and failed; toolchain was already installed, so no action needed.
- litex_sim booted to the BIOS prompt (litex> is the SoC BIOS, not a Linux shell).
- Golden model and tests written; spec v0.1 drafted.
- Next: Day 2, the MAC lane array and control FSM with a cocotb testbench.
## Day 2
- gemm_core.v written (LANES 4/8/16); cocotb regression on Icarus, 7 tests x 3 LANES.
- Chose Icarus over Verilator for cocotb (version support); Verilator used for lint only.
- Measured: cycles = 64/LANES + 1.
## Day 3
- Added accumulate to gemm_core; 9 core tests x 3 LANES pass.
- Registers live in the Wishbone window instead of LiteX CSRs (portable IP, cocotb-testable);
  trade-off: hand-written fw/gemm_regs.h instead of LiteX-generated docs.
- gemm_wb.v + 10 cocotb tests x 3 LANES pass.
- SoC: monkeypatched litex_sim.SimSoC (soc/gemm_sim.py); gemm at 0x90000000.
- BIOS smoke test transcript in docs/bios_smoke.txt.
- Issues/lint notes: <paste anything you hit>
- Next: Day 4, bare-metal firmware benchmark.

## Day 4
- Firmware built from LiteX demo scaffold; .bss moved to main RAM; memcmp replaced with a local word compare.
- PIO baseline passes (known answers, 200 random tiles, N=4..32) at LANES=4 and 16.
- Result: 4x4 tile 733 cycles vs 1100 naive and 485 unrolled C. Data movement is 96 percent of the tile time, so LANES has no visible effect.
- Open: load/read cost asymmetry and driver overhead not yet profiled; build an optimized PIO baseline first thing on Day 5.
- Next: Day 5, DMA master with cocotb bus-memory model.
