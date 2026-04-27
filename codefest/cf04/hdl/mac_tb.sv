`timescale 1ns/1ps

module mac_tb_cl;

    // ----------------------------------------------------------------
    // Signal declarations
    // ----------------------------------------------------------------
    logic                clk;
    logic                rst;
    logic signed [7:0]   a;
    logic signed [7:0]   b;
    logic signed [31:0]  out;

    // ----------------------------------------------------------------
    // DUT instantiation
    // ----------------------------------------------------------------
    mac_llm_A dut (
        .clk (clk),
        .rst (rst),
        .a   (a),
        .b   (b),
        .out (out)
    );

    // ----------------------------------------------------------------
    // Clock generation — 10ns period (100 MHz)
    // ----------------------------------------------------------------
    initial clk = 0;
    always #5 clk = ~clk;

    // ----------------------------------------------------------------
    // Task: check output and report PASS / FAIL
    // ----------------------------------------------------------------
    task automatic check(
        input logic signed [31:0] expected,
        input string              label
    );
        #1;
        if (out === expected)
            $display("PASS | %-24s | out = %0d", label, out);
        else
            $display("FAIL | %-24s | expected %0d, got %0d",
                     label, expected, out);
    endtask

    // ----------------------------------------------------------------
    // Stimulus
    // ----------------------------------------------------------------
    initial begin

        // --- Initialise ---
        rst = 1;
        a   = '0;
        b   = '0;

        // ============================================================
        // Reset check
        // ============================================================
        @(posedge clk);
        $display("--- Reset applied ---");
        check(32'sd0, "after_reset");

        // ============================================================
        // Phase 1: a=3, b=4 for 3 cycles
        //   cycle 1 → out = 12
        //   cycle 2 → out = 24
        //   cycle 3 → out = 36
        // ============================================================
        rst = 0;
        a   =  8'sd3;
        b   =  8'sd4;

        $display("--- Phase 1: a=3, b=4 (3 cycles) ---");
        @(posedge clk); check(32'sd12, "p1_cycle1 (exp: 12)");
        @(posedge clk); check(32'sd24, "p1_cycle2 (exp: 24)");
        @(posedge clk); check(32'sd36, "p1_cycle3 (exp: 36)");

        // ============================================================
        // Mid-sequence reset
        // ============================================================
        rst = 1;
        a   = '0;
        b   = '0;

        $display("--- Reset asserted mid-sequence ---");
        @(posedge clk); check(32'sd0, "mid_reset (exp: 0)");

        // ============================================================
        // Phase 2: a=−5, b=2 for 2 cycles
        //   cycle 1 → out = −10
        //   cycle 2 → out = −20
        // ============================================================
        rst = 0;
        a   = -8'sd5;
        b   =  8'sd2;

        $display("--- Phase 2: a=-5, b=2 (2 cycles) ---");
        @(posedge clk); check(-32'sd10, "p2_cycle1 (exp: -10)");
        @(posedge clk); check(-32'sd20, "p2_cycle2 (exp: -20)");

        // ============================================================
        $display("--- Simulation complete ---");
        $finish;
    end

endmodule