// dump_waves.sv — Waveform dump helper (simulation-only, not synthesizable)
// Project: Hardware Accelerator for ESN — ECE 510 Spring 2026
//
// Include this file in the simulation sources to dump an FST waveform.
// Open the resulting compute_core_waves.fst in GTKWave for inspection.
//
// This module is a stand-alone block of testbench infrastructure; it
// instantiates nothing and exists only for the side effect of $dumpfile/
// $dumpvars during simulation. It must NOT be synthesized.

module dump_waves;
    initial begin
        $dumpfile("compute_core_waves.vcd");
        $dumpvars(0, compute_core);   // dump everything inside compute_core
    end
endmodule
