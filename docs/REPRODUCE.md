# Reproducing the results

Environments are recorded in docs/ENVIRONMENT.md (WSL2 Ubuntu, Python venvs, tool versions).

## Tier 1: RTL only (about 15 minutes). No LiteX, no RISC-V toolchain.

Needs the OSS CAD Suite (Yosys, SymbiYosys, Boolector, Verilator, Icarus) and Python with cocotb 1.9.2,
numpy and pytest.

    source ~/oss-cad-suite/environment
    pip install cocotb==1.9.2 numpy pytest
    make static budget formal test

Expected: structural check OK, budget OK, three sby tasks PASS, "ALL PASSED" for 99 test runs.
Mutation check (about 6 minutes): `make mutate`; expected score at least 85 percent.

## Tier 2: simulated SoC, bare-metal firmware (needs LiteX venv and a RISC-V GCC)

    source ~/litex/venv/bin/activate
    GEMM_LANES=4 ./scripts/gen_soc.sh
    ./scripts/build_fw.sh day6_main.c
    python3 scripts/run_fw_sim.py --lanes 4 --out build/soc_L4.log
    python3 scripts/check_soc_log.py build/soc_L4.log --lanes 4

Repeat with 8 and 16. Expected N=64 DMA cycles: 177,278 / 144,510 / 128,126, within the checker's
tolerance of the cycle model. Recorded logs: docs/day6_run_L4.log, L8, L16.

## Tier 3: Zephyr driver (needs the Zephyr workspace and SDK)

From the Zephyr workspace with the SDK/toolchain installed:

```bash
cd ~/zephyrproject
source .venv/bin/activate

cd ~/litex-gemm
west build -p always \
  -b litex_vexriscv/litex_vexriscv \
  zephyr/app \
  -d build/zephyr_app


Expected: all self-tests PASS; N=64 cycles within about 12 percent of docs/day7_tables.md.

## Regenerating figures and tables

    python3 scripts/day10_figures.py
