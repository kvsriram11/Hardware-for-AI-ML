"""
test_compute_core.py — cocotb testbench for compute_core.sv

Project   : Hardware Accelerator for Reservoir State Update in ESNs
Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
Author    : Venkata Sriram Kamarajugadda
Milestone : M2

Strategy (M2-graded testbench)
------------------------------
Drives ONE complete ESN reservoir-state update for one neuron through the
DUT, using a representative input vector. Computes the expected output
INDEPENDENTLY in NumPy (a software model that performs identical Q15
arithmetic, identical 7-segment PWL tanh, and identical leak blend), and
asserts the DUT output matches bit-exactly.

Per the M2 rubric:
  - Representative input: an N=16 dot product with realistic ESN-scale
    operands (|w|, |x_prev| < 0.3), plus non-trivial win_u and leak_rate.
  - Independent reference: NumPy. NOT a prior DUT run.
  - Prints PASS / FAIL based on comparison.

Tests
-----
  test_basic_update       : N=16 representative update, single neuron.
  test_two_back_to_back   : Two consecutive updates with different inputs;
                            verifies FSM returns to IDLE between starts.
  test_realistic_n64      : N=64 dot product with random reservoir-scale
                            operands; demonstrates the design scales.
"""

import math
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


# =============================================================================
# Q-format helpers
# =============================================================================
Q15_ONE_FP   = 1 << 15
Q30_ONE_FP   = 1 << 30
Q15_POS_ONE  =  (1 << 15) - 1
Q15_NEG_ONE  = -(1 << 15)
INT16_MAX    =  Q15_POS_ONE
INT16_MIN    =  Q15_NEG_ONE
INT32_MAX    =  (1 << 31) - 1
INT32_MIN    = -(1 << 31)


def to_q15(real):
    v = int(round(real * Q15_ONE_FP))
    return max(INT16_MIN, min(INT16_MAX, v))


def to_q30(real):
    v = int(round(real * Q30_ONE_FP))
    return max(INT32_MIN, min(INT32_MAX, v))


def to_unsigned16(v):
    return v & 0xFFFF


def to_unsigned32(v):
    return v & 0xFFFFFFFF


def take_low16_signed(v):
    v &= 0xFFFF
    if v & 0x8000:
        v -= 0x10000
    return v


# =============================================================================
# Software golden model — reproduces compute_core.sv arithmetic exactly
# =============================================================================
def golden_pwl_tanh(acc_q30):
    """Identical to q15_tanh.sv (7-segment PWL)."""
    Q30_HALF     = 0x20000000
    Q30_NEG_HALF = -0x20000000
    Q30_ONE      = 0x40000000
    Q30_NEG_ONE  = -0x40000000

    def shr_take16(value, n):
        # Arithmetic right shift on signed; take low 16 bits as signed
        v = value >> n   # Python >> on signed is arithmetic
        return take_low16_signed(v)

    Q15_HALF     =  0x4000
    Q15_NEG_HALF = -0x4000
    Q15_3_16     =  0x0C00
    Q15_NEG_3_16 = -0x0C00

    x_q15         = shr_take16(acc_q30, 15)
    x_half_q15    = shr_take16(acc_q30, 16)
    x_quarter_q15 = shr_take16(acc_q30, 17)
    x_eighth_q15  = shr_take16(acc_q30, 18)
    x_5_8_q15     = take_low16_signed(x_half_q15 + x_eighth_q15)

    if acc_q30 >= INT32_MAX:
        result = Q15_POS_ONE
    elif acc_q30 >= Q30_ONE:
        result = x_quarter_q15 + Q15_HALF
    elif acc_q30 >= Q30_HALF:
        result = x_5_8_q15 + Q15_3_16
    elif acc_q30 > Q30_NEG_HALF:
        result = x_q15
    elif acc_q30 > Q30_NEG_ONE:
        result = x_5_8_q15 + Q15_NEG_3_16
    elif acc_q30 > INT32_MIN:
        result = x_quarter_q15 + Q15_NEG_HALF
    else:
        result = Q15_NEG_ONE

    return take_low16_signed(result)


