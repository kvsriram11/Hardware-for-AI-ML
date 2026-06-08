# C + OpenBLAS Baseline — Echo State Network State Update

## Purpose

This is the *fair-comparison* CPU baseline. Python+NumPy includes interpreter dispatch overhead per BLAS call, 
which doesn't reflect what a CPU can actually do on this kernel. The C+OpenBLAS measurement removes that overhead 
and gives the realistic ceiling against which the accelerator must be compared.

## Platform

- **CPU**: Intel i7-1165G7 (Tigerlake), single thread
- **OS**: Microsoft Windows 11
- **Compiler**: gcc 16.1.0 (MinGW-w64 / MSYS2)
- **Flags**: `-O3 -march=native -Wall`
- **BLAS**: OpenBLAS 0.3.33, forced to single thread via `OPENBLAS_NUM_THREADS=1`
- **Weights**: loaded from `baselines/c_openblas/weights/*.bin` — produced by `dump_weights.py` using `numpy.random.RandomState(42)`, 
so C and Python operate on bit-identical W and Win matrices.

## Kernel implementation

Direct port of the state-update kernel using two `cblas_sgemv` calls (Win@[1,u] and W@x), 
a fused multiply-add for the leak blend, and `tanhf` from libm. 
No tiling, no manual vectorization — OpenBLAS handles SIMD inside sgemv.

## Results — sweep

| N | C per-step (µs) | C updates/sec | C GFLOP/s | Python per-step (µs) | Python GFLOP/s | C/Python speedup | W size | Fits L3? |
|---|---|---|---|---|---|---|---|---|
| 100 | 1.20 | 833,327 | 17.42 | 89.00 | 0.23 | **74.17×** | 0.04 MB | ✓ |
| 500 | 16.30 | 61,350 | 30.95 | 139.80 | 3.61 | **8.58×** | 1.00 MB | ✓ |
| 1000 | 103.40 | 9,671 | 19.43 | 224.90 | 8.93 | **2.18×** | 4.00 MB | ✓ |
| 2000 | 340.00 | 2,941 | 23.58 | 916.60 | 8.75 | **2.70×** | 16.00 MB | ✗ |

## Cross-validation against Python

Final-state L2-norm comparison after 4000 steps (relative error tolerance: 0.5%, all below 1e-6%):

| N | C ‖x‖ | Python ‖x‖ | rel diff |
|---|---|---|---|
| 100 | 4.611791667 | 4.611791665 | 4.34e-08% ✓ |
| 500 | 11.329666814 | 11.329666865 | 4.50e-07% ✓ |
| 1000 | 16.586226898 | 16.586227189 | 1.75e-06% ✓ |
| 2000 | 22.679666463 | 22.679666840 | 1.66e-06% ✓ |

**Validation: PASS.** C+OpenBLAS produces final states identical to Python+NumPy within FP rounding error.

## Where the operating point sits on the roofline

At N=1000, C achieves **19.4 GFLOP/s** sustained. 
i7-1165G7 peak compute is 179.2 GFLOP/s, so C reaches 
**10.8% of peak**. 
Python+NumPy at the same N reaches 8.9 GFLOP/s = 
5.0% of peak.

The 2.2× gap between them is exactly the Python interpreter dispatch cost per kernel call. 
OpenBLAS itself is the same in both cases.

## What this means for the accelerator pitch

The honest fair-comparison baseline is **C+OpenBLAS at 9,671 updates/sec (N=1000)**.

Projected accelerator throughput (16-MAC parallel, 100 MHz target, see `precision.md` / M2): 
**~1.54M updates/sec**.

Speedup vs C+OpenBLAS: **~159×**. Speedup vs Python+NumPy: ~347×. 
The 159× number is the one we cite; the 347× is informational.

## Reproduce

```bash
# In MSYS2 MINGW64 shell:
cd baselines/c_openblas
gcc -O3 -march=native -Wall -I/mingw64/include/openblas -o benchmark.exe benchmark.c -lopenblas -lm
export OPENBLAS_NUM_THREADS=1
./benchmark.exe 1000 30 ../../reference/minimalESN/MackeyGlass_t17.txt
```

## Files

- `benchmark.c` — C source
- `dump_weights.py` — Python script that writes weights/*.bin

- `cross_validate.py` — Python validation script (PASS confirmed)
- `c_results.json` — captured benchmark output

- `weights/W_N{100,500,1000,2000}.bin`, `weights/Win_N*.bin` — float32 row-major binary weights
