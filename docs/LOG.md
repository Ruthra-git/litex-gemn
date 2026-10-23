# Build log

## Day 1
- Environment: WSL2 Ubuntu, LiteX in a venv, apt-installed riscv64-unknown-elf GCC 13.2.0.
- Issue: litex_setup.py --gcc=riscv tried apt without sudo and failed; toolchain was already installed, so no action needed.
- litex_sim booted to the BIOS prompt (litex> is the SoC BIOS, not a Linux shell).
- Golden model and tests written; spec v0.1 drafted.
- Next: Day 2, the MAC lane array and control FSM with a cocotb testbench.
