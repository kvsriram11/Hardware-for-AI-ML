//==========================================================================
// wave_tb.sv — tiny standalone harness to produce the M4 annotated waveform.
//
// cocotb's --waves injects a full $dumpvars(0, top) (every lane's internals,
// ~85 MB VCD). This harness instead lets top.sv's own enumerated $dumpvars
// (control signals + lane-0 mirrors only) run under a plain iverilog/vvp,
// yielding a small VCD of exactly the signals the waveform needs.
//
// Result correctness is already proven by tb/m4/test_top.py; this run only
// exercises the FSM timing for the picture. Weights/x are the $readmemh files
// the runner emitted (DATA_W=16) — present in tb/m4/.
//==========================================================================
`timescale 1ns/1ps
module wave_tb;
    localparam int DATA_W = 16, N = 1000;
    logic clk = 0, rst_n = 0, start = 0;
    logic signed [DATA_W-1:0] leak_a;
    logic busy, done;
    logic [31:0] cycles;
    logic [$clog2(N+1)-1:0] rd_addr = 0;
    wire signed [DATA_W-1:0] rd_data;

    top #(.DATA_W(DATA_W), .MAC_WIDTH(16), .ACC_W(40), .FRAC_W(15),
          .K(64), .N(N)) dut (
        .clk(clk), .rst_n(rst_n), .start(start), .leak_a(leak_a),
        .busy(busy), .done(done), .cycles(cycles),
        .rd_addr(rd_addr), .rd_data(rd_data)
    );

    always #5 clk = ~clk;   // 100 MHz

    initial begin
        leak_a = 16'sd9830;            // 0.3 in Q15
        repeat (5) @(posedge clk);
        @(posedge clk) #1 rst_n = 1;   // drive stimulus 1ns AFTER the edge so the
        @(posedge clk) #1 start = 1;   // DUT samples stable values (no NBA race)
        @(posedge clk) #1 start = 0;
        wait (done == 1'b1);
        repeat (4) @(posedge clk);
        $display("wave_tb: done, cycles=%0d", cycles);
        $finish;
    end

    // watchdog + periodic status
    initial begin
        #150000;  // 15000 cycles
        $display("wave_tb TIMEOUT cstate=%0d busy=%b done=%b cycles=%0d batch=%0d",
                 dut.cstate, busy, done, cycles, dut.batch_cnt);
        $finish;
    end
endmodule
