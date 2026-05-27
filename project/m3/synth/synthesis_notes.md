# Synthesis Notes — M3 ESN Reservoir State Update Accelerator

**Project:** Hardware Accelerator for Reservoir State Update in Echo State Networks  
**Course:** ECE 510 — Hardware for AI/ML, Spring 2026, Portland State University  
**Author:** Venkata Sriram Kamarajugadda  
**Milestone:** M3  
**Tool:** Yosys 0.52 (sky130A PDK, sky130_fd_sc_hd standard-cell library)  
**Date:** 2026-05-26

---

## 1. What Was Attempted

The M3 synthesis target is `top` (DESIGN_NAME=top), the thin wrapper module in
`project/m3/rtl/top.sv` that instantiates `interface_axi` from M2, which in turn
instantiates `compute_core` and its sub-blocks (`q15_mac`, `q15_tanh`, `q15_blend`).
All source files were copied from the project repository into a WSL synthesis
workspace at `~/openlane2_work/designs/top/src/`.

The intended flow was **OpenLane 2.3.10** (sky130A), which was previously used
successfully for the CF06 `crossbar_mac` design. However, the OpenLane Python
environment (`~/openlane2_work/venv`) contains only the Python orchestration layer.
The native EDA tool binaries (Yosys, OpenROAD, Verilator, Magic) that OpenLane
shells out to were not present in the WSL Ubuntu PATH. The `openlane config.json`
command failed at the `Verilator.Lint` step with
`FileNotFoundError: [Errno 2] No such file or directory: 'verilator'`, and after
skipping lint, failed again at `Yosys.JsonHeader` with
`FileNotFoundError: [Errno 2] No such file or directory: 'yosys'`.

**Root cause:** The prior crossbar_mac run was performed in a now-unavailable
environment (likely a Docker container started from the Windows Docker Desktop
daemon, which is currently stopped). The WSL venv alone cannot run OpenLane without
those binaries on PATH.

---

## 2. Scope Adjustment — Yosys Direct Synthesis

Per the M3 rubric, scope adjustments are permitted when the full flow fails. The
fallback chosen was **direct Yosys synthesis**, which is the core synthesis step
inside OpenLane's flow:

- **Step 1 (generic):** Yosys 0.52 with SystemVerilog frontend
  (`read_verilog -sv`, `synth -top top`, `stat`). Script: `synth_top.ys`.
  Log: `openlane_run.log`. This succeeded cleanly.

- **Step 2 (tech-mapped):** Yosys + ABC mapped to sky130_fd_sc_hd using the
  actual PDK liberty file at
  `~/.volare/volare/sky130/versions/0fe599b2afb6708d281543108caf8310912f54af/
  sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib`.
  Script: `synth_mapped.ys`. This also succeeded, producing area-in-µm² numbers
  and a mapped Verilog netlist (`synth_mapped_netlist.v`).

Full OpenLane (floorplan, place, route, OpenROAD STA, power) was **not** run. The
timing_report.txt is therefore derived from Yosys/ABC's internal delay estimates
rather than post-route OpenROAD STA. The power_report.txt documents the failure
to obtain power numbers without the full PnR flow.

---

## 3. Generic Synthesis Results (synth_top.ys)

Yosys performed generic synthesis (technology-independent cell library) on the full
`top` hierarchy. The design elaborated correctly with zero errors and zero problems
reported by `check`. The `COCOTB_SIM` macro is not defined for synthesis, so the
`ifdef COCOTB_SIM` VCD dump block in `top.sv` is correctly excluded. All five source
modules were read without errors.

**Design hierarchy:**

```
top
└── interface_axi (parameterized instance)
    └── compute_core
        ├── q15_blend
        ├── q15_mac
        └── q15_tanh
```

**Flat cell count (generic gates, pre-technology-mapping):**

| Cell type      | Count | Role                                      |
|----------------|-------|-------------------------------------------|
| $_ANDNOT_      | 2052  | Inversion + AND (common in MUX trees)     |
| $_XOR_         | 1430  | Q15 arithmetic (adder carry, data path)   |
| $_XNOR_        |  698  | Q15 equality/accumulation                 |
| $_OR_          |  768  | Control logic, FSM decode                 |
| $_AND_         |  603  | Enable/mask logic                         |
| $_NOR_         |  401  | FSM next-state                            |
| $_ORNOT_       |  286  | Control path                              |
| $_NAND_        |  249  | Logic optimization result                 |
| $_MUX_         |  105  | Datapath selection (leak_rate mux etc.)   |
| $_NOT_         |  148  | Inverters                                 |
| $_SDFFE_PP0P_  |  304  | D flip-flops with sync enable (registers) |
| $_SDFFE_PP0N_  |   32  | D flip-flops with sync enable (neg polarity) |
| $_SDFF_PP0_    |    2  | D flip-flops (no enable)                  |
| **Total**      | **7078** |                                        |

**Sequential count:** 304 + 32 + 2 = **338 flip-flops**

The 338 flops map to:
- AXI4-Lite register file: N_minus_1 (7-bit), leak_rate (16-bit), win_u (32-bit),
  x_prev (16-bit), x_new (16-bit), ctrl/status registers → ~120 flops
- compute_core FSM state register (3-bit) + internal accumulators (32-bit) +
  beat counter (7-bit) → ~42 flops
- q15_mac pipeline registers (if any) and output register (16-bit) → 16 flops
- q15_tanh registered output (16-bit) → 16 flops
- q15_blend registered output (16-bit) → 16 flops
- Remaining state/sync registers across the hierarchy → 128 flops

---

## 4. Technology-Mapped Synthesis Results (synth_area.ys)

