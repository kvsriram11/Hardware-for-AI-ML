# M2 — Compute-Core RTL and Verification

**Due:** May 3, 2026 (graded **Satisfactory**)
**Goal:** Implement the parameterized fixed-point compute core in SystemVerilog, exercise it through cocotb testbenches against an independent Python golden model, and characterize quantization error at the chosen precision against an FP32 reference.

---

## Result Summary

- **5 SystemVerilog modules** parameterized by `DATA_W` (target: 16, also runnable at 8, 4): `mac_array`, `tanh_pwl`, `leak_blend`, `compute_core`, `interface_axi`
- **5 cocotb tests, all PASS:** 3 directly on `compute_core` (zero-input, representative vector, multi-random-vector sweep), 2 on the integrated AXI interface (register write-readback, full pipeline)
- **Quantization at Q15:** SNR = **79.14 dB**, MSE = $5.32 \times 10^{-10}$, MAE = $2.0 \times 10^{-5}$ over 200 random samples against FP32 reference
- **Three RTL bugs identified and fixed during verification:** leak-blend off-by-one, MAC/tanh Q-format scaling mismatch, MAC product width truncation (full bug postmortem in [`../m4/design_justification.pdf`](../m4/design_justification.pdf) Section 6.1)

---

## Files

### RTL (synthesizable SystemVerilog)

| File | Description |
|---|---|
| [`rtl/mac_array.sv`](rtl/mac_array.sv) | 16-wide MAC array with 3-stage pipelined product → reduce → accumulate. Width-parameterized by `DATA_W`; accumulator fixed at `ACC_W=40` bits |
| [`rtl/tanh_pwl.sv`](rtl/tanh_pwl.sv) | 4-segment piecewise-linear $\tanh$ approximation; single-cycle combinational; uses powers-of-two slope coefficients (no actual multiplier) |
| [`rtl/leak_blend.sv`](rtl/leak_blend.sv) | $\alpha \mathbf{y} + (1-\alpha)\mathbf{x}$ leak-integrator stage; signed fixed-point Q$1.(W-1)$ |
| [`rtl/compute_core.sv`](rtl/compute_core.sv) | Top-level integration of mac_array + tanh_pwl + leak_blend behind a 5-state FSM (IDLE → MAC → FLUSH → ACTIVATE → BLEND → DONE) |
| [`rtl/interface_axi.sv`](rtl/interface_axi.sv) | AXI4-Lite control plane (CTRL/STATUS/LEAK_A/WIN_T/XPREV/XNEXT registers) and AXI4-Stream data plane (weight loading) |
| [`rtl/README.md`](rtl/README.md) | Module-by-module description of ports, parameters, and intended dataflow |
| [`rtl/precision.md`](rtl/precision.md) | Q-format convention, dynamic-range derivation, and accumulator width justification |
| [`rtl/quantization_stats.json`](rtl/quantization_stats.json) | Machine-readable record of the 200-sample quantization study (MAE, MSE, SNR per precision) |

### Testbench (cocotb 2.0.1)

| File | Description |
|---|---|
| [`tb/golden.py`](tb/golden.py) | Bit-exact Python golden model for `compute_core` |
| [`tb/test_compute_core.py`](tb/test_compute_core.py) | 3 cocotb tests directly exercising `compute_core` |
| [`tb/test_interface.py`](tb/test_interface.py) | 2 cocotb tests exercising the integrated AXI wrapper |
| [`tb/runner.py`](tb/runner.py) | cocotb runner script invoking Icarus Verilog with the SystemVerilog sources |
| [`tb/vcd_to_png.py`](tb/vcd_to_png.py) | Matplotlib-based waveform renderer used to produce the M2 figure for the M4 report |
| [`tb/Makefile`](tb/Makefile) | cocotb Makefile (alternative invocation path) |

### Simulation outputs

| File | Description |
|---|---|
| [`sim/compute_core_run.log`](sim/compute_core_run.log) | Cocotb run log for the 3 compute_core tests; ends with `TESTS=3 PASS=3 FAIL=0` |
| [`sim/interface_run.log`](sim/interface_run.log) | Cocotb run log for the 2 interface tests; ends with `TESTS=2 PASS=2 FAIL=0` |
| [`sim/waveform.png`](sim/waveform.png) | Matplotlib-annotated waveform for the `test_representative_vector` run (used as Figure 3a in the M4 report) |
| [`sim/waveform_gtkwave.png`](sim/waveform_gtkwave.png) | GTKWave screenshot of the same simulation (used as Figure 3b in the M4 report) |

---

## Reproducing the M2 Results

From the project root:

```bash
cd project/m2/tb

# Run the 3 compute_core tests
python runner.py compute_core
# Expected: TESTS=3 PASS=3 FAIL=0

# Run the 2 interface tests
python runner.py interface
# Expected: TESTS=2 PASS=2 FAIL=0
```

Both runners produce a `waves.vcd` in their working directory; `vcd_to_png.py` converts these into the matplotlib renders found in `sim/`.

---

## Architecture Notes

The M2 RTL is the single-neuron compute core (one element of the state vector per AXI `start` pulse). The M3 milestone integrates this core into a top-level AXI-wrapped module that processes a full $N=64$ reservoir update through the AXI interface only. The M4 milestone replicates the core 64-fold into a parallel-lane fabric processing the full $N=1000$ reservoir update in a single AXI transaction. The compute_core RTL committed in this milestone is the unit that gets replicated in M4.

The 40-bit accumulator (`ACC_W=40`) is sized to hold the worst-case sum of $N=1000$ signed Q1.($W-1$) × Q1.($W-1$) products at any precision: 1 sign + 30 magnitude (Q15 worst-case product) + 10 dynamic-range bits ($\log_2 1000$). The same 40-bit accumulator is reused across all three precisions (Q15, INT8, Q4), which simplifies the parameterized design at no cost — the lower precisions never exercise the full 40-bit headroom.
