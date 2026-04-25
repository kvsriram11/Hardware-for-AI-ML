<div align="center">

# Hardware Accelerator for Reservoir State Update in Echo State Networks

*Custom co-processor chiplet for efficient ESN inference — ECE 510, Portland State University*

[![Course](https://img.shields.io/badge/Course-ECE%20510%20%E2%80%94%20HW%20for%20AI%2FML-4A90D9?style=flat-square)](https://github.com/kvsriram11/Hardware-for-AI-ML)
[![Term](https://img.shields.io/badge/Term-Spring%202026-6C8EBF?style=flat-square)](#)
[![Status](https://img.shields.io/badge/Status-M2%20In%20Progress-F0A500?style=flat-square)](#milestones)
[![M1](https://img.shields.io/badge/M1-Satisfactory-2E7D32?style=flat-square)](#milestones)
[![License](https://img.shields.io/badge/License-MIT-lightgrey?style=flat-square)](LICENSE)

[![HDL](https://img.shields.io/badge/HDL-SystemVerilog-blueviolet?style=flat-square)](#toolchain)
[![Synthesis](https://img.shields.io/badge/Synthesis-OpenLane%202-orange?style=flat-square)](#toolchain)
[![Simulation](https://img.shields.io/badge/Simulation-Verilator%20%2F%20cocotb-blue?style=flat-square)](#toolchain)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](#toolchain)

**Author:** Venkata Sriram Kamarajugadda &nbsp;|&nbsp; **Instructor:** Prof. Christof Teuscher &nbsp;|&nbsp; **Portland State University**

</div>

---

## Overview

Echo State Networks (ESNs) are a class of recurrent reservoir computing models effective at streaming time-series inference. Their dominant computational cost — the reservoir state update — is executed thousands of times per inference run and is bottlenecked by memory bandwidth, not arithmetic throughput. On a general-purpose CPU, the dense 1000×1000 recurrent weight matrix must be repeatedly fetched from DRAM, yielding an arithmetic intensity of only **0.25 FLOP/byte** and placing the kernel firmly in the memory-bound region of the roofline model.

This project designs, implements, and benchmarks a custom co-processor chiplet that accelerates the reservoir state-update kernel using structured sparsity, on-chip state buffering, and a pipelined MAC datapath — targeting measurable throughput improvement over the software baseline with a research-grade multi-precision comparison.

> **Research goal:** Publish a multi-precision hardware comparison — CPU (FP64) → GPU → Accelerator FP32 → Accelerator INT16 → Accelerator INT8 → SOTA.

---

## Target Kernel

The sole kernel accelerated by the chiplet:

```
x(t) = (1 - a) * x(t-1) + a * tanh( W_res * x(t-1) + W_in * u(t) )
```

| Symbol | Description |
|--------|-------------|
| `x(t)` | Reservoir state vector (N = 1000) |
| `W_res` | Recurrent weight matrix (N × N = 1000 × 1000) |
| `W_in` | Input weight matrix (N × 2) |
| `u(t)` | Scalar input sample |
| `a` | Leak rate (0.3) |

The dominant operation is the recurrent matrix-vector multiply `W_res * x(t-1)`. The full update chain — input projection, accumulation, tanh activation, and leak-rate blending — is the hardware target. All other ESN functions (spectral normalization, readout training, orchestration) remain in software on the host.

---

## Software Baseline

> **Platform:** Intel Core i7-1165G7 · Windows 11 · Python 3.12 · NumPy + SciPy  
> **Dataset:** Mackey-Glass delay-17 · Reservoir: N = 1000 · FP64 precision · 10 benchmark runs

| Metric | Value |
|--------|-------|
| Median wall-clock runtime | **2.85 s / run** (steady-state, runs 2–10) |
| State update throughput | **1,403 updates/s** |
| Estimated compute rate | **2.82 GFLOP/s** |
| Arithmetic intensity | **0.25 FLOP/byte** |
| Prediction MSE | **1.026 × 10⁻⁶** |
| Peak process RSS | **4.28 MB** |

The kernel is **memory-bound**. The i7-1165G7 roofline ridge point sits at 3.50 FLOP/byte; the software kernel at 0.25 FLOP/byte achieves roughly **1.6% of peak compute throughput** — leaving substantial headroom for a purpose-built accelerator.

---

## Accelerator Design

### Hardware / Software Partition

<table>
<tr>
<th>⚡ Chiplet (hardware)</th>
<th>💻 Host (software)</th>
</tr>
<tr>
<td>

- Structured-sparse recurrent MAC array
- On-chip SRAM state vector buffer
- Piecewise-linear tanh approximation unit
- Leak-rate blending datapath
- AXI4-Stream data interface
- AXI4-Lite control register interface

</td>
<td>

- Spectral radius normalization (one-time setup)
- Ridge regression readout training
- Weight loading and configuration
- Dataset I/O, logging, and verification

</td>
</tr>
</table>

### Hardware Interface

| Parameter | Value |
|-----------|-------|
| Data interface | AXI4-Stream |
| Control interface | AXI4-Lite |
| Host platform | FPGA SoC |
| Required bandwidth | 0.00016 GB/s (scalar I/O per timestep) |
| Interface bottleneck | **No** — 0.04% of rated AXI4-Stream capacity |

The reservoir state vector is stored entirely on-chip. Only the scalar input `u(t)` and scalar output cross the external interface per timestep, so the design is not interface-bound.

---

## Precision Study

This project targets a research-grade multi-precision evaluation suitable for publication.

| Precision | Role | Notes |
|-----------|------|-------|
| **FP32** | Baseline accelerator | Functionally correct reference; direct comparison with CPU / GPU |
| **INT16 (Q15)** | Primary research variant | Reduced area and power; full quantization error analysis |
| **INT8** | Stretch goal | Second data point if schedule allows |

**Evaluation pipeline:**

```
CPU (FP64)  ──►  GPU  ──►  Accel-FP32  ──►  Accel-INT16  ──►  Accel-INT8  ──►  SOTA
```

---

## Toolchain

| Tool | Purpose |
|------|---------|
| [![SystemVerilog](https://img.shields.io/badge/SystemVerilog-RTL-blueviolet?style=flat-square)](#) | Hardware description |
| [![OpenLane 2](https://img.shields.io/badge/OpenLane%202-Synthesis-orange?style=flat-square)](#) | RTL-to-GDSII flow |
| [![Verilator](https://img.shields.io/badge/Verilator%20%2F%20cocotb-Simulation-blue?style=flat-square)](#) | Functional verification |
| [![Python](https://img.shields.io/badge/Python%20%2B%20NumPy%20%2B%20SciPy-Baseline-3776AB?style=flat-square&logo=python&logoColor=white)](#) | SW baseline and golden reference |
| [![cProfile](https://img.shields.io/badge/cProfile%20%2F%20line__profiler-Profiling-grey?style=flat-square)](#) | Runtime hotspot identification |

---

## Repository Structure

```
Hardware-for-AI-ML/
├── README.md
├── project/
│   ├── heilmeier.md               ← Heilmeier Q1–Q3
│   ├── algorithm_diagram.png      ← High-level algorithm diagram
│   └── m1/
│       ├── sw_baseline.md         ← Software benchmark
│       ├── interface_selection.md ← Interface choice + bandwidth analysis
│       └── system_diagram.png     ← Chiplet block diagram
└── codefest/
    └── cf02/
        ├── profiling/
        │   ├── project_profile.txt
        │   └── roofline_project.png
        └── analysis/
            ├── ai_calculation.md
            └── partition_rationale.md
```

> **Note:** The `codefest/` directory contains all codefest submissions for the course. Some tasks feed directly into project milestones (e.g., cf02 — roofline analysis and profiling). Others are standalone course exercises unrelated to the ESN accelerator. Project-relevant codefest work is explicitly referenced in the milestone table below.

---

## Milestones

| # | Due | Status | Deliverables |
|---|-----|--------|--------------|
| **M1** | Apr 12 | ✅ **Satisfactory** | Software baseline, profiling, roofline analysis, interface selection, block diagram |
| **M2** | May 3  | 🔄 **In progress** | Compute core HDL + testbench, AXI interface HDL + testbench, precision analysis |
| **M3** | May 24 | ⬜ Upcoming | OpenLane 2 synthesis, timing + area report, end-to-end co-simulation |
| **M4** | Jun 7  | ⬜ Upcoming | Full package: synthesis results, benchmark comparison, design justification report |

---

## License

This project is released under the [MIT License](LICENSE), inheriting from the original [`minimalESN`](https://mantas.info/code/simple_esn/) reference implementation where applicable.
