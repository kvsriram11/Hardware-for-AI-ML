# M3 — Integration + Synthesis

Integrated top for the ESN state-update accelerator: wraps the frozen M2
compute IP, drives a full N-neuron reservoir update over AXI only, and pushes
the design through Yosys + sky130 synthesis.

## File catalog

### RTL (`rtl/m3/`)
| File | Description |
|---|---|
| `top.sv` | Integrated chip-top. Instantiates `interface_axi` (which instantiates `compute_core`). All control is via AXI4-Lite + AXI4-Stream; no back-door pins. Parameterized DATA_W/MAC_WIDTH/ACC_W/FRAC_W. |
| `README.md` | This file. |

### Testbench / cosim (`tb/m3/`)
| File | Description |
|---|---|
| `golden_top.py` | Full N-neuron Python reference; reuses the bit-exact M2 per-neuron golden to build the expected `x_next` vector. |
| `test_top.py` | cocotb end-to-end cosim. Drives N=64 reservoir through AXI only (per neuron: AXIL XPREV/WIN_T/start → 4 AXIS beats → poll STATUS → read XNEXT). Checks every neuron vs golden within 1 LSB. |
| `runner.py` | cocotb 2.0 runner (`cocotb_tools.runner`) for `top`. `--waves` dumps FST; `--n` sets reservoir size. |
| `cosim_vcd_to_png.py` | Renders `sim/cosim_waveform.png` — neuron-0 AXI transaction with HOST WRITE / COMPUTE / HOST READ regions annotated. |

### Simulation outputs (`sim/`)
| File | Description |
|---|---|
| `cosim_run.log` | cocotb cosim log; contains the PASS line. |
| `cosim_waveform.png` | Annotated AXI cosim waveform. |

### Synthesis (`synth/`)
| File | Description |
|---|---|
| `config.json` | Synthesis config: design, sources, 100 MHz clock, sky130 liberty path. |
| `synth.ys` | Yosys script (read → hierarchy → synth → dfflibmap → abc → write_verilog → stat → ltp). |
| `sky130_fd_sc_hd__tt_025C_1v80.lib` | sky130 HD standard-cell liberty (typical corner). |
| `yosys_run.log` | Full Yosys stdout/stderr. |
| `top_netlist.v` | Mapped gate-level netlist (sky130 cells). |
| `area_report.txt` | `stat -liberty` — cell counts and area per module. |
| `timing_report.txt` | `ltp` longest-path (logic-depth) critical-path proxy + header. |
| `power_report.txt` | First-order power estimate + documented deferral plan. |
| `critical_path.md` | Start reg, end reg, logic stages, why critical, how to shorten. |
| `synthesis_notes.md` | ≥500-word narrative: what synthesized, scope adjustments, M4 plan. |

## Reproduce

```bash
cd ESN-redo
source env/venv/Scripts/activate

# --- cosim (N=64) ---
python -u tb/m3/runner.py --waves 2>&1 | tee sim/cosim_run.log
/c/iverilog/gtkwave/bin/fst2vcd.exe -f tb/m3/waves.vcd \
    -o tb/m3/sim_build/top_DW16/waves.vcd
python tb/m3/cosim_vcd_to_png.py        # -> sim/cosim_waveform.png

# --- synthesis ---
pip install yowasp-yosys                 # WASM yosys, no Docker/native build
yowasp-yosys -s synth/synth.ys > synth/yosys_run.log 2>&1
```

Expected: `TESTS=1 PASS=1 FAIL=0 SKIP=0`, 64/64 neurons bit-exact.

## Tools and versions
- **Simulator:** Icarus Verilog 12.0 (devel)
- **Cocotb:** 2.0.1 (`cocotb_tools.runner` API)
- **Synthesis:** yowasp-yosys 0.66 (WebAssembly Yosys — no Docker required)
- **PDK:** sky130_fd_sc_hd, corner `tt_025C_1v80`
- **STA:** Yosys `ltp` (OpenSTA unavailable on host — see `synth/synthesis_notes.md`)
- **Waveform:** GTKWave 3.3.100 `fst2vcd`; PNG via matplotlib
- **Host:** Windows 11, MSYS2 + Git Bash, Python 3.12 venv `env/venv/`

## Key results
- Cosim: **64/64 neurons bit-exact** vs `golden_top.py`, worst |diff| = 0 LSB.
- Synthesis: **30,197 cells**, **217,132 µm²**, 789 flip-flops, 100 MHz target.
- Critical path: MAC 16-input 40-bit adder tree (`prod_ext_q` → `tree_q`).

## Scope adjustments (full rationale in `synth/synthesis_notes.md`)
- **Yosys instead of OpenLane 2** — Docker not bring-able on this Windows/MSYS2 host; Yosys gives a sky130 netlist + area/timing in ~30 s iterations.
- **N=64 cosim instead of N=1000** — sim tractability; the datapath is a fixed 16-lane streaming MAC, so N is a runtime beat count, not a hardware parameter, and gate area is N-independent.
