# M1 — Profiling, Roofline Analysis, and Interface Selection

**Due:** Apr 12, 2026 (graded **Satisfactory**)
**Goal:** Identify the dominant recurring kernel of the Echo State Network workload, characterize its position on a roofline plot of the target host, and propose a hardware/software partition with the required AXI interface bandwidth justified by measurement.

---

## Result Summary

- **Dominant kernel:** ESN reservoir state update (the only routine that runs every time step during deployment)
- **Software baselines at N=1000, FP32, single-thread on i7-1165G7:**
  - Python+NumPy: **4,446 updates/sec**, 8.93 GFLOP/s
  - C+OpenBLAS: **10,415 updates/sec**, 19.43 GFLOP/s (2.34× over Python)
- **Arithmetic intensity:** $\mathrm{AI} = (2N^2 + 9N) / (4N^2 + 16N + 4) \approx 0.50$ FLOP/byte
- **Host roofline:** peak 179.2 GFLOP/s compute, 51.2 GB/s DRAM bandwidth, ridge at 3.5 FLOP/byte
- **Classification:** **memory-bound** by a factor of 7
- **Bandwidth-limited ceiling at AI=0.5:** 25.6 GFLOP/s. C+OpenBLAS already achieves 76% of this ceiling, leaving no algorithmic headroom on the CPU.

---

## Files

### Top-level project documents

| File | Description |
|---|---|
| [`../heilmeier.md`](../heilmeier.md) | Heilmeier Q1, Q2, Q3 answers grounded in this milestone's profiling data |

### Documentation (this milestone)

| File | Description |
|---|---|
| [`sw_baseline.md`](sw_baseline.md) | Software baseline platform, configuration, methodology, and measured throughput/latency/memory numbers for Python+NumPy |
| [`interface_selection.md`](interface_selection.md) | AXI4-Lite + AXI4-Stream interface selection rationale, register map, bandwidth requirement at target throughput |
| [`system_diagram.png`](system_diagram.png) | High-level block diagram: host, AXI interface, chiplet boundary, compute engine, on-chip SRAM |

### Profiling

| File | Description |
|---|---|
| [`profiling/cprofile/`](profiling/cprofile/) | cProfile output across reservoir sizes N ∈ {100, 500, 1000, 2000} for the Python+NumPy implementation |
| [`profiling/vtune/`](profiling/vtune/) | Intel VTune microarchitecture profile (memory-access analysis on i7-1165G7) |
| [`profiling/analysis/ai_calculation.md`](profiling/analysis/ai_calculation.md) | Term-by-term derivation of FLOPs and bytes per state update at N=1000 |
| [`profiling/analysis/kernel_comparison.md`](profiling/analysis/kernel_comparison.md) | Per-function timing breakdown; identifies the state update as the only recurring kernel |
| [`profiling/analysis/partition_rationale.md`](profiling/analysis/partition_rationale.md) | HW/SW partition proposal addressing the four required subquestions (which kernel, what SW retains, interface bandwidth, bound classification) |
| [`profiling/analysis/roofline_project.png`](profiling/analysis/roofline_project.png) | M1 roofline plot showing the dominant kernel position on the i7-1165G7 roofline |
| [`profiling/analysis/roofline_sweep.png`](profiling/analysis/roofline_sweep.png) | Roofline sweep across N ∈ {100, 500, 1000, 2000} for both Python and C+OpenBLAS baselines |
| [`profiling/analysis/ai_summary.json`](profiling/analysis/ai_summary.json) | Machine-readable summary of the AI calculation and roofline coordinates |
| [`profiling/analysis/M1_AUDIT.md`](profiling/analysis/M1_AUDIT.md) | Audit log mapping every M1 rubric checkbox to the file that satisfies it |

### Software baselines

| File | Description |
|---|---|
| [`baselines/python_numpy/`](baselines/python_numpy/) | Python+NumPy ESN baseline (entry point: `benchmark.py`); 10-run timed harness reporting median wall-clock per state update |
| [`baselines/c_openblas/`](baselines/c_openblas/) | C+OpenBLAS reimplementation (entry point: `benchmark`, built via `make`); cross-validated bit-equivalent to the Python baseline to 6 decimal places |
| [`baselines/colab_t4/`](baselines/colab_t4/) | Google Colab T4 GPU baseline (reference point; not used as primary comparator) |

---

## Reproducing the M1 Results

From a clean checkout:

```bash
# Python+NumPy baseline (~30 seconds)
cd project/m1/baselines/python_numpy
python benchmark.py

# C+OpenBLAS baseline (~10 seconds)
cd project/m1/baselines/c_openblas
make
./benchmark

# Roofline plots (regenerates from baseline JSON outputs)
cd project/m1/profiling/analysis
python build_analysis.py
```

The two roofline PNGs in `profiling/analysis/` regenerate identically.

---

## Notes on Roofline Conventions

The roofline plots in this milestone show the i7-1165G7 host system only. No projected accelerator points appear on the host roofline; this is deliberate, as a roofline is a property of a single memory hierarchy and mixing host bytes with chiplet FLOPs creates a hierarchy mismatch. The chiplet's own roofline is presented separately in M4 (`project/m4/bench/roofline_final.png`), with FLOPs and bytes counted at the chiplet's SRAM interface where its bandwidth physically lives.
