// project/m3/tb/tb_top.sv
//
// This project uses cocotb (Python-based testbench framework) rather than a
// pure-SystemVerilog testbench. The actual M3 integrated-top test driver is:
//
//   test_top.py          -- cocotb cosim, drives the AXI top end-to-end
//   golden_top.py        -- Python golden reference model
//   runner.py            -- cocotb-tools runner (entry point)
//   cosim_vcd_to_png.py  -- renders ../sim/cosim_waveform.png from the VCD
//
// To reproduce from this directory:
//
//   python runner.py     # TESTS=1 PASS=1 FAIL=0 (dut == golden)
//
// Logs are in ../sim/cosim_run.log.

module tb_top;
  initial begin
    $display("M3 testbench is cocotb-based. Run: python runner.py");
    $finish;
  end
endmodule
