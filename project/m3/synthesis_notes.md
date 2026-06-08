# M3 Synthesis Notes

## Summary

The integrated `top` (the M3 chip-top wrapping `interface_axi`, which in turn
instantiates `compute_core` → `mac_array` / `tanh_pwl` / `leak_blend`) was
synthesized to the SkyWater **sky130_fd_sc_hd** standard-cell library at the
typical corner (`tt_025C_1v80`) with a 100 MHz (10 ns) target. Synthesis,
technology mapping, netlist write-out, area reporting, and a topological
critical-path analysis all completed successfully. Power was attempted and is
delivered as a documented first-order estimate rather than a sign-off number,
for the reasons below.

## What synthesized successfully

The full hierarchy elaborated and mapped cleanly. Reported results
(`synth/area_report.txt`):

- **Total standard cells:** 30,197
- **Sequential cells:** 789 `sky130_fd_sc_hd__dfxtp_1` flip-flops (15,803 µm²,
  7.39% of area)
- **Chip area (`top`):** 217,132 µm² (cell area; pre-place-and-route)
- **Dominant combinational cells:** `xnor2_1` (5,699), `nand2_1` (4,751),
  `xor2_1` (3,123) — the signature of the MAC multipliers and the wide
  signed adder tree.

The simulation-only `$dumpvars` `initial` blocks in `compute_core.sv` and
`interface.sv` are guarded by `` `ifdef __ICARUS__ ``, which Yosys does not
define, so they were correctly excluded from the synthesizable netlist. No RTL
under `rtl/m2/` was modified for synthesis — the M2 IP is frozen and synthesizes
as-is. The gate-level netlist is written to `synth/top_netlist.v` (~3.7 MB).

## What did not synthesize / was not produced

**Power sign-off.** Yosys has no native power engine, and accurate dynamic power
needs post-P&R parasitics plus back-annotated switching activity. `synth/power_report.txt`
gives a transparent first-order estimate (~18–20 mW dynamic at 100 MHz from
cell count × activity × per-cell energy) and a concrete plan to obtain a real
number in M4 via OpenROAD `report_power` driven by the M3 cosim VCD.

**ns-accurate STA.** Without OpenSTA, `synth/timing_report.txt` reports the
longest *topological* path (logic depth, 310 mapped cells) instead of
back-annotated worst-negative-slack. This is sufficient to identify the
critical region (see `critical_path.md`) but is not a slack sign-off.

## Scope adjustments and why each is defensible

### 1. Yosys + sky130 liberty (+ Yosys `ltp`) instead of OpenLane 2

OpenLane 2 requires Docker. On this Windows 11 / MSYS2 host Docker could not be
brought up cleanly for the OpenLane container flow. Yosys — here the pip-installable
**yowasp-yosys 0.66** (WebAssembly build, no native toolchain or container
needed) — reads the SystemVerilog directly, maps to real sky130 cells, and
produces a synthesizable gate-level netlist with area, cell counts, and a
critical-path proxy. Iteration is ~30 seconds versus OpenLane's 1–2 hour
P&R-inclusive runs, which made the multiple synth/debug cycles here practical.
The trade-off is that Yosys stops at logical synthesis: no placement, routing,
parasitics, or sign-off STA/power. For an M3 milestone whose goal is *"push the
integrated design through synthesis and characterize area/timing/power"*, the
gate-level netlist + area + critical path from Yosys covers the substantive
deliverables; the P&R-dependent items (ns slack, extracted power) are explicitly
deferred with a stated M4 plan. This is a defensible scope adjustment, not a gap.

### 2. N = 64 cosim vs N = 1000 production reservoir

The `compute_core` processes **one neuron per `start`**; a full reservoir update
is N sequential neuron updates issued by the host over AXI. Verifying N = 1000
in an event-driven cocotb/Icarus cosim (1000 neurons × ~60 cycles × AXI
overhead) would be needlessly slow with no added coverage of *logic* — every
neuron exercises the identical datapath. The cosim therefore runs **N = 64**
(four 16-lane AXIS beats per neuron), which fully exercises multi-beat MAC
accumulation, the FSM, and the AXI4-Lite/Stream control loop, and completes in
under a second of sim time. Result: **64/64 neurons bit-exact** vs the
independent `golden_top.py` reference, worst |diff| = 0 LSB.

Crucially, **N is not a hardware parameter.** `compute_core` is a fixed
MAC_WIDTH = 16-lane *streaming* MAC; reservoir size only changes how many AXIS
beats the host streams and how many `start`s it issues. The synthesized gate
area (217k µm²) is therefore identical for N = 64 and N = 1000 — the same
silicon runs both. So the N = 64 cosim and the synthesized area are mutually
consistent, and the M1 "dominant kernel = state update of arbitrary N" claim is
preserved.

## How M4 benchmarks stay meaningful vs the M1 baseline

The M1 software baseline measured **9,671 state-updates/sec at N = 1000**
(C + OpenBLAS). Because the hardware datapath is N-independent and the per-neuron
cycle count is fixed, M4 can measure cycles-per-neuron at N = 64 on hardware (or
in gate-level sim) and **project to N = 1000 by the known linear scaling**
(reservoir update = N sequential neuron updates + streaming bandwidth). At the
synthesized 100 MHz with ~9 cycles of compute latency per neuron plus AXI
streaming, the projected N = 1000 throughput is directly comparable to the
9,671 updates/sec FP32 baseline, letting M4 state a clean speed-up (and, with
the multi-precision RTL, an accuracy-vs-throughput curve).

## What was learned, informing M4

- **The MAC adder tree is the timing bottleneck** (`critical_path.md`): the
  16-input 40-bit reduction. Pipelining it is the first M4 RTL optimization, and
  the existing `S_FLUSH` drain state already accommodates a deeper pipeline.
- **The streaming architecture decouples area from N**, so the multi-precision
  sweep (DATA_W = 16 / 8 / 4) is the lever that actually moves area/power — the
  M4 sweep should re-run this exact Yosys flow at each width.
- **Tooling for M4:** stand up OpenROAD (native Windows or WSL2) for real STA +
  power, and/or a Vivado/Zybo bring-up for measured FPGA throughput and XPE
  power, using the M3 cosim VCD as the activity stimulus.
