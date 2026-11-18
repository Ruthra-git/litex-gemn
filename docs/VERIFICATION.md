## Results

### Unit tests
- Core: 9 tests × 3 LANES configurations = 27 executions.
- Wishbone: 10 tests × 3 LANES configurations = 30 executions.
- DMA: 14 tests × 3 LANES configurations = 42 executions.
- Total: 99/99 functional test cases passed, 0 reported test failures.
- Limitation: Icarus/Cocotb simulator process segfaulted after test summaries. Clean shutdown and XML result retention remain unresolved.

### Formal verification
- SymbiYosys prove: PASS.
- SymbiYosys BMC: PASS.
- SymbiYosys cover: PASS.
- Cover points reached: 10.
- Scope: bounded control-logic verification under the assumptions listed above.

### Mutation testing
- Initial reported result: 13/13 killed (100%), 0 survived, 0 invalid.
- Status: preliminary; mutation-result classification must be corrected to distinguish functional test failures from simulator crashes and missing XML results.
- The score must not yet be presented as a confirmed 100% mutation-detection result.

### Resource budget
| LANES | LUT4 | LUT budget | FF | FF budget | MULT18X18D | DSP budget | Status |
|---:|---:|---:|---:|---:|---:|---:|---|
| 4 | 9686 | 10700 | 1879 | 2000 | 4 | 4 | PASS |
| 8 | 9872 | 10900 | 1911 | 2050 | 8 | 8 | PASS |
| 16 | 10125 | 11200 | 1975 | 2100 | 16 | 16 | PASS |

All three configurations passed the reported resource budgets.

### SoC log checks
- LANES=4: 21/21 checks passed.
- LANES=8: 21/21 checks passed.
- LANES=16: 21/21 checks passed.
- Total: 63/63 checks passed against the recorded Day 6 firmware logs.
- Note: these results validate recorded logs; they do not independently demonstrate a fresh non-interactive CI SoC run.
