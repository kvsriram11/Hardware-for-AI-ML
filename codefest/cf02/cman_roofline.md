# Codefest CF02 Roofline Analysis

## Hardware specification

The roofline is constructed using the given hardware parameters:

- Peak compute = **10 TFLOP/s = 10,000 GFLOP/s**
- Peak DRAM bandwidth = **320 GB/s**
- Ridge point:

```text
Ridge point = Peak compute / Peak bandwidth
            = 10,000 / 320
            = 31.25 FLOP/byte
```

Therefore:

- if `AI < 31.25 FLOP/byte`, the kernel is **memory-bound**
- if `AI > 31.25 FLOP/byte`, the kernel is **compute-bound**

---

## (a) Labeled roofline diagram

### Roofline equation

```text
P(AI) = min(10,000, 320 × AI)
```

where:
- `AI` is arithmetic intensity in FLOP/byte
- `P` is attainable performance in GFLOP/s

### Ridge point coordinates

```text
(31.25 FLOP/byte, 10,000 GFLOP/s)
```

### Diagram

Insert the generated labeled roofline figure here, for example:

```text
[Insert roofline_clean.png here]
```

The plot should show:

- bandwidth-limited diagonal: `P = 320 × AI`
- compute-limited ceiling: `P = 10,000 GFLOP/s`
- ridge point at `(31.25, 10,000)`
- Kernel A point: Dense GEMM
- Kernel B point: Vector Addition

---

## (b) Kernel A — Dense GEMM

Kernel A multiplies two FP32 matrices of size `1024 × 1024`.

### FLOPs

For square GEMM:

```text
FLOPs = 2 × N^3
```

With `N = 1024`:

```text
FLOPs = 2 × 1024^3
      = 2 × 1,073,741,824
      = 2,147,483,648 FLOPs
```

### Bytes transferred

Each matrix has:

```text
1024 × 1024 = 1,048,576 elements
```

Each FP32 element is 4 bytes, so each matrix is:

```text
1,048,576 × 4 = 4,194,304 bytes
```

Assuming all three matrices are loaded/stored from DRAM with no cache reuse:

- `A` read = `4,194,304 bytes`
- `B` read = `4,194,304 bytes`
- `C` write = `4,194,304 bytes`

Total bytes:

```text
Bytes = 4,194,304 + 4,194,304 + 4,194,304
      = 12,582,912 bytes
```

### Arithmetic intensity

```text
AI = FLOPs / Bytes
   = 2,147,483,648 / 12,582,912
   = 170.67 FLOP/byte
```

### Attainable performance ceiling

```text
P = min(10,000, 320 × 170.67)
  = min(10,000, 54,614.4)
  = 10,000 GFLOP/s
```

### Bound classification

Since:

```text
170.67 > 31.25
```

Kernel A is **compute-bound** on this hardware.

### Result summary

- FLOPs = **2,147,483,648**
- Bytes = **12,582,912**
- AI = **170.67 FLOP/byte**
- Attainable performance = **10,000 GFLOP/s**
- Bound = **Compute-bound**

### Architectural recommendation

For dense GEMM, the best improvement is to **increase effective compute throughput** using a larger systolic or tensor-style MAC array, because the kernel already has very high arithmetic intensity and is limited by the compute ceiling rather than DRAM bandwidth.

---

## (c) Kernel B — Vector Addition

Kernel B adds two FP32 vectors of length `4,194,304`.

### FLOPs

Vector addition performs one add per element:

```text
FLOPs = N
      = 4,194,304 FLOPs
```

### Bytes transferred

Each vector has:

```text
4,194,304 × 4 = 16,777,216 bytes
```

Traffic assuming no cache reuse:

- `A` read = `16,777,216 bytes`
- `B` read = `16,777,216 bytes`
- `C` write = `16,777,216 bytes`

Total bytes:

```text
Bytes = 16,777,216 + 16,777,216 + 16,777,216
      = 50,331,648 bytes
```

### Arithmetic intensity

```text
AI = FLOPs / Bytes
   = 4,194,304 / 50,331,648
   = 0.08333 FLOP/byte
```

### Attainable performance ceiling

```text
P = min(10,000, 320 × 0.08333)
  = min(10,000, 26.67)
  = 26.67 GFLOP/s
```

### Bound classification

Since:

```text
0.08333 < 31.25
```

Kernel B is **memory-bound** on this hardware.

### Result summary

- FLOPs = **4,194,304**
- Bytes = **50,331,648**
- AI = **0.08333 FLOP/byte**
- Attainable performance = **26.67 GFLOP/s**
- Bound = **Memory-bound**

### Architectural recommendation

For vector addition, the best improvement is to **increase effective memory bandwidth or reduce bytes moved per result**, because the kernel performs very little computation per byte transferred and is fundamentally limited by DRAM traffic rather than compute throughput.

---

## (d) Final comparison

| Kernel | FLOPs | Bytes | AI (FLOP/byte) | Attainable GFLOP/s | Bound |
|---|---:|---:|---:|---:|---|
| Dense GEMM (1024×1024) | 2,147,483,648 | 12,582,912 | 170.67 | 10,000 | Compute-bound |
| Vector Add (4,194,304) | 4,194,304 | 50,331,648 | 0.08333 | 26.67 | Memory-bound |

---

## Conclusion

Kernel A, dense GEMM, lies far to the right of the ridge point and is compute-bound, so architectural effort should focus on increasing MAC throughput and compute utilization. Kernel B, vector addition, lies far to the left of the ridge point and is memory-bound, so performance is best improved by raising memory bandwidth or reducing DRAM traffic per output.
