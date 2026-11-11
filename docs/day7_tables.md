| LANES | K steps | DMA cycles | transfers | stall cycles | bare-metal cycles (Day 6) |
|---|---|---|---|---|---|
| 4 | 1 | 89 | 24 | 41 | 74 |
| 4 | 4 | 206 | 48 | 71 | 188 |
| 4 | 8 | 358 | 80 | 107 | 340 |

| N | Zephyr naive | Zephyr blocked | Zephyr DMA poll | Zephyr DMA irq | bare-metal DMA poll | Zephyr/bare poll | irq extra per descriptor (Zephyr) | irq extra per descriptor (bare-metal) | match |
|---|---|---|---|---|---|---|---|---|---|
| 4 | 1123 | 414 | 1439 | 6502 | 712 | 2.02x | 5063 | 202 | yes |
| 8 | 7881 | 2269 | 2729 | 19855 | 1255 | 2.17x | 4281 | 160 | yes |
| 16 | 57673 | 16971 | 9459 | 73791 | 4446 | 2.13x | 4020 | 144 | yes |
| 32 | 450553 | 126034 | 46411 | 288660 | 25574 | 1.81x | 3785 | 141 | yes |
| 64 | 3730532 | 1054490 | 252262 | 1165869 | 177278 | 1.42x | 3568 | 136 | yes |

Per-tile offload (N=64, 256 descriptors)

| LANES | N | mode | cycles | background iterations | CPU available |
|---|---|---|---|---|---|
| 4 | 64 | poll | 248896 | 0 | 0% |
| 4 | 64 | irq | 1144346 | 0 | 0% |

Long descriptor offload (one descriptor)

| LANES | K steps | mode | cycles | background iterations | CPU available |
|---|---|---|---|---|---|
| 4 | 4000 | poll | 153722 | 0 | 0% |
| 4 | 4000 | irq | 155344 | 19396 | 90% |
