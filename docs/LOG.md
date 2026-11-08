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

## Day 5
- PIO baseline corrected: memcpy in ld32 was a real call. 4x4 load 475 -> 71 cycles, total 733 -> 329; PIO now 3.34x vs naive and 1.47x vs unrolled SW.
- gemm_dma.v: strided tile fetch, hardware K-loop with accumulate, single C write-back, error codes, timeout, IRQ.
- cocotb: bus-memory model; 93 test runs pass (9 core + 10 wb + 12 dma at LANES 4/8/16). DMA cycles fit 50 + K*(core+27) exactly.
- SoC BIOS smoke test passed: identity matrix via DMA from main RAM; DMA_CYCLES 185 on the SoC vs 94 ideal, so effective bus latency is about 4.8 cycles/transfer.
- Open: cache flush handling and IRQ on the SoC (Day 6); LANES=8/16 firmware runs; blocked/unrolled SW baseline for larger N.
- Day 6 first firmware run: DMA known-answer and error-path tests pass; xfers 24/48/80; DMA cycles 74/188/340 (36 + 38*K); average stall 1.08-1.11; coherency probe: 16 stale words without flush, 0 after.
- Failures found: IRQ wait timed out (CPU pending register is probably masked; mask was 0) and IRQ-mode benchmark cells were timeouts; combined match flag hid per-method results; CPU-side baselines slower than Day 5 (suspected cache conflicts from array layout).
- Fixes in day6_main.c v2: own ISR with event counter, per-method match flags, skewed buffer pool, flush-cost measurement.

## Day 6 (complete)
- v2 firmware passes on the SoC: all self-checks pass, all five methods match at N=4..64. N=64: DMA 177278 cycles vs PIO 521745, blocked SW 1023084, naive SW 3629589.
- IRQ failure root cause: the CPU pending register is masked (mask was 0); fixed with a firmware ISR that counts events and masks the level line. Build uses -Wl,--allow-multiple-definition because libbase also defines isr.
- CPU-side slowdown root cause (consistent with): buffers a multiple of the cache size apart; fixed by a skewed pool layout.
- Findings: DMA useless at 4x4, crossover between N=4 and 8; interrupt completion costs about 140 cycles per descriptor; flush 137 cycles; engine utilization about 39 percent at N=64.
- Open: v0.6 unit-test summary; LANES 8/16 firmware runs; overlap of fetch and compute; Day 7 driver.
# Day 7 Completion Summary

## Completed
- Zephyr application successfully built for LiteX VexRiscV.
- Zephyr firmware successfully booted in LiteX simulation.
- GEMM accelerator initialization and known-answer tests passed.
- 100 randomized GEMM tile tests passed.
- DMA polling and interrupt-mode tests passed.
- DMA error handling and recovery passed.
- Interrupt event-count validation passed.
- Cache-coherency probe passed.
- DMA performance counters collected.
- Matrix multiplication benchmarks completed for N=4, 8, 16, 32 and 64.
- Software and accelerator output comparisons passed.
- Final simulation reported RESULT: PASS.

## Performance observations
- DMA achieved 14.61x speedup over naive software at N=64.
- DMA achieved 4.13x speedup over blocked software at N=64.
- DMA setup overhead affected smaller workloads.
- Interrupt-mode execution was slower than polling in the measured run.

## Final status
Day 7 functional integration and validation successfully completed.
Performance optimization and comparative analysis remain open.
EOF
