"""
Cocotb test for interface.sv (interface_axi).

Exercises:
  - AXI4-Lite write to LEAK_A register, read back, verify
  - Full pipeline: AXIL-configure + AXIS-stream + AXIL-read x_next, vs golden

Pass criteria: AXI handshakes complete per spec; final x_next matches golden.
"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from golden import state_update_golden, float_to_q, sign_extend

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly

DATA_W    = int(os.environ.get('DATA_W', 16))
MAC_WIDTH = int(os.environ.get('MAC_WIDTH', 16))
ACC_W     = int(os.environ.get('ACC_W', 40))
FRAC_W    = DATA_W - 1

ADDR_CTRL   = 0x00
ADDR_STATUS = 0x04
ADDR_LEAK_A = 0x08
ADDR_WIN_T  = 0x0C
ADDR_XPREV  = 0x10
ADDR_XNEXT  = 0x14


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
    """One AXI4-Lite write. AW and W handshake independently per spec."""
    # Drive AW
    dut.s_axil_awaddr.value = addr
    dut.s_axil_awvalid.value = 1
    # Drive W
    dut.s_axil_wdata.value = data & 0xFFFFFFFF
    dut.s_axil_wvalid.value = 1

    aw_done = False
    w_done  = False
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        # Check at the next rising edge: did slave assert ready last cycle?
        # In cocotb we read inputs after the edge, which reflects values from the prior cycle.
        if not aw_done and int(dut.s_axil_awready.value) == 1:
            dut.s_axil_awvalid.value = 0
            aw_done = True
        if not w_done and int(dut.s_axil_wready.value) == 1:
            dut.s_axil_wvalid.value = 0
            w_done = True
        if aw_done and w_done:
            break
    else:
        raise TimeoutError(f"axil_write @0x{addr:02x}: AW/W handshake timeout")

    # Wait for bvalid, then accept it
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_bvalid.value) == 1:
            # bready already 1 in reset, so this is the handshake cycle
            await RisingEdge(dut.clk)  # let slave see bready then deassert bvalid
            return
    raise TimeoutError(f"axil_write @0x{addr:02x}: BVALID never asserted")


async def axil_read(dut, addr, timeout=200):
    """One AXI4-Lite read. Returns 32-bit value."""
    dut.s_axil_araddr.value = addr
    dut.s_axil_arvalid.value = 1
    # Wait for arready
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_arready.value) == 1:
            dut.s_axil_arvalid.value = 0
            break
    else:
        raise TimeoutError(f"axil_read @0x{addr:02x}: ARREADY never asserted")
    # Wait for rvalid
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axil_rvalid.value) == 1:
            data = int(dut.s_axil_rdata.value)
            await RisingEdge(dut.clk)
            return data
    raise TimeoutError(f"axil_read @0x{addr:02x}: RVALID never asserted")


def pack_chunk(vec, data_w):
    mask = (1 << data_w) - 1
    out = 0
    for i, v in enumerate(vec):
        out |= (v & mask) << (i * data_w)
    return out


async def axis_beat(dut, w_vec, x_vec, last=True, timeout=200):
    """Send one AXI4-Stream beat carrying packed (w || x) and tlast."""
    w_packed = pack_chunk(w_vec, DATA_W)
    x_packed = pack_chunk(x_vec, DATA_W)
    tdata = (w_packed << (MAC_WIDTH * DATA_W)) | x_packed
    dut.s_axis_tdata.value = tdata
    dut.s_axis_tvalid.value = 1
    dut.s_axis_tlast.value = 1 if last else 0
    for cyc in range(timeout):
        await RisingEdge(dut.clk)
        if int(dut.s_axis_tready.value) == 1:
            dut.s_axis_tvalid.value = 0
            dut.s_axis_tlast.value = 0
            return
    raise TimeoutError("axis_beat: TREADY never asserted")


@cocotb.test()
async def test_axil_write_readback(dut):
    """Smoke test: write to LEAK_A, read it back, verify match."""
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset_dut(dut)

    test_val = float_to_q(0.3, DATA_W) & ((1 << DATA_W) - 1)
    dut._log.info(f"Writing LEAK_A = 0x{test_val:04x}")
    await axil_write(dut, ADDR_LEAK_A, test_val)
    dut._log.info("Write done, reading back")
    rb = await axil_read(dut, ADDR_LEAK_A)
    rb_signed = sign_extend(rb & ((1 << DATA_W) - 1), DATA_W)
    expect_signed = sign_extend(test_val, DATA_W)
    dut._log.info(f"Readback raw=0x{rb:08x}, signed={rb_signed}, expect={expect_signed}")
    assert rb_signed == expect_signed, f"AXIL readback mismatch: rb={rb_signed}, expect={expect_signed}"
    dut._log.info("AXIL WRITE/READ PASS")


@cocotb.test()
async def test_full_pipeline(dut):
    """End-to-end: configure via AXIL, send vector via AXIS, read result via AXIL."""
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())
    await reset_dut(dut)

    random.seed(42)
    w = [float_to_q(random.uniform(-0.1, 0.1), DATA_W) for _ in range(MAC_WIDTH)]
    x = [float_to_q(random.uniform(-0.5, 0.5), DATA_W) for _ in range(MAC_WIDTH)]
    x_prev_i = float_to_q(random.uniform(-0.5, 0.5), DATA_W)
    leak_a = float_to_q(0.3, DATA_W)
    # Win term in ACC_W bits, low-32 truncation through AXIL
    # win_term is Q1.(DATA_W-1) sign-extended into ACC_W bits (per corrected RTL contract).
    # On the AXIL bus we sign-extend Q1.15 into the low bits of a 32-bit word.
    win_q = float_to_q(random.uniform(-0.05, 0.05), DATA_W)
    win_term_signed = sign_extend(win_q, ACC_W)
    win_term_32 = win_q & 0xFFFFFFFF
    if win_q < 0:
        # sign-extend into upper 32 bits for the AXIL 32-bit word write
        win_term_32 = (win_q & 0xFFFFFFFF)

    dut._log.info("Configuring via AXIL")
    await axil_write(dut, ADDR_LEAK_A, leak_a & 0xFFFFFFFF)
    await axil_write(dut, ADDR_XPREV,  x_prev_i & 0xFFFFFFFF)
    await axil_write(dut, ADDR_WIN_T,  win_term_32)
    dut._log.info("Asserting CTRL.start")
    await axil_write(dut, ADDR_CTRL, 0x1)

    dut._log.info("Streaming AXIS beat")
    await axis_beat(dut, w, x, last=True)

    # Poll STATUS.done
    dut._log.info("Polling STATUS for done")
    for poll in range(50):
        status = await axil_read(dut, ADDR_STATUS)
        if status & 0x2:
            dut._log.info(f"done after {poll+1} polls (status=0x{status:x})")
            break
    else:
        raise TimeoutError("done never asserted")

    rb = await axil_read(dut, ADDR_XNEXT)
    dut_x_next = sign_extend(rb & ((1 << DATA_W) - 1), DATA_W)
    gold = state_update_golden(w, x, x_prev_i, win_term_signed, leak_a, DATA_W, ACC_W, FRAC_W)
    dut._log.info(f"FULL PIPELINE: dut={dut_x_next}, golden={gold}")
    assert dut_x_next == gold, f"PIPELINE FAIL: dut={dut_x_next}, golden={gold}, diff={dut_x_next-gold}"
    dut._log.info("FULL PIPELINE PASS")
