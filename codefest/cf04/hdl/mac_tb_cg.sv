`timescale 1ns/1ps

module mac_tb_cg;

    logic clk;
    logic rst;
    logic signed [7:0] a;
    logic signed [7:0] b;
    logic signed [31:0] out;

    mac_llm_B dut (
        .clk (clk),
        .rst (rst),
        .a   (a),
        .b   (b),
        .out (out)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        a   = 8'sd0;
        b   = 8'sd0;

        // Hold reset for one clock cycle
        @(negedge clk);
        rst = 1'b0;

        // Apply a = 3, b = 4 for 3 cycles
        @(negedge clk);
        a = 8'sd3;
        b = 8'sd4;

        @(posedge clk); // out = 12
        @(posedge clk); // out = 24
        @(posedge clk); // out = 36

        // Assert synchronous reset for one clock cycle
        @(negedge clk);
        rst = 1'b1;

        @(posedge clk); // out = 0

        @(negedge clk);
        rst = 1'b0;
        a = -8'sd5;
        b = 8'sd2;

        @(posedge clk); // out = -10
        @(posedge clk); // out = -20

        // Wait a little so final value is visible in waveform
        #10;

        $stop;
    end

endmodule