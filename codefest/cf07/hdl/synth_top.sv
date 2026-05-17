// =============================================================================
// crossbar_mac.sv
// 4x4 binary-weight crossbar MAC unit
//
// out[j] = sum over i of W[i][j] * in[i],  W in {+1, -1}
//
// Inputs : 4 lines, 8-bit signed (in0..in3)
// Weights: 4x4 register, 1 bit per cell, packed into 16 bits.
//          w_reg[i*4 + j] = 1 means W[i][j] = +1
//          w_reg[i*4 + j] = 0 means W[i][j] = -1
// Outputs: 4 lines, 16-bit signed (plenty of headroom for 4 terms)
//
// Weights are loaded synchronously on load_w. Outputs are combinational.
// =============================================================================

module crossbar_mac (
    input  logic                clk,
    input  logic                rst_n,
    input  logic                load_w,
    input  logic [15:0]         w_in,
    input  logic signed [7:0]   in0, in1, in2, in3,
    output logic signed [15:0]  out0, out1, out2, out3
);

    // -------------------------------------------------------------------------
    // Weight register
    // -------------------------------------------------------------------------
    logic [15:0] w_reg;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            w_reg <= 16'b0;
        else if (load_w)
            w_reg <= w_in;
    end

    // -------------------------------------------------------------------------
    // Sign-extend each input to 16 bits once
    // -------------------------------------------------------------------------
    wire signed [15:0] x0 = {{8{in0[7]}}, in0};
    wire signed [15:0] x1 = {{8{in1[7]}}, in1};
    wire signed [15:0] x2 = {{8{in2[7]}}, in2};
    wire signed [15:0] x3 = {{8{in3[7]}}, in3};

    // -------------------------------------------------------------------------
    // Name each weight bit explicitly to avoid simulator bit-select issues
    // wij is the bit for row i, column j
    // -------------------------------------------------------------------------
    wire w00 = w_reg[ 0];  wire w01 = w_reg[ 1];  wire w02 = w_reg[ 2];  wire w03 = w_reg[ 3];
    wire w10 = w_reg[ 4];  wire w11 = w_reg[ 5];  wire w12 = w_reg[ 6];  wire w13 = w_reg[ 7];
    wire w20 = w_reg[ 8];  wire w21 = w_reg[ 9];  wire w22 = w_reg[10];  wire w23 = w_reg[11];
    wire w30 = w_reg[12];  wire w31 = w_reg[13];  wire w32 = w_reg[14];  wire w33 = w_reg[15];

    // -------------------------------------------------------------------------
    // Per-cell signed contribution: +x if bit=1, -x if bit=0
    // -------------------------------------------------------------------------
    wire signed [15:0] c00 = w00 ? x0 : -x0;
    wire signed [15:0] c10 = w10 ? x1 : -x1;
    wire signed [15:0] c20 = w20 ? x2 : -x2;
    wire signed [15:0] c30 = w30 ? x3 : -x3;

    wire signed [15:0] c01 = w01 ? x0 : -x0;
    wire signed [15:0] c11 = w11 ? x1 : -x1;
    wire signed [15:0] c21 = w21 ? x2 : -x2;
    wire signed [15:0] c31 = w31 ? x3 : -x3;

    wire signed [15:0] c02 = w02 ? x0 : -x0;
    wire signed [15:0] c12 = w12 ? x1 : -x1;
    wire signed [15:0] c22 = w22 ? x2 : -x2;
    wire signed [15:0] c32 = w32 ? x3 : -x3;

    wire signed [15:0] c03 = w03 ? x0 : -x0;
    wire signed [15:0] c13 = w13 ? x1 : -x1;
    wire signed [15:0] c23 = w23 ? x2 : -x2;
    wire signed [15:0] c33 = w33 ? x3 : -x3;

    // -------------------------------------------------------------------------
    // Column sums
    // -------------------------------------------------------------------------
    assign out0 = c00 + c10 + c20 + c30;
    assign out1 = c01 + c11 + c21 + c31;
    assign out2 = c02 + c12 + c22 + c32;
    assign out3 = c03 + c13 + c23 + c33;

endmodule
