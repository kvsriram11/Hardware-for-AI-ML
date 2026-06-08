# M4 — K=64 Parallel-Lane Fabric, Multi-Precision Sweep, and Final Benchmark

**Due:** Jun 7, 2026
**Goal:** Deliver the complete, characterized accelerator: $K=64$ parallel MAC lanes processing the full $N=1000$ ESN state update in a single AXI transaction, swept across three fixed-point precisions (Q15, INT8, Q4), with measured throughput, synthesized area/power, and a written design-justification report.

---

## Headline Result

**Measured: 1169 clock cycles per $N=1000$ state update, identical at all three precisions.**

| Implementation | Updates/sec | GFLOP/s | vs. Python | vs. C+OpenBLAS |
|---|---|---|---|---|
| Python+NumPy (i7-1165G7, 1T) | 4,446 | 8.93 | 1.00× | 0.43× |
| C+OpenBLAS (i7-1165G7, 1T) | 10,415 | 19.43 | 2.34× | 1.00× |
| Chiplet Q15 @ 100 MHz (conservative) | 85,543 | 171.86 | 19.2× | 8.21× |
| **Chiplet Q15 @ 125 MHz (target)** | **106,929** | **214.82** | **24.0×** | **10.27×** |

Multi-precision sweep at the same 1169-cycle measured throughput:

| Precision | SNR (dB) | Area (mm²) | Power est. (mW) | Cells |
|---|---|---|---|---|
| Q15 | 79.14 | 13.67 | 1425 | 1,899,584 |
| INT8 | 31.58 | 3.86 | 397 | 529,536 |
| Q4 | 7.85 | 1.36 | 134 | 179,136 |

Throughput is **precision-independent**: lower precision shrinks area and power by an order of magnitude while measured throughput stays at 215 GFLOP/s. This validates the memory-bound regime predicted by the M1 roofline analysis and is the central empirical finding of the project.

---

## Files

### Final design justification report

| File | Description |
|---|---|
| [`design_justification.pdf`](design_justification.pdf) | 9-section design report (problem, roofline, precision, dataflow, interface, verification, synthesis, benchmark, what-did-not-work) plus references, acknowledgements, and reproducibility appendix |
| [`design_justification.tex`](design_justification.tex) | LaTeX source for the report |

### RTL

| File | Description |
|---|---|
| [`rtl/top.sv`](rtl/top.sv) | K=64 parallel-lane top module. Internal sequencer drives 16 batches of 64 neurons per AXI `start` pulse, eliminating the per-neuron AXI handshake overhead that limited M3 |
| [`rtl/compute_core.sv`](rtl/compute_core.sv) | One MAC lane (a copy of the M2 compute_core); $K=64$ of these are instantiated by `top.sv` |
| [`rtl/interface.sv`](rtl/interface.sv) | AXI wrapper for the K=64 fabric |
| [`rtl/README.md`](rtl/README.md) | Architecture overview of the K=64 fabric, batch-sequencer description, and how it differs from the M3 top |

### Testbench

| File | Description |
|---|---|
| [`tb/test_top.py`](tb/test_top.py) | Cocotb test driving an $N=1000$ reservoir update at each of the three precisions through the AXI interface |
| [`tb/golden_top.py`](tb/golden_top.py) | Python golden model for the full K=64 batched dataflow |
| [`tb/runner.py`](tb/runner.py) | Cocotb runner script with `--data-w` flag to select Q15/INT8/Q4 at simulation time |
| [`tb/wave_tb.sv`](tb/wave_tb.sv) | Standalone Verilog test harness used to produce the M4 final waveform (avoids the multi-GB VCD that a full $N=1000$ cocotb run would generate) |
| [`tb/wave_to_png.py`](tb/wave_to_png.py) | Matplotlib renderer for the wave_tb output |
| [`tb/w_mem.hex`](tb/w_mem.hex) | Hex weight-matrix preload file for cocotb's `$readmemh` backdoor |
| [`tb/win.hex`](tb/win.hex) | Hex input-projection preload file |
| [`tb/x_chunk.hex`](tb/x_chunk.hex), [`tb/x_scalar.hex`](tb/x_scalar.hex) | State-vector preload files |

### Simulation outputs

