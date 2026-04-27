`timescale 1ns/1ps

module mac_tb_gm;

    // Signal Declarations
    logic        clk;
    logic        rst;
    logic signed [7:0]  a;
    logic signed [7:0]  b;
    logic signed [31:0] out;

    // Instantiate the Unit Under Test (UUT)
    mac_llm_C uut (
        .clk(clk),
        .rst(rst),
        .a(a),
        .b(b),
        .out(out)
    );

    // Clock Generation: 10ns period (100MHz)
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Stimulus Process
    initial begin
        // Initialize Inputs
        rst = 1;
        a = 0;
        b = 0;

        // Hold reset for 2 cycles to ensure a clean start
        repeat(2) @(posedge clk);
        
        // Release reset
        @(posedge clk);
        rst <= 0;

        // Task 1: Apply [a=3, b=4] for 3 cycles
        // Expected accumulation: 12 -> 24 -> 36
        a <= 8'sd3;
        b <= 8'sd4;
        repeat(3) @(posedge clk);

        // Task 2: Assert reset
        // This will clear 'out' on the next rising edge
        rst <= 1;
        @(posedge clk);
        rst <= 0;

        // Task 3: Apply [a=-5, b=2] for 2 cycles
        // Expected accumulation: -10 -> -20
        a <= -8'sd5;
        b <= 8'sd2;
        repeat(2) @(posedge clk);

        // End Simulation
        #10;
        $finish;
    end

    // Optional: Monitor changes in the console
    initial begin
        $monitor("Time=%0t | rst=%b | a=%d | b=%d | out=%d", 
                 $time, rst, a, b, out);
    end

endmodule