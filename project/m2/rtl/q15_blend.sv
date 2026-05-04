// =============================================================================
// q15_blend.sv
//
// Q15 leak-rate blend stage of the ESN compute core.
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M2
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// Computes the leak-rate blend that finishes the ESN reservoir state update:
//
//     x_new = (1 - a) * x_prev + a * tanh_out
//
// where  x_prev, tanh_out, leak_rate (a)  are all Q15 (signed 16-bit), and
//        x_new                            is also Q15.
//
// This module is purely combinational. It has two Q15 multipliers in parallel
// and one final adder. The output is saturation-clamped to [Q15_NEG_ONE,
// Q15_POS_ONE] for robustness against boundary effects.
//
// -----------------------------------------------------------------------------
// FIXED-POINT ARITHMETIC
// -----------------------------------------------------------------------------
// Q15 * Q15 = Q30. Each multiply produces a 32-bit signed result. Since both
// (1 - a) and a are non-negative and sum to exactly 1.0, the final sum
// (1-a)*x_prev + a*tanh_out is bounded by the max of |x_prev| and |tanh_out|.
// Both inputs are bounded to [-1, +1) by the upstream tanh stage and reservoir
// dynamics, so no overflow can occur in the sum.
//
// Q30 → Q15 conversion: arithmetic right shift by 15 on the signed sum.
//
// -----------------------------------------------------------------------------
// LEAK RATE INTERPRETATION
// -----------------------------------------------------------------------------
// leak_rate is a Q15 unsigned-style value in the range [0, +1.0). Conceptual
// values for the Mackey-Glass benchmark:
//
//   leak_rate = 0x0000  → a = 0.0  (no leak, full update from tanh_out)
//                          NOTE: this would NOT compute x_new = tanh_out,
//                          it computes x_new = (1)*x_prev + (0)*tanh_out
//                          which holds x_prev. Matches ESN convention where
//                          a controls the "speed" of state update.
//   leak_rate = 0x2666  → a = 0.3  (project SW baseline value)
//   leak_rate = 0x4000  → a = 0.5
//   leak_rate = 0x7FFF  → a ≈ 1.0  (full update, x_new ≈ tanh_out)
//
// -----------------------------------------------------------------------------
// CLOCK / RESET
// -----------------------------------------------------------------------------
// Combinational. No clock, no reset.
//
// -----------------------------------------------------------------------------
// PORTS
// -----------------------------------------------------------------------------
//   Name       Dir   Width        Purpose
//   ----       ---   -----        -------
//   x_prev     in    16   signed  Previous reservoir state in Q15
//   tanh_out   in    16   signed  PWL tanh result in Q15 (from q15_tanh)
//   leak_rate  in    16   signed  Q15 leak rate a, in [0, +1.0)
//   x_new      out   16   signed  Updated reservoir state in Q15
// =============================================================================

module q15_blend (
    input  logic signed [15:0]   x_prev,
    input  logic signed [15:0]   tanh_out,
    input  logic signed [15:0]   leak_rate,
    output logic signed [15:0]   x_new
);

    // -------------------------------------------------------------------------
    // Q15 saturation constants
    // -------------------------------------------------------------------------
    localparam logic signed [15:0] Q15_POS_ONE = 16'sh7FFF;   // ≈+1.0
    localparam logic signed [15:0] Q15_NEG_ONE = 16'sh8000;   //  -1.0
    localparam logic signed [15:0] Q15_ONE     = 16'sh7FFF;   // ≈+1.0 reference

    // -------------------------------------------------------------------------
    // Compute (1 - a) — combinational subtract
    //
    // For leak_rate up to 0x7FFF, (Q15_ONE - leak_rate) ranges from 0 to
    // 0x7FFF and is non-negative. Result fits in 16 bits.
    // -------------------------------------------------------------------------
    logic signed [15:0] one_minus_a;
    assign one_minus_a = Q15_ONE - leak_rate;

    // -------------------------------------------------------------------------
    // Two parallel Q15 * Q15 multiplies (each yields Q30 signed 32-bit)
    // -------------------------------------------------------------------------
    logic signed [31:0] term_prev;     // (1 - a) * x_prev  in Q30
    logic signed [31:0] term_new;      //   a     * tanh_out in Q30

    assign term_prev = one_minus_a * x_prev;
    assign term_new  = leak_rate   * tanh_out;

    // -------------------------------------------------------------------------
    // Sum in Q30, then convert back to Q15 via signed arithmetic right shift.
    // The sum is guaranteed to fit in 32 bits because (1-a) + a = 1 and both
    // operand magnitudes are ≤ 1.
    // -------------------------------------------------------------------------
    logic signed [31:0] sum_q30;
    logic signed [31:0] sum_shr15;

    assign sum_q30   = term_prev + term_new;
    assign sum_shr15 = sum_q30 >>> 15;

    // -------------------------------------------------------------------------
    // Saturate to Q15 range. Protects against boundary overshoot from
    // multiply truncation when both inputs are near full-scale.
    // -------------------------------------------------------------------------
    always_comb begin
        if (sum_shr15 > 32'sh00007FFF)
            x_new = Q15_POS_ONE;
        else if (sum_shr15 < 32'shFFFF8000)  // sign-extended -32768
            x_new = Q15_NEG_ONE;
        else
            x_new = sum_shr15[15:0];
    end

endmodule
