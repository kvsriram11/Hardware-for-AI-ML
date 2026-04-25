# Hardware Accelerator for Reservoir State Update in Echo State Networks

**Course:** ECE 510 — Hardware for AI/ML, Spring 2026  
**Author:** Venkata Sriram Kamarajugadda  
**Instructor:** Prof. Christof Teuscher, Portland State University  
**GitHub:** [kvsriram11/Hardware-for-AI-ML](https://github.com/kvsriram11/Hardware-for-AI-ML)

---

## Overview

Echo State Networks (ESNs) are a class of recurrent reservoir computing models effective at streaming time-series inference. Their dominant computational cost — the reservoir state update — is executed thousands of times per inference run and is bottlenecked by memory bandwidth, not arithmetic throughput. On a general-purpose CPU, the dense 1000×1000 recurrent weight matrix must be repeatedly fetched from DRAM, yielding an arithmetic intensity of only 0.25 FLOP/byte and placing the kernel firmly in the memory-bound region of the roofline model.

This project designs, implements, and benchmarks a custom co-processor chiplet that accelerates the reservoir state-update kernel using structured sparsity, on-chip state buffering, and a pipelined MAC datapath — targeting measurable throughput improvement over the software baseline with a research-grade multi-precision comparison.

---

## Target Kernel

The kernel accelerated by the chiplet is:

```
x(t) = (1 - a) * x(t-1) + a * tanh( W_res * x(t-1) + W_in * u(t) )
```

| Symbol | Description |
|--------|-------------|
| `x(t)` | Reservoir state vector (N = 1000) |
| `W_res` | Recurrent weight matrix (N × N) |
| `W_in` | Input weight matrix (N × 2) |
| `u(t)` | Input sample |
| `a` | Leak rate (0.3) |

The dominant operation is the recurrent matrix-vector multiply `W_res * x(t-1)`. The full update chain — input projection, vector accumulation, tanh activation, and leak-rate blending — is the sole hardware target. All other ESN functions (spectral normalization, readout training, orchestration) remain in software on the host.

---

## Software Baseline

Measured on an Intel Core i7-1165G7 running Windows 11, Python 3.12, NumPy + SciPy. Benchmark uses the Mackey-Glass (delay-17) chaotic time-series dataset with a reservoir of 1000 neurons.

| Metric | Value |
|--------|-------|
| Median wall-clock runtime | 2.85 s / run (steady-state, runs 2–10) |
| State update throughput | 1,403 updates/s |
| Estimated compute rate | 2.82 GFLOP/s |
| Arithmetic intensity | 0.25 FLOP/byte |
| Prediction MSE | 1.026 × 10⁻⁶ |
| Peak process RSS | 4.28 MB |
| Benchmark runs | 10 |

The kernel is **memory-bound** on the host platform. The i7-1165G7 roofline has a ridge point of 3.50 FLOP/byte; the software kernel at 0.25 FLOP/byte is well into the bandwidth-limited region, achieving roughly 1.6% of peak compute throughput.

---

## Accelerator Design

### Hardware / Software Partition

**Chiplet (hardware):**
- Structured-sparse recurrent MAC array
- On-chip SRAM state vector buffer (eliminates repeated DRAM fetches)
- Piecewise-linear tanh approximation unit
- Leak-rate blending datapath
- AXI4-Stream data interface
- AXI4-Lite control register interface

**Host (software):**
- Spectral radius normalization (one-time setup)
- Ridge regression readout training
- Weight loading and configuration
- Dataset I/O, logging, and verification

### Hardware Interface

| Parameter | Value |
|-----------|-------|
| Data interface | AXI4-Stream |
| Control interface | AXI4-Lite |
| Host platform | FPGA SoC |
| Required bandwidth | 0.00016 GB/s (scalar I/O only) |
| Interface bottleneck | No — 0.04% of rated AXI4-Stream capacity |

The reservoir state vector is stored on-chip. Only the scalar input `u(t)` and scalar output cross the external interface per timestep, so the accelerator is not interface-bound.

---

## Precision Study

This project targets a research-grade multi-precision comparison suitable for publication.

| Precision | Role | Description |
|-----------|------|-------------|
| FP32 | Baseline accelerator | Functionally correct reference; direct comparison with CPU/GPU |
| INT16 (Q15) | Primary research variant | Reduced area and power; full quantization error analysis |
| INT8 | Stretch goal | Second data point if schedule allows |

**Evaluation matrix:**

```
CPU (FP64)  →  GPU  →  Accel-FP32  →  Accel-INT16  →  Accel-INT8  →  SOTA (if applicable)
```

---

## Toolchain

| Tool | Purpose |
|------|---------|
| SystemVerilog | RTL hardware description |
| OpenLane 2 | RTL-to-GDSII synthesis flow |
| cocotb / Verilator | Simulation and testbench |
| Python, NumPy, SciPy | Software baseline and golden reference |
| cProfile / line_profiler | Runtime profiling |

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

> **Note:** The `codefest/` directory contains all codefest submissions for the course. Some codefest tasks are directly related to the project (e.g., cf02 — roofline and profiling) and feed into milestone deliverables. Others are standalone exercises unrelated to the ESN accelerator. Project-relevant codefest work is referenced explicitly in the milestone documentation above.

---

## Milestones

| Milestone | Due | Status | Deliverables |
|-----------|-----|--------|--------------|
| M1 | Apr 12 | ✅ Satisfactory | Baseline, profiling, roofline, interface selection, block diagram |
| M2 | May 3  | 🔄 In progress | Compute core HDL + testbench, AXI interface HDL + testbench, precision analysis |
| M3 | May 24 | ⬜ Upcoming | OpenLane 2 synthesis, timing + area report, end-to-end co-simulation |
| M4 | Jun 7  | ⬜ Upcoming | Full package: synthesis results, benchmark comparison, design justification report |

---

## License

MIT License — inherits from the original `minimalESN` reference implementation where applicable.
