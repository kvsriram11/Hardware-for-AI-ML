// =============================================================================
// q15_tanh.sv
//
// Q15 piecewise-linear tanh approximation (7-segment).
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M2
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// Maps a Q30 signed 32-bit accumulator value to a Q15 signed 16-bit output
// using a 7-segment piecewise-linear approximation of tanh(x). Combinational;
// no internal state.
//
// -----------------------------------------------------------------------------
// PWL DEFINITION  (x = acc as Q30 real, y = tanh_out as Q15 real)
// -----------------------------------------------------------------------------
//
//        x ≤ -2.0       :  y = -1.0
//   -2.0 < x ≤ -1.0     :  y = 0.25·x − 0.5
//   -1.0 < x ≤ -0.5     :  y = 0.625·x − 0.1875
//   -0.5 < x < +0.5     :  y = x                  (identity, central region)
//   +0.5 ≤ x < +1.0     :  y = 0.625·x + 0.1875
//   +1.0 ≤ x < +2.0     :  y = 0.25·x + 0.5
//        x ≥ +2.0       :  y = +1.0
//
// Reference: Amin, Curtis & Hayes-Gill, "Piecewise Linear Approximation
// Applied to Nonlinear Function of a Neural Network", IEE Proc.-Circuits
// Devices Syst. 144(6), 1997.
//
// Max abs error vs true tanh: ~0.073 over x ∈ [-3, +3].
// MAE: ~0.026.
// All slopes are dyadic fractions, so the PWL reduces to shifts and adds —
// no multipliers required.
//
// -----------------------------------------------------------------------------
// SIGN-EXTENSION DESIGN NOTE
// -----------------------------------------------------------------------------
// SystemVerilog bit-selects (e.g., acc[31:17]) are UNSIGNED expressions even
// when the parent vector is declared 'signed'. Assigning such a slice to a
// signed variable of larger width causes ZERO-extension, not sign-extension,
// which silently corrupts negative values.
//
// To get arithmetic-right-shift semantics on the Q30 accumulator, we use
// the SystemVerilog signed-arithmetic-right-shift operator (>>>) on the
// signed accumulator, then slice the low Q15-width bits. This guarantees
// proper sign extension regardless of input polarity.
//
// -----------------------------------------------------------------------------
// CLOCK / RESET
// -----------------------------------------------------------------------------
// Combinational. No clock, no reset.
//
// -----------------------------------------------------------------------------
// PORTS
// -----------------------------------------------------------------------------
//   Name      Dir   Width        Purpose
//   ----      ---   -----        -------
//   acc       in    32   signed  Q30 accumulator value (from q15_mac)
//   tanh_out  out   16   signed  Q15 PWL-tanh approximation
// =============================================================================

module q15_tanh (
    input  logic signed [31:0]   acc,
    output logic signed [15:0]   tanh_out
);

    // -------------------------------------------------------------------------
    // Q30 boundary constants (signed 32-bit)
    // -------------------------------------------------------------------------
    localparam logic signed [31:0] Q30_HALF      = 32'sh20000000;   // +0.5
    localparam logic signed [31:0] Q30_NEG_HALF  = 32'shE0000000;   // -0.5
    localparam logic signed [31:0] Q30_ONE       = 32'sh40000000;   // +1.0
    localparam logic signed [31:0] Q30_NEG_ONE   = 32'shC0000000;   // -1.0
    localparam logic signed [31:0] Q30_TWO_MARK  = 32'sh7FFFFFFF;   // +2.0 (max)
    localparam logic signed [31:0] Q30_NEGTWO    = 32'sh80000000;   // -2.0

    // -------------------------------------------------------------------------
    // Q15 output constants (signed 16-bit)
    // -------------------------------------------------------------------------
    localparam logic signed [15:0] Q15_POS_ONE   = 16'sh7FFF;       // ≈+1.0
    localparam logic signed [15:0] Q15_NEG_ONE   = 16'sh8000;       // -1.0
    localparam logic signed [15:0] Q15_HALF      = 16'sh4000;       //  0.5
    localparam logic signed [15:0] Q15_NEG_HALF  = 16'shC000;       // -0.5
    localparam logic signed [15:0] Q15_3_16      = 16'sh0C00;       //  0.1875
    localparam logic signed [15:0] Q15_NEG_3_16  = 16'shF400;       // -0.1875

    // -------------------------------------------------------------------------
    // Slope helpers — built from arithmetic right shifts of the SIGNED acc.
    //
    //   x_q15        =  x          = acc >>> 15  (Q30 → Q15)
    //   x_half_q15   =  0.5  · x   = acc >>> 16
    //   x_quarter_q15=  0.25 · x   = acc >>> 17
    //   x_eighth_q15 =  0.125· x   = acc >>> 18
    //
    // The >>> operator performs arithmetic (sign-preserving) right shift on
    // signed operands, so negative values shift correctly. We then truncate
    // to the low 16 bits, which gives the correct Q15 representation.
    // -------------------------------------------------------------------------
    logic signed [31:0] acc_shr15;
    logic signed [31:0] acc_shr16;
    logic signed [31:0] acc_shr17;
    logic signed [31:0] acc_shr18;

    assign acc_shr15 = acc >>> 15;
    assign acc_shr16 = acc >>> 16;
    assign acc_shr17 = acc >>> 17;
    assign acc_shr18 = acc >>> 18;

    logic signed [15:0] x_q15;
    logic signed [15:0] x_half_q15;
    logic signed [15:0] x_quarter_q15;
    logic signed [15:0] x_eighth_q15;

    assign x_q15         = acc_shr15[15:0];
    assign x_half_q15    = acc_shr16[15:0];
    assign x_quarter_q15 = acc_shr17[15:0];
    assign x_eighth_q15  = acc_shr18[15:0];

    // 0.625·x = 0.5·x + 0.125·x
    logic signed [15:0] x_5_8_q15;
    assign x_5_8_q15 = x_half_q15 + x_eighth_q15;

    // -------------------------------------------------------------------------
    // PWL selector
    // -------------------------------------------------------------------------
    always_comb begin
        if (acc >= Q30_TWO_MARK) begin
            // x ≥ +2.0 → +1.0
            tanh_out = Q15_POS_ONE;
        end
        else if (acc >= Q30_ONE) begin
            // +1.0 ≤ x < +2.0 → 0.25·x + 0.5
            tanh_out = x_quarter_q15 + Q15_HALF;
        end
        else if (acc >= Q30_HALF) begin
            // +0.5 ≤ x < +1.0 → 0.625·x + 0.1875
            tanh_out = x_5_8_q15 + Q15_3_16;
        end
        else if (acc > Q30_NEG_HALF) begin
            // -0.5 < x < +0.5 → identity
            tanh_out = x_q15;
        end
        else if (acc > Q30_NEG_ONE) begin
            // -1.0 < x ≤ -0.5 → 0.625·x − 0.1875
            tanh_out = x_5_8_q15 + Q15_NEG_3_16;
        end
        else if (acc > Q30_NEGTWO) begin
            // -2.0 < x ≤ -1.0 → 0.25·x − 0.5
            tanh_out = x_quarter_q15 + Q15_NEG_HALF;
        end
        else begin
            // x ≤ -2.0 → -1.0
            tanh_out = Q15_NEG_ONE;
        end
    end

endmodule