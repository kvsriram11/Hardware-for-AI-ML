# M3 — Integrated Cosimulation and Synthesis

**Due:** May 24, 2026 (graded **Satisfactory**)
**Goal:** Wrap the M2 compute core inside an AXI-accessible top module, demonstrate a full $N=64$ reservoir update driven exclusively through the AXI interface (no direct compute-core poking), and run logic synthesis against the SkyWater 130 nm standard-cell library to report area, critical-path depth, and first-order power.

---

## Result Summary

- **Integrated cosimulation:** $N=64$ reservoir update, **64-of-64 outputs bit-exact** vs Python golden, driven through AXI4-Lite control plane and AXI4-Stream data plane only
- **Synthesis target:** sky130_fd_sc_hd_tt_025C_1v80 standard cells at 100 MHz
- **Synthesis tool:** `yowasp-yosys` (WebAssembly build of Yosys, since native Yosys is unavailable in the project environment)
- **Mapped result:** **30,197 cells, 217,132 µm², 789 flip-flops** at 100 MHz
- **Critical path:** **310 mapped cells**, runs through the MAC adder tree (`prod_ext_q` → 16-operand 40-bit add → `tree_q`)
- **First-order power estimate:** ~18–20 mW (Yosys does not natively perform power estimation; this is a cell-count × average-switching-energy first-order estimate from the sky130 datasheet)

---

## Files

### RTL

| File | Description |
|---|---|
| [`rtl/top.sv`](rtl/top.sv) | Integrated top-level module wrapping `interface_axi` and `compute_core` (from M2). Single AXI4-Lite + AXI4-Stream presented to the host |
| [`rtl/README.md`](rtl/README.md) | Top-level integration notes, port list, and AXI register map summary |

The M2 RTL modules (`mac_array.sv`, `tanh_pwl.sv`, `leak_blend.sv`, `compute_core.sv`, `interface_axi.sv`) are pulled in unchanged from [`../m2/rtl/`](../m2/rtl/) at simulation and synthesis time.

### Testbench

| File | Description |
|---|---|
| [`tb/test_top.py`](tb/test_top.py) | Cocotb test `test_full_reservoir`: drives an $N=64$ reservoir update through AXI only and verifies all 64 neuron outputs against the multi-neuron golden |
| [`tb/golden_top.py`](tb/golden_top.py) | Multi-neuron Python golden model (same kernel as M2's `golden.py`, extended to process the full state vector) |
| [`tb/runner.py`](tb/runner.py) | cocotb runner for the integrated top-level test |
| [`tb/cosim_vcd_to_png.py`](tb/cosim_vcd_to_png.py) | Matplotlib-based renderer for the M3 cosimulation waveform |

### Simulation outputs

| File | Description |
|---|---|
| [`sim/cosim_run.log`](sim/cosim_run.log) | Cocotb log for the integrated test; ends with `TESTS=1 PASS=1 FAIL=0` |
| [`sim/cosim_waveform.png`](sim/cosim_waveform.png) | Matplotlib-annotated cosimulation waveform showing the host-write / compute / host-read phases (used as Figure 4a in the M4 report) |
| [`sim/cosim_waveform_gtkwave.png`](sim/cosim_waveform_gtkwave.png) | GTKWave screenshot of the same simulation (used as Figure 4b in the M4 report) |

### Synthesis outputs

| File | Description |
|---|---|
| [`synth/synth.ys`](synth/synth.ys) | Yosys synthesis script: read SystemVerilog sources, hierarchical pass, optimization, technology mapping to sky130 |
| [`synth/config.json`](synth/config.json) | Synthesis configuration (target frequency, optimization flags, liberty file path) |
| [`synth/yosys_run.log`](synth/yosys_run.log) | Full Yosys synthesis log |
| [`synth/area_report.txt`](synth/area_report.txt) | Cell-by-cell area breakdown (30,197 cells total, 217,132 µm²) |
| [`synth/timing_report.txt`](synth/timing_report.txt) | Static timing analysis result via Yosys `ltp` (longest topological path); see `critical_path.md` for explanation of why OpenSTA was not used |
| [`synth/power_report.txt`](synth/power_report.txt) | First-order power estimate (~18–20 mW), derived from cell count × average switching energy from the sky130 datasheet |
| [`synth/critical_path.md`](synth/critical_path.md) | Identification and explanation of the critical path: MAC array's 16-operand 40-bit adder tree, 310 mapped sky130 cells |
| [`synth/synthesis_notes.md`](synth/synthesis_notes.md) | Notes on tool deviations (yowasp-yosys vs native Yosys, ltp vs OpenSTA), liberty file source, and how power was estimated |
| [`synth/top_netlist.v`](synth/top_netlist.v) | Mapped Verilog netlist (sky130 standard cell instances) |

The sky130 liberty file (`sky130_fd_sc_hd__tt_025C_1v80.lib`, ~13 MB) is included in this directory because it is the reference against which all synthesis numbers in this milestone and M4 are reported. It is the standard PDK liberty file from the SkyWater open-source PDK.

---

## Reproducing the M3 Results

From the project root:

```bash
# Cosimulation (~30 seconds)
cd project/m3/tb
python runner.py
# Expected: TESTS=1 PASS=1 FAIL=0 with N=64 reservoir update bit-exact

# Synthesis (~2 minutes)
cd ../synth
python -m yowasp_yosys -s synth.ys
# Produces top_netlist.v, area_report.txt, timing_report.txt, power_report.txt
```

The cocotb runner produces `tb/sim_build/.../waves.vcd`; `cosim_vcd_to_png.py` renders this into the matplotlib waveform PNG.

---

## Synthesis Tool Notes

`yowasp-yosys` is a WebAssembly distribution of Yosys, installed via `pip install yowasp-yosys`. It is used here because native Yosys is not available on the Windows development host in this project. The WASM build is functionally equivalent for synthesis purposes but is slower at elaboration time. For static timing analysis, OpenSTA is unavailable in the WASM toolchain; this milestone uses Yosys's `ltp` (longest topological path) command, which reports critical-path logic depth in mapped cells rather than a sign-off-quality wire-delay-accurate timing report. This is acknowledged as a methodology limitation; M4 documents the same approach with explicit comparison between the M3 (310-cell at 100 MHz) and M4 (307-cell at 125 MHz) results to defend the timing target by analogy.

---

## Architecture Note

The same silicon synthesized in this milestone is what runs in the M4 benchmark — the parameter $N$ (reservoir size) is a beat count fed through AXI, not a hardware parameter baked into synthesis. The M3 cosimulation runs at $N=64$ for verification convenience; the M4 measurement runs the identical RTL at $N=1000$. The transition from M3 (one neuron per AXI start) to M4 (one full reservoir update per AXI start) is an internal-sequencer change in `top.sv`, not a change to the underlying compute core.
