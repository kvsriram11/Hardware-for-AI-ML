# GEMM Analysis

## (a) Why is the naive kernel memory-bound?

The naive GEMM kernel is memory-bound because each thread computes one output element and repeatedly reads matrix A and matrix B values directly from global memory inside the inner loop. Many nearby threads request overlapping data, so the same elements are fetched multiple times from DRAM instead of being reused efficiently. Global memory has much higher latency than registers or shared memory, which causes the GPU to spend many cycles waiting for data rather than executing floating-point operations. Because memory access becomes the limiting factor, the kernel cannot approach the theoretical compute peak of the Tesla T4 GPU.

## (b) How does tiling reduce DRAM traffic?

Tiling reduces DRAM traffic by dividing matrices into smaller submatrices and loading each tile of A and B into shared memory once per thread block. Threads cooperate to fetch the tile data and then reuse those values for multiple multiply-accumulate operations before loading the next tile. This avoids repeatedly requesting the same data from global memory. As a result, tiling improves locality, reduces redundant memory transactions, and increases arithmetic intensity.

## (c) Did the tiled kernel achieve the expected improvement? If not, what was the remaining bottleneck?

The tile size 8 kernel achieved only a small improvement over the naive version. Although memory reuse improved, the gain was reduced by synchronization overhead from `__syncthreads()`, extra shared-memory instructions, and low occupancy caused by small 8x8 thread blocks. After increasing tile size to 32x32, performance improved significantly to about 688 GFLOP/s, confirming that inefficient tile configuration was the main remaining bottleneck.
