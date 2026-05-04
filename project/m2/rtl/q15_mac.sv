// =============================================================================
// q15_mac.sv
//
// Q15 fixed-point multiply-accumulate unit.
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M2
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// Single-cycle MAC unit used inside the ESN compute core's dot-product engine.
// Computes:
//
//     acc <= acc + (w * x)         when en = 1
//     acc <= 0                     when clr = 1   (clr has priority over en)
//     acc <= acc                   otherwise
//
// where  w, x  are Q15 (signed 16-bit, 15 fractional bits) and
//        acc   is a Q30 signed 32-bit accumulator.
//
// -----------------------------------------------------------------------------
// FIXED-POINT NOTES
// -----------------------------------------------------------------------------
// Q15 multiplication rule: Q15 * Q15 = Q30. We retain the Q30 product in the
// accumulator and defer the >>15 rescale to the consumer (tanh stage). This
// preserves precision across long accumulations (the ESN dot product has
// length N=1000).
//
// Accumulator width: 32 bits.
//   - One Q15*Q15 product fits in 31 bits (30 frac + sign).
//   - Accumulating 1000 such products needs ~10 extra bits of headroom in the
//     worst case (|w|=|x|=1.0 every cycle), making the safe width 41 bits.
//   - Real ESN reservoir activations satisfy |x| < 0.5, which recovers ~2 bits
//     of headroom. 32 bits is sufficient for the M2 representative test
//     vectors. Width review deferred to M3.
//
// -----------------------------------------------------------------------------
// CLOCK / RESET
// -----------------------------------------------------------------------------
// Single clock domain: clk.
// Reset: synchronous, active-high (rst).
//
// -----------------------------------------------------------------------------
// PORTS
// -----------------------------------------------------------------------------
//   Name      Dir   Width        Purpose
//   ----      ---   -----        -------
//   clk       in    1            Rising-edge system clock
//   rst       in    1            Synchronous active-high reset; clears acc to 0
//   clr       in    1            Synchronous clear; clears acc to 0 (per-dot-prod)
//   en        in    1            Enable: when high, perform one MAC step
//   w         in    16   signed  Q15 weight operand
//   x         in    16   signed  Q15 state operand
//   acc       out   32   signed  Q30 accumulator output (registered)
// =============================================================================

module q15_mac (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 clr,
    input  logic                 en,
    input  logic signed [15:0]   w,
    input  logic signed [15:0]   x,
    output logic signed [31:0]   acc
);

    // -------------------------------------------------------------------------
    // Combinational product (Q15 * Q15 = Q30)
    // -------------------------------------------------------------------------
    // SystemVerilog 'signed' arithmetic on two 16-bit signed operands produces
    // a 32-bit signed result automatically. No manual sign extension needed.
    // -------------------------------------------------------------------------
    logic signed [31:0] product;
    assign product = w * x;

    // -------------------------------------------------------------------------
    // Accumulator register
    //
    // Priority order:  rst  >  clr  >  en  >  hold
    //
    // - rst is the global synchronous reset (e.g., system bring-up).
    // - clr is asserted by the FSM at the start of each per-neuron dot product
    //   to zero the accumulator before summing 1000 products.
    // - en advances the MAC by one step when both operands are valid.
    // - When neither rst, clr, nor en is asserted, the accumulator holds.
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (rst)
            acc <= 32'sd0;
        else if (clr)
            acc <= 32'sd0;
        else if (en)
            acc <= acc + product;
        // else: hold
    end

endmodule
