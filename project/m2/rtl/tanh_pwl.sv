//==========================================================================
// tanh_pwl.sv — 4-segment piecewise-linear tanh, parameterized DATA_W.
//
// Input  : signed ACC_W pre-activation in Q1.(DATA_W-1) format
//          (FRAC_W = DATA_W-1 fractional bits, low ACC_W bits used)
// Output : signed DATA_W activation in same Q1.(DATA_W-1) format
//
// Approximation:
//   x <= -2.0        : -1+lsb       (saturate)
//   -2 < x <= -1     : x/4 - 0.5
//   -1 < x <  +1     : x/2
//   +1 <= x <  +2    : x/4 + 0.5
//   x >= +2.0        : +1-lsb       (saturate)
//
// Input and output share the same fractional-bit count, so the linear
// segments are pure arithmetic right shifts followed by truncation to
// the low DATA_W bits (the value is bounded by the segment range, so
// the upper bits are pure sign extension and are dropped safely).
//
// Reset: active-low sync. Single clock. Latency: 1 cycle.
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module tanh_pwl #(
    parameter int DATA_W = 16,
    parameter int ACC_W  = 40,
    parameter int FRAC_W = 15
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       en,
    input  wire signed [ACC_W-1:0]    pre_in,
    output reg  signed [DATA_W-1:0]   act_out
);
    localparam signed [DATA_W-1:0] SAT_HI = {1'b0, {(DATA_W-1){1'b1}}};
    localparam signed [DATA_W-1:0] SAT_LO = {1'b1, {(DATA_W-1){1'b0}}} + 1'b1;

    // Thresholds: 1.0 and 2.0 in Q-format, sign-extended to ACC_W
    localparam signed [ACC_W-1:0] X_NEG2 = -($signed({{(ACC_W-FRAC_W-2){1'b0}}, 2'd2, {FRAC_W{1'b0}}}));
    localparam signed [ACC_W-1:0] X_NEG1 = -($signed({{(ACC_W-FRAC_W-2){1'b0}}, 2'd1, {FRAC_W{1'b0}}}));
    localparam signed [ACC_W-1:0] X_POS1 =  $signed({{(ACC_W-FRAC_W-2){1'b0}}, 2'd1, {FRAC_W{1'b0}}});
    localparam signed [ACC_W-1:0] X_POS2 =  $signed({{(ACC_W-FRAC_W-2){1'b0}}, 2'd2, {FRAC_W{1'b0}}});

    localparam signed [DATA_W-1:0] HALF_OUT = {2'b01, {(DATA_W-2){1'b0}}};

    reg signed [ACC_W-1:0] shifted;
    reg signed [DATA_W-1:0] y_q;
    always @(*) begin
        if (pre_in <= X_NEG2) begin
            shifted = '0;  // unused but keep tools quiet
            y_q = SAT_LO;
        end else if (pre_in <= X_NEG1) begin
            shifted = pre_in >>> 2;
            y_q = shifted[DATA_W-1:0] - HALF_OUT;
        end else if (pre_in < X_POS1) begin
            shifted = pre_in >>> 1;
            y_q = shifted[DATA_W-1:0];
        end else if (pre_in < X_POS2) begin
            shifted = pre_in >>> 2;
            y_q = shifted[DATA_W-1:0] + HALF_OUT;
        end else begin
            shifted = '0;
            y_q = SAT_HI;
        end
    end

    always @(posedge clk) begin
        if (!rst_n)    act_out <= '0;
        else if (en)   act_out <= y_q;
    end
endmodule
`default_nettype wire
