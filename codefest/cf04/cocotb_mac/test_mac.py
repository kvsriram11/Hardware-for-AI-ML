import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

async def tick(dut):
    """Wait one full clock cycle."""
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")   # 1 ns after posedge — FF output settled


async def reset_dut(dut):
    """Hold reset for two full cycles so out is guaranteed 0."""
    dut.rst.value = 1
    dut.a.value   = 0
    dut.b.value   = 0
    await tick(dut)
    await tick(dut)


def check(dut, expected, label):
    actual = dut.out.value.to_signed()
    if actual == expected:
        cocotb.log.info(f"PASS | {label:<28} | out = {actual}")
    else:
        raise AssertionError(
            f"FAIL | {label:<28} | expected {expected}, got {actual}"
        )


# ----------------------------------------------------------------
# Test 1 — basic MAC sequence
# ----------------------------------------------------------------
@cocotb.test()
async def test_mac_basic(dut):
    """
    Apply a=3, b=4 for 3 cycles, assert reset,
    then apply a=-5, b=2 for 2 cycles.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # --- Reset ---
    await reset_dut(dut)
    check(dut, 0, "after_reset")

    # --- Phase 1: a=3, b=4 for 3 cycles ---
    # Drive inputs on falling edge so they are stable at next posedge
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.a.value   = 3
    dut.b.value   = 4

    await tick(dut); check(dut,  12, "p1_cycle1 (exp:  12)")
    await tick(dut); check(dut,  24, "p1_cycle2 (exp:  24)")
    await tick(dut); check(dut,  36, "p1_cycle3 (exp:  36)")

    # --- Mid-sequence reset ---
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    dut.a.value   = 0
    dut.b.value   = 0

    await tick(dut); check(dut,   0, "mid_reset   (exp:   0)")

    # --- Phase 2: a=-5, b=2 for 2 cycles ---
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.a.value   = -5
    dut.b.value   =  2

    await tick(dut); check(dut, -10, "p2_cycle1 (exp: -10)")
    await tick(dut); check(dut, -20, "p2_cycle2 (exp: -20)")


# ----------------------------------------------------------------
# Test 2 — overflow / wrap-around behaviour
# ----------------------------------------------------------------
@cocotb.test()
async def test_mac_overflow(dut):
    """
    Drive accumulator to overflow using a=127, b=127 (16129/cycle).
    Checks that the design wraps (two's complement), not saturates.
    """
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await reset_dut(dut)

    # Drive max positive INT8 on falling edge
    await FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.a.value   = 127
    dut.b.value   = 127

    product   = 127 * 127       # 16129
    MAX_INT32 = (1 << 31) - 1  # 2147483647

    # Run just past overflow point
    cycles = (MAX_INT32 // product) + 2

    # Track expected value with same 32-bit signed wrap as DUT
    accumulated = 0
    for _ in range(cycles):
        await tick(dut)
        accumulated += product
        accumulated  = (accumulated + (1 << 31)) % (1 << 32) - (1 << 31)

    actual = dut.out.value.to_signed()

    cocotb.log.info(
        f"After {cycles} cycles: DUT = {actual}, model = {accumulated}"
    )

    if actual == accumulated:
        cocotb.log.info(
            "PASS | overflow_wrap | "
            "Accumulator wraps (two's complement) — no saturation."
        )
    else:
        raise AssertionError(
            f"FAIL | overflow_wrap | expected {accumulated}, got {actual}"
        )
