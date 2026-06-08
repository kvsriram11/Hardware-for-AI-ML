# Cocotb Makefile for M2 testbenches.
# Run from tb/m2/:    make TOP=compute_core
#                or:  make TOP=interface_axi

SIM         ?= icarus
TOPLEVEL_LANG ?= verilog
TOP         ?= compute_core

# Precision parameters (override on cmdline)
DATA_W      ?= 16
MAC_WIDTH   ?= 16
ACC_W       ?= 40

RTL_DIR  := ../../rtl/m2
VERILOG_SOURCES := \
    $(RTL_DIR)/mac_array.sv \
    $(RTL_DIR)/tanh_pwl.sv \
    $(RTL_DIR)/leak_blend.sv \
    $(RTL_DIR)/compute_core.sv \
    $(RTL_DIR)/interface.sv

ifeq ($(TOP),compute_core)
    TOPLEVEL := compute_core
    MODULE   := test_compute_core
endif

ifeq ($(TOP),interface_axi)
    TOPLEVEL := interface_axi
    MODULE   := test_interface
endif

COMPILE_ARGS += -g2012
COMPILE_ARGS += -Pcompute_core.DATA_W=$(DATA_W)
COMPILE_ARGS += -Pcompute_core.MAC_WIDTH=$(MAC_WIDTH)
COMPILE_ARGS += -Pcompute_core.ACC_W=$(ACC_W)
COMPILE_ARGS += -Pinterface_axi.DATA_W=$(DATA_W)
COMPILE_ARGS += -Pinterface_axi.MAC_WIDTH=$(MAC_WIDTH)
COMPILE_ARGS += -Pinterface_axi.ACC_W=$(ACC_W)

export DATA_W
export MAC_WIDTH
export ACC_W

include $(shell cocotb-config --makefiles)/Makefile.sim