def golden_blend(x_prev_q15, tanh_out_q15, leak_rate_q15):
    """Identical to q15_blend.sv."""
    one_minus_a = Q15_POS_ONE - leak_rate_q15
    term_prev = one_minus_a * x_prev_q15
    term_new  = leak_rate_q15 * tanh_out_q15
    sum_q30 = term_prev + term_new
    sum_shr15 = sum_q30 >> 15
    if sum_shr15 > Q15_POS_ONE:
        return Q15_POS_ONE
    elif sum_shr15 < Q15_NEG_ONE:
        return Q15_NEG_ONE
    return take_low16_signed(sum_shr15)


def golden_compute_core(w_list_q15, x_list_q15, win_u_q30,
                        x_prev_self_q15, leak_rate_q15):
    """
    Full ESN single-neuron update. Mirrors the FSM:
      acc = sum(w[k] * x[k])  in Q30
      pre = acc + win_u       in Q30
      tanh_out = PWL(pre)     in Q15
      x_new    = blend(...)   in Q15
    """
    acc = 0
    for w, x in zip(w_list_q15, x_list_q15):
        acc += w * x  # Q15 * Q15 → Q30

    # Wrap to signed 32-bit (matches RTL accumulator width)
    acc_32 = acc & 0xFFFFFFFF
    if acc_32 & 0x80000000:
        acc_32 -= 0x100000000

    # Add win_u (also Q30)
    pre = acc_32 + win_u_q30
    pre_32 = pre & 0xFFFFFFFF
    if pre_32 & 0x80000000:
        pre_32 -= 0x100000000

    tanh_out = golden_pwl_tanh(pre_32)
    return golden_blend(x_prev_self_q15, tanh_out, leak_rate_q15)


# =============================================================================
# Test harness helpers
# =============================================================================
async def tick(dut):
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def reset_dut(dut):
    """Drive a clean synchronous reset for two cycles."""
    dut.rst.value         = 1
    dut.start.value       = 0
    dut.N_minus_1.value   = 0
    dut.leak_rate.value   = 0
    dut.win_u.value       = 0
    dut.x_prev_self.value = 0
    dut.w_data.value      = 0
    dut.w_valid.value     = 0
    dut.x_data.value      = 0
    dut.x_valid.value     = 0
    await tick(dut)
    await tick(dut)
    dut.rst.value = 0
    await FallingEdge(dut.clk)


async def run_one_update(dut, w_list_q15, x_list_q15, win_u_q30,
                         x_prev_self_q15, leak_rate_q15):
    """
    Drive one full ESN single-neuron update through the DUT.
    Returns the registered x_new value once x_new_valid pulses.
    """
    N = len(w_list_q15)
    assert len(x_list_q15) == N

    # Drive configuration and pulse start (must be synchronous to clk edge)
    await FallingEdge(dut.clk)
    dut.N_minus_1.value   = N - 1
    dut.leak_rate.value   = to_unsigned16(leak_rate_q15)
    dut.win_u.value       = to_unsigned32(win_u_q30)
    dut.x_prev_self.value = to_unsigned16(x_prev_self_q15)
    dut.start.value       = 1

    await RisingEdge(dut.clk)
    dut.start.value = 0

    # FSM is now IDLE→LOAD on this edge; LOAD→ACCUM next edge.
    # We need to start streaming (w, x) pairs while in S_ACCUM.
    # Wait for one cycle to allow LOAD→ACCUM transition.
    await tick(dut)

    # Stream the dot-product operands one per cycle
    for k in range(N):
        await FallingEdge(dut.clk)
        dut.w_data.value  = to_unsigned16(w_list_q15[k])
        dut.x_data.value  = to_unsigned16(x_list_q15[k])
        dut.w_valid.value = 1
        dut.x_valid.value = 1
        await RisingEdge(dut.clk)

    await FallingEdge(dut.clk)
    dut.w_valid.value = 0
    dut.x_valid.value = 0

    # FSM now goes ACCUM → ADDU → NL → DONE (3 cycles).
    # Wait for x_new_valid pulse with a generous timeout.
    timeout_cycles = 20
    for _ in range(timeout_cycles):
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        if int(dut.x_new_valid.value) == 1:
            return dut.x_new.value.to_signed()

    raise AssertionError("Timeout waiting for x_new_valid")


