//==========================================================================
// mac_array.sv — MAC_WIDTH-wide parallel MAC array (parameterized precision)
// DATA_W={16,8,4}. Reset: active-low sync. Single clock domain.
// Pipeline: 1-stage mul, 1-stage reduce, 1-stage accumulate = 3 stages.
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module mac_array #(
    parameter int DATA_W    = 16,
    parameter int MAC_WIDTH = 16,
    parameter int ACC_W     = 40
) (
    input  wire                                 clk,
    input  wire                                 rst_n,
    input  wire                                 en,        // drains pipeline (stages 2,3)
    input  wire                                 mul_en,    // latches new products (stage 1)
    input  wire signed [MAC_WIDTH*DATA_W-1:0]   w_in,
    input  wire signed [MAC_WIDTH*DATA_W-1:0]   x_in,
    input  wire                                 acc_clr,
    output reg  signed [ACC_W-1:0]              sum_out
);
    // Stage 1: parallel multiply, products stored sign-extended to ACC_W
    // (sign extension happens at the same time as the multiply so the
    // adder tree never has to do a constant select inside the loop)
    reg signed [ACC_W-1:0] prod_ext_q [0:MAC_WIDTH-1];
    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            for (i = 0; i < MAC_WIDTH; i = i + 1) prod_ext_q[i] <= '0;
        end else if (mul_en) begin
            for (i = 0; i < MAC_WIDTH; i = i + 1) begin
                // Sign-extend each lane to ACC_W *before* the multiply so the
                // product is computed at full width. Wrapping the product in a
                // single $signed() instead would force a self-determined
                // DATA_W-wide context and truncate the result to DATA_W bits.
                prod_ext_q[i] <=
                    $signed({{(ACC_W-DATA_W){w_in[i*DATA_W+DATA_W-1]}},
                             w_in[i*DATA_W +: DATA_W]})
                  * $signed({{(ACC_W-DATA_W){x_in[i*DATA_W+DATA_W-1]}},
                             x_in[i*DATA_W +: DATA_W]});
            end
        end else begin
            // Hold products at zero when not multiplying so they don't
            // accumulate stale values during the drain cycles.
            for (i = 0; i < MAC_WIDTH; i = i + 1) prod_ext_q[i] <= '0;
        end
    end

    // Stage 2: adder tree (operating on already-extended signed accumulators)
    reg signed [ACC_W-1:0] tree_q;
    integer j;
    reg signed [ACC_W-1:0] tree_sum;
    always @(*) begin
        tree_sum = '0;
        for (j = 0; j < MAC_WIDTH; j = j + 1) begin
            tree_sum = tree_sum + prod_ext_q[j];
        end
    end
    always @(posedge clk) begin
        if (!rst_n) tree_q <= '0;
        else if (en) tree_q <= tree_sum;
    end

    // Stage 3: accumulate
    always @(posedge clk) begin
        if (!rst_n)       sum_out <= '0;
        else if (acc_clr) sum_out <= '0;
        else if (en)      sum_out <= sum_out + tree_q;
    end
endmodule
`default_nettype wire
