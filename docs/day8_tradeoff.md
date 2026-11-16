| LANES | COMB | FF | MULT | Fmax median (min-max) MHz | cycles per K step | DMA cycles N=64 | MAC/cycle | speedup vs blocked SW | speedup per 1000 COMB | MMAC/s at Fmax |
|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 10220 | 1879 | 4 | 60.0 (59.8-60.1) | 38.0 | 177278 | 1.48 | 5.77x | 0.56 | 89 |
| 8 | 10442 | 1911 | 8 | 60.0 (59.7-60.4) | 30.0 | 144510 | 1.81 | 7.08x | 0.68 | 109 |
| 16 | 10767 | 1975 | 16 | 57.5 (56.7-59.3) | 26.0 | 128126 | 2.05 | 7.98x | 0.74 | 118 |

Notes: resource and clock figures are Yosys + nextpnr-ecp5 estimates (accelerator only, out-of-context, seed medians). Cycles come from the simulated SoC (shared clock, ideal-ish memory). MMAC/s at Fmax is an accelerator-limited upper bound that ignores the CPU's own maximum clock.
