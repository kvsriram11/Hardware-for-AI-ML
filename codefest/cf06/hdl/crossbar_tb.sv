// =============================================================================
// crossbar_tb.sv
// Testbench for crossbar_mac
//
// Loaded weights (row major):
//   row 0: [ 1, -1,  1, -1]
//   row 1: [ 1,  1, -1, -1]
//   row 2: [-1,  1,  1, -1]
//   row 3: [-1, -1, -1,  1]
//
// Input: [10, 20, 30, 40]
// Expected output (hand-calculated): [-40, 0, -20, -20]
// =============================================================================
`timescale 1ns/1ps

module crossbar_tb;

    logic                clk;
    logic                rst_n;
    logic                load_w;
    logic [15:0]         w_in;
    logic signed [7:0]   in0, in1, in2, in3;
    logic signed [15:0]  out0, out1, out2, out3;

    // DUT
    crossbar_mac dut (
        .clk    (clk),
        .rst_n  (rst_n),
        .load_w (load_w),
        .w_in   (w_in),
        .in0    (in0), .in1(in1), .in2(in2), .in3(in3),
        .out0   (out0), .out1(out1), .out2(out2), .out3(out3)
    );

    // -------------------------------------------------------------------------
    // Clock: 10 ns period
    // -------------------------------------------------------------------------
    initial clk = 0;
    always #5 clk = ~clk;

    // -------------------------------------------------------------------------
    // Helper: pack one row of {+1,-1} into 4 bits (col 0 = bit 0 of the row)
    // Returned value is shifted into the right slot of w_in by the caller
    // -------------------------------------------------------------------------
    function automatic logic [3:0] pack_row(
        input int w0, input int w1, input int w2, input int w3
    );
        pack_row[0] = (w0 == 1) ? 1'b1 : 1'b0;
        pack_row[1] = (w1 == 1) ? 1'b1 : 1'b0;
        pack_row[2] = (w2 == 1) ? 1'b1 : 1'b0;
        pack_row[3] = (w3 == 1) ? 1'b1 : 1'b0;
    endfunction

    integer errors;

    initial begin
        // ---------------- reset ----------------
        errors = 0;
        rst_n  = 1'b0;
        load_w = 1'b0;
        w_in   = 16'b0;
        in0    = 8'sd0;
        in1    = 8'sd0;
        in2    = 8'sd0;
        in3    = 8'sd0;
        #12;
        rst_n  = 1'b1;

        // ---------------- pack weights ----------------
        // w_in layout: bits [3:0] = row 0, [7:4] = row 1, [11:8] = row 2, [15:12] = row 3
        w_in[ 3: 0] = pack_row( 1, -1,  1, -1);
        w_in[ 7: 4] = pack_row( 1,  1, -1, -1);
        w_in[11: 8] = pack_row(-1,  1,  1, -1);
        w_in[15:12] = pack_row(-1, -1, -1,  1);

        // ---------------- load weights ----------------
        load_w = 1'b1;
        @(posedge clk);
        #1;
        load_w = 1'b0;

        // ---------------- apply inputs ----------------
        in0 = 8'sd10;
        in1 = 8'sd20;
        in2 = 8'sd30;
        in3 = 8'sd40;

        #1;  // let combinational logic settle

        $display("------------------------------------------------------------");
        $display(" 4x4 binary-weight crossbar MAC simulation");
        $display("------------------------------------------------------------");
        $display(" Inputs : in = [%0d, %0d, %0d, %0d]", in0, in1, in2, in3);
        $display(" Weights (row major):");
        $display("   row 0:  +1  -1  +1  -1");
        $display("   row 1:  +1  +1  -1  -1");
        $display("   row 2:  -1  +1  +1  -1");
        $display("   row 3:  -1  -1  -1  +1");
        $display(" Packed weight word w_in = 16'h%h", w_in);
        $display("------------------------------------------------------------");

        check_output(0, out0, -16'sd40);
        check_output(1, out1,  16'sd0);
        check_output(2, out2, -16'sd20);
        check_output(3, out3, -16'sd20);

        $display("------------------------------------------------------------");
        if (errors == 0)
            $display(" RESULT: All 4 outputs match expected values. Test PASSED.");
        else
            $display(" RESULT: %0d mismatch(es). Test FAILED.", errors);
        $display("------------------------------------------------------------");

        #20;
        $finish;
    end

    // -------------------------------------------------------------------------
    // Compare one output against its expected value
    // -------------------------------------------------------------------------
    task automatic check_output(
        input int                  j,
        input logic signed [15:0]  got,
        input logic signed [15:0]  exp_val
    );
        if (got === exp_val)
            $display(" out[%0d] = %0d   expected = %0d   PASS", j, got, exp_val);
        else begin
            $display(" out[%0d] = %0d   expected = %0d   FAIL", j, got, exp_val);
            errors = errors + 1;
        end
    endtask

endmodule
