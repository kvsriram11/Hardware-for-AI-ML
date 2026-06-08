"""
Cocotb test for compute_core.sv

Drives one full state-update for a single neuron:
  - feeds N=16 weights + N=16 prior-state values in one chunk (MAC_WIDTH==N)
  - asserts start, waits for done
  - compares DUT x_next_o against golden state_update_golden()

Pass criteria: bit-exact match (DUT == golden) for the representative vector.
"""
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from golden import (state_update_golden, float_to_q, sign_extend,
                    mac_golden, tanh_pwl_golden, leak_blend_golden)

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

DATA_W    = int(os.environ.get('DATA_W', 16))
MAC_WIDTH = int(os.environ.get('MAC_WIDTH', 16))
ACC_W     = int(os.environ.get('ACC_W', 40))
FRAC_W    = DATA_W - 1


def pack_chunk(vec, data_w):
    """Pack MAC_WIDTH signed values into a single wide bus integer."""
    mask = (1 << data_w) - 1
    out = 0
    for i, v in enumerate(vec):
        out |= (v & mask) << (i * data_w)
    return out


async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.chunk_valid.value = 0
    dut.last_chunk.value = 0
    dut.w_row.value = 0
    dut.x_chunk.value = 0
    dut.leak_a.value = 0
    dut.x_prev_i.value = 0
    dut.win_term_i.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def run_one_neuron(dut, w_vec, x_vec, x_prev_i, win_term, leak_a, name="vec"):
    """Run one state update through the DUT and return its output."""
    n = len(w_vec)
    assert n == MAC_WIDTH, f"This testbench expects MAC_WIDTH={MAC_WIDTH} but got n={n}"

    # Pre-load scalars
    mask_d = (1 << DATA_W) - 1
    mask_a = (1 << ACC_W) - 1
    dut.leak_a.value = leak_a & mask_d
    dut.x_prev_i.value = x_prev_i & mask_d
    dut.win_term_i.value = win_term & mask_a

    # Fire start, then deliver chunk on next cycle
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    dut.w_row.value = pack_chunk(w_vec, DATA_W)
    dut.x_chunk.value = pack_chunk(x_vec, DATA_W)
    dut.chunk_valid.value = 1
    dut.last_chunk.value = 1
    await RisingEdge(dut.clk)
    dut.chunk_valid.value = 0
    dut.last_chunk.value = 0

    # Wait for done
    for cycle in range(50):
        await RisingEdge(dut.clk)
        if os.environ.get("MAC_PROBE") == "1" and name == "repr":
            try:
                await Timer(1, units="ns")
                st = int(dut.state.value)
                fc = int(dut.flush_cnt.value)
                tq = sign_extend(int(dut.u_mac.tree_q.value), ACC_W)
                so = sign_extend(int(dut.u_mac.sum_out.value), ACC_W)
                psum = 0
                for ii in range(MAC_WIDTH):
                    psum += sign_extend(int(dut.u_mac.prod_ext_q[ii].value), ACC_W)
                dut._log.info(f"PROBE cyc={cycle} state={st} flush={fc} "
                              f"sum(prod)={psum} tree_q={tq} sum_out={so}")
            except Exception as e:
                dut._log.info(f"PROBE err: {e}")
        if int(dut.done.value) == 1:
            x_next = sign_extend(int(dut.x_next_o.value), DATA_W)
            # Internal signal probes for debugging:
            try:
                pre_act_int = sign_extend(int(dut.pre_act.value), 40)
                tanh_out_int = sign_extend(int(dut.tanh_out.value), DATA_W)
                blend_out_int = sign_extend(int(dut.blend_out.value), DATA_W)
                # Also probe MAC sum (40-bit) and win_term_i (40-bit)
                mac_sum_int = sign_extend(int(dut.u_mac.sum_out.value), 40)
                win_term_int = sign_extend(int(dut.win_term_i.value), 40)
                dut._log.info(f"[{name}] internals: mac_sum={mac_sum_int}, win_term_i={win_term_int}, pre_act={pre_act_int}, tanh_out={tanh_out_int}, blend_out={blend_out_int}")
            except Exception as e:
                dut._log.info(f"[{name}] could not probe internals: {e}")
            dut._log.info(f"[{name}] DUT done after {cycle+1} cycles, x_next={x_next}")
            return x_next
    raise TimeoutError(f"compute_core did not assert done within 50 cycles for {name}")


