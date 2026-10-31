SIM ?= icarus
TOPLEVEL_LANG ?= verilog
LANES ?= 4
DUT ?= core

ifeq ($(DUT),core)
TOPLEVEL = gemm_core
MODULE   = test_gemm_core
else
TOPLEVEL = gemm_wb
MODULE   = test_gemm_wb
endif

VERILOG_SOURCES = $(shell pwd)/../rtl/gemm_core.v $(shell pwd)/../rtl/gemm_wb.v
COMPILE_ARGS += -P$(TOPLEVEL).LANES=$(LANES)
SIM_BUILD = sim_build_$(DUT)_L$(LANES)
include $(shell cocotb-config --makefiles)/Makefile.sim
