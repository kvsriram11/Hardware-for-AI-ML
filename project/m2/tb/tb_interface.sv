// project/m2/tb/tb_interface.sv
//
// This project uses cocotb (Python-based testbench framework) rather than a
// pure-SystemVerilog testbench. The actual M2 interface test driver is:
//
//   test_interface.py  -- cocotb test (AXI4-Lite write/readback + full pipeline)
//   golden.py          -- bit-exact Q-format Python golden reference
//   runner.py          -- cocotb-tools runner (entry point)
//
// To reproduce from this directory:
//
//   python runner.py interface   # TESTS=2 PASS=2 FAIL=0 (bit-exact vs golden)
//
// Logs are in ../sim/interface_run.log.

module tb_interface;
  initial begin
    $display("M2 interface testbench is cocotb-based. Run: python runner.py interface");
    $finish;
  end
endmodule
