# litex-gemm: an int8 GEMM accelerator on a LiteX / VexRiscv RISC-V SoC

![ci](https://github.com/Ruthra-git/litex-gemm/actions/workflows/ci.yml/badge.svg)

A custom int8 matrix-multiply accelerator (4x4x4 tile, int32 accumulate, 4/8/16 MAC lanes) with a
descriptor-driven Wishbone DMA master, integrated into a simulated LiteX SoC with a VexRiscv core.
It comes with bare-metal firmware, a Zephyr driver, a cocotb regression, formal properties on the
DMA state machine, a mutation check of the tests, synthesis estimates for Lattice ECP5, and CI.

**Everything here is simulation or synthesis estimation. There is no FPGA board in this project:
no timing closure on hardware and no silicon measurements.**

## Results

<!-- RESULTS-BEGIN -->

Cycle counts below are from the cycle-accurate simulated SoC (bare-metal firmware, N = 64). Area and clock are Yosys + nextpnr-ecp5 estimates, not silicon measurements.

| LANES | DMA cycles (N=64) | MAC/cycle | vs register-blocked C | vs naive C |
|---|---|---|---|---|
| 4 | 177,278 | 1.48 | 5.77x | 20.5x |
| 8 | 144,510 | 1.81 | 7.08x | 25.1x |
| 16 | 128,126 | 2.05 | 7.98x | 28.3x |

| LANES | logic cells (LFE5U-25F) | FF | MULT18X18D | est. clock (MHz) | est. MMAC/s |
|---|---|---|---|---|---|
| 4 | 10,220 | 1,879 | 4 | 60.0 | 89 |
| 8 | 10,442 | 1,911 | 8 | 60.0 | 109 |
| 16 | 10,767 | 1,975 | 16 | 57.5 | 118 |

| Zephyr driver, LANES=4, N=64 | cycles |
|---|---|
| naive C | 3,730,532 |
| register-blocked C | 1,054,490 |
| DMA, poll completion | 252,262 |
| DMA, interrupt completion | 1,165,869 |

<!-- RESULTS-END -->

Figures: [Zephyr cycles vs N](docs/figures/fig1_zephyr_cycles.png),
[lanes vs speedup and throughput](docs/figures/fig2_lanes.png),
[v0.6 vs v0.7 datapath](docs/figures/fig3_v06_vs_v07.png).
Raw data: [docs/data/results.json](docs/data/results.json).

What the numbers say:

- At 64x64 the DMA path is 5.8x to 8.0x faster than register-blocked C and 20x to 28x faster than
  naive C, depending on LANES. LANES=8 is the knee: LANES=16 adds only about 13 percent more speed for
  about 3 percent more logic, because the fixed DMA and bus cost dominates.
- At 4x4 the accelerator loses to register-blocked C (712 vs 412 cycles). The crossover is between
  N=4 and N=8, so tiny matrices should stay in software.
- Interrupt completion costs more than polling for per-tile descriptors. It pays off only for long
  descriptors: with K=4000 it frees about 90 percent of the CPU.
- The v0.7 datapath (operand prefetch with small muxes) cut logic by 35 percent at LANES=4 and
  raised the estimated clock by about 1.6x compared with v0.6, with identical cycle behaviour.

## Architecture

    VexRiscv CPU (ibus, dbus) --+
                                +--> shared Wishbone interconnect (round-robin, 3 masters, 5 slaves)
    gemm_dma (bus master)  -----+            |
                                             +--> gemm_wb @ 0x90000000: registers, tile buffers, IRQ
                                                    +-- gemm_dma: descriptor, K loop, 8 reads/K + 16 writes/tile
                                                    +-- gemm_core: 4x4x4 int8 tile, LANES MACs per cycle

One descriptor computes one 4x4 output tile over K tiles in hardware. Details, the cycle model and
the register map are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SPEC.md](docs/SPEC.md).

## Verification

- cocotb: 99 test runs (core 9, wb 10, dma 14, at LANES 4, 8 and 16) against a NumPy golden model.
- Formal (SymbiYosys): 11 properties on the DMA FSM (bounded: TIMEOUT=2, K<=1; K<=2 for cover).
- Mutation check: 13/13 mutants reported killed (preliminary; classification remains under review due to simulator shutdown/XML-retention issues).
  in [docs/VERIFICATION.md](docs/VERIFICATION.md).
- SoC firmware regression with a log checker against the cycle model at LANES 4, 8 and 16.
- Yosys resource budget gate and structural check in CI.

Requirement-to-evidence mapping and the list of things not verified: [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Reproduce

Three tiers, from lightest to heaviest, in [docs/REPRODUCE.md](docs/REPRODUCE.md). Tier 1 needs only
the OSS CAD Suite and Python, and runs with: `make static budget formal test`

## Limits

- Cycle counts come from a simulated SoC with a shared bus and simulated memory. Real DRAM latency
  would change the absolute numbers and the crossover points.
- Clock and area are nextpnr and Yosys estimates from out-of-context runs. Treat them as relative
  comparisons between lanes and core versions, not as achievable Fmax.
- The Zephyr tree is a development snapshot (4.4.99). Zephyr is 1.4x to 2.2x slower than bare metal on
  the DMA path, from per-descriptor driver overhead that I did not isolate.
- Build-to-build cycle variation reached about 12 percent at small N; large-N figures are stable.
- Formal covers the DMA control logic only, with bounded parameters. gemm_core and gemm_wb rely on
  simulation and mutation testing.
- About 10,000 logic cells do not scale with LANES. The module-level attribution is in
  [docs/day8_results.md](docs/day8_results.md).

## Repository layout

    rtl/       gemm_core.v (v0.7), gemm_dma.v, gemm_wb.v, attic/ (superseded files)
    tb/        cocotb suites and Wishbone memory model
    formal/    SymbiYosys config and DMA properties
    model/     NumPy golden model
    soc/       LiteX wrapper and simulated SoC
    fw/        bare-metal firmware and register header
    zephyr/    Zephyr driver, devicetree binding, demo app
    scripts/   build, run, synthesis, check and release scripts
    docs/      spec, log, results, verification, figures
    ci/        resource budget

## License

MIT. See [LICENSE](LICENSE).
