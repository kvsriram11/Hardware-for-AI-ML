# Arithmetic Intensity Calculation

## Dominant Kernel Selection

The cleaned software baseline was profiled using `cProfile` after removing plotting overhead from the execution path. The largest single function in the raw profile is spectral-radius normalization through `scipy.linalg.eig()`, which is a one-time initialization step used during reservoir construction. Since the project targets streaming inference acceleration rather than offline setup, the selected hardware target is the **recurring reservoir state-update kernel** executed repeatedly during training-state collection and generative inference.

Profiled recurring functions:

- `collect_states()` = 1.228 s
- `run_generative()` = 0.762 s

Total recurring state-update time:

\[
1.228 + 0.762 = 1.990 \text{ s}
\]

Total profiled runtime:

\[
7.144 \text{ s}
\]

Recurring kernel runtime share:

\[
\frac{1.990}{7.144} \times 100 \approx 27.9\%
\]

Therefore, the dominant operational kernel for acceleration is the **reservoir state update**, accounting for approximately **27.9%** of total profiled runtime in the current software baseline. One-time initialization functions remain outside the primary acceleration scope. :contentReference[oaicite:0]{index=0}

---

## Kernel Equation

The Echo State Network updates its internal state each timestep as:

\[
x(t) = (1-a)x(t-1) + a \tanh(W_{res}x(t-1) + W_{in}u(t))
\]

Where:

- \(x(t)\) = current reservoir state
- \(x(t-1)\) = previous state
- \(u(t)\) = input sample
- \(W_{res}\) = recurrent reservoir matrix
- \(W_{in}\) = input matrix
- \(a\) = leaking rate

For this baseline:

- Reservoir size \(N = 1000\)
- Input size = 1
- NumPy/SciPy default datatype is FP64
- Each FP64 value = 8 bytes

---

## FLOP Count Per State Update

Arithmetic operations are counted analytically for one timestep.

### 1. Recurrent Matrix-Vector Multiply

\[
W_{res}x(t-1)
\]

Dense \(N \times N\) matrix-vector multiply:

\[
N \times (N \text{ mult} + (N-1) \text{ add}) \approx 2N^2
\]

For \(N=1000\):

\[
2(1000)^2 = 2{,}000{,}000
\]

FLOPs.

### 2. Input Projection

\[
W_{in}u(t)
\]

The implementation stacks \([1,u]\), so \(W_{in}\) is \(N \times 2\):

\[
N \times (2 \text{ mult} + 1 \text{ add}) = 3N
\]

For \(N=1000\):

\[
3000
\]

FLOPs.

### 3. Vector Accumulation

Adding recurrent and input terms:

\[
N = 1000
\]

FLOPs.

### 4. tanh Activation

One nonlinear activation per element:

\[
N = 1000
\]

operations.

**Note:** For roofline-level modeling, tanh is counted as one elementwise operation per state entry. Exact floating-point micro-operation counts depend on software library implementation or hardware approximation method.

### 5. Leak Integration

\[
(1-a)x(t-1)+a\tanh(\cdot)
\]

Per element:

- 2 multiplies
- 1 add

\[
3N = 3000
\]

FLOPs.

---

## Total FLOPs

\[
2N^2 + 3N + N + N + 3N
\]

\[
= 2N^2 + 8N
\]

Substitute \(N=1000\):

\[
2(1000)^2 + 8(1000)
\]

\[
= 2{,}000{,}000 + 8{,}000
\]

\[
= 2{,}008{,}000
\]

\[
\boxed{\text{FLOPs per state update} \approx 2.008 \times 10^6}
\]

---

## Byte Count Per State Update

Following the assignment requirement, bytes are estimated assuming all operands are fetched from DRAM with no reuse. This is intentionally conservative. Actual cache reuse or on-chip SRAM buffering can reduce bandwidth demand significantly. :contentReference[oaicite:1]{index=1}

### 1. Recurrent Weights

\[
1000 \times 1000 \times 8 = 8{,}000{,}000
\]

bytes.

### 2. Input Weights

\[
1000 \times 2 \times 8 = 16{,}000
\]

bytes.

### 3. Previous State Vector

\[
1000 \times 8 = 8{,}000
\]

bytes.

### 4. Input Vector \([1,u]\)

\[
2 \times 8 = 16
\]

bytes.

### 5. Output State Vector Writeback

\[
1000 \times 8 = 8{,}000
\]

bytes.

---

## Total Bytes

\[
8{,}000{,}000 + 16{,}000 + 8{,}000 + 16 + 8{,}000
\]

\[
= 8{,}032{,}016
\]

\[
\boxed{\text{Bytes per state update} \approx 8.032 \times 10^6}
\]

---

## Arithmetic Intensity

\[
AI = \frac{\text{FLOPs}}{\text{Bytes}}
\]

\[
AI = \frac{2{,}008{,}000}{8{,}032{,}016}
\]

\[
AI \approx 0.25
\]

\[
\boxed{AI \approx 0.25 \text{ FLOP/byte}}
\]

---

## Interpretation

An arithmetic intensity of **0.25 FLOP/byte** is low, which indicates the dense software kernel is strongly **memory-bound** under the no-reuse DRAM model. This motivates the proposed accelerator direction:

- structured sparsity to reduce weight traffic
- local SRAM / buffering to reuse states and weights
- parallel MAC datapath to raise throughput
- improved effective arithmetic intensity relative to the dense baseline

---

## Summary

- Largest raw single function: spectral-radius normalization (`eig`)
- Selected acceleration target: recurring reservoir state-update kernel
- Runtime share of recurring kernel: **27.9%**
- FLOPs per timestep: **2,008,000**
- Bytes per timestep: **8,032,016**
- Arithmetic intensity: **0.25 FLOP/byte**
- Bound classification: **memory-bound**

This confirms that accelerating the repeated state-update path is more valuable than accelerating one-time initialization work. :contentReference[oaicite:2]{index=2}