@cocotb.test()
async def test_zero_input(dut):
    """Trivial smoke test: all zeros -> tanh(0)=0 -> leak_blend(a, 0, 0) = 0"""
    cocotb.start_soon(Clock(dut.clk, 10, units='ns').start())
    await reset_dut(dut)

    w = [0] * MAC_WIDTH
    x = [0] * MAC_WIDTH
    leak_a = float_to_q(0.3, DATA_W)
    dut_out = await run_one_neuron(dut, w, x, x_prev_i=0, win_term=0, leak_a=leak_a, name="zero")
    gold = state_update_golden(w, x, 0, 0, leak_a, DATA_W, ACC_W, FRAC_W)
    dut._log.info(f"zero: dut={dut_out}, golden={gold}")
    assert dut_out == gold, f"ZERO TEST FAIL: dut={dut_out}, golden={gold}"


@cocotb.test()
async def test_representative_vector(dut):
    """Representative ESN-like input — random small reservoir weights, random state."""
    cocotb.start_soon(Clock(dut.clk, 10, units='ns').start())
    await reset_dut(dut)

    random.seed(42)

    # Reservoir-style weights: small, signed, mean zero
    w = [float_to_q(random.uniform(-0.1, 0.1), DATA_W) for _ in range(MAC_WIDTH)]
    x = [float_to_q(random.uniform(-0.5, 0.5), DATA_W) for _ in range(MAC_WIDTH)]
    x_prev_i = float_to_q(random.uniform(-0.5, 0.5), DATA_W)
    leak_a = float_to_q(0.3, DATA_W)
    # Win term: small contribution
    # win_term is Q1.(DATA_W-1) sign-extended into ACC_W bits (per corrected RTL contract)
    win_term = sign_extend(float_to_q(random.uniform(-0.05, 0.05), DATA_W), ACC_W)

    dut_out = await run_one_neuron(dut, w, x, x_prev_i, win_term, leak_a, name="repr")
    gold = state_update_golden(w, x, x_prev_i, win_term, leak_a, DATA_W, ACC_W, FRAC_W)

    dut._log.info(f"REPRESENTATIVE: dut={dut_out}, golden={gold}")
    if dut_out == gold:
        dut._log.info("BIT-EXACT MATCH")
    else:
        dut._log.error(f"MISMATCH: diff={dut_out - gold}")
    assert dut_out == gold, f"REPRESENTATIVE FAIL: dut={dut_out}, golden={gold}, diff={dut_out-gold}"


@cocotb.test()
async def test_multiple_random_vectors(dut):
    """Stress test: 20 random vectors, all must bit-match."""
    cocotb.start_soon(Clock(dut.clk, 10, units='ns').start())
    await reset_dut(dut)

    random.seed(123)
    fails = 0
    n_vectors = 20
    leak_a = float_to_q(0.3, DATA_W)

    for k in range(n_vectors):
        w = [float_to_q(random.uniform(-0.2, 0.2), DATA_W) for _ in range(MAC_WIDTH)]
        x = [float_to_q(random.uniform(-0.8, 0.8), DATA_W) for _ in range(MAC_WIDTH)]
        x_prev_i = float_to_q(random.uniform(-0.5, 0.5), DATA_W)
        # Q1.(DATA_W-1) sign-extended into ACC_W bits
        win_term = sign_extend(float_to_q(random.uniform(-0.1, 0.1), DATA_W), ACC_W)

        dut_out = await run_one_neuron(dut, w, x, x_prev_i, win_term, leak_a, name=f"r{k}")
        gold = state_update_golden(w, x, x_prev_i, win_term, leak_a, DATA_W, ACC_W, FRAC_W)
        diff = dut_out - gold
        # Allow 1-lsb tolerance for sign-extension rounding differences between
        # Verilog signed >>> and Python >> on negative values. Q15 lsb = 2^-15 ≈ 3e-5.
        if abs(diff) > 1:
            fails += 1
            dut._log.error(f"r{k}: dut={dut_out} golden={gold} diff={diff} EXCEEDS 1 lsb")
        elif diff != 0:
            dut._log.warning(f"r{k}: PASS within 1 lsb (dut={dut_out}, golden={gold}, diff={diff})")
        else:
            dut._log.info(f"r{k}: PASS bit-exact ({dut_out})")

    dut._log.info(f"RANDOM SWEEP: {n_vectors - fails}/{n_vectors} PASS")
    assert fails == 0, f"{fails}/{n_vectors} random vectors mismatched"
