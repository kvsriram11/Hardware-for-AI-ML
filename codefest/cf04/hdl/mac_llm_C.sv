module mac_llm_C (
    input  logic              clk,
    input  logic              rst,
    input  logic signed [7:0] a,
    input  logic signed [7:0] b,
    output logic signed [31:0] out
);

    // Internal signal to hold the product of a and b
    // 8-bit * 8-bit signed results in a 16-bit signed value
    logic signed [15:0] product;

    // Combinational multiplication
    assign product = a * b;

    // Sequential accumulation logic
    always_ff @(posedge clk) begin
        if (rst) begin
            out <= 32'sd0;
        end else begin
            // Sign-extension of the product to 32 bits happens automatically 
            // in SystemVerilog when performing signed arithmetic.
            out <= out + product;
        end
    end

endmodule