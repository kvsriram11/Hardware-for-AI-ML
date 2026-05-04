"""
test_interface.py — cocotb testbench for interface.sv

Project   : Hardware Accelerator for Reservoir State Update in ESNs
Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
Author    : Venkata Sriram Kamarajugadda
Milestone : M2

Strategy
--------
Uses the cocotb-bus AXI4LiteMaster driver for the AXI4-Lite slave port,
which handles the handshake protocol correctly without manual signal
poking. The AXI4-Stream slave port is driven manually since cocotb-bus
0.3.0 does not include an AXI4-Stream master helper in this install
(cocotbext-axi would be the alternative).

Tests
-----
  test_axil_write_read_basic : Multiple writes + reads via AXI4LiteMaster.
  test_full_neuron_via_axi   : End-to-end neuron update — writes, start,
                               stream operands, poll status, read result.
"""

import math
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer

from cocotb_bus.drivers.amba import AXI4LiteMaster


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


def to_unsigned16(v): return v & 0xFFFF
def to_unsigned32(v): return v & 0xFFFFFFFF


def take_low16_signed(v):
    v &= 0xFFFF
    if v & 0x8000:
        v -= 0x10000
    return v


# =============================================================================
# Register addresses (must match interface.sv)
# =============================================================================
ADDR_CTRL      = 0x00
ADDR_STATUS    = 0x04
ADDR_N_MINUS_1 = 0x08
ADDR_LEAK_RATE = 0x0C
ADDR_WIN_U     = 0x10
ADDR_X_PREV    = 0x14
ADDR_X_NEW     = 0x18

CTRL_START_BIT = 0x1
STATUS_BUSY    = 0x1
STATUS_DONE    = 0x2


# =============================================================================
# Software golden model — same as test_compute_core
# =============================================================================
def golden_pwl_tanh(acc):
    Q30_HALF = 0x20000000; Q30_NEG_HALF = -0x20000000
    Q30_ONE = 0x40000000;  Q30_NEG_ONE = -0x40000000
    Q15_HALF = 0x4000; Q15_NEG_HALF = -0x4000
    Q15_3_16 = 0x0C00; Q15_NEG_3_16 = -0x0C00

    def shr_take16(value, n):
        return take_low16_signed(value >> n)

    x_q15 = shr_take16(acc, 15)
    x_half_q15 = shr_take16(acc, 16)
    x_quarter_q15 = shr_take16(acc, 17)
    x_eighth_q15 = shr_take16(acc, 18)
    x_5_8_q15 = take_low16_signed(x_half_q15 + x_eighth_q15)

    if acc >= INT32_MAX:
        return Q15_POS_ONE
    elif acc >= Q30_ONE:
        return take_low16_signed(x_quarter_q15 + Q15_HALF)
    elif acc >= Q30_HALF:
        return take_low16_signed(x_5_8_q15 + Q15_3_16)
    elif acc > Q30_NEG_HALF:
        return x_q15
    elif acc > Q30_NEG_ONE:
        return take_low16_signed(x_5_8_q15 + Q15_NEG_3_16)
    elif acc > INT32_MIN:
        return take_low16_signed(x_quarter_q15 + Q15_NEG_HALF)
    else:
        return Q15_NEG_ONE


def golden_blend(x_prev, tanh_out, leak_rate):
    one_minus_a = Q15_POS_ONE - leak_rate
    sum_q30 = one_minus_a * x_prev + leak_rate * tanh_out
    sum_shr15 = sum_q30 >> 15
    if sum_shr15 > Q15_POS_ONE: return Q15_POS_ONE
    if sum_shr15 < Q15_NEG_ONE: return Q15_NEG_ONE
    return take_low16_signed(sum_shr15)


def golden_compute(w_list, x_list, win_u, x_prev_self, leak_rate):
    acc = sum(w * x for w, x in zip(w_list, x_list))
    acc &= 0xFFFFFFFF
    if acc & 0x80000000: acc -= 0x100000000
    pre = acc + win_u
    pre &= 0xFFFFFFFF
    if pre & 0x80000000: pre -= 0x100000000
    tanh_out = golden_pwl_tanh(pre)
    return golden_blend(x_prev_self, tanh_out, leak_rate)


# =============================================================================
# Reset and clock helpers
# =============================================================================
async def tick(dut):
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def reset_dut(dut):
    """
    Drive the non-AXI-Lite inputs low and pulse rst. The AXI4LiteMaster
    driver manages all s_axil_* signals (including BREADY=1, RREADY=1
    which it asserts in its constructor) — we MUST NOT touch those.
    """
    dut.rst.value             = 1
    dut.s_axis_tdata.value    = 0
    dut.s_axis_tvalid.value   = 0
    dut.s_axis_tlast.value    = 0
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)


# =============================================================================
# AXI4-Stream beat (manual — cocotb-bus 0.3.0 has no AXIS master)
# =============================================================================
async def axis_send_beat(dut, w_q15, x_q15, timeout=500):
    """Send one (w, x) beat: tdata = {x_q15, w_q15}."""
    tdata = (to_unsigned16(x_q15) << 16) | to_unsigned16(w_q15)
    await FallingEdge(dut.clk)
    dut.s_axis_tdata.value  = tdata
    dut.s_axis_tvalid.value = 1

    # Sample tready ON the rising edge (use ReadOnly-style: settle 0 ns)
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        # Sample at the edge BEFORE any propagation
        if int(dut.s_axis_tready.value) == 1:
            break
    else:
        raise AssertionError("axis_send_beat: tready never asserted")

    await FallingEdge(dut.clk)
    dut.s_axis_tvalid.value = 0


