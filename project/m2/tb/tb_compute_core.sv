// project/m2/tb/tb_compute_core.sv
//
// This project uses cocotb (Python-based testbench framework) rather than a
// pure-SystemVerilog testbench. The actual M2 compute_core test driver is:
//
//   test_compute_core.py  -- cocotb test (zero, representative, 20 random vectors)
//   golden.py             -- bit-exact Q-format Python golden reference
//   runner.py             -- cocotb-tools runner (entry point)
//
// To reproduce from this directory:
//
//   python runner.py compute_core   # TESTS=3 PASS=3 FAIL=0 (bit-exact vs golden)
//
// Waveform: vcd_to_png.py renders ../sim/waveform.png from the dumped VCD.
// Logs are in ../sim/compute_core_run.log.

module tb_compute_core;
  initial begin
    $display("M2 compute_core testbench is cocotb-based. Run: python runner.py compute_core");
    $finish;
  end
endmodule
