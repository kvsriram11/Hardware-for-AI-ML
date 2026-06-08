"""
test_top.py — M3 end-to-end cosim for top.sv.

Drives a full N=64 reservoir state-update through the AXI boundary ONLY:
no compute_core port is ever poked directly. Per neuron i the host:

    a) AXIL write XPREV[i]            (this neuron's prior state, for the blend)
    b) AXIL write WIN_T[i]            (precomputed Win@[1,u] contribution)
    c) AXIL write CTRL.start
    d) stream ceil(N/MAC_WIDTH) AXIS beats of (w_row_chunk, x_chunk)
    e) poll STATUS until done
    f) AXIL read XNEXT
    g) accumulate into the x_next vector

LEAK_A is written once up front (it is constant across the reservoir).
Every neuron's XNEXT must match golden_top within 1 LSB — same tolerance
basis as M2's random sweep (signed-shift rounding), bit-exact expected for
nearly all neurons.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from golden_top import gen_network, state_update_top
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm2'))
from golden import sign_extend

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

DATA_W    = int(os.environ.get('DATA_W', 16))
MAC_WIDTH = int(os.environ.get('MAC_WIDTH', 16))
ACC_W     = int(os.environ.get('ACC_W', 40))
FRAC_W    = DATA_W - 1
N         = int(os.environ.get('N_RESERVOIR', 64))

ADDR_CTRL   = 0x00
ADDR_STATUS = 0x04
ADDR_LEAK_A = 0x08
ADDR_WIN_T  = 0x0C
ADDR_XPREV  = 0x10
ADDR_XNEXT  = 0x14

MASK_D = (1 << DATA_W) - 1


async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.s_axil_awaddr.value = 0
    dut.s_axil_awvalid.value = 0
    dut.s_axil_wdata.value = 0
    dut.s_axil_wstrb.value = 0xF
    dut.s_axil_wvalid.value = 0
    dut.s_axil_bready.value = 1
    dut.s_axil_araddr.value = 0
    dut.s_axil_arvalid.value = 0
    dut.s_axil_rready.value = 1
    dut.s_axis_tdata.value = 0
    dut.s_axis_tvalid.value = 0
    dut.s_axis_tlast.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    for _ in range(2):
        await RisingEdge(dut.clk)


async def axil_write(dut, addr, data, timeout=200):
    dut.s_axil_awaddr.value = addr
    dut.s_axil_awvalid.value = 1
    dut.s_axil_wdata.value = data & 0xFFFFFFFF
    dut.s_axil_wvalid.value = 1
    aw_done = w_done = False
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if not aw_done and int(dut.s_axil_awready.value) == 1:
            dut.s_axil_awvalid.value = 0
            aw_done = True
        if not w_done and int(dut.s_axil_wready.value) == 1:
            dut.s_axil_wvalid.value = 0
            w_done = True
        if aw_done and w_done:
            break
    else:
        raise TimeoutError(f"axil_write @0x{addr:02x}: AW/W timeout")
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_bvalid.value) == 1:
            await RisingEdge(dut.clk)
            return
    raise TimeoutError(f"axil_write @0x{addr:02x}: BVALID timeout")


async def axil_read(dut, addr, timeout=200):
    dut.s_axil_araddr.value = addr
    dut.s_axil_arvalid.value = 1
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_arready.value) == 1:
            dut.s_axil_arvalid.value = 0
            break
    else:
        raise TimeoutError(f"axil_read @0x{addr:02x}: ARREADY timeout")
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_rvalid.value) == 1:
            data = int(dut.s_axil_rdata.value)
            await RisingEdge(dut.clk)
            return data
    raise TimeoutError(f"axil_read @0x{addr:02x}: RVALID timeout")


def pack_chunk(vec, data_w):
    out = 0
    for i, v in enumerate(vec):
        out |= (v & MASK_D) << (i * data_w)
    return out


async def axis_beat(dut, w_vec, x_vec, last, timeout=200):
    w_packed = pack_chunk(w_vec, DATA_W)
    x_packed = pack_chunk(x_vec, DATA_W)
    dut.s_axis_tdata.value = (w_packed << (MAC_WIDTH * DATA_W)) | x_packed
    dut.s_axis_tvalid.value = 1
    dut.s_axis_tlast.value = 1 if last else 0
    for _ in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axis_tready.value) == 1:
            dut.s_axis_tvalid.value = 0
            dut.s_axis_tlast.value = 0
            return
    raise TimeoutError("axis_beat: TREADY timeout")


async def run_neuron(dut, w_row, x_prev_vec, x_prev_i, win_term, n_beats):
    """One full single-neuron update over AXI; returns DUT XNEXT (signed)."""
    await axil_write(dut, ADDR_XPREV, x_prev_i & 0xFFFFFFFF)
    await axil_write(dut, ADDR_WIN_T, win_term & 0xFFFFFFFF)
    await axil_write(dut, ADDR_CTRL, 0x1)  # start

    for k in range(n_beats):
        lo = k * MAC_WIDTH
        w_chunk = w_row[lo:lo + MAC_WIDTH]
        x_chunk = x_prev_vec[lo:lo + MAC_WIDTH]
        await axis_beat(dut, w_chunk, x_chunk, last=(k == n_beats - 1))

    for _ in range(100):
        status = await axil_read(dut, ADDR_STATUS)
        if status & 0x2:  # done
            break
    else:
        raise TimeoutError("neuron: done never asserted")

    rb = await axil_read(dut, ADDR_XNEXT)
    return sign_extend(rb & MASK_D, DATA_W)


@cocotb.test()
async def test_full_reservoir(dut):
    """Drive all N neurons through AXI and check each XNEXT vs golden_top."""
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset_dut(dut)

    net = gen_network(N, DATA_W, ACC_W)
    gold = state_update_top(net)
    n_beats = (N + MAC_WIDTH - 1) // MAC_WIDTH
    dut._log.info(f"N={N}, MAC_WIDTH={MAC_WIDTH}, beats/neuron={n_beats}")

    # LEAK_A is constant for the whole reservoir step.
    await axil_write(dut, ADDR_LEAK_A, net['leak_a'] & 0xFFFFFFFF)

    x_next = []
    fails = 0
    worst = 0
    for i in range(N):
        dut_xi = await run_neuron(dut, net['W'][i], net['x_prev'],
                                  net['x_prev'][i], net['win_term'][i], n_beats)
        x_next.append(dut_xi)
        diff = dut_xi - gold[i]
        worst = max(worst, abs(diff))
        if abs(diff) > 1:
            fails += 1
            dut._log.error(f"neuron {i}: dut={dut_xi} golden={gold[i]} "
                           f"diff={diff} EXCEEDS 1 lsb")
        elif diff != 0:
            dut._log.warning(f"neuron {i}: within 1 lsb (diff={diff})")

    exact = sum(1 for i in range(N) if x_next[i] == gold[i])
    dut._log.info(f"RESERVOIR COSIM: N={N} neurons, {exact}/{N} bit-exact, "
                  f"worst |diff|={worst} lsb, {N - fails}/{N} within tolerance")
    assert fails == 0, f"{fails}/{N} neurons exceeded 1-lsb tolerance"
    dut._log.info("FULL RESERVOIR COSIM PASS")
