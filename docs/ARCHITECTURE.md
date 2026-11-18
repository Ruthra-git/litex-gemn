# Architecture

## Blocks

- gemm_core: computes C = A*B (or C += A*B with the accumulate bit) for a 4x4x4 int8 tile with int32
  accumulation. LANES (4, 8 or 16) sets how many multiply-accumulates run per cycle, so the engine takes
  64/LANES + 1 cycles. v0.7 prefetches operands through small muxes with per-slot register enables.
- gemm_dma: a Wishbone bus master driven by one descriptor per 4x4 output tile. For each of the K steps
  it reads 8 words (4 of A, 4 of B), starts the core, waits for it, and accumulates. After the last step
  it writes 16 words of C. Transfers are back-to-back.
- gemm_wb: the Wishbone slave at 0x90000000. It holds the tile buffers (PIO path), the control and
  status registers, the DMA registers, the performance counters (DMA_CYCLES, DMA_XFERS, DMA_WAITS) and
  the interrupt logic. ID reads 0x47454D4D ("GEMM"); INFO carries register-interface version 6 and LANES.

## One DMA descriptor

1. Software writes the A, B and C base addresses, strides and K_TILES, then starts the DMA.
2. The DMA checks alignment and K; a bad descriptor is rejected with an error code and no bus traffic.
3. For each K step: read 4 words of A and 4 of B, clear or hold the accumulator, start the core, wait
   for done.
4. After K steps: write 16 words of C, set done (or an error code on bus error or the 1024-cycle timeout).

Error codes: 1 misaligned, 2 bus error, 3 timeout, 4 bad K.

## Timing model

Hardware time per tile = 36 + (engine + 21) * K cycles, with engine = 64/LANES + 1. For N=64 the DMA
total is 256 tiles times the per-tile time plus 12,414 cycles of CPU-side overhead. This is an empirical
fit to the performance counters; it reproduces every measured DMA value at LANES 4, 8 and 16 exactly.
It is a description of this simulated SoC, not a derivation from the RTL alone.

## Interrupts and coherency

- IRQ = IRQ_EN and (DMA done or DMA error, or core done when no DMA is running); SoC interrupt line 2.
- The data cache is write-back and the DMA does not snoop. After a DMA write the CPU must flush the
  data cache before reading C (measured: 16 stale words without a flush, 0 after; the flush costs
  137 cycles bare metal). The Zephyr driver does this with the LiteX flush instruction encoding.

## Software

- Bare metal (fw/): PIO, DMA with poll, DMA with interrupt, and software baselines (naive and
  register-blocked C), benchmarked from N=4 to 64.
- Zephyr (zephyr/): devicetree node litex,gemm-accel with interrupt-parent = <&intc0>, poll and
  interrupt completion, a semaphore and mutex, and cache handling in the driver.

## Why LANES=8 is the knee

Past a point the fixed DMA and bus time per K step dominates, so doubling lanes from 8 to 16 saves only
4 engine cycles of the 30-cycle K step while adding multipliers.

## Evolution

v0.3 added accumulate; v0.5 added the DMA; v0.6 added performance counters and back-to-back transfers;
v0.7 reworked the core datapath for area and clock with no change in cycle behaviour
(rtl/attic/gemm_core_v06.v is the rollback).
