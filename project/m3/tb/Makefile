# =============================================================================
# Makefile — M3 cocotb co-simulation for the integrated top module
#
# Project   : Hardware Accelerator for Reservoir State Update in ESNs
# Course    : ECE 510 — Hardware for AI/ML, Spring 2026
# Milestone : M3
#
# Usage (from project/m3/tb/):
#   make             # runs cosim, writes results.xml + dump.vcd
#   make clean
#
# Tools (Windows 11 + Git Bash):
#   Icarus Verilog 12.0   (C:\iverilog\bin\iverilog.exe)
#   Python   3.14.4       (C:\Python314\)
#   cocotb   2.0.1
#   cocotb-bus 0.3.0
#   GTKWave  3.3.100      (for viewing dump.vcd)
# =============================================================================

SIM            ?= icarus
TOPLEVEL_LANG  ?= verilog
TOPLEVEL       := top
MODULE         := test_top

# RTL sources — top + M2 wrapper + compute core + sub-modules
# Paths are relative to this Makefile (project/m3/tb/)
RTL_DIR_M3 := ../rtl
RTL_DIR_M2 := ../../m2/rtl

VERILOG_SOURCES += $(RTL_DIR_M3)/top.sv
VERILOG_SOURCES += $(RTL_DIR_M2)/interface.sv
VERILOG_SOURCES += $(RTL_DIR_M2)/compute_core.sv
VERILOG_SOURCES += $(RTL_DIR_M2)/q15_mac.sv
VERILOG_SOURCES += $(RTL_DIR_M2)/q15_tanh.sv
VERILOG_SOURCES += $(RTL_DIR_M2)/q15_blend.sv

# VCD waveform dumping is embedded inside top.sv under `ifdef COCOTB_SIM,
# per the official cocotb Icarus support pattern. No separate dump shim file
# is needed; synthesis (OpenLane) never sees the dump block.

# SystemVerilog support for Icarus
COMPILE_ARGS += -g2012

# Enable VCD waveform output (cocotb 2.0 Icarus mechanism injects cocotb_iverilog_dump.v)
WAVES = 1

# cocotb 2.0 — include Makefile.sim ONLY (Makefile.inc is deprecated)
include $(shell cocotb-config --makefiles)/Makefile.sim
