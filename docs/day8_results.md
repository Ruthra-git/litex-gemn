# Day 8: synthesis, timing and the speedup-versus-resources trade-off

## Summary
- Resource and clock estimates for the accelerator (gemm_wb: Wishbone slave, DMA master and GEMM core) at LANES = 4, 8, 16 with Yosys and nextpnr-ecp5 (Lattice ECP5, speed grade 6, out-of-context place and route, seeds 1-3, median over seeds).
- The first sweep (core v0.6) showed the datapath was far larger than the arithmetic needs: 15,771 / 19,744 / 33,355 logic cells with an estimated 31-37 MHz clock on the LFE5U-85F. LANES=16 did not fit the LFE5U-25F (about 137 percent of its 24,288 cells).
- Core v0.7 selects each output group's operands one cycle ahead with small constant-width multiplexers and writes results through per-slot register enables instead of variable part-selects on 128- and 512-bit vectors. Ports and cycle behavior are unchanged.
- Result on the LFE5U-25F: 10,220 / 10,442 / 10,767 logic cells (42-44 percent of the device), estimated clock 60.0 / 60.0 / 57.5 MHz, multiplier blocks 4 / 8 / 16 (equal to LANES). Compared with v0.6 on the 85F, logic is 1.5x / 1.9x / 3.1x smaller and the estimated clock 1.6x / 1.7x / 1.8x higher.
- On the simulated SoC the new core reproduces the Day 6 LANES=4 results exactly, and the LANES=8 and 16 results match the cycle model derived from the LANES=4 data to the cycle.

## Method
- Yosys synth_ecp5 with the top module gemm_wb and chparam LANES; nextpnr-ecp5 with --out-of-context, speed grade 6, package CABGA381, target 100 MHz (a placement-effort setting, so the timing_met column in the CSV files only means "below 100 MHz"), seeds 1, 2, 3.
- Scripts: scripts/synth_sweep.sh, day8_parse.py, day8_check.py, day8_compare.py, day8_tradeoff.py, day8_modules.py. Raw data in docs/day8_resources_*.csv, critical-path excerpts in docs/day8_critical_path_*.txt.
- Cycle counts: the Day 6 bare-metal firmware on the simulated LiteX SoC (docs/day6_run_L4.log, day6_run_L8.log, day6_run_L16.log).

## Results
Before and after, LFE5U-85F (median over 3 seeds):
LANES 4: logic 15,771 to 10,220 (0.65x), clock 37.1 to 59.2 MHz (1.60x), multipliers 4 and 4.
LANES 8: logic 19,744 to 10,442 (0.53x), clock 35.2 to 60.7 MHz (1.72x), multipliers 8 and 8.
LANES 16: logic 33,355 to 10,767 (0.32x), clock 30.8 to 55.9 MHz (1.82x), multipliers 16 and 16.
Core v0.7 on the LFE5U-25F: logic 10,220 / 10,442 / 10,767 (42.1 / 43.0 / 44.3 percent), flip-flops 1,879 / 1,911 / 1,975, clock 59.99 (59.8-60.1) / 59.96 (59.7-60.4) / 57.49 (56.7-59.3) MHz, no block RAM, no latches.

Trade-off (v0.7, N=64 matrix multiply on the simulated SoC):
LANES 4: 38 cycles per K step, DMA 177,278 cycles, 1.48 MAC per cycle, 5.77x faster than blocked software, 0.56 speedup per 1000 logic cells, about 89 MMAC/s at the estimated clock.
LANES 8: 30 cycles per K step, DMA 144,510 cycles, 1.81 MAC per cycle, 7.08x, 0.68 per 1000 cells, about 109 MMAC/s.
LANES 16: 26 cycles per K step, DMA 128,126 cycles, 2.05 MAC per cycle, 7.98x, 0.74 per 1000 cells, about 118 MMAC/s.
DMA counters (K=1, 4, 8): LANES 4: 74 / 188 / 340 cycles; LANES 8: 66 / 156 / 276; LANES 16: 62 / 140 / 244.

## Findings
1. Synthesis exposed an oversized datapath in v0.6. Replacing variable part-selects on wide vectors removed about 5,500 logic cells at LANES=4 and raised the estimated clock by 1.6x-1.8x. This supports, but did not directly isolate, a barrel-shifter explanation.
2. About 10,000 logic cells (roughly 95 percent of the LANES=4 total) do not scale with LANES; growth from LANES=4 to 16 is only 547 cells. Own-logic LUT4 per module at LANES=4 (hierarchical Yosys statistics): gemm_core 1391, gemm_dma 2391, gemm_wb 7631.
3. The multiplier blocks scale exactly with LANES and the flip-flop count grows by only 64 / 96 / 160 over the v0.6 count, as expected from the operand registers (the A-row register is shared across lanes).
4. Lane scaling is cheap in area but saturates in speed: hardware time per K step is the engine time (17, 9, 5 cycles) plus about 21 bus and control cycles that do not shrink. LANES 4 to 8 gives 22 percent more throughput for 2.2 percent more logic at the same clock; LANES 8 to 16 gives 8 percent more for 3.1 percent more logic and a 4 percent lower clock. On these measurements LANES=8 is the knee.
5. The next speedup lever is overlapping the next fetch with compute, not more lanes (roadmap, not implemented).
6. Estimated clocks of 57-60 MHz exceed a typical 50 MHz LiteX system clock.

## Limitations
- Estimates only: nextpnr out-of-context place and route, no hardware timing. In out-of-context mode the clock is not on a dedicated clock network, which can distort clock estimates.
- One device family and speed grade; three seeds (clock spread up to 4.4 percent on the 25F, up to 5 percent on the 85F).
- Accelerator only: the VexRiscv CPU's own maximum clock was not measured, so MMAC/s at the estimated clock is an upper bound.
- Cycle counts come from simulation with ideal main memory, one shared bus and a CPU that waits during DMA; the blocked-software baseline varied by up to 20 cycles (0.002 percent) between runs.
- v0.6 LANES=16 does not fit the 25F, so its before-and-after comparison uses the 85F.
- Verification: Unit tests (core 9, wb 10, dma 14 tests at LANES 4, 8 and 16, 99 runs): ALL PASSED. The LANES=4 SoC run is cycle-identical to Day 6.