| File | Description |
|---|---|
| [`sim/final_run.log`](sim/final_run.log) | Cocotb log for the three-precision sweep. Shows three PASS lines (one per `DATA_W`) and the measured 1169-cycle count |
| [`sim/final_waveform.png`](sim/final_waveform.png) | Matplotlib-rendered annotated final waveform showing one full $N=1000$ state update from `start` to `done` |

### Synthesis outputs

The K=64 design is synthesized per-lane and reported as 64× the single-lane figures. This approach is exact for critical-path delay (lanes are parallel and identical) and linear-faithful for area. The `yowasp-yosys` WebAssembly elaborator cannot handle the full 1.9M-cell K=64 design as a single elaboration.

| Path | Description |
|---|---|
| [`synth/q15/`](synth/q15/) | Q15 per-lane synthesis (config.json, synth.ys, yosys_run.log, area_report.txt, timing_report.txt, power_report.txt, critical_path.md, top_netlist.v) |
| [`synth/int8/`](synth/int8/) | INT8 per-lane synthesis (same file set) |
| [`synth/q4/`](synth/q4/) | Q4 per-lane synthesis (same file set) |
| [`synth/synthesis_notes.md`](synth/synthesis_notes.md) | Discussion of methodology deviations: per-lane synthesis × 64, ltp vs OpenSTA, first-order power, and the 125 MHz target's defensibility-by-analogy to M3's 100 MHz |

### Benchmark

| File | Description |
|---|---|
| [`bench/benchmark.md`](bench/benchmark.md) | Methodology and measured-numbers writeup: cycle-to-wall-clock conversion, AI computation at the SRAM interface, energy estimate |
| [`bench/benchmark_data.csv`](bench/benchmark_data.csv) | Per-precision benchmark numbers (cycles, updates/s, GFLOP/s, MSE, SNR, cells, area, power) |
| [`bench/benchmark_summary.json`](bench/benchmark_summary.json) | Machine-readable summary of the same data |
| [`bench/roofline_final.png`](bench/roofline_final.png) | Final roofline plot: i7 reference (left panel) + K=64 chiplet roofline (right panel). Each system on its own roofline with no memory-hierarchy mixing (see Section 8.2 of `design_justification.pdf`) |
| [`bench/precision_study.py`](bench/precision_study.py) | Python script that runs the multi-precision sweep and regenerates `benchmark_data.csv` and the roofline PNG |

---

## Reproducing the M4 Results

From the project root:

```bash
# Cocotb verification at three precisions (~5 minutes per run)
cd project/m4/tb
python runner.py --data-w 16
python runner.py --data-w 8
python runner.py --data-w 4
# Each ends with TESTS=1 PASS=1 FAIL=0 and reports 1169 cycles_per_update

# Per-precision synthesis (~2 minutes each)
cd ../synth/q15 && python -m yowasp_yosys -s synth.ys && cd ../..
cd synth/int8 && python -m yowasp_yosys -s synth.ys && cd ../..
cd synth/q4 && python -m yowasp_yosys -s synth.ys && cd ../..

# Benchmark consolidation and roofline plot
cd bench
python precision_study.py
```

---

## What Did Not Survive to Submission

Two items were planned for M4 and explicitly deferred. They are documented in detail in Section 9 of the design justification report.

**FPGA bring-up on Zybo (XC7Z010).** Planned as a stretch goal but deferred for time. The target board's fabric (17,600 LUTs, 80 DSP slices) cannot accommodate the full $K=64$ design and would have required a scaled-down configuration ($K=4$, $N=64$) as a hardware sanity check rather than a true validation of the M4 numbers. This remains the highest-priority next step for follow-on work.

**OpenSTA-signed-off timing.** The 125 MHz target clock is supported by Yosys topological-depth analysis (307 mapped cells, comparable to M3's 310-cell path that closed at 100 MHz) but is not OpenSTA-signed-off. The conservative 100 MHz target (85,543 updates/s, 8.21× over C+OpenBLAS) remains valid as a fallback and is reported alongside the headline 125 MHz number throughout this milestone.

---

## Final Cocotb Regression Status

All milestones still pass at submission time:

```
M2 compute_core : TESTS=3 PASS=3 FAIL=0
M2 interface    : TESTS=2 PASS=2 FAIL=0
M3 top          : TESTS=1 PASS=1 FAIL=0
M4 Q15/INT8/Q4  : TESTS=1 PASS=1 FAIL=0  (×3)
```
