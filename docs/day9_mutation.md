# Mutation check (LANES=4)

| Mutant | Injected bug | Result | Caught by | Time (s) |
|---|---|---|---|---|
| dma_a_step | A pointer advances 8 bytes per K step instead of 4 | KILLED | dma | 47.2 |
| dma_b_step | B pointer advances 8 rows per K step instead of 4 | KILLED | dma | 43.0 |
| dma_no_acc | later K steps do not accumulate | KILLED | dma | 45.4 |
| dma_cstr_chk | C stride alignment check removed | KILLED | dma | 55.4 |
| dma_cwords | C write-back stops one word early | KILLED | dma | 44.9 |
| core_acc_mode | accumulate request ignored | KILLED | core | 16.5 |
| core_done_early | DONE one cycle early | KILLED | core | 11.0 |
| core_cycles | cycle counter starts at 0 | KILLED | core | 15.6 |
| core_sign | dot product subtracted | KILLED | core | 11.1 |
| core_bytes | A byte lane 1 taken from lane 2 | KILLED | core | 11.1 |
| wb_irq | core DONE raises the interrupt during a DMA | KILLED | dma | 55.7 |
| wb_dma_start | DMA start bit moved | KILLED | dma | 75.8 |
| wb_version | INFO version changed | KILLED | wb | 31.0 |

Score: 13/13 killed (100%), 0 survived, 0 invalid
