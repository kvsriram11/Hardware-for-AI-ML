# Arithmetic Intensity Calculation

## Dominant kernel selection

The cleaned software baseline was profiled using `cProfile` after removing plotting overhead from the execution path. The largest single function in the raw profile is spectral-radius normalization through `scipy.linalg.eig()`, which is a one-time initialization step used during reservoir construction.

Since the project targets streaming inference acceleration rather than offline setup, the selected hardware target is the **recurring reservoir state-update kernel** executed repeatedly during training-state collection and generative inference.

Profiled recurring functions:

- `collect_states()` = 1.228 s
- `run_generative()` = 0.762 s

Total recurring state-update time:

`1.228 + 0.762 = 1.990 s`

Total profiled runtime:

`7.144 s`

Recurring kernel runtime share:

`(1.990 / 7.144) × 100 = 27.9%`

Therefore, the dominant operational kernel for acceleration is the **reservoir state update**, accounting for approximately **27.9%** of total profiled runtime in the current software baseline. One-time initialization functions remain outside the primary acceleration scope.

---

## Kernel equation

The Echo State Network updates its internal state each timestep as:

`x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))`

Where:

- `x(t)` = current reservoir state  
- `x(t-1)` = previous state  
- `u(t)` = input sample  
- `Wres` = recurrent reservoir matrix  
- `Win` = input matrix  
- `a` = leaking rate  

For this baseline:

- Reservoir size `N = 1000`
- Input size = 1
- NumPy / SciPy default datatype = FP64
- Each FP64 value = 8 bytes

---

# FLOP count per state update

Arithmetic operations are counted analytically for one timestep.

## 1. Recurrent matrix-vector multiply

`Wres * x(t-1)`

Dense `N x N` matrix-vector multiply:

Each row performs:

- `N` multiplies
- `(N - 1)` adds

Approximation:

`≈ 2N²`

For `N = 1000`:

`2 × 1000² = 2,000,000 FLOPs`

---

## 2. Input projection

`Win * u(t)`

The implementation stacks `[1, u]`, so `Win` is `N x 2`

Per row:

- 2 multiplies
- 1 add

Total:

`3N`

For `N = 1000`:

`3 × 1000 = 3,000 FLOPs`

---

## 3. Vector accumulation

Add recurrent term and input term:

`N = 1000 FLOPs`

---

## 4. tanh activation

One nonlinear activation per state element:

`N = 1000 operations`

**Modeling note:** For roofline-level analysis, tanh is counted as one operation per element. Exact floating-point internal cost depends on software implementation or hardware approximation method.

---

## 5. Leak integration

`(1-a)x(t-1) + a*tanh(...)`

Per element:

- 2 multiplies
- 1 add

Total:

`3N`

For `N = 1000`:

`3,000 FLOPs`

---

# Total FLOPs

Total per timestep:

`2N² + 3N + N + N + 3N`

Simplified:

`2N² + 8N`

Substitute `N = 1000`

`2(1000²) + 8(1000)`

`= 2,000,000 + 8,000`

`= 2,008,000 FLOPs`

**Final result:**

`≈ 2.008 × 10^6 FLOPs per state update`

---

# Byte count per state update

Following the assignment requirement, bytes are estimated assuming all operands are fetched from DRAM with no reuse. This is conservative. Real cache reuse or on-chip SRAM buffering can reduce bandwidth significantly.

## 1. Recurrent weights

Matrix size:

`1000 x 1000`

Bytes:

`1000 × 1000 × 8 = 8,000,000 bytes`

---

## 2. Input weights

Matrix size:

`1000 x 2`

Bytes:

`1000 × 2 × 8 = 16,000 bytes`

---

## 3. Previous state vector

Size:

`1000`

Bytes:

`1000 × 8 = 8,000 bytes`

---

## 4. Input vector `[1,u]`

Size:

`2`

Bytes:

`2 × 8 = 16 bytes`

---

## 5. Output state vector writeback

Size:

`1000`

Bytes:

`1000 × 8 = 8,000 bytes`

---

# Total bytes

`8,000,000 + 16,000 + 8,000 + 16 + 8,000`

`= 8,032,016 bytes`

**Final result:**

`≈ 8.032 × 10^6 bytes`

---

# Arithmetic intensity

Definition:

`AI = FLOPs / Bytes`

Substitute values:

`AI = 2,008,000 / 8,032,016`

`AI = 0.25 FLOP/byte`

---

# Interpretation

An arithmetic intensity of **0.25 FLOP/byte** is low. This means the dense software kernel is strongly **memory-bound** under the no-reuse DRAM model.

This motivates the proposed hardware accelerator approach:

- structured sparsity to reduce weight traffic
- on-chip SRAM / buffering for reuse
- parallel MAC datapath for higher throughput
- better effective arithmetic intensity than dense software baseline

---

# Summary

Summary

- Largest raw single initialization function: spectral-radius normalization (eig)
- Selected hardware target: recurring reservoir state-update kernel
- Python-visible runtime share of state-update phases: 27.9%
- Additional compute may reside inside NumPy / BLAS native kernels
- FLOPs per timestep: 2,008,000
- Bytes per timestep: 8,032,016
- Arithmetic intensity: 0.25 FLOP/byte
- Classification: memory-bound

This confirms that accelerating the repeated state-update path is more valuable than accelerating one-time initialization work.
