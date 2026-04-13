# Arithmetic Intensity Calculation

## Purpose

This document estimates the arithmetic intensity of the software baseline to identify whether the dominant ESN workload is compute-bound or memory-bound. The result is used for roofline analysis and hardware accelerator justification.

---

# Dominant Kernel Selection

The cleaned software baseline was profiled using `cProfile` after removing plotting overhead from the execution path.

The largest raw single function in the profile is spectral-radius normalization through `scipy.linalg.eig()`. However, this is a one-time initialization step used during reservoir construction and is not part of repeated streaming inference.

The dominant recurring kernel is the **reservoir state-update computation**, accounting for approximately **27.9% of total profiled runtime** at the Python-visible level.

Visible recurring phases:

- `collect_states()` = 1.228 s
- `run_generative()` = 0.762 s

Total recurring state-update time:

`1.228 + 0.762 = 1.990 s`

Total profiled runtime:

`7.144 s`

Runtime share:

`(1.990 / 7.144) × 100 = 27.9%`

**Note:** Additional execution time may reside inside optimized NumPy / BLAS native kernels called by these phases.

---

# Kernel Equation

The Echo State Network updates its internal state each timestep as:

`x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))`

Where:

- `x(t)` = current reservoir state vector
- `x(t-1)` = previous state vector
- `u(t)` = input sample
- `Wres` = recurrent reservoir matrix
- `Win` = input matrix
- `a` = leaking rate

Software baseline parameters:

- Reservoir size `N = 1000`
- Input size = 1
- Arrays use FP64 precision
- Each FP64 element = 8 bytes

---

# FLOP Count Per State Update

Arithmetic operations are derived analytically for one timestep.

---

## 1. Recurrent Matrix-Vector Multiply

`Wres * x(t-1)`

Dense matrix size:

`N x N`

Each output row performs:

- `N` multiplications
- `(N - 1)` additions

Approximation:

`N × (N + N - 1) ≈ 2N²`

For `N = 1000`:

`2 × 1000² = 2,000,000 FLOPs`

---

## 2. Input Projection

`Win * u(t)`

The implementation stacks `[1, u]`, so `Win` has size:

`N x 2`

Each row performs:

- 2 multiplications
- 1 addition

Total:

`3N`

For `N = 1000`:

`3 × 1000 = 3,000 FLOPs`

---

## 3. Vector Accumulation

Add recurrent term and input term:

`N`

For `N = 1000`:

`1,000 FLOPs`

---

## 4. tanh Activation

One nonlinear activation per state element:

`N`

For `N = 1000`:

`1,000 operations`

**Modeling Note:** For roofline-level analysis, tanh is counted as one abstract elementwise operation. Exact internal floating-point cost depends on software library implementation or hardware approximation method.

---

## 5. Leak Integration

`(1-a)x(t-1) + a*tanh(...)`

Per element:

- 2 multiplications
- 1 addition

Total:

`3N`

For `N = 1000`:

`3,000 FLOPs`

---

# Total FLOPs

Total operations per timestep:

`2N² + 3N + N + N + 3N`

Simplified:

`2N² + 8N`

Substitute `N = 1000`

`2(1000²) + 8(1000)`

`= 2,000,000 + 8,000`

`= 2,008,000 FLOPs`

## Final FLOP Count

**≈ 2.008 × 10^6 FLOPs per state update**

---

# Byte Transfer Per State Update

Following the assignment requirement, all operands are assumed to be fetched from DRAM with no reuse. This is intentionally conservative.

Real implementations using cache reuse or on-chip SRAM buffering can reduce external bandwidth significantly.

---

## Weights

### Recurrent Weights

Matrix size:

`1000 x 1000`

Bytes:

`1000 × 1000 × 8 = 8,000,000 bytes`

### Input Weights

Matrix size:

`1000 x 2`

Bytes:

`1000 × 2 × 8 = 16,000 bytes`

---

## Inputs

### Previous State Vector

Size:

`1000`

Bytes:

`1000 × 8 = 8,000 bytes`

### Input Vector `[1,u]`

Size:

`2`

Bytes:

`2 × 8 = 16 bytes`

---

## Outputs

### Updated State Vector Writeback

Size:

`1000`

Bytes:

`1000 × 8 = 8,000 bytes`

---

# Total Bytes

`8,000,000 + 16,000 + 8,000 + 16 + 8,000`

`= 8,032,016 bytes`

## Final Byte Count

**≈ 8.032 × 10^6 bytes per state update**

---

# Arithmetic Intensity

Definition:

`AI = FLOPs / Bytes`

Substitute values:

`AI = 2,008,000 / 8,032,016`

`AI = 0.25 FLOP/byte`

## Final Arithmetic Intensity

**0.25 FLOP/byte**

---

# Interpretation

An arithmetic intensity of **0.25 FLOP/byte** is low. Under the no-reuse DRAM model, the dense software kernel is strongly **memory-bound**.

This motivates the proposed hardware accelerator direction:

- structured sparsity to reduce weight traffic
- on-chip SRAM buffering for reuse
- parallel MAC datapath for higher throughput
- improved effective arithmetic intensity relative to the dense software baseline

---

# Summary

- Dominant recurring kernel: reservoir state-update computation
- Runtime share: 27.9% of total profiled runtime
- FLOPs per timestep: 2,008,000
- Bytes per timestep: 8,032,016
- Arithmetic intensity: 0.25 FLOP/byte
- Classification: memory-bound

This confirms that accelerating the repeated reservoir state-update path is more valuable than accelerating one-time initialization work.