def check(label, expected, actual):
    if actual == expected:
        cocotb.log.info(f"PASS | {label:<46} | x_new = {actual}")
    else:
        cocotb.log.error(
            f"FAIL | {label:<46} | expected {expected}, got {actual}"
        )
        raise AssertionError(
            f"FAIL | {label}: expected {expected}, got {actual}"
        )


# =============================================================================
# Test 1 — basic representative N=16 update
# =============================================================================
@cocotb.test()
async def test_basic_update(dut):
    """
    Drive one full ESN single-neuron update with N=16 and realistic
    reservoir-scale operands. Compare DUT x_new to NumPy golden model.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # Build representative inputs (deterministic seed)
    random.seed(42)
    N = 16
    w_list = [to_q15(random.uniform(-0.25, 0.25)) for _ in range(N)]
    x_list = [to_q15(random.uniform(-0.3,  0.3))  for _ in range(N)]
    win_u_q30      = to_q30(0.05)             # small input projection
    x_prev_self    = to_q15(0.1)              # small previous state
    leak_rate_q15  = to_q15(0.3)              # project's Mackey-Glass setting

    expected = golden_compute_core(
        w_list, x_list, win_u_q30, x_prev_self, leak_rate_q15
    )
    cocotb.log.info(f"NumPy golden: expected x_new = {expected}")

    actual = await run_one_update(
        dut, w_list, x_list, win_u_q30, x_prev_self, leak_rate_q15
    )

    check("basic_N16_update", expected, actual)


# =============================================================================
# Test 2 — back-to-back updates verify FSM returns to IDLE
# =============================================================================
@cocotb.test()
async def test_two_back_to_back(dut):
    """Run two updates in sequence and verify both produce correct outputs."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    random.seed(100)
    N = 8
    leak_rate_q15 = to_q15(0.3)

    # Update #1
    w1 = [to_q15(random.uniform(-0.2, 0.2)) for _ in range(N)]
    x1 = [to_q15(random.uniform(-0.2, 0.2)) for _ in range(N)]
    win_u_1     = to_q30(0.0)
    x_prev_1    = to_q15(0.0)
    expected_1  = golden_compute_core(w1, x1, win_u_1, x_prev_1, leak_rate_q15)
    actual_1    = await run_one_update(dut, w1, x1, win_u_1, x_prev_1, leak_rate_q15)
    check("update_1_x_prev_zero", expected_1, actual_1)

    # Wait a couple of cycles to let DONE→IDLE settle
    for _ in range(3):
        await tick(dut)

    # Update #2 — different inputs
    w2 = [to_q15(random.uniform(-0.3, 0.3)) for _ in range(N)]
    x2 = [to_q15(random.uniform(-0.3, 0.3)) for _ in range(N)]
    win_u_2     = to_q30(0.1)
    x_prev_2    = to_q15(actual_1 / Q15_ONE_FP)   # use update 1's output
    expected_2  = golden_compute_core(w2, x2, win_u_2, x_prev_2, leak_rate_q15)
    actual_2    = await run_one_update(dut, w2, x2, win_u_2, x_prev_2, leak_rate_q15)
    check("update_2_uses_prior_output", expected_2, actual_2)


# =============================================================================
# Test 3 — N=64 demonstrates scaling
# =============================================================================
@cocotb.test()
async def test_realistic_n64(dut):
    """
    A larger N=64 dot product proves the FSM scales without state corruption.
    Same comparison strategy as test 1.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    random.seed(2026)
    N = 64
    w_list = [to_q15(random.uniform(-0.15, 0.15)) for _ in range(N)]
    x_list = [to_q15(random.uniform(-0.25, 0.25)) for _ in range(N)]
    win_u_q30     = to_q30(-0.02)
    x_prev_self   = to_q15(-0.05)
    leak_rate_q15 = to_q15(0.3)

    expected = golden_compute_core(
        w_list, x_list, win_u_q30, x_prev_self, leak_rate_q15
    )
    cocotb.log.info(f"NumPy golden (N=64): expected x_new = {expected}")

    actual = await run_one_update(
        dut, w_list, x_list, win_u_q30, x_prev_self, leak_rate_q15
    )
    check("realistic_N64", expected, actual)
