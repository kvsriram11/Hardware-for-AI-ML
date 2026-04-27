import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

@cocotb.test()
async def test_mac_basic(dut):
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # Reset
    dut.rst.value = 1
    dut.a.value = 0
    dut.b.value = 0
    await RisingEdge(dut.clk)
    dut.rst.value = 0

    # Apply a=3, b=4 for 3 cycles, expect 12, 24, 36
    dut.a.value = 3
    dut.b.value = 4
    for expected in [12, 24, 36]:
        await RisingEdge(dut.clk)
        assert dut.out.value.signed_integer == expected, \
            f"Expected {expected}, got {dut.out.value.signed_integer}"

    # Assert reset
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    assert dut.out.value.signed_integer == 0, "Reset did not clear output"
    dut.rst.value = 0

    # Apply a=-5, b=2 for 2 cycles, expect -10, -20
    dut.a.value = -5
    dut.b.value = 2
    for expected in [-10, -20]:
        await RisingEdge(dut.clk)
        assert dut.out.value.signed_integer == expected, \
            f"Expected {expected}, got {dut.out.value.signed_integer}"

    cocotb.log.info("test_mac_basic PASSED")


@cocotb.test()
async def test_mac_overflow(dut):
    """
    Overflow behavior test for the 32-bit signed accumulator.

    The accumulator is 32-bit signed, so it holds values from
    -2147483648 to +2147483647 (i.e. -(2^31) to 2^31 - 1).

    We push it close to +2^31 - 1 then one step further to observe
    whether the design SATURATES (clamps at max) or WRAPS (rolls over
    to a large negative number).

    Expected result with plain Verilog addition (no saturation logic):
      The accumulator WRAPS — it does NOT saturate.
      e.g. 2147483647 + 127*127 = 2147483647 + 16129 = 2147499776
      which wraps to a NEGATIVE number: -2147467520

    This is documented behavior — the mac_correct.sv design uses
    standard 2's complement addition with no overflow guard.
    Saturation would require explicit comparison logic not present here.
    """
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())

    # Reset first
    dut.rst.value = 1
    dut.a.value = 0
    dut.b.value = 0
    await RisingEdge(dut.clk)
    dut.rst.value = 0

    # Use a=127, b=127 to accumulate +16129 per cycle (max INT8 product)
    # We need to reach near 2^31 - 1 = 2147483647
    # 2147483647 / 16129 = ~133,137 cycles — too many to step one by one
    # Instead: use a=127, b=1 (+127/cycle) and pre-load via many cycles,
    # OR just drive large values directly.
    #
    # Simplest approach: accumulate with a=127, b=127 for 133136 cycles
    # to get just below overflow, then one more cycle to trigger the wrap.
    #
    # For simulation speed we use cocotb's non-blocking loop.

    dut.a.value = 127
    dut.b.value = 127  # product = 16129 per cycle

    # Accumulate to just below 2^31 - 1
    # 133136 * 16129 = 2147418064  (below 2147483647)
    # 133137 * 16129 = 2147434193  (still below)
    # 133144 * 16129 = 2147547176  (above — wraps)
    # Find exact crossing: 2147483647 / 16129 = 133137.xxx
    # So after 133138 cycles accumulator should wrap

    cycles_to_near_max = 133137
    for _ in range(cycles_to_near_max):
        await RisingEdge(dut.clk)

    val_before = dut.out.value.signed_integer
    cocotb.log.info(f"Accumulator just before overflow: {val_before}")
    cocotb.log.info(f"2^31 - 1 = {2**31 - 1}")
    assert val_before > 0, "Accumulator should be large positive before overflow"
    assert val_before <= 2**31 - 1, "Should still be within signed 32-bit range"

    # One more cycle — this pushes past 2^31 - 1
    await RisingEdge(dut.clk)
    val_after = dut.out.value.signed_integer
    cocotb.log.info(f"Accumulator after overflow step: {val_after}")

    # Document the behavior
    if val_after < 0:
        cocotb.log.info(
            "BEHAVIOR: WRAPS — accumulator rolled over to negative. "
            "No saturation logic present in mac_correct.sv. "
            "This is standard 2's complement overflow behavior in Verilog."
        )
    elif val_after == 2**31 - 1:
        cocotb.log.info(
            "BEHAVIOR: SATURATES — accumulator clamped at 2^31-1. "
            "Design includes saturation logic."
        )
    else:
        cocotb.log.info(f"BEHAVIOR: Unexpected value {val_after}")

    # We expect WRAP (not saturate) since mac_correct.sv has no saturation
    assert val_after < 0, (
        f"Expected wrap-around to negative, got {val_after}. "
        f"If positive, design may be saturating — document accordingly."
    )

    cocotb.log.info("test_mac_overflow PASSED — wrap behavior confirmed and documented")
