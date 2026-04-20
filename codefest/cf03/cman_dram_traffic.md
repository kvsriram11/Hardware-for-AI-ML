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

- `k` runs from `0` to `31`
- so `A[i][k]` is accessed `32` times total
- and `B[k][j]` is also accessed `32` times total

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

So total accesses across the full output matrix are:

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
\boxed{\text{Naive DRAM traffic} = 262144 \text{ bytes}}
$$

---

## 2. Tiled loop (`T = 8`)

Number of tiles along one dimension:

$$
\frac{N}{T} = \frac{32}{8} = 4
$$

So the output matrix is divided into:

$$
4 \times 4 = 16 \text{ output tiles}
$$

For each output tile:

- we must iterate over 4 positions in the reduction dimension
- so each output tile needs:
  - 4 tiles from `A`
  - 4 tiles from `B`

### Total A-tile loads

$$
16 \times 4 = 64
$$

### Total B-tile loads

$$
16 \times 4 = 64
$$

### Total tile loads

$$
64 + 64 = 128
$$

Each tile is `8 × 8`, so each tile contains:

$$
T^2 = 8^2 = 64 \text{ elements}
$$

So total element loads are:

$$
128 \times 64 = 8192
$$

Each element is 4 bytes.

### Total tiled DRAM traffic

$$
8192 \times 4 = 32768 \text{ bytes}
$$

So,

$$
\boxed{\text{Tiled DRAM traffic} = 32768 \text{ bytes}}
$$

---

## 3. Ratio of naive DRAM traffic to tiled DRAM traffic

From above:

- Naive DRAM traffic = `262144 bytes`
- Tiled DRAM traffic = `32768 bytes`

So the ratio is:

$$
\frac{262144}{32768} = 8
$$

Therefore,

$$
\boxed{\text{Naive/Tiled traffic ratio} = 8}
$$

### Explanation

The ratio comes out to `8` because tiling allows each loaded tile to be reused across 8 multiply-accumulate steps, so the DRAM traffic is reduced by the tile size `T = 8`.

> Note: If the handout says the ratio equals `N`, that is inconsistent with the direct tile-load counting above. Using the actual tile-load calculation, the correct ratio is `8`.

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
32768 \text{ bytes}
$$

So memory time is:

$$
t_{\text{tiled,mem}} = \frac{32768}{320 \times 10^9}
$$

$$
t_{\text{tiled,mem}} = 1.024 \times 10^{-7} \text{ s}
$$

$$
\boxed{t_{\text{tiled,mem}} = 102.4 \text{ ns}}
$$

Compare:

- compute time = `6.5536 ns`
- memory time = `102.4 ns`

Since memory time is still larger,

$$
\boxed{\text{Tiled case is also memory-bound}}
$$

So execution time is approximately:

$$
\boxed{t_{\text{tiled}} \approx 102.4 \text{ ns}}
$$

---

## Final Answers

- **Naive DRAM traffic** = `262144 bytes`
- **Tiled DRAM traffic** = `32768 bytes`
- **Traffic ratio** = `8`
- **Naive execution time** = `819.2 ns` → memory-bound
- **Tiled execution time** = `102.4 ns` → memory-bound
