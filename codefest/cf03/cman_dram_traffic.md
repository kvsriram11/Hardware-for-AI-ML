# CMAN — DRAM Traffic Analysis: Naive vs. Tiled Matrix Multiply

Given:

- Matrix size: `N = 32`
- Tile size: `T = 8`
- Data type: `FP32 = 4 bytes/element`
- DRAM bandwidth = `320 GB/s`
- Peak compute = `10 TFLOP/s`

## (a) Naive DRAM traffic calculation with formula and values

For naive matrix multiplication,

\[
C[i][j] = \sum_{k=0}^{N-1} A[i][k] \times B[k][j]
\]

For one output element `C[i][j]`:

- accesses to `A` = `N = 32`
- accesses to `B` = `N = 32`

Total number of output elements:

\[
N^2 = 32^2 = 1024
\]

So total element accesses are:

\[
\text{Total A accesses} = N^2 \cdot N = N^3 = 32^3 = 32768
\]

\[
\text{Total B accesses} = N^2 \cdot N = N^3 = 32^3 = 32768
\]

Total element accesses:

\[
32768 + 32768 = 65536
\]

Since each FP32 access is 4 bytes:

\[
\text{Naive DRAM traffic} = 65536 \times 4 = 262144 \text{ bytes}
\]

\[
\boxed{\text{Naive DRAM traffic} = 262144 \text{ bytes} = 256 \text{ KB}}
\]

## (b) Tiled DRAM traffic calculation

For tiled GEMM with `T = 8`:

Number of tiles along one dimension:

\[
\frac{N}{T} = \frac{32}{8} = 4
\]

So the number of output tiles is:

\[
4 \times 4 = 16
\]

For each output tile, the computation iterates over 4 tile positions in the reduction dimension, so it loads:

- 4 tiles of `A`
- 4 tiles of `B`

Therefore total tile loads are:

\[
\text{A tile loads} = 16 \times 4 = 64
\]

\[
\text{B tile loads} = 16 \times 4 = 64
\]

Total tile loads:

\[
64 + 64 = 128
\]

Each tile contains:

\[
T^2 = 8^2 = 64 \text{ elements}
\]

So total element loads:

\[
128 \times 64 = 8192
\]

Since each element is 4 bytes:

\[
\text{Tiled DRAM traffic} = 8192 \times 4 = 32768 \text{ bytes}
\]

\[
\boxed{\text{Tiled DRAM traffic} = 32768 \text{ bytes} = 32 \text{ KB}}
\]

## (c) Traffic ratio with one-sentence explanation

\[
\text{Ratio} = \frac{\text{Naive DRAM traffic}}{\text{Tiled DRAM traffic}}
= \frac{262144}{32768} = 8
\]

\[
\boxed{\text{Naive/Tiled traffic ratio} = 8}
\]

**One-sentence explanation:** The ratio is 8 because tiling allows each loaded tile to be reused across 8 multiply-accumulate steps, so the DRAM traffic is reduced by the tile size `T = 8`.

> Note: The handout says the ratio equals `N`, but with the direct full-computation tile-load count above, the mathematically consistent result is `8`, not `32`.

## (d) Execution time for naive and tiled cases with bound classification

Total GEMM floating-point work:

\[
2N^3 = 2(32^3) = 2(32768) = 65536 \text{ FLOPs}
\]

### Compute time

\[
t_{\text{compute}} = \frac{65536}{10 \times 10^{12}}
= 6.5536 \times 10^{-9} \text{ s}
\]

\[
\boxed{t_{\text{compute}} = 6.5536 \text{ ns}}
\]

### Naive case

Naive DRAM traffic:

\[
262144 \text{ bytes}
\]

Memory time:

\[
t_{\text{naive,mem}} = \frac{262144}{320 \times 10^9}
= 8.192 \times 10^{-7} \text{ s}
\]

\[
\boxed{t_{\text{naive,mem}} = 819.2 \text{ ns}}
\]

Since:

\[
819.2 \text{ ns} > 6.5536 \text{ ns}
\]

the naive case is:

\[
\boxed{\text{Naive case is memory-bound}}
\]

Execution time:

\[
\boxed{t_{\text{naive}} \approx 819.2 \text{ ns}}
\]

### Tiled case

Tiled DRAM traffic:

\[
32768 \text{ bytes}
\]

Memory time:

\[
t_{\text{tiled,mem}} = \frac{32768}{320 \times 10^9}
= 1.024 \times 10^{-7} \text{ s}
\]

\[
\boxed{t_{\text{tiled,mem}} = 102.4 \text{ ns}}
\]

Since:

\[
102.4 \text{ ns} > 6.5536 \text{ ns}
\]

the tiled case is also:

\[
\boxed{\text{Tiled case is memory-bound}}
\]

Execution time:

\[
\boxed{t_{\text{tiled}} \approx 102.4 \text{ ns}}
\]

## Final Answers Summary

- **Naive DRAM traffic:** `262144 bytes`
- **Tiled DRAM traffic:** `32768 bytes`
- **Traffic ratio:** `8`
- **Naive execution time:** `819.2 ns` → **memory-bound**
- **Tiled execution time:** `102.4 ns` → **memory-bound**
