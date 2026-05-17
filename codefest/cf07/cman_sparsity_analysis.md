# CMAN — Sparsity Breakeven Analysis

**Codefest 7 — CMAN Deliverable**
**ECE 410/510: Hardware for AI and ML, Spring 2026**

---

## Setup

- Weight matrix `W` of size `N × N`, with `N = 512`
- Sparsity `s` = fraction of zeros, so fraction of nonzeros = `(1 − s)`
- Number of nonzeros: **nnz = (1 − s)·N²**
- Dense storage: 4 bytes (FP32) per element
- CSR storage:
  - `values[]`: nnz entries × 4 bytes (FP32)
  - `col_idx[]`: nnz entries × 4 bytes (INT32)
  - `row_ptr[]`: (N+1) entries × 4 bytes (INT32)
- Convention used here: **FLOPs**, where 1 MAC = 2 FLOPs (1 multiply + 1 add)

---

## Task 1 — Four Expressions for Dense and Sparse Compute/Memory

### (a) Dense MVM compute (FLOPs)

A dense MVM performs one MAC per matrix entry: N² MACs total. Each MAC = 2 FLOPs.

$$
\boxed{\text{Dense FLOPs} = 2N^2}
$$

For N = 512: 2 × 262,144 = **524,288 FLOPs**

### (b) Dense memory bytes

All N² weights stored, 4 bytes each.

$$
\boxed{\text{Dense bytes} = 4N^2}
$$

For N = 512: 4 × 262,144 = **1,048,576 bytes (~1 MB)**

### (c) Sparse compute (FLOPs)

If hardware skips zero MACs, only nnz MACs are performed.

$$
\boxed{\text{Sparse FLOPs} = 2 \cdot \text{nnz} = 2(1-s)N^2}
$$

### (d) Sparse memory bytes (CSR)

Sum of the three CSR arrays:

| Array | Entries | Bytes |
|---|---|---|
| `values` | nnz | 4·nnz |
| `col_idx` | nnz | 4·nnz |
| `row_ptr` | N+1 | 4·(N+1) |

$$
\boxed{\text{Sparse bytes} = 8 \cdot \text{nnz} + 4(N+1) = 8(1-s)N^2 + 4(N+1)}
$$

---

## Task 2 — FLOPs Speedup and the 2× Point

### Speedup expression

$$
\text{Speedup}_{\text{compute}} = \frac{\text{Dense FLOPs}}{\text{Sparse FLOPs}} = \frac{2N^2}{2(1-s)N^2} = \frac{1}{1-s}
$$

The factor of 2 (and N²) cancels cleanly, leaving a function of sparsity alone.

### Sparsity for 2× speedup

Set the speedup to 2 and solve:

$$
\frac{1}{1-s} = 2 \;\;\Rightarrow\;\; 1 - s = \frac{1}{2} \;\;\Rightarrow\;\; \boxed{s = 0.5}
$$

**At 50% sparsity, a sparsity-exploiting accelerator does half the MACs of a dense unit → 2× compute speedup.**

### Reference table

| Sparsity s | Compute speedup |
|---|---|
| 0.0 | 1× |
| 0.5 | 2× |
| 0.9 | 10× |
| 0.99 | 100× |

The growth is superlinear in s — this is why neural network pruning research targets very high sparsity.

---

## Task 3 — Memory Breakeven Sparsity

### Setup

Find the sparsity `s` at which sparse memory bytes equal dense memory bytes.

### Derivation

Set 1(d) = 1(b):

$$
8(1-s)N^2 + 4(N+1) = 4N^2
$$

Divide both sides by 4:

$$
2(1-s)N^2 + (N+1) = N^2
$$

Isolate the (1−s) term:

$$
2(1-s)N^2 = N^2 - (N+1)
$$

$$
(1-s) = \frac{N^2 - N - 1}{2N^2}
$$

$$
\boxed{s = 1 - \frac{N^2 - N - 1}{2N^2}}
$$

### Numerical value at N = 512

$$
s = 1 - \frac{262144 - 512 - 1}{2 \cdot 262144} = 1 - \frac{261631}{524288} = 1 - 0.49902 \approx \mathbf{0.5010}
$$

### Approximate (large-N) result

For large N, the `(N+1)` term is negligible compared to N². Dropping it:

$$
2(1-s)N^2 \approx N^2 \;\;\Rightarrow\;\; (1-s) \approx \frac{1}{2} \;\;\Rightarrow\;\; s \approx 0.5
$$

