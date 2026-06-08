//==========================================================================
// leak_blend.sv — x_next = (1-a)*x_prev + a*z
// Q-format: a is Q1.(DATA_W-1), x_prev/z/x_next are Q1.(DATA_W-1).
// Reset: active-low sync. Single clock. 1 cycle latency.
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module leak_blend #(
    parameter int DATA_W = 16
) (
    input  wire                      clk,
    input  wire                      rst_n,
    input  wire                      en,
    input  wire signed [DATA_W-1:0]  a,
    input  wire signed [DATA_W-1:0]  x_prev,
    input  wire signed [DATA_W-1:0]  z,
    output reg  signed [DATA_W-1:0]  x_next
);
    wire signed [DATA_W-1:0] one_minus_a = $signed({1'b0, {(DATA_W-1){1'b1}}}) - a; // ~1.0 - a
    wire signed [2*DATA_W-1:0] term1 = one_minus_a * x_prev;
    wire signed [2*DATA_W-1:0] term2 = a * z;
    wire signed [2*DATA_W-1:0] sum   = term1 + term2;
    wire signed [DATA_W-1:0]   sum_q = sum[2*DATA_W-2 -: DATA_W];  // back to Q1.(DATA_W-1)
    always_ff @(posedge clk) begin
        if (!rst_n)   x_next <= '0;
        else if (en)  x_next <= sum_q;
    end
endmodule
`default_nettype wire
