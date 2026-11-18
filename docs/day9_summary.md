# Day 9 verification summary (2026-11-18)

## Static checks
    LANES=4: structural check passed
    LANES=8: structural check passed
    LANES=16: structural check passed
    STRUCTURAL OK

## Resource budget
    | LANES | LUT4 | budget | Day 8 baseline | FF | budget | MULT18X18D | budget | status |
    |---|---|---|---|---|---|---|---|---|
    | 4 | 9686 | 10700 | 9686 | 1879 | 2000 | 4 | 4 | ok |
    | 8 | 9872 | 10900 | 9872 | 1911 | 2050 | 8 | 8 | ok |
    | 16 | 10125 | 11200 | 10125 | 1975 | 2100 | 16 | 16 | ok |
    BUDGET OK

## Formal (SymbiYosys)
    prove: SBY  6:49:23 [gemm_dma_prove] DONE (PASS, rc=0)
    bmc: SBY  6:55:20 [gemm_dma_bmc] DONE (PASS, rc=0)
    cover: SBY  6:49:35 [gemm_dma_cover] DONE (PASS, rc=0)
    cover points reached: 10

## Unit tests

## Mutation
    Score: 13/13 killed (100%), 0 survived, 0 invalid

## SoC log checks (recorded Day 6 logs)
    SOC CHECK OK (21/21 checks) LANES=4
    SOC CHECK OK (21/21 checks) LANES=8
    SOC CHECK OK (21/21 checks) LANES=16
