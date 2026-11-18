export PYTEST_DISABLE_PLUGIN_AUTOLOAD = 1
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
LANES ?= 4
DUT ?= core
RTL_DIR ?= $(shell pwd)/../rtl
SUFFIX ?=

ifeq ($(DUT),core)
TOPLEVEL = gemm_core
MODULE   = test_gemm_core
else ifeq ($(DUT),wb)
TOPLEVEL = gemm_wb
MODULE   = test_gemm_wb
else
TOPLEVEL = gemm_wb
MODULE   = test_gemm_dma
endif

VERILOG_SOURCES = $(RTL_DIR)/gemm_core.v $(RTL_DIR)/gemm_dma.v $(RTL_DIR)/gemm_wb.v
COMPILE_ARGS += -P$(TOPLEVEL).LANES=$(LANES)
SIM_BUILD = sim_build_$(DUT)_L$(LANES)$(SUFFIX)
include $(shell cocotb-config --makefiles)/Makefile.sim