async def axis_send_stream(dut, w_list, x_list):
    assert len(w_list) == len(x_list)
    for w, x in zip(w_list, x_list):
        await axis_send_beat(dut, w, x)


# =============================================================================
# Test 1 — basic AXI4-Lite write/read via AXI4LiteMaster
# =============================================================================
@cocotb.test()
async def test_axil_write_read_basic(dut):
    """
    Multiple complete write transactions and read transactions using
    cocotb-bus AXI4LiteMaster. Satisfies M2 rubric:
      - At least one full write transaction (we do four)
      - At least one full read transaction (we do two)
    The driver handles all AXI handshaking internally per the protocol spec.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # AXI4LiteMaster instantiation. Bus prefix "s_axil_" tells it to look for
    # signals named s_axil_AWVALID, s_axil_AWADDR, etc. (case-insensitive).
    axil = AXI4LiteMaster(dut, "s_axil", dut.clk)

    await reset_dut(dut)

    # Four configuration writes
    await axil.write(ADDR_N_MINUS_1, 15)
    cocotb.log.info("PASS | axil_write_N_MINUS_1")

    await axil.write(ADDR_LEAK_RATE, to_unsigned16(to_q15(0.3)))
    cocotb.log.info("PASS | axil_write_LEAK_RATE")

    await axil.write(ADDR_WIN_U, to_unsigned32(to_q30(0.05)))
    cocotb.log.info("PASS | axil_write_WIN_U")

    await axil.write(ADDR_X_PREV, to_unsigned16(to_q15(0.0)))
    cocotb.log.info("PASS | axil_write_X_PREV")

    # Read STATUS — should be idle
    status = int(await axil.read(ADDR_STATUS))
    if (status & STATUS_BUSY) != 0:
        raise AssertionError(f"FAIL | STATUS busy when idle: 0x{status:08X}")
    cocotb.log.info(f"PASS | axil_read_STATUS_idle  | status = 0x{status:08X}")

    # Read X_NEW — should be 0 (uninitialized)
    x_new_raw = int(await axil.read(ADDR_X_NEW))
    if take_low16_signed(x_new_raw & 0xFFFF) != 0:
        raise AssertionError(f"FAIL | X_NEW reset not zero: 0x{x_new_raw:08X}")
    cocotb.log.info("PASS | axil_read_X_NEW_zero")


# =============================================================================
# Test 2 — full end-to-end neuron update through AXI
# =============================================================================
@cocotb.test()
async def test_full_neuron_via_axi(dut):
    """
    End-to-end M2 demonstration:
      1. Write all configuration via AXI4-Lite (AXI4LiteMaster)
      2. Pulse start via CTRL register
      3. Stream N=16 (w, x_prev) beats via AXI4-Stream
      4. Poll STATUS until done
      5. Read X_NEW
      6. Compare to NumPy golden
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    axil = AXI4LiteMaster(dut, "s_axil", dut.clk)

    await reset_dut(dut)

    # Build representative inputs
    random.seed(42)
    N = 16
    w_list = [to_q15(random.uniform(-0.25, 0.25)) for _ in range(N)]
    x_list = [to_q15(random.uniform(-0.30, 0.30)) for _ in range(N)]
    win_u_q30      = to_q30(0.05)
    x_prev_self_q15= to_q15(0.10)
    leak_rate_q15  = to_q15(0.30)

    expected = golden_compute(
        w_list, x_list, win_u_q30, x_prev_self_q15, leak_rate_q15
    )
    cocotb.log.info(f"NumPy golden: expected x_new = {expected}")

    # 1. Configuration writes via AXI4-Lite
    await axil.write(ADDR_N_MINUS_1, N - 1)
    await axil.write(ADDR_LEAK_RATE, to_unsigned16(leak_rate_q15))
    await axil.write(ADDR_WIN_U,     to_unsigned32(win_u_q30))
    await axil.write(ADDR_X_PREV,    to_unsigned16(x_prev_self_q15))

    # 2. Start
    await axil.write(ADDR_CTRL, CTRL_START_BIT)

    # 3. Stream operand pairs
    await axis_send_stream(dut, w_list, x_list)

    # 4. Poll STATUS for done (sticky)
    poll_max = 200
    done = False
    for _ in range(poll_max):
        status = int(await axil.read(ADDR_STATUS))
        if (status & STATUS_DONE):
            done = True
            break
        await tick(dut)
    if not done:
        raise AssertionError("FAIL | done bit never set in STATUS")
    cocotb.log.info("PASS | sticky_done_via_axil_status")

    # 5. Read X_NEW
    rdata = int(await axil.read(ADDR_X_NEW))
    actual = take_low16_signed(rdata & 0xFFFF)

    # 6. Compare to golden
    if actual == expected:
        cocotb.log.info(
            f"PASS | end_to_end_axi_neuron_update | x_new = {actual}"
        )
    else:
        raise AssertionError(
            f"FAIL | end_to_end x_new: expected {expected}, got {actual}"
        )
