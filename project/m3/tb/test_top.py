"""
test_top.py — cocotb end-to-end co-simulation testbench for top.sv

Project   : Hardware Accelerator for Reservoir State Update in ESNs
Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
Author    : Venkata Sriram Kamarajugadda
Milestone : M3

M3 RUBRIC COMPLIANCE
--------------------
- Drives the integrated top module from the host side (AXI4-Lite + AXI4-Stream).
- NEVER accesses compute_core ports directly — all data flow goes through
  the AXI interface, satisfying the M3 "co-simulation must not bypass the
  interface" rule.
- N=64 input vector matches the kernel scale defended in M1 profiling
  (M1's dominant kernel was the recurrent matvec, characterized at N=1000;
   N=64 is a representative sub-vector, not a 2x2 toy input).
- Independent NumPy golden model (Q15 fixed-point bit-accurate) computes
  expected result.
- Single unambiguous PASS or FAIL line printed at end.

REUSES THE WORKING M2 PATTERN
-----------------------------
The AXI4LiteMaster driver, manual AXIS beat sender, Q-format helpers, and
golden_compute() function are copied verbatim from M2's test_interface.py
which passed in M2 simulation. The only change for M3 is:
  - DUT toplevel is `top` (was `interface_axi`)
  - N=64 instead of N=16
"""

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
# Register addresses (must match interface_axi.sv)
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
# Software golden model (Q15 bit-accurate, copied from M2)
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
async def reset_dut(dut):
    """Drive non-AXI-Lite inputs low and pulse rst. AXI4LiteMaster owns s_axil_*."""
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

    for _ in range(timeout):
        await RisingEdge(dut.clk)
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
# M3 END-TO-END CO-SIMULATION TEST
# =============================================================================
@cocotb.test()
async def test_cosim_end_to_end(dut):
    """
    M3 co-simulation: drive top.sv from the host side through AXI ONLY,
    perform one full reservoir-neuron update, read result through AXI ONLY,
    compare to bit-accurate Q15 golden, print PASS/FAIL.

    Sequence:
      1.  Reset
      2.  AXI4-Lite writes: N-1, leak_rate, Win*u, x_prev_self
      3.  AXI4-Lite write to CTRL: start pulse (bit 0)
      4.  Three AXI-protocol regions are now active:
            a. Host write   (config + start, complete by this point)
            b. Compute      (FSM walking q15_mac → tanh → blend)
            c. Host read    (poll STATUS, read X_NEW)
      5.  Stream N=64 (w_k, x_prev_k) beats via AXI4-Stream
      6.  AXI4-Lite read STATUS until done bit set
      7.  AXI4-Lite read X_NEW
      8.  Compare to NumPy golden
      9.  Print PASS or FAIL
    """
    # Start clock (10 ns period = 100 MHz)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # AXI4-Lite host driver (prefix s_axil_ matches DUT ports)
    axil = AXI4LiteMaster(dut, "s_axil", dut.clk)

    await reset_dut(dut)

    # -------------------------------------------------------------------------
    # Build representative N=64 input — defensible scale per M1 kernel choice
    # -------------------------------------------------------------------------
    random.seed(42)
    N = 64
    w_list = [to_q15(random.uniform(-0.25, 0.25)) for _ in range(N)]
    x_list = [to_q15(random.uniform(-0.30, 0.30)) for _ in range(N)]

    leak_rate_q15 = to_q15(0.3)
    win_u_q30     = to_q30(0.05)
    x_prev_self   = to_q15(0.1)

    # -------------------------------------------------------------------------
    # Compute golden BEFORE driving DUT (independent reference)
    # -------------------------------------------------------------------------
    golden = golden_compute(
        w_list, x_list,
        win_u=win_u_q30,
        x_prev_self=x_prev_self,
        leak_rate=leak_rate_q15,
    )
    cocotb.log.info(f"GOLDEN | x_new_q15 = {golden} (0x{to_unsigned16(golden):04X})")

    # -------------------------------------------------------------------------
    # === REGION A: Host write transaction (AXI4-Lite config writes) ==========
    # -------------------------------------------------------------------------
    cocotb.log.info("REGION A | host write transaction starts")
    await axil.write(ADDR_N_MINUS_1, N - 1)
    await axil.write(ADDR_LEAK_RATE, to_unsigned16(leak_rate_q15))
    await axil.write(ADDR_WIN_U,     to_unsigned32(win_u_q30))
    await axil.write(ADDR_X_PREV,    to_unsigned16(x_prev_self))
    cocotb.log.info("REGION A | configuration writes complete")

    # Pulse start
    await axil.write(ADDR_CTRL, CTRL_START_BIT)
    cocotb.log.info("REGION A | start pulse issued via CTRL")

    # -------------------------------------------------------------------------
    # === REGION B: Internal compute activity ================================
    #   FSM consumes AXIS beats, runs MAC → tanh → blend
    # -------------------------------------------------------------------------
    cocotb.log.info("REGION B | internal compute starts (streaming N=64 beats)")
    await axis_send_stream(dut, w_list, x_list)
    cocotb.log.info("REGION B | all 64 operand beats accepted by FSM")

    # -------------------------------------------------------------------------
    # === REGION C: Host read transaction (poll STATUS, read X_NEW) ==========
    # -------------------------------------------------------------------------
    cocotb.log.info("REGION C | host read transaction starts")
    for poll in range(2000):
        status = int(await axil.read(ADDR_STATUS))
        if (status & STATUS_DONE) != 0:
            cocotb.log.info(f"REGION C | STATUS.done observed after {poll+1} polls "
                            f"(status=0x{status:08X})")
            break
    else:
        raise AssertionError("FAIL | STATUS.done never asserted after 2000 polls")

    x_new_raw = int(await axil.read(ADDR_X_NEW))
    dut_result = take_low16_signed(x_new_raw & 0xFFFF)
    cocotb.log.info(f"REGION C | X_NEW read: dut={dut_result} (0x{to_unsigned16(dut_result):04X})")

    # -------------------------------------------------------------------------
    # PASS/FAIL comparison (bit-exact match required — golden is Q15-accurate)
    # -------------------------------------------------------------------------
    if dut_result == golden:
        cocotb.log.info("=" * 60)
        cocotb.log.info(f"PASS | cosim_end_to_end | dut={dut_result} golden={golden}")
        cocotb.log.info("=" * 60)
    else:
        cocotb.log.error("=" * 60)
        cocotb.log.error(f"FAIL | cosim_end_to_end | dut={dut_result} golden={golden} "
                         f"diff={dut_result - golden}")
        cocotb.log.error("=" * 60)
        raise AssertionError(
            f"FAIL | cosim_end_to_end | dut={dut_result} golden={golden}"
        )
