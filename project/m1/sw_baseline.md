# Software Baseline

## Project Title

Structured-Sparse Hardware Accelerator for Efficient Reservoir State Update in Streaming Inference

## Course

ECE510: Hardware for AI/ML  
Spring 2026

## Author

Venkata Sriram Kamarajugadda

## Instructor

Prof. Christof Teuscher

---

# Overview

This document summarizes the software baseline used to study the computational behavior of an Echo State Network (ESN) before hardware acceleration.

The purpose of this baseline is to:

- Validate functional correctness of the ESN model
- Measure runtime performance on CPU
- Identify computational bottlenecks
- Select the best recurring kernel for hardware acceleration
- Establish reference metrics for later FPGA / ASIC comparison
- Enable reproducible future Milestone 4 speedup comparisons

The implementation is based on the `minimalESN` Python reference model using NumPy and SciPy.

---

# Workload Description

The ESN is evaluated using the Mackey-Glass chaotic time-series benchmark.

Core reservoir update equation:

`x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))`

Where:

- `x(t)` = reservoir state vector
- `u(t)` = input sample
- `Wres` = recurrent reservoir weight matrix
- `Win` = input weight matrix
- `a` = leaking rate

Reservoir size used in this baseline:

- 1000 neurons

---

# Platform and Configuration

## Hardware Platform

- System Manufacturer: HP
- System Model: HP Spectre x360 Convertible 14-ea0xxx
- CPU: 11th Gen Intel Core i7-1165G7 @ 2.80 GHz
- CPU Cores / Threads: 4 cores / 8 threads
- Installed RAM: 16 GB
- GPU: Not used for software baseline benchmark
- System Type: x64-based PC

## Software Platform

- OS: Microsoft Windows 11 Home
- OS Version: 10.0.26200 Build 26200
- Python Version: 3.14.3
- Libraries: NumPy, SciPy, Matplotlib

## Dataset

- `MackeyGlass_t17.txt`

## Simulation Parameters

- Training length: 2000 timesteps
- Testing length: 2000 timesteps
- Washout length: 100 timesteps
- Reservoir size: 1000
- Leak rate: 0.3
- Random seed: 42
- Batch size: 1 (sequential streaming timestep processing)

---

# Functional Accuracy

Measured prediction quality:

- Mean Squared Error (MSE): **1.026e-06**

This confirms that the software baseline is functioning correctly and producing stable predictions.

---

# Execution Time Benchmark

Wall-clock runtime was measured over **10 repeated runs**.

| Metric | Value |
|------|------|
| Mean Runtime | 8.13 s |
| Median Runtime | 7.86 s |
| Minimum Runtime | 7.09 s |
| Maximum Runtime | 10.02 s |
| Number of Runs | 10 |

The **median runtime** is used as the primary baseline metric for later speedup comparison.

---

# Throughput

Each full execution performs:

- 2000 training-state updates
- 2000 inference-state updates

Total:

- **4000 reservoir state updates per run**

Using median runtime:

## Runtime Throughput

| Metric | Value |
|------|------|
| Full Runs / Second | 0.127 runs/s |
| State Updates / Second | ~509 updates/s |

## Estimated Compute Throughput

Using the arithmetic model derived separately:

- FLOPs per state update ≈ 2,008,000

Estimated compute rate:

`(2,008,000 × 4000) / 7.86`

≈ **1.02 GFLOPs/s**

---

# Memory Usage

| Metric | Value |
|------|------|
| Wrapper Benchmark RSS | 4.46 MB |
| Peak ESN Process RSS | Not yet directly instrumented |
| GPU Memory Usage | Not applicable |

**Note:** Current memory value corresponds to the benchmark wrapper process. Future milestones may use direct process instrumentation for peak runtime memory.

---

# Profiling Summary

Python `cProfile` was used to identify runtime hotspots.

| Function | Contribution |
|------|------|
| Spectral radius normalization (`eig`) | High one-time setup cost |
| Reservoir state collection | Major recurring cost |
| Generative inference loop | Major recurring cost |
| Ridge regression training | Moderate cost |

---

# Key Observation

The most important recurring workload is the reservoir state-update loop, which repeatedly performs:

- Matrix-vector multiplication
- Accumulation
- tanh activation
- Leak-rate blending
- State writeback

This recurring kernel is the best target for hardware acceleration rather than one-time initialization functions.

---

# Why Acceleration is Needed

The baseline uses a dense `1000 x 1000` recurrent matrix.

This creates:

- High arithmetic workload
- Large memory traffic
- Poor scaling for larger reservoirs
- Limited CPU efficiency for streaming workloads

---

# Hardware Direction

Planned accelerator target:

## Reservoir State Update Engine

Likely features:

- Structured sparse weight storage
- Parallel MAC array
- Streaming interface
- tanh approximation hardware
- On-chip state memory
- Synthesizable SystemVerilog RTL
- OpenLane compatible implementation path

---

# Baseline Importance

This software model serves as the golden reference for:

- Functional verification
- Accuracy comparison
- Speedup measurement
- Throughput comparison
- Memory comparison
- RTL validation

---

# Next Steps

- Sweep reservoir sizes (128 / 256 / 512 / 1024)
- Measure scaling behavior
- Introduce sparsity patterns
- Build cycle-accurate RTL model
- Compare software vs hardware performance
- Perform synthesis / area analysis

---

# License

MIT License (inherits original `minimalESN` reference implementation where applicable)
