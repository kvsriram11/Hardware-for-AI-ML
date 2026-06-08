// project/m4/tb/tb_top.sv
//
// This project uses cocotb (Python-based testbench framework) rather than a
// pure-SystemVerilog testbench. The actual M4 test driver is:
//
//   test_top.py    -- cocotb test, drives N=1000 reservoir update via AXI
//   golden_top.py  -- Python golden reference model
//   runner.py      -- cocotb-tools runner (entry point)
//
// To reproduce M4 simulation from this directory:
//
//   python runner.py --data-w 16   # Q15  (1000/1000 bit-exact)
//   python runner.py --data-w 8    # INT8 (999/1000 within 1 LSB)
//   python runner.py --data-w 4    # Q4   (988/1000 within 1 LSB)
//
// Each run produces TESTS=1 PASS=1 FAIL=0 and reports 1169 cycles/update.
// Logs are in ../sim/final_run.log.
//
// The wave_tb.sv file in this directory IS a pure-SystemVerilog testbench;
// it was used to produce ../sim/final_waveform.png and demonstrates the
// AXI handshake structure independently of cocotb.

module tb_top;
  initial begin
    $display("M4 testbench is cocotb-based. Run: python runner.py");
    $finish;
  end
endmodule
