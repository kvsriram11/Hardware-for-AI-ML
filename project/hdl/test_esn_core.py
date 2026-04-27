"""
test_esn_core.py — cocotb testbench stub for esn_core.sv
Project : Hardware Accelerator for ESN (ECE 510, Spring 2026)
Author  : Venkata Sriram Kamarajugadda

Simulation harness goals (COPT Part B):
  - Drive synchronous active-high reset
  - Apply one representative MAC input (single neuron update)
  - Verify cycle_count increments and x_new_valid asserts after pipeline drain
  - Complex assertions deferred to M2 full testbench

Run (once cocotb + iverilog are installed):
    cd project/hdl
    make SIM=icarus TOPLEVEL_LANG=verilog \
         VERILOG_SOURCES=$(PWD)/esn_core.sv \
         TOPLEVEL=esn_core MODULE=test_esn_core
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles


# ---------------------------------------------------------------------------
# Helper: drive reset for N cycles
# ---------------------------------------------------------------------------
async def reset_dut(dut, cycles=2):
    dut.rst.value       = 1
    dut.w_valid.value   = 0
    dut.win_u_valid.value = 0
    dut.w_res.value     = 0
    dut.x_prev.value    = 0
    dut.win_u.value     = 0
    dut.leak_rate.value = 0x4000  # a ≈ 0.5 in Q15
    await ClockCycles(dut.clk, cycles)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


# ---------------------------------------------------------------------------
# Test 1: Basic reset + single MAC step
#
# Scenario (INT16/Q15):
#   x_prev  = 0x0100  (≈ 0.0078 in Q15)
#   w_res   = 0x0200  (≈ 0.0156 in Q15)
#   win_u   = 0x0400  (≈ 0.0313 in Q15)
#   Expected: mac_accum accumulates one product, then win_u added;
#             tanh stub saturates/passes through; x_new_valid goes high.
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_esn_core_basic(dut):
    """Reset DUT, drive one neuron's MAC inputs, check x_new_valid asserts."""

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # --- Reset ---
    await reset_dut(dut, cycles=3)

    dut._log.info("Reset complete. cycle_count=%s", dut.cycle_count.value)
    assert dut.cycle_count.value >= 3, "cycle_count did not increment during reset"
    assert int(dut.x_reg.value) == 0, "x_reg must be 0 after reset"   # type: ignore[attr-defined]

    # --- Apply one W_res * x_prev product ---
    dut.x_prev.value  = 0x0100   # representative reservoir state
    dut.w_res.value   = 0x0200   # representative weight
    dut.w_valid.value = 1
    await RisingEdge(dut.clk)
    dut.w_valid.value = 0

    dut._log.info("MAC cycle done. mac_accum (internal) should be non-zero.")

    # --- Inject win_u to complete pre-activation ---
    dut.win_u.value       = 0x0400
    dut.win_u_valid.value = 1
    await RisingEdge(dut.clk)
    dut.win_u_valid.value = 0

    # Allow pipeline to drain (tanh stage + blend stage = 2 more cycles)
    await ClockCycles(dut.clk, 2)

    dut._log.info("x_new=%s  x_new_valid=%s",
                  dut.x_new.value, dut.x_new_valid.value)

    assert dut.x_new_valid.value == 1, \
        "x_new_valid should assert after pipeline drain"

    dut._log.info("test_esn_core_basic PASSED")


# ---------------------------------------------------------------------------
# Test 2: Reset clears state mid-run
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_esn_core_reset_mid_run(dut):
    """Confirm synchronous reset zeroes x_reg even after partial computation."""

    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    await reset_dut(dut, cycles=2)

    # Drive some data
    dut.w_res.value   = 0x7FFF  # max positive weight
    dut.x_prev.value  = 0x7FFF  # max positive state
    dut.w_valid.value = 1
    await RisingEdge(dut.clk)
    dut.w_valid.value = 0

    # Assert reset immediately
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)

    assert int(dut.x_reg.value) == 0, \
        "Synchronous reset must zero x_reg regardless of in-flight data"

    dut._log.info("test_esn_core_reset_mid_run PASSED")
