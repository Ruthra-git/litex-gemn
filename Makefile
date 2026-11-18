.RECIPEPREFIX = >
LANES_LIST ?= 4 8 16
.PHONY: all static formal budget test mutate soc-check summary

all: static budget formal test mutate soc-check

static:
> verilator --lint-only -Wall -Wno-fatal rtl/gemm_core.v rtl/gemm_dma.v rtl/gemm_wb.v --top-module gemm_wb
> ./scripts/yosys_check.sh

formal:
> cd formal && sby -f gemm_dma.sby

budget:
> python3 scripts/synth_budget.py

test: vectors
> LANES_LIST="$(LANES_LIST)" ./scripts/run_unit_tests.sh

mutate:
> python3 scripts/mutation_check.py --lanes 4

soc-check:
> for L in 4 8 16; do python3 scripts/check_soc_log.py docs/day6_run_L$$L.log --lanes $$L || exit 1; done

summary:
> ./scripts/day9_collect.sh
.RECIPEPREFIX = >
LANES_LIST ?= 4 8 16
.PHONY: all static formal budget test mutate soc-check summary

all: static budget formal test mutate soc-check

static:
> verilator --lint-only -Wall -Wno-fatal rtl/gemm_core.v rtl/gemm_dma.v rtl/gemm_wb.v --top-module gemm_wb
> ./scripts/yosys_check.sh

formal:
> cd formal && sby -f gemm_dma.sby

budget:
> python3 scripts/synth_budget.py

test: vectors
> LANES_LIST="$(LANES_LIST)" ./scripts/run_unit_tests.sh

mutate:
> python3 scripts/mutation_check.py --lanes 4

soc-check:
> for L in 4 8 16; do python3 scripts/check_soc_log.py docs/day6_run_L$$L.log --lanes $$L || exit 1; done

summary:
> ./scripts/day9_collect.sh

vectors:
> python3 model/gemm_golden.py
