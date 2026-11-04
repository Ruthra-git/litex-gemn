# Day 4: programmed-I/O (PIO) baseline

## Setup
- CPU: VexRiscv in litex_sim. Settings found in soc.h: #define CONFIG_CPU_TYPE_VEXRISCV #define CONFIG_CPU_VARIANT_STANDARD 
- CPUFLAGS=-march=rv32i2p0_m     -mabi=ilp32 -D__vexriscv__
- 256 KB main RAM, 1 MHz simulated clock, cycle-accurate Verilator simulation with ideal memory.
- Timing: LiteX timer0 uptime counter; read overhead of 21 cycles subtracted from each measurement.
- Software baselines: a plain C triple loop ("naive") and a hand-unrolled 4x4 version ("unrolled"), compiled with LiteX's default firmware flags.
- PIO means the CPU copies every input word to the accelerator and reads every result word back itself.

## 4x4 tile, average cycles over 100 runs
| LANES | clear | load | start | wait | read | HW total | engine cycles | SW naive | SW unrolled |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 2 | 475 | 2 | 26 | 228 | 733 | 17 | 1100 | 485 |
| 8 | pending | | | | | | 9 (expected) | 1100 | 485 |
| 16 | 2 | 475 | 2 | 26 | 228 | 733 | 5 | 1100 | 485 |

Whole-tile speedup (SW cycles / HW total): 1.50x versus naive, 0.66x versus unrolled. The accelerator with PIO is slower than hand-unrolled software for a single tile.

## Matrix sizes (tiled, hardware accumulate over K)
| N | SW naive | HW PIO, LANES=4 | speedup | HW PIO, LANES=16 | speedup |
|---|---|---|---|---|---|
| 4 | 1110 | 883 | 1.25x | 871 | 1.27x |
| 8 | 7570 | 5263 | 1.43x | 5160 | 1.46x |
| 16 | 56675 | 39337 | 1.44x | 38509 | 1.47x |
| 32 | 439906 | 287568 | 1.52x | 280925 | 1.56x |

All hardware results matched the software reference exactly. Speedups are against the naive loop only; the unrolled version was timed only for 4x4.

## Findings
1. Correctness: known-answer tests, 200 random tiles and all four matrix sizes match the C reference.
2. Data movement dominates: 707 of 733 cycles per tile are clear, load, start and read. The engine computes in 17 cycles (2.3 percent) at LANES=4 and 5 cycles (0.7 percent) at LANES=16.
3. LANES has no visible effect under PIO: the tile total is identical at LANES=4 and 16.
4. PIO ceiling: with free compute, the tile time stays near 707 cycles, so the speedup versus naive cannot exceed about 1.56x, and it stays below 1x versus unrolled (about 0.69x).
5. Motivation for DMA and data reuse: the engine needs data delivered without CPU copies, and tiles that reuse data already inside the accelerator.

## Open items and limitations
- Load costs about 59 cycles per word written, but reads cost about 14 cycles per word. The difference is not yet explained. Suspected causes: index arithmetic, loads from stack memory, uncached store behavior. Not profiled.
- The N=4 matrix path (883 cycles) is slower than the tile path (733 cycles) for the same hardware operations, which suggests software overhead in the PIO driver. A tuned PIO baseline (unrolled, precomputed addresses) should be added before comparing against DMA.
- Wait is 26 cycles at both LANES values. A plausible reason is that two status polls (about 13 cycles each) is the minimum; not verified.
- Numbers come from simulation with ideal memory; real SDRAM or DDR latency would change absolute values.
- Timer reads add overhead; it is subtracted but not zero-error.

## Addendum (Day 5): superseded findings
The Day 4 tile-load path used memcpy, which in this libc is a real function call (about 8 calls per tile). After replacing it with an aligned load, the 4x4 load phase fell from 475 to 71 cycles and the tile total from 733 to 329. Superseded conclusions: "slower than unrolled software" (now 1.47x faster), "PIO ceiling about 1.56x" (corrected ceiling about 3.6x over naive), and the load/read asymmetry (explained). Corrected numbers are in docs/day5_results.md.
