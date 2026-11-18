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
