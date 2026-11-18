#!/usr/bin/env bash
# Runs the whole verification stack and writes docs/day9_summary.md (indented blocks, no fences).
cd "$(dirname "$0")/.."
OUT=docs/day9_summary.md
ind() { sed 's/^/    /'; }
{
echo "# Day 9 verification summary ($(date -u +%Y-%m-%d))"
echo; echo "## Static checks"
./scripts/yosys_check.sh 2>&1 | tail -n 4 | ind
echo; echo "## Resource budget"
python3 scripts/synth_budget.py 2>&1 | ind
echo; echo "## Formal (SymbiYosys)"
( cd formal && sby -f gemm_dma.sby >/dev/null 2>&1 )
for t in prove bmc cover; do
  echo "$t: $(grep -h 'DONE (' formal/gemm_dma_$t/logfile.txt | tail -n 1)" | ind
done
echo "cover points reached: $(grep -c 'Reached cover statement' formal/gemm_dma_cover/logfile.txt)" | ind
echo; echo "## Unit tests"
./scripts/run_unit_tests.sh 2>&1 | grep -E "TESTS=|FAILED|ALL PASSED" | ind
echo; echo "## Mutation"
python3 scripts/mutation_check.py --lanes 4 >/dev/null 2>&1
tail -n 1 docs/day9_mutation.md | ind
echo; echo "## SoC log checks (recorded Day 6 logs)"
for L in 4 8 16; do python3 scripts/check_soc_log.py docs/day6_run_L$L.log --lanes $L | tail -n 1 | ind; done
} > "$OUT"
echo "wrote $OUT"
