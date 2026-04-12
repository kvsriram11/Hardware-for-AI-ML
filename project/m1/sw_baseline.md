# Software Baseline

## Project Title
Structured-Sparse Hardware Accelerator for Efficient Reservoir State Update in Streaming Inference

## Course
ECE510: Hardware for AI/ML – Spring 2026

## Author
Venkata Sriram Kamarajugadda

## Instructor
Prof. Christof Teuscher

---

# Overview

This document summarizes the software baseline used to study the computational behavior of an Echo State Network (ESN) before hardware acceleration.

The goal of this baseline is to:

- Validate functional correctness of the ESN model
- Measure runtime performance on a CPU
- Identify computational bottlenecks
- Determine the most suitable kernel for hardware acceleration
- Establish reference metrics for future FPGA / ASIC implementations

The implementation is based on a minimal ESN model using Python, NumPy, and SciPy.

---

# Workload Description

The ESN is evaluated using the Mackey-Glass chaotic time-series benchmark.

Core reservoir update equation:

x(t) = (1 - a)x(t-1) + a tanh(Wres x(t-1) + Win u(t))

Where:

- x(t) = reservoir state vector
- u(t) = input sample
- Wres = recurrent reservoir weight matrix
- Win = input weight matrix
- a = leaking rate

The reservoir size used in this baseline:

- Reservoir neurons: 1000

---

# Experimental Setup

## Platform

- OS: Windows 11
- Python: 3.14.3
- NumPy
- SciPy
- Matplotlib

## Dataset

- MackeyGlass_t17.txt

## Simulation Parameters

- Training length: 2000
- Testing length: 2000
- Washout length: 100
- Reservoir size: 1000
- Leak rate: 0.3
- Random seed: 42

---

# Functional Accuracy

Measured prediction error:

- Mean Squared Error (MSE): **1.026e-06**

This confirms that the software implementation is functioning correctly and generating high-quality predictions.

---

# Runtime Benchmark

10 repeated runs were performed.

| Metric | Value |
|-------|-------|
| Mean Runtime | 8.13 s |
| Median Runtime | 7.86 s |
| Minimum Runtime | 7.09 s |
| Maximum Runtime | 10.02 s |
| Throughput | 0.127 runs/s |

---

# Profiling Summary

Python cProfile was used to identify runtime hotspots.

## Major Functions

| Function | Runtime Contribution |
|---------|----------------------|
| Spectral radius normalization (`eig`) | High one-time setup cost |
| Reservoir state collection | Major recurring cost |
| Generative inference loop | Major recurring cost |
| Ridge regression training | Moderate cost |

---

# Key Observation

The most important recurring workload is the **reservoir state update loop**, which repeatedly performs:

- Matrix-vector multiplication
- Accumulation
- tanh activation
- Leak-rate blending
- State writeback

This kernel dominates streaming inference and is the best candidate for hardware acceleration.

---

# Why Acceleration is Needed

The baseline uses dense matrix-vector multiplication with a 1000 x 1000 reservoir matrix.

This creates:

- High arithmetic workload
- Large memory bandwidth demand
- Poor scalability for larger reservoirs
- Inefficient CPU execution for real-time streaming systems

---

# Hardware Direction

The accelerator will target:

## Reservoir State Update Engine

Features planned:

- Structured sparse weight storage
- Parallel MAC array
- Streaming input/output interface
- tanh approximation hardware
- On-chip state memory
- Synthesizable SystemVerilog RTL
- OpenLane compatible design flow

---

# Baseline Importance

This software model serves as the golden reference for:

- Functional verification
- Accuracy comparison
- Performance speedup measurement
- Power/performance tradeoff studies
- RTL validation

---

# Next Steps

- Sweep reservoir sizes (128 / 256 / 512 / 1024)
- Measure scaling trends
- Introduce sparsity patterns
- Build cycle-accurate RTL model
- Compare software vs hardware throughput
- Perform synthesis and area analysis

---

# License

MIT License (inherits original minimalESN reference implementation where applicable)

---
