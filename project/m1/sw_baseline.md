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

## Overview

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

## Workload Description

The ESN is evaluated using the Mackey-Glass chaotic time-series benchmark.

Core reservoir update equation:

```text
x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))
```

Where:

- `x(t)` = reservoir state vector
- `u(t)` = input sample
- `Wres` = recurrent reservoir weight matrix
- `Win` = input weight matrix
- `a` = leaking rate

Reservoir size used in this baseline:

- 1000 neurons

---

## Platform and Configuration

### Hardware Platform

- System Manufacturer: HP
- System Model: HP Spectre x360 Convertible 14-ea0xxx
- CPU: 11th Gen Intel Core i7-1165G7 @ 2.80 GHz
- CPU Cores / Threads: 4 cores / 8 threads
- Installed RAM: 16 GB
- GPU: Not used for software baseline benchmark
- System Type: x64-based PC

### Software Platform

- OS: Microsoft Windows 11 Home
- OS Version: 10.0.26200 Build 26200
- Python Version: 3.14.3
- Libraries: NumPy, SciPy, Matplotlib

### Dataset

- MackeyGlass_t17.txt

### Simulation Parameters

- Training length: 2000 timesteps
- Testing length: 2000 timesteps
- Washout length: 100 timesteps
- Reservoir size: 1000
- Leak rate: 0.3
- Random seed: 42
- Batch size: 1 (sequential streaming timestep processing)

---

## Functional Accuracy

Measured prediction quality:

- Mean Squared Error (MSE): `1.026e-06`

This confirms that the software baseline is functioning correctly and producing stable predictions.

---

## Execution Time Benchmark

Wall-clock runtime was measured over 10 repeated runs.

The first run showed startup overhead from Python process launch, library initialization, and file/cache warmup. Since the project focuses on sustained kernel performance rather than one-time startup cost, steady-state runs 2–10 are used as the primary baseline for later comparison.

| Metric | Value |
|---|---|
| Full 10-run Mean Runtime | 3.74 s |
| Full 10-run Median Runtime | 2.91 s |
| Full 10-run Minimum Runtime | 2.60 s |
| Full 10-run Maximum Runtime | 11.95 s |
| Steady-State Median Runtime (Runs 2–10) | 2.85 s |
| Number of Runs | 10 |

The steady-state median runtime is used as the primary software baseline metric for later speedup comparison.

---

## Throughput

Each full execution performs:

- 2000 training-state updates
- 2000 inference-state updates

Total:

- 4000 reservoir state updates per run

Using the steady-state median runtime of `2.85 s`:

### Runtime Throughput

| Metric | Value |
|---|---|
| Full Runs / Second | 0.351 runs/s |
| State Updates / Second | 1403 updates/s |

### Estimated Compute Throughput

Using the arithmetic model derived separately:

- FLOPs per state update ≈ `2,008,000`

Estimated compute rate:

```text
(2,008,000 × 4000) / 2.85
```

≈ `2.82 GFLOPs/s`

---

## Memory Usage

| Metric | Value |
|---|---|
| Peak Child RSS Across Runs | 4.28 MB |
| Mean Peak Child RSS Across Runs | 3.94 MB |
| Wrapper Process RSS | 22.70 MB |
| GPU Memory Usage | Not applicable |

Note: Peak child RSS was measured by monitoring the spawned `minimalESN.py` process during execution. Reported RSS may still underestimate short-lived native library allocations on Windows, but it is more relevant than wrapper-only process memory.

---

## Profiling Summary

Python `cProfile` was used to identify runtime hotspots.

| Function | Contribution |
|---|---|
| Spectral radius normalization (`eig`) | High one-time setup cost |
| Reservoir state collection | Major recurring cost |
| Generative inference loop | Major recurring cost |
| Ridge regression training | Moderate cost |

### Key Observation

The most important recurring workload is the reservoir state-update loop, which repeatedly performs:

- Matrix-vector multiplication
- Accumulation
- `tanh` activation
- Leak-rate blending
- State writeback

This recurring kernel is the best target for hardware acceleration rather than one-time initialization functions.

---

## Why Acceleration is Needed

The baseline uses a dense `1000 × 1000` recurrent matrix.

This creates:

- High arithmetic workload
- Large memory traffic
- Poor scaling for larger reservoirs
- Limited CPU efficiency for streaming workloads

---

## Hardware Direction

Planned accelerator target:

- Reservoir State Update Engine

Likely features:

- Structured sparse weight storage
- Parallel MAC array
- Streaming interface
- `tanh` approximation hardware
- On-chip state memory
- Synthesizable SystemVerilog RTL
- OpenLane compatible implementation path

---

## Baseline Importance

This software model serves as the golden reference for:

- Functional verification
- Accuracy comparison
- Speedup measurement
- Throughput comparison
- Memory comparison
- RTL validation

---

## Next Steps

- Sweep reservoir sizes (128 / 256 / 512 / 1024)
- Measure scaling behavior
- Introduce sparsity patterns
- Build cycle-accurate RTL model
- Compare software vs hardware performance
- Perform synthesis / area analysis

---

## License

MIT License (inherits original `minimalESN` reference implementation where applicable)