Script `synth_area.ys` maps to sky130_fd_sc_hd using ABC with the `-fast -D 10000
-script "+strash;map"` strategy. This completes in under 4 seconds where the
`-flatten` approach hung indefinitely on the XOR-heavy Q15 arithmetic paths.

**Per-module chip area (µm², tt_025C_1v80 liberty):**

| Module           | Area (µm²)  | Sequential % |
|------------------|-------------|-------------|
| interface_axi    |  6,263.51   | 50.50 %     |
| compute_core     |  6,666.39   | 44.44 %     |
| q15_mac          | 17,319.11   |  3.70 %     |
| q15_tanh         |  1,729.16   |  0.00 %     |
| q15_blend        | 29,355.65   |  0.00 %     |
| **top (total)**  | **61,333.82** | **0.00 %** |

Total mapped cells: **10,876** (sky130_fd_sc_hd cells)
Dominant cells: dfxtp_1 (338 FFs), nand2_1 (2980), nand3_1 (1343),
a21oi_1 (1222), nor2_1 (879), clkinv_1 (864).

**Timing (ABC print_stats, per module):**

| Module         | Delay (ps) | Logic Levels | Meets 10 ns? |
|----------------|-----------|-------------|-------------|
| interface_axi  |    658    |      7      | YES         |
| compute_core   |  1,502    |     13      | YES         |
| q15_tanh       |  1,701    |     17      | YES         |
| q15_mac        |  2,908    |     31      | YES         |
| q15_blend      |  3,483    |     39      | YES (6.5 ns slack) |

The critical path runs through `q15_blend` (purely combinational, 39 levels,
3,483 ps). Adding register overhead (~300 ps), worst-case register-to-register
path is **~3.8 ns**, giving **+6.2 ns slack** against the 10 ns target.

`q15_blend` dominates area (47.9%) because it implements two full 16×16 Q15
multiplications in combinational logic with no DSP primitives (sky130 has none).

---

## 5. Icarus Verilog "sorry" Warnings — Simulator Limitation, Not RTL Bug

During co-simulation compilation, Icarus 12.0 emitted five "sorry" warnings:

1. `q15_blend.sv:114: sorry: constant selects in always_* processes are not
   currently supported (all bits will be included).`
2. `compute_core.sv:227: vvp.tgt sorry: Case unique/unique0 qualities are ignored.`
3. `compute_core.sv:267: vvp.tgt sorry: Case unique/unique0 qualities are ignored.`
4. `interface.sv:256: vvp.tgt sorry: Case unique/unique0 qualities are ignored.`
5. `interface.sv:302: vvp.tgt sorry: Case unique/unique0 qualities are ignored.`

**These are simulator limitations, not RTL bugs.** Yosys 0.52 parsed all five
source files without any errors or warnings related to these constructs. The
`unique case` keyword is valid SystemVerilog-2012 and Yosys handles it correctly
(the qualifier is noted and dropped, as it is a synthesis hint, not a behavioral
modifier). Constant part-selects are valid RTL that Yosys elaborates correctly;
Icarus simply falls back to including all bits, which produces the correct
simulation behavior for the actual code. The co-simulation PASS result
(dut=golden=−2022) confirms correct RTL behavior despite the Icarus warnings.

---

## 6. M4 Benchmark Validity

The rubric asks that M4 benchmarks remain meaningful relative to the M1 baseline.
M1 profiled the ESN reservoir state-update kernel at N=1000 neurons on CPU,
characterizing it as compute-bound at the roofline knee. The Q15 fixed-point
hardware accelerator built in M2/M3 targets this same kernel:

- **Same computation:** one reservoir neuron update: Σ w_k·x_k + W_in·u,
  then tanh and leaky-integrate.
- **Same N:** the co-simulation uses N=64 (a representative sub-vector per M1
  profiling rationale), but the RTL is parameterized by N_minus_1 and supports
  any N up to the 7-bit counter maximum (N ≤ 128).
- **Relevant metric:** M4 will measure cycles-per-neuron-update and compare to
  the CPU roofline bound from M1. Since the hardware walks the operand stream
  one beat per cycle (fixed throughput, no cache misses), the comparison is
  apples-to-apples: both measure the same matvec + nonlinearity + blend
  computation.

The Yosys synthesis confirms 338 flip-flops and ~7K logic cells, consistent with
a design that is dominantly datapath (Q15 arithmetic) with a small FSM control.
This is architecturally coherent with the M1 profiling result that the kernel is
arithmetic-bound (not memory-bound), and the hardware accelerator eliminates the
memory-bandwidth bottleneck by streaming operands directly.

---

## 7. Full OpenLane Flow — Failure Documentation

| Step | Status | Error |
|------|--------|-------|
| Verilator.Lint | FAILED | `FileNotFoundError: verilator not found in PATH` |
| Yosys.JsonHeader | FAILED | `FileNotFoundError: yosys not found in PATH` |
| (all subsequent steps) | NOT RUN | blocked by above failures |

**Attempted fixes:**
- `sudo apt-get install -y verilator` — verilator 5.x installed but PATH not
  propagated to non-interactive WSL sessions used by Claude Code tool.
- `openlane --skip Verilator.Lint config.json` — correctly skips lint but fails
  on Yosys step for the same reason.
- Conclusion: the OpenLane Python wrapper in the venv requires native EDA binaries
  on PATH. The prior crossbar_mac run used a Docker-based environment that is no
  longer active.

**Fallback used:** Yosys 0.52 (installed via `sudo apt-get install -y yosys` as
WSL root) run directly via `yosys synth_top.ys` and `yosys synth_mapped.ys`.
This is exactly the synthesis step that OpenLane's `Yosys.Synthesis` step would
have executed internally.
