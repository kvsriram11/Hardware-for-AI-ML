"""
test_q15_mac.py — cocotb testbench for q15_mac.sv

Project   : Hardware Accelerator for Reservoir State Update in ESNs
Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
Author    : Venkata Sriram Kamarajugadda
Milestone : M2

Strategy
--------
We test q15_mac as the computational core of a 1000-element dot product.
A NumPy golden model performs the exact same Q15 fixed-point arithmetic
the hardware does (signed 16-bit operands, signed 32-bit accumulator,
two's-complement wrap on overflow), and we compare cycle-by-cycle.

Tests
-----
  test_reset            : Reset clears the accumulator from a non-zero state.
  test_single_mac       : One known product matches Python.
  test_dot_product_50   : A 50-deep dot product over realistic Q15 reservoir
                          values matches Python every cycle.
  test_clr_priority     : 'clr' overrides 'en' on the same cycle.

Run
---
    cd project/m2/tb
    make
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


# -----------------------------------------------------------------------------
# Q15 helpers (Python-side golden model)
# -----------------------------------------------------------------------------

Q15_ONE      =  1 << 15
Q15_MAX      =  (1 << 15) - 1     # +32767  ≈ +0.99997
Q15_MIN      = -(1 << 15)         # -32768  ≈ -1.00000
ACC_MAX      =  (1 << 31) - 1
ACC_MIN      = -(1 << 31)
ACC_MOD      =  1 << 32           # for two's-complement wrap


def to_q15(real):
    """Convert a Python float in [-1, 1) to a signed Q15 integer."""
    v = int(round(real * Q15_ONE))
    if v > Q15_MAX:
        v = Q15_MAX
    if v < Q15_MIN:
        v = Q15_MIN
    return v


def acc_wrap(value):
    """Wrap an integer to signed 32-bit, matching SystemVerilog semantics."""
    value &= (ACC_MOD - 1)              # keep low 32 bits
    if value >= (1 << 31):
        value -= ACC_MOD                # sign-extend
    return value


# -----------------------------------------------------------------------------
# Test harness helpers
# -----------------------------------------------------------------------------

async def tick(dut):
    """Wait one full clock cycle and let outputs settle."""
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def reset_dut(dut):
    """Drive a clean synchronous reset for two cycles."""
    dut.rst.value = 1
    dut.clr.value = 0
    dut.en.value  = 0
    dut.w.value   = 0
    dut.x.value   = 0
    await tick(dut)
    await tick(dut)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


def check(dut, expected, label):
    """Compare DUT acc to expected, print PASS/FAIL, raise on FAIL."""
    actual = dut.acc.value.to_signed()
    if actual == expected:
        cocotb.log.info(f"PASS | {label:<32} | acc = {actual}")
    else:
        raise AssertionError(
            f"FAIL | {label:<32} | expected {expected}, got {actual}"
        )


# -----------------------------------------------------------------------------
# Test 1 — Reset clears a non-zero accumulator
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_reset(dut):
    """Reset must zero the accumulator even after partial accumulation."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # Pre-load some non-zero state
    dut.en.value = 1
    dut.w.value  = to_q15(0.5)
    dut.x.value  = to_q15(0.5)
    await tick(dut)
    await tick(dut)
    assert dut.acc.value.to_signed() != 0, "accumulator should be non-zero"

    # Assert reset; accumulator must clear next cycle
    dut.rst.value = 1
    dut.en.value  = 0
    await tick(dut)
    check(dut, 0, "reset_clears_acc")


# -----------------------------------------------------------------------------
# Test 2 — One known MAC step
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_single_mac(dut):
    """Drive one product (w=0.5, x=0.5) and check acc = 0.5 * 0.5 in Q30."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    w_q15 = to_q15(0.5)        # 0x4000 = 16384
    x_q15 = to_q15(0.5)        # 0x4000 = 16384
    expected = w_q15 * x_q15   # 268,435,456 (Q30 representation of 0.25)

    dut.en.value = 1
    dut.w.value  = w_q15
    dut.x.value  = x_q15
    await tick(dut)
    dut.en.value = 0
    check(dut, expected, "single_mac_0.5_x_0.5")


# -----------------------------------------------------------------------------
# Test 3 — 50-deep dot product over realistic Q15 reservoir values
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_dot_product_50(dut):
    """
    Accumulate 50 products with operands drawn from a realistic ESN range
    (|w|, |x| < 0.3) and verify the running accumulator every cycle against
    a NumPy golden model that performs identical Q15 arithmetic.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # Clear the accumulator before the dot product
    dut.clr.value = 1
    await tick(dut)
    dut.clr.value = 0

    random.seed(42)  # deterministic for reproducibility

    expected_acc = 0
    for k in range(50):
        # Realistic reservoir-scale operands
        w_real = random.uniform(-0.3, 0.3)
        x_real = random.uniform(-0.3, 0.3)
        w_q15  = to_q15(w_real)
        x_q15  = to_q15(x_real)

        # Drive DUT
        dut.en.value = 1
        dut.w.value  = w_q15
        dut.x.value  = x_q15
        await tick(dut)

        # Update golden model with same wrap semantics
        expected_acc = acc_wrap(expected_acc + w_q15 * x_q15)

        # Check after each step
        actual = dut.acc.value.to_signed()
        if actual != expected_acc:
            raise AssertionError(
                f"FAIL | dot_product step {k} | "
                f"expected {expected_acc}, got {actual}"
            )

    dut.en.value = 0
    cocotb.log.info(
        f"PASS | dot_product_50 (final acc = {expected_acc})"
    )


# -----------------------------------------------------------------------------
# Test 4 — clr has priority over en in the same cycle
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_clr_priority(dut):
    """If clr and en are both high, clr wins and acc returns to 0."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # Build up a non-zero accumulator
    dut.en.value = 1
    dut.w.value  = to_q15(0.25)
    dut.x.value  = to_q15(0.25)
    for _ in range(3):
        await tick(dut)
    assert dut.acc.value.to_signed() != 0

    # Now drive clr=1 and en=1 simultaneously
    dut.clr.value = 1
    dut.en.value  = 1
    await tick(dut)

    check(dut, 0, "clr_overrides_en")
    dut.clr.value = 0
    dut.en.value  = 0
