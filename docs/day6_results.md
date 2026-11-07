# Day 6: DMA driver, interrupt completion, benchmarks to 64x64 (LANES=4)

## Summary
- Firmware drives the v0.6 DMA (one descriptor per 4x4 output tile, hardware K loop) and was verified against a C reference at N = 4, 8, 16, 32, 64 for five methods: naive software, register-blocked software, optimized PIO, DMA with polling, DMA with interrupt completion. All methods match at all sizes.
- Self-checks pass: DMA known answers, 100 random tiles (poll and interrupt alternating), misaligned-descriptor error path, interrupt delivery (exactly one interrupt per completion).
- Measured on the simulated SoC (cycle-accurate simulation): at N=64 DMA is 20.5x faster than naive software, 5.8x faster than blocked software and 2.9x faster than PIO.

## DMA hardware behavior on the SoC
Counters (v0.6): K=1: 74 cycles, 24 transfers, 26 stall cycles; K=4: 188, 48, 53; K=8: 340, 80, 89. Cycles fit 36 + 38*K exactly. Average stall 1.08-1.11 cycles per transfer (ideal 1.0), so bus contention from the CPU is small while it polls.

## Benchmark results (cycles)
N=4: naive 1120, blocked 412, PIO 482, DMA 712, DMA+IRQ 914
N=8: 7596, 2248, 1751, 1255, 1896
N=16: 56746, 16069, 9490, 4446, 6755
N=32: 440205, 123172, 63566, 25574, 34637
N=64: 3629589, 1023084, 521745, 177278, 212197
DMA vs PIO: 0.68x, 1.40x, 2.13x, 2.49x, 2.94x for N = 4, 8, 16, 32, 64. DMA vs blocked: 0.57x, 1.79x, 3.61x, 4.81x, 5.77x.
At N=64: 1.48 MAC/cycle for DMA versus 0.26 (blocked) and 0.07 (naive); the engine peak at LANES=4 is 3.76, so utilization is about 39 percent.

## Findings
1. The accelerator does not pay off at 4x4: blocked software is faster (412 vs 482 PIO vs 712 DMA). The crossover is between N=4 and N=8. The N=4 row is also noisy (fast PIO measured 360 in the Day 5 firmware).
2. DMA's advantage grows with size because one descriptor covers a whole K loop and C is written back once per output tile.
3. At large N the DMA path is mostly hardware time (hardware model about 93 percent of the measured time at N=64); CPU-side overhead is about 45-55 cycles per descriptor plus a fixed cost per call. A data-cache flush costs 137 cycles and each call flushes twice.
4. Interrupt completion costs about 135-160 cycles more per descriptor than polling (ISR entry/exit). It benefits only when the CPU has useful work to overlap, which this benchmark does not model.
5. Cache coherency is mandatory: after a DMA write the CPU data cache returned 16 of 16 stale words until flushed.
6. Benchmark sensitivity to data layout: placing the matrices at addresses a multiple of the cache size apart made CPU-side timings about 2.2x slower at N=4 (naive 2435 vs 1120 cycles). Buffers are now placed at skewed offsets. The cache geometry was not verified; the cause is consistent with, not proven to be, cache conflicts.

## Limitations
- Simulation only (cycle-accurate Verilator, ideal main memory), single LANES value on the SoC (4); LANES 8 and 16 have been measured in cocotb only.
- The CPU waits during DMA; the offload benefit is not measured.
- Software baselines are one reasonable C kernel each (naive and 2x4 register-blocked), not tuned for this CPU.
- Engine utilization is limited by bus transfers; overlapping fetch and compute and pipelined bus requests are not implemented.
- The firmware overrides the library interrupt handler (link flag allow-multiple-definition); it handles the UART and the accelerator only.
