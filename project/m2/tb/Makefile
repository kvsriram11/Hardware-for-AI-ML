SIM           = icarus
TOPLEVEL_LANG = verilog
SIM_BUILD     = sim_build_q15_mac

VERILOG_SOURCES = $(PWD)/../rtl/q15_mac.sv
TOPLEVEL        = q15_mac
MODULE          = test_q15_mac

COMPILE_ARGS    = -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
