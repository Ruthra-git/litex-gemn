| N | Zephyr naive | Zephyr blocked | Zephyr DMA poll | Zephyr DMA irq | bare-metal DMA poll | Zephyr/bare DMA poll | match |
|---|---:|---:|---:|---:|---:|---:|---|
| 4 | 1202 | 415 | 1290 | 6848 | 712 | 1.81x | yes |
| 8 | 7857 | 2273 | 2889 | 22545 | 1255 | 2.30x | yes |
| 16 | 58273 | 16173 | 9815 | 83745 | 4446 | 2.21x | yes |
| 32 | 448471 | 128301 | 44723 | 328534 | 25574 | 1.75x | yes |
| 64 | 3721946 | 1054291 | 254680 | 1314939 | 177278 | 1.44x | yes |

| LANES | N | mode | DMA cycles | background iterations | CPU available (%) |
|---:|---:|---|---:|---:|---:|
| 4 | 64 | poll | 252228 | 0 | 0 |
| 4 | 64 | irq | 1291716 | 0 | 0 |
