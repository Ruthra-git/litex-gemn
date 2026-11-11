# Day 7: Zephyr driver for the GEMM accelerator (LANES=4)

## Summary
- Zephyr (development snapshot, version string 4.4.99, SDK 1.0.1) boots on the simulated LiteX SoC. The accelerator is a devicetree node (litex,gemm-accel at 0x90000000, interrupt 2 via intc0, parent given explicitly) with a driver offering polled and interrupt-driven completion, cache maintenance and a mutex.
- All self-tests pass: known answers, 100 random tiles (poll and interrupt alternating), misaligned-descriptor error and recovery, exactly 10 interrupt events for 10 interrupt-mode descriptors and 0 in poll mode, coherency probe (16 stale words without flush, 0 after). Every benchmark method matches the reference at N = 4 to 64.
- Key finding: per-tile interrupt completion returns no CPU time to other threads (a 4x4-tile descriptor lasts about 660 cycles, shorter than an RTOS context switch round trip), but a single long descriptor (K=4000, about 155,000 cycles) in interrupt mode gives a background thread 90 percent of its solo rate versus 0 percent when polling.

## Results (run 2, final): cycles
N=4: naive 1123, blocked 414, DMA poll 1439, DMA irq 6502
N=8: 7881, 2269, 2729, 19855
N=16: 57673, 16971, 9459, 73791
N=32: 450553, 126034, 46411, 288660
N=64: 3730532, 1054490, 252262, 1165869
DMA poll beats blocked software from N=16 (1.79x) and is 14.78x faster than naive at N=64 (4.18x versus blocked). Zephyr DMA poll is 1.42x-2.17x slower than the Day 6 bare-metal driver (N=64: 252262 vs 177278 cycles).
DMA counters (hardware): K=1/4/8 = 89/206/358 cycles, 24/48/80 transfers, stall 41/71/107 (bare metal: 74/188/340).
Offload: per-tile N=64 poll 248896 cycles 0 percent, irq 1144346 cycles 0 percent; long descriptor K=4000 poll 153722 cycles 0 percent, irq 155344 cycles 90 percent (19396 background iterations).
Run 1 (earlier binary) is in docs/day7_raw_run1.csv.

## Findings
1. Interrupt completion in one long descriptor costs about 1600 cycles over polling; in the per-tile loop it costs about 3600-5100 cycles per descriptor (bare metal: about 136-202), so per-tile interrupts are impractical under an RTOS. A hardware loop over all tiles with one interrupt would fix the granularity.
2. The long-descriptor poll time fits the hardware model 51 + 38*K (152051 predicted, 153722 measured).
3. The CPU does not get 100 percent: the DMA and CPU share one bus (hypothesis, not tested).
4. Zephyr DMA poll costs more CPU time per descriptor than bare metal (about 330 cycles versus 48 at N=64, derived) and shows a small constant hardware stall offset; causes not isolated (candidates: semaphore reset in poll mode, call overhead, instruction-cache refills).
5. Build-to-build variation: functionally identical binaries with different code layout differ by up to about 12 percent at small N; treat differences below about 10 percent as noise.
6. Cache coherency is required in Zephyr as in bare metal; the driver flushes with the VexRiscv/LiteX instruction (encoding 0x500F, confirmed in the LiteX headers).

## Limitations
- Simulation only, one LANES value, one run per configuration; Zephyr is a development snapshot.
- The offload demo measures a synthetic background loop, not a real workload.
- The 4x4-tile benchmark reflects per-descriptor driver overhead; no descriptor chaining exists yet.
