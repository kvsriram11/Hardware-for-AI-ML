module mac_llm_A (
    input  logic                clk,
    input  logic                rst,
    input  logic signed [7:0]   a,
    input  logic signed [7:0]   b,
    output logic signed [31:0]  out
);

    // Intermediate wire for the signed product (8-bit × 8-bit = 16-bit)
    logic signed [15:0] product;

    // Combinational product — no extra register, no latency
    assign product = a * b;

    always_ff @(posedge clk) begin
        if (rst)
            out <= 32'sd0;
        else
            out <= out + {{16{product[15]}}, product};
    end

endmodule