"""
test_q15_blend.py — cocotb testbench for q15_blend.sv

Project   : Hardware Accelerator for Reservoir State Update in ESNs
Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
Author    : Venkata Sriram Kamarajugadda
Milestone : M2

Strategy
--------
q15_blend implements:  x_new = (1 - a) * x_prev + a * tanh_out

This is purely combinational. We drive Q15 input triples through the DUT
and compare to a Python golden model that performs identical Q15 arithmetic
(two Q15*Q15=Q30 multiplies, sum, arithmetic right shift by 15, saturate).

Tests
-----
  test_extreme_leak_rates : a=0 (hold) and a≈1 (full update).
  test_project_leak_03    : a = 0.3 (the SW baseline value), several
                            (x_prev, tanh_out) combinations.
  test_random_500         : 500 random Q15 input triples, every output
                            matches the golden bit-exactly.
  test_saturation_corner  : both inputs at full-scale, verify no wrap.
"""

import random

import cocotb
from cocotb.triggers import Timer


# -----------------------------------------------------------------------------
# Q15 helpers
# -----------------------------------------------------------------------------
Q15_ONE_FP   = 1 << 15           # 32768
Q15_POS_ONE  =  (1 << 15) - 1    # +32767
Q15_NEG_ONE  = -(1 << 15)        # -32768
INT16_MAX    =  Q15_POS_ONE
INT16_MIN    =  Q15_NEG_ONE


def to_q15(real):
    """Convert a real in [-1, 1) to a signed Q15 integer."""
    v = int(round(real * Q15_ONE_FP))
    return max(INT16_MIN, min(INT16_MAX, v))


def to_unsigned16(v):
    """Pack a signed 16-bit int into the unsigned representation cocotb expects."""
    return v & 0xFFFF


def golden_blend(x_prev_q15, tanh_out_q15, leak_rate_q15):
    """
    Mirror q15_blend.sv exactly. Inputs are signed Q15 ints; output is
    signed Q15 int after saturation.
    """
    one_minus_a = Q15_POS_ONE - leak_rate_q15  # = 0x7FFF - a

    # Q15 * Q15 = Q30 (signed 32-bit)
    term_prev = one_minus_a * x_prev_q15
    term_new  = leak_rate_q15 * tanh_out_q15

    sum_q30 = term_prev + term_new

    # Arithmetic right shift by 15 (Python's >> is arithmetic on signed ints)
    sum_shr15 = sum_q30 >> 15

    # Saturate to Q15
    if sum_shr15 > Q15_POS_ONE:
        return Q15_POS_ONE
    elif sum_shr15 < Q15_NEG_ONE:
        return Q15_NEG_ONE
    else:
        # Take low 16 bits, interpret as signed
        v = sum_shr15 & 0xFFFF
        if v & 0x8000:
            v -= 0x10000
        return v


# -----------------------------------------------------------------------------
# Test harness
# -----------------------------------------------------------------------------
async def apply_inputs(dut, x_prev_q15, tanh_out_q15, leak_rate_q15):
    dut.x_prev.value    = to_unsigned16(x_prev_q15)
    dut.tanh_out.value  = to_unsigned16(tanh_out_q15)
    dut.leak_rate.value = to_unsigned16(leak_rate_q15)
    await Timer(1, unit="ns")
    return dut.x_new.value.to_signed()


def check(label, expected, actual):
    if actual == expected:
        cocotb.log.info(f"PASS | {label:<46} | x_new = {actual}")
    else:
        raise AssertionError(
            f"FAIL | {label:<46} | expected {expected}, got {actual}"
        )


# -----------------------------------------------------------------------------
# Test 1 — extreme leak rates (a=0 holds, a≈1 fully updates)
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_extreme_leak_rates(dut):
    """
    a = 0       : x_new should equal x_prev (state held; tanh_out ignored)
    a = 0x7FFF  : x_new should equal tanh_out (state fully replaced)
    """
    # Case 1: a = 0
    a = 0
    x_prev   = to_q15(0.5)
    tanh_out = to_q15(-0.7)
    expected = golden_blend(x_prev, tanh_out, a)
    actual   = await apply_inputs(dut, x_prev, tanh_out, a)
    check("a=0_holds_state                (x_new ≈ x_prev)", expected, actual)

    # Case 2: a = 0x7FFF (≈ 1.0)
    a = Q15_POS_ONE
    x_prev   = to_q15(0.5)
    tanh_out = to_q15(-0.7)
    expected = golden_blend(x_prev, tanh_out, a)
    actual   = await apply_inputs(dut, x_prev, tanh_out, a)
    check("a≈1_replaces_state             (x_new ≈ tanh_out)", expected, actual)


# -----------------------------------------------------------------------------
# Test 2 — project leak rate a = 0.3
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_project_leak_03(dut):
    """Test a = 0.3 (the Mackey-Glass SW baseline) with several state pairs."""
    a = to_q15(0.3)

    cases = [
        ( 0.0,   0.0,  "x_prev=0,        tanh_out=0"),
        ( 0.5,   0.0,  "x_prev=+0.5,     tanh_out=0"),
        ( 0.0,   0.5,  "x_prev=0,        tanh_out=+0.5"),
        ( 0.5,  -0.5,  "x_prev=+0.5,     tanh_out=-0.5"),
        (-0.7,   0.7,  "x_prev=-0.7,     tanh_out=+0.7"),
        ( 0.9,  -0.9,  "x_prev=+0.9,     tanh_out=-0.9"),
    ]
    for xp, tn, label in cases:
        x_prev   = to_q15(xp)
        tanh_out = to_q15(tn)
        expected = golden_blend(x_prev, tanh_out, a)
        actual   = await apply_inputs(dut, x_prev, tanh_out, a)
        check(label, expected, actual)


# -----------------------------------------------------------------------------
# Test 3 — 500 random input triples
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_random_500(dut):
    """500 random (x_prev, tanh_out, a) triples; every output matches."""
    random.seed(2026)

    fail_count = 0
    for k in range(500):
        x_prev   = random.randint(INT16_MIN, INT16_MAX)
        tanh_out = random.randint(INT16_MIN, INT16_MAX)
        # leak_rate is non-negative in [0, 0x7FFF]
        a = random.randint(0, INT16_MAX)

        actual   = await apply_inputs(dut, x_prev, tanh_out, a)
        expected = golden_blend(x_prev, tanh_out, a)
        if actual != expected:
            fail_count += 1
            cocotb.log.error(
                f"random k={k}: x_prev={x_prev}, tanh_out={tanh_out}, a={a} | "
                f"expected={expected}, actual={actual}"
            )

    if fail_count == 0:
        cocotb.log.info("PASS | random_500_match_golden")
    else:
        raise AssertionError(f"{fail_count} mismatches in 500-point random test")


# -----------------------------------------------------------------------------
# Test 4 — saturation corner (full-scale inputs with full leak)
# -----------------------------------------------------------------------------
@cocotb.test()
async def test_saturation_corner(dut):
    """
    Drive both x_prev and tanh_out to ±Q15 limits with a near 1.0.
    Verify the output stays within [Q15_NEG_ONE, Q15_POS_ONE].
    """
    cases = [
        ( Q15_POS_ONE,  Q15_POS_ONE,  Q15_POS_ONE, "full positive (a≈1)"),
        ( Q15_NEG_ONE,  Q15_NEG_ONE,  Q15_POS_ONE, "full negative (a≈1)"),
        ( Q15_POS_ONE,  Q15_NEG_ONE,  to_q15(0.5), "mixed full-scale (a=0.5)"),
        ( Q15_POS_ONE,  Q15_POS_ONE,  0,           "full positive (a=0, hold)"),
    ]
    for xp, tn, a, label in cases:
        actual   = await apply_inputs(dut, xp, tn, a)
        expected = golden_blend(xp, tn, a)
        check(label, expected, actual)
        if not (Q15_NEG_ONE <= actual <= Q15_POS_ONE):
            raise AssertionError(
                f"FAIL saturation: {label} produced out-of-range {actual}"
            )
