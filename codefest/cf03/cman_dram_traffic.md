# CMAN — DRAM Traffic Analysis: Naive vs. Tiled Matrix Multiply

## Given

- Matrix size: `N = 32`
- Tile size: `T = 8`
- Data type: `FP32 = 4 bytes/element`
- DRAM bandwidth = `320 GB/s`
- Peak compute = `10 TFLOP/s`

---

## 1. Naive triple loop (`ijk` order)

For matrix multiplication,

$$
C[i][j] = \sum_{k=0}^{N-1} A[i][k]\times B[k][j]
$$

For one output element `C[i][j]`:

- `A[i][k]` is accessed once for each value of `k`
- `B[k][j]` is accessed once for each value of `k`
- since `k` runs from `0` to `31`, each output element requires:
  - `N = 32` accesses to `A`
  - `N = 32` accesses to `B`

So for one output element:

$$
\text{A accesses per output} = N = 32
$$

$$
\text{B accesses per output} = N = 32
$$

Now total number of output elements is:

$$
N^2 = 32^2 = 1024
$$

So total accesses across the full matrix multiplication are:

### Total accesses to A

$$
N^2 \cdot N = N^3 = 32^3 = 32768
$$

### Total accesses to B

$$
N^2 \cdot N = N^3 = 32^3 = 32768
$$

### Total element accesses

$$
32768 + 32768 = 65536
$$

Each access is FP32, so each access is 4 bytes.

### Total naive DRAM traffic

$$
65536 \times 4 = 262144 \text{ bytes}
$$

So,

$$
\boxed{\text{Naive DRAM traffic} = 262144 \text{ bytes} = 256\ \text{KB}}
$$

---

## 2. Tiled loop (`T = 8`)

In the intended tiled DRAM model, tiling allows data loaded from DRAM to be reused on-chip.  
So instead of counting repeated tile fetches during the blocked execution, we count the **unique matrix data** that must be brought from DRAM.

Each matrix has:

$$
N^2 = 32^2 = 1024 \text{ elements}
$$

So:

### Total DRAM loads for A

Each element of `A` is loaded once from DRAM:

$$
N^2 = 1024 \text{ elements}
$$

### Total DRAM loads for B

Each element of `B` is loaded once from DRAM:

$$
N^2 = 1024 \text{ elements}
$$

### Total element loads

$$
1024 + 1024 = 2048
$$

Each element is FP32, so each element is 4 bytes.

### Total tiled DRAM traffic

$$
2048 \times 4 = 8192 \text{ bytes}
$$

So,

$$
\boxed{\text{Tiled DRAM traffic} = 8192 \text{ bytes} = 8\ \text{KB}}
$$

---

## 3. Ratio of naive DRAM traffic to tiled DRAM traffic

From above:

- Naive DRAM traffic = `262144 bytes`
- Tiled DRAM traffic = `8192 bytes`

So the ratio is:

$$
\frac{262144}{8192} = 32
$$

Therefore,

$$
\boxed{\text{Naive/Tiled traffic ratio} = 32}
$$

### One-sentence explanation

The ratio equals `N` because naive GEMM reads matrix data from DRAM `O(N^3)` times, while ideal tiled GEMM loads each matrix element only once from DRAM and reuses it on-chip, reducing DRAM traffic to `O(N^2)`.

---

## 4. Execution time and bottleneck classification

Total floating-point work for GEMM:

$$
2N^3 = 2(32^3) = 2(32768) = 65536 \text{ FLOPs}
$$

Peak compute is:

$$
10 \text{ TFLOP/s} = 10 \times 10^{12} \text{ FLOP/s}
$$

### Compute time

$$
t_{\text{compute}} = \frac{65536}{10 \times 10^{12}}
$$

$$
t_{\text{compute}} = 6.5536 \times 10^{-9} \text{ s}
$$

$$
\boxed{t_{\text{compute}} = 6.5536 \text{ ns}}
$$

---

### Naive case

Naive DRAM traffic:

$$
262144 \text{ bytes}
$$

DRAM bandwidth:

$$
320 \text{ GB/s} = 320 \times 10^9 \text{ bytes/s}
$$

So memory time is:

$$
t_{\text{naive,mem}} = \frac{262144}{320 \times 10^9}
$$

$$
t_{\text{naive,mem}} = 8.192 \times 10^{-7} \text{ s}
$$

$$
\boxed{t_{\text{naive,mem}} = 819.2 \text{ ns}}
$$

Compare:

- compute time = `6.5536 ns`
- memory time = `819.2 ns`

Since memory time is much larger,

$$
\boxed{\text{Naive case is memory-bound}}
$$

So execution time is approximately:

$$
\boxed{t_{\text{naive}} \approx 819.2 \text{ ns}}
$$

---

### Tiled case

Tiled DRAM traffic:

$$
8192 \text{ bytes}
$$

So memory time is:

$$
t_{\text{tiled,mem}} = \frac{8192}{320 \times 10^9}
$$

$$
t_{\text{tiled,mem}} = 2.56 \times 10^{-8} \text{ s}
$$

$$
\boxed{t_{\text{tiled,mem}} = 25.6 \text{ ns}}
$$

Compare:

- compute time = `6.5536 ns`
- memory time = `25.6 ns`

Since memory time is still larger,

$$
\boxed{\text{Tiled case is also memory-bound}}
$$

So execution time is approximately:

$$
\boxed{t_{\text{tiled}} \approx 25.6 \text{ ns}}
$$

---

## Final Answers

- **Naive DRAM traffic** = `262144 bytes`
- **Tiled DRAM traffic** = `8192 bytes`
- **Traffic ratio** = `32`
- **Naive execution time** = `819.2 ns` → memory-bound
- **Tiled execution time** = `25.6 ns` → memory-bound