### Interpretation

The breakeven sits **just above 50%**. Two structural reasons:

1. **The 50% floor comes from CSR's per-nonzero overhead.** Each nonzero costs 8 bytes in CSR (4 for the FP32 value + 4 for the INT32 column index) versus 4 bytes in dense format. CSR pays a **2× per-nonzero tax**, so you must eliminate at least half the entries just to compensate.
2. **The +0.001 offset comes from `row_ptr`.** This adds a constant 4·(N+1) ≈ 2 KB overhead — negligible for N = 512 (~0.2% of the matrix), but it shifts breakeven slightly above 0.5.

**Above s ≈ 0.501, CSR uses less memory than dense.** Below that threshold, CSR is actually *more* expensive — a critical caveat that's easy to miss.

---

## Task 4 — End-to-End Speedup at s = 0.9 (Memory-Bound)

### Setup

System parameters:
- N = 512
- s = 0.9
- Memory bandwidth = 320 GB/s

In a memory-bandwidth-limited system, execution time is dominated by **bytes moved**, not FLOPs computed:

$$
T \approx \frac{\text{bytes loaded}}{\text{bandwidth}}
$$

### Calculation

**Dense bytes:**
$$
4N^2 = 4 \times 262{,}144 = 1{,}048{,}576 \text{ bytes}
$$

**Sparse bytes at s = 0.9:**
$$
8(1-s)N^2 + 4(N+1) = 8 \times 0.1 \times 262{,}144 + 4 \times 513
$$
$$
= 209{,}715 + 2{,}052 = 211{,}767 \text{ bytes}
$$

**End-to-end speedup (bandwidth cancels in the ratio):**
$$
\text{Speedup}_{\text{end-to-end}} = \frac{T_{\text{dense}}}{T_{\text{sparse}}} = \frac{\text{Dense bytes}}{\text{Sparse bytes}} = \frac{1{,}048{,}576}{211{,}767} \approx \boxed{4.95\times}
$$

### Sanity check — absolute times

| Version | Bytes | Time at 320 GB/s |
|---|---|---|
| Dense | 1,048,576 | 3.28 µs |
| Sparse (s = 0.9) | 211,767 | 0.66 µs |

3.28 / 0.66 ≈ 4.95× ✓

### The key insight — compute vs. memory speedup gap

| Metric at s = 0.9 | Speedup |
|---|---|
| Pure compute (FLOPs) | **10×** |
| End-to-end (memory-bound) | **~4.95×** |

**The end-to-end speedup is roughly half the compute speedup.** This gap is the central insight of the analysis.

### Why the gap exists

In the memory-bound regime, the speedup is bounded by the bytes ratio:

$$
\frac{\text{Sparse bytes}}{\text{Dense bytes}} \approx \frac{8(1-s)N^2}{4N^2} = 2(1-s)
$$

At s = 0.9: 2 × 0.1 = 0.2 → 5× less memory → ~5× speedup.

That **factor of 2** is the same per-nonzero CSR overhead that drove the 50% breakeven in Task 3. Although 90% of the *entries* were eliminated, only ~80% of the *memory traffic* was eliminated, because every surviving nonzero costs 8 bytes instead of 4.

### Takeaway for hardware design

Sparse acceleration in memory-bound systems is fundamentally limited by indexing overhead. This motivates:

- **Structured sparsity** (e.g., N:M sparsity, block sparsity) that amortizes or eliminates per-nonzero indices
- **Compressed index encodings** (e.g., shared bit-masks for blocks)
- **On-chip storage** that converts repeated loads into reuse

For streaming inference workloads such as reservoir state updates (W·x at each timestep), the MVM is the dominant cost and lives squarely in the memory-bound regime — making the compute-vs-memory gap a primary design constraint for any sparse-accelerator implementation.

---

## Summary

| Task | Result |
|---|---|
| 1(a) Dense compute | 2N² FLOPs |
| 1(b) Dense memory | 4N² bytes |
| 1(c) Sparse compute | 2(1−s)N² FLOPs |
| 1(d) Sparse memory | 8(1−s)N² + 4(N+1) bytes |
| 2 Compute speedup | 1/(1−s); s = 0.5 for 2× |
| 3 Memory breakeven (N = 512) | s ≈ 0.501 |
| 4 End-to-end speedup (s = 0.9, memory-bound) | ≈ 4.95× |
