# M4 — K=64 Parallel-Lane ESN Accelerator + Multi-Precision Sweep

K=64 parallel compute lanes process a full N=1000 reservoir state-update in 16
batches with **one** AXI `start` (vs M3's one-neuron-at-a-time). Swept across
Q15 / INT8 / Q4, with measured cosim cycle counts and sky130 synthesis at each
precision. Headline: **10.27× vs C+OpenBLAS at Q15** (125 MHz).

## File catalog

### RTL (`rtl/m4/`)
| File | Description |
|---|---|
| `top.sv` | K=64 parallel-lane top. 64 `compute_core` lanes in lockstep, batch sequencer FSM (IDLE→START→STREAM→WAIT→DONE), lane-local weight SRAM + resident x (`$readmemh` preload under `ifdef __ICARUS__`), per-neuron result SRAM with on-demand readout. One `start` per N=1000 update; `cycles` output = measured compute latency. Parameterized by DATA_W. |
| `compute_core.sv` | The per-lane datapath — verbatim copy of the frozen M2 `compute_core` (MAC + tanh + leak), with the sim-only `$dumpvars` block removed so 64 instances don't each dump their subtree. |
| `interface.sv` | AXI4-Lite/Stream wrapper concept for host integration (start/status/readout). The N=1000 cosim drives `top` directly with backdoor weight preload (load is one-time and unmeasured per the brief); `interface.sv` documents the AXI path, equivalent to the M3-verified wrapper. |
| `README.md` | This file. |

### Testbench / cosim (`tb/m4/`)
| File | Description |
|---|---|
| `golden_top.py` | Full N=1000 bit-exact reference (reuses frozen M2 per-neuron golden; exact int64 MAC). Parameterized by DATA_W. `emit_hex()` writes the four `$readmemh` files matching `top.sv` memory layout. |
| `test_top.py` | cocotb N=1000 cosim: one `start`, measure cycles, check every neuron vs golden within 1 LSB. Emits `M4_MEASURE` line. |
| `runner.py` | cocotb 2.0 runner; `--data-w {16,8,4}`. Emits the hex preload files before sim. |
| `wave_tb.sv` | Standalone SV harness for the waveform (avoids cocotb's full-design `$dumpvars`; lets `top.sv`'s enumerated dump produce a small VCD). |
| `wave_to_png.py` | Renders `sim/m4/final_waveform.png` (annotated START / COMPUTE-16-batches / DONE). |

### Simulation outputs (`sim/m4/`)
| File | Description |
|---|---|
| `final_run.log` | cocotb logs for all 3 precisions, each with `TESTS=1 PASS=1 FAIL=0` + `M4_MEASURE`. |
| `final_waveform.png` | Annotated end-to-end Q15 waveform (16 batches, one start). |

### Synthesis (`synth/m4/`) — `q15/`, `int8/`, `q4/` each contain:
| File | Description |
|---|---|
| `config.json` | design, DATA_W/FRAC_W, 125 MHz target, sky130 liberty. |
| `synth.ys` | Yosys script (read → chparam → synth → dfflibmap → abc → stat → ltp). |
| `yosys_run.log` | full Yosys stdout/stderr. |
| `netlist.v` | mapped sky130 gate netlist (one lane). |
| `area_report.txt` | cells + area (per lane; ×64 for the design). |
| `timing_report.txt` | `ltp` critical-path proxy + header. |
| `power_report.txt` | first-order power (per lane + ×64). |
| `critical_path.md` | start reg `prod_ext_q`, end reg `tree_q`, adder-tree logic stages. |
| `synthesis_notes.md` (in `synth/m4/`) | what synthesized, per-lane×64 scope, cross-precision comparison. |

### Benchmark (`bench/`)
| File | Description |
|---|---|
| `precision_study.py` | combines measured cycles + synth + MSE/SNR; emits CSV + roofline. |
| `benchmark_data.csv` | one row per precision, all rubric columns. |
| `benchmark.md` | speedup tables (vs Python+NumPy, vs C+OpenBLAS), energy, multi-precision narrative. |
| `roofline_final.png` | i7 roofline + 5 measured points (Py, C, accel Q15/INT8/Q4). |

## Architecture
- **K=64 lanes**, each a 16-wide streaming MAC = 1024 multipliers; 16 batches × ~73 cycles = **1169 cycles** per N=1000 update.
- One `start` per update; weights preloaded once (unmeasured); x_next resident, host-read on demand.
- N is a **runtime beat/batch count, not a hardware parameter** — gate area is N-independent; precision (DATA_W) is the area/power lever.

## Key results
| | Q15 | INT8 | Q4 |
|---|---|---|---|
| cycles/update | 1169 | 1169 | 1169 |
| updates/sec @125MHz | 106,929 | 106,929 | 106,929 |
| speedup vs C+OpenBLAS | **10.27×** | 10.27× | 10.27× |
| SNR vs FP32 | 79.1 dB | 31.6 dB | 7.9 dB |
| area (×64) | 13.67 mm² | 3.86 mm² | 1.36 mm² |
| bit-exact neurons | 1000/1000 | 999/1000 | 988/1000 (≤1 LSB) |

## Reproduce
```bash
source env/venv/Scripts/activate
python -u tb/m4/runner.py --data-w 16   # and 8, 4
python tb/m4/wave_to_png.py             # via wave_tb (iverilog -> waves.vcd)
yowasp-yosys -s synth/m4/q15/synth.ys   # and int8, q4
python bench/precision_study.py
```

## Tools
Icarus Verilog 12.0 · cocotb 2.0.1 · yowasp-yosys 0.66 (WASM) · sky130_fd_sc_hd `tt_025C_1v80` · GTKWave `fst2vcd` · matplotlib. Host: Windows 11 / MSYS2.
