"""
test_top.py — M4 K=64 accelerator cosim at N=1000, parameterized by DATA_W.

Weights / x / Win are preloaded into the lane SRAMs via $readmemh (one-time,
unmeasured load — the runner emits the hex files before simulation). The test
issues ONE start, measures the COMPUTE latency in cycles, then checks every
neuron's x_next against the bit-exact golden within 1 LSB (M2/M3 tolerance
basis). The measured cycle count drives the throughput numbers in bench/.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from golden_top import gen_network, state_update_top

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

DATA_W    = int(os.environ.get('DATA_W', 16))
MAC_WIDTH = int(os.environ.get('MAC_WIDTH', 16))
ACC_W     = int(os.environ.get('ACC_W', 40))
N         = int(os.environ.get('N_RESERVOIR', 1000))
SEED      = int(os.environ.get('SEED', 2026))
MASK_D    = (1 << DATA_W) - 1


def s_ext(v):
    return v - (1 << DATA_W) if v & (1 << (DATA_W - 1)) else v


@cocotb.test()
async def test_full_reservoir(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit='ns').start())

    net = gen_network(N, DATA_W, ACC_W, SEED)
    gold = state_update_top(net)

    # reset
    dut.rst_n.value = 0
    dut.start.value = 0
    dut.leak_a.value = net['leak_a'] & MASK_D
    dut.rd_addr.value = 0
    for _ in range(5):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)

    # one start for the whole N=1000 update
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    cyc = 0
    for _ in range(20000):
        await RisingEdge(dut.clk)
        cyc += 1
        if int(dut.done.value) == 1:
            break
    else:
        raise TimeoutError("done never asserted")

    measured = int(dut.cycles.value)
    dut._log.info(f"M4 DATA_W={DATA_W}: COMPUTE done, cycles={measured} "
                  f"(loop-counted {cyc})")

    # check every neuron (backdoor read of result SRAM)
    fails = 0
    worst = 0
    exact = 0
    for i in range(N):
        dv = s_ext(int(dut.xnext_mem[i].value) & MASK_D)
        diff = dv - gold[i]
        worst = max(worst, abs(diff))
        if diff == 0:
            exact += 1
        elif abs(diff) > 1:
            fails += 1
            if fails <= 8:
                dut._log.error(f"neuron {i}: dut={dv} gold={gold[i]} diff={diff}")

    dut._log.info(f"M4 RESULT DATA_W={DATA_W} N={N}: {exact}/{N} bit-exact, "
                  f"worst|diff|={worst} lsb, cycles_per_update={measured}")
    assert fails == 0, f"{fails}/{N} neurons exceeded 1-lsb tolerance"
    # machine-readable line for the runner to scrape
    dut._log.info(f"M4_MEASURE data_w={DATA_W} cycles={measured} "
                  f"exact={exact} worst={worst} N={N}")
    dut._log.info(f"M4 DATA_W={DATA_W} FULL RESERVOIR PASS")
