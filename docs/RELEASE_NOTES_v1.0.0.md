# v1.0.0

Complete int8 GEMM accelerator on a simulated LiteX/VexRiscv SoC.

Included: RTL (core v0.7, DMA v0.6, Wishbone wrapper with register-interface version 6), bare-metal
firmware, Zephyr driver, cocotb regression (99 runs), SymbiYosys properties on the DMA FSM, mutation
check, Yosys resource gate, ECP5 synthesis estimates, GitHub Actions CI.

Headline numbers (simulation, N=64): DMA 5.8x to 8.0x faster than register-blocked C and 20x to 28x faster
than naive C across LANES 4, 8, 16. Area and clock are tool estimates only.

Known limits are listed in the README. No FPGA hardware was used.
