SIM ?= icarus
TOPLEVEL_LANG ?= verilog
LANES ?= 4
TOPLEVEL = gemm_core
MODULE = test_gemm_core
VERILOG_SOURCES = $(shell pwd)/../rtl/gemm_core.v
COMPILE_ARGS += -P$(TOPLEVEL).LANES=$(LANES)
SIM_BUILD = sim_build_L$(LANES)
include $(shell cocotb-config --makefiles)/Makefile.sim
