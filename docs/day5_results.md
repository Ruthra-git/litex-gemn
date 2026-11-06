# Day 5: DMA master, verification, corrected PIO baseline

## Summary
- Added a descriptor-driven DMA master (gemm_dma.v) to the Wishbone peripheral (gemm_wb.v v0.5): strided 4x4 tile fetch from main RAM, hardware K-loop with accumulate, one C write-back per output tile, error codes, timeout, interrupt.
- Verified with cocotb against a bus-memory model (configurable latency, bus-error and hang injection): 93 test runs pass (9 core + 10 wb + 12 dma, each at LANES 4, 8, 16), zero failures.
- Corrected the Day 4 PIO baseline: a libc memcpy call in the tile-load path inflated the load phase from 71 to 475 cycles.
- SoC-level DMA check passed: BIOS smoke test on the simulated LiteX SoC (identity matrix fetched from main RAM by the DMA, C = 1..16, status DONE, DMA_CYCLES = 185).

## Verification evidence
Suite counts: core 9, wb 10, dma 12 tests; all pass at LANES 4, 8 and 16. Two independent runs of the dma suite at LANES=4 gave identical simulated time (384340 ns) and cycle counts.
The dma suite covers: register readback; single tile; matrices 4, 8, 16, 32 against numpy with bus-traffic counts (8 reads per K step, 16 C writes per output tile); ACC_FIRST; alignment and parameter errors (no bus traffic on a bad descriptor); bus error on read and write; timeout; interrupt (masked during intermediate core completions); PIO writes ignored during DMA; memory-latency sweep; soft reset mid-transfer.
Known harmless log noise: a pytest plugin (launch_testing) fails to load; it only affects assertion message detail.

## DMA cycle behavior (RTL simulation, ideal memory, latency 1)
Measured cycles fit exactly: DMA cycles = 50 + K * (core_cycles + 27), core_cycles = 64/LANES + 1.
Per K step: LANES 4 = 44, LANES 8 = 36, LANES 16 = 32 cycles. About 27 of these are bus transfers and control that do not shrink with LANES, so LANES scaling saturates.
Each extra cycle of memory latency adds one cycle per bus transfer (8K + 16 transfers per tile).
Measured tile cycles (K = 1, 2, 4, 8): LANES 4: 94, 138, 226, 402. LANES 8: 86, 122, 194, 338. LANES 16: 82, 114, 178, 306.

## PIO re-measurement (firmware on the simulated SoC, LANES=4)
4x4 tile, cycles: clear 2, load 71 (was 475), start 2, wait 26, read 228, total 329 (was 733). SW naive 1101, SW unrolled 486. Speedup 3.34x vs naive, 1.47x vs unrolled (Day 4 reported 1.50x and 0.66x; superseded).
Matrix sizes (naive SW cycles, PIO fixed, PIO fast): N=4: 1111, 483, 360. N=8: 7577, 2038, 1615. N=16: 56694, 11537, 9705. N=32: 439963, 75610, 66248.
Best PIO speedup vs naive: 6.64x at N=32. All results matched the software reference.
Reading C back is 69 percent of the 4x4 tile time under PIO, which is what DMA write-back removes.

## Expectations for Day 6 (model-based projection, not a measurement)
Hardware-only DMA time for N=32 at LANES=4 would be 64 tiles x 402 = 25,728 cycles (latency 1), versus 66,248 for the best PIO, so at most about 2.6x better than PIO before CPU descriptor setup and real bus contention. These bounds will be replaced by measured values.

## Limitations and open items
- Simulation only, ideal memory with fixed latency; a real shared LiteX bus adds contention.
- Baseline fairness: unrolled SW was timed at 4x4 only; add a blocked/unrolled software baseline for larger N.
- Coverage gaps: no latency jitter or second bus master in cocotb; errors and timeouts injected at the first K step only; K up to 8; int32 accumulation wrap not tested.
- Cache coherency (CPU data cache flush around DMA) is firmware work for Day 6.


## First SoC measurement (BIOS smoke test, LANES=4)
- INFO read 04 04 05 00 (LANES 4, tile 4, version 5).
- Descriptor: A at 0x40020000 stride 4, B at 0x40020100 stride 4, C at 0x40020200 stride 16, K=1; A = 1..16, B = identity.
- Result: DMA_STATUS = 0x2 (done, no error); all 16 C words correct (1..16).
- DMA_CYCLES = 185 on the SoC versus 94 in the ideal-memory cocotb model (same tile).
- Derived (single data point, CPU idle): 24 bus transfers, so about 3.8 extra cycles per transfer, an effective memory latency of about 4.8 cycles instead of 1. Assumes the extra time is spread evenly over reads and writes; not verified separately.
- Revised projection (not a measurement): N=32 at LANES=4 is 80 transfers per tile, about 705 cycles per tile, about 45,100 cycles for 64 tiles, before CPU descriptor setup and polling. That is about 1.5x better than the best PIO (66,248) and about 9.8x better than naive software. The earlier ideal-memory estimate (about 2.6x versus best PIO) overstates the gain on this bus. The DMA also frees the CPU during these cycles, which a cycle comparison does not capture.
- Optimization candidates: pipelined or back-to-back bus requests, and prefetching the next K step while the core computes.

## Addendum (Day 6): superseded SoC latency estimate
The Day 5 BIOS smoke test measured 185 cycles for the K=1 tile with the v0.5 DMA, from which an effective bus latency of about 4.8 cycles per transfer and a projection of about 1.5x over the best PIO at N=32 were inferred. Day 6 measurements with the v0.6 DMA counters show an average stall of about 1.1 cycles per transfer (K=1: 74 cycles, 24 transfers, 26 stall cycles), and DMA cycles on the SoC fit 36 + 38*K at LANES=4. The Day 5 estimate came from a different context (BIOS prompt, v0.5 RTL) and is superseded; the projection above should be disregarded.
