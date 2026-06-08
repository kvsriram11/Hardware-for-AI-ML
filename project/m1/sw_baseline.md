# Software Baseline — Echo State Network State Update (N=1000)

## Platform

- **CPU**: Intel i7-1165G7 (Tiger Lake), single thread (OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, OMP_NUM_THREADS=1)
- **OS**: Microsoft Windows 11
- **Python**: 3.12.10
- **NumPy**: 1.26.4 (linked against OpenBLAS)
- **Pinned environment**: see `env/python_requirements.txt`
- **Source under test**: `reference/minimalESN/minimalESN.py` (Mantas Lukoševičius, MIT, 2012-2020)
- **Reproducibility hashes**: `reference/minimalESN/PROVENANCE.txt`

## Workload

Full canonical minimalESN run with Mackey-Glass τ=17 dataset, N=1000 reservoir, 
4000 timesteps (2000 training + 2000 generative test), 100-step initial warmup. 
Spectral radius 1.25, leak rate 0.3, ridge regression regularization 1e-8, seed 42.

## Headline timing

**Median of 10 runs at N=1000:**

- **Median**: 1.6799 s
- **Min**: 1.6395 s
- **Max**: 2.0326 s
- **All runs (s)**: 1.6395, 1.6401, 1.6636, 1.6738, 1.6793, 1.6799, 1.6992, 1.7233, 1.7504, 2.0326
- **Canonical validation MSE (seed=42)**: 1.022954e-06

## Throughput

**Full-pipeline view (4000 steps / median time):**

- 2381.1 updates/sec (full pipeline including spectral normalization and ridge training)

**Isolated state-update view (most relevant for accelerator comparison):**

- Per-step: 224.9 µs
- 4446.4 state updates/sec
- 8.93 GFLOP/s sustained

## Memory footprint (N=1000)

- W matrix (FP32, dense): 4.00 MB — fits in L3 (12 MB)
- Win matrix: 8.00 KB
- Reservoir state x: 4.00 KB
- Design matrix X (1002 × 1900): 7.62 MB

## Reproduce

```bash
source env/venv/Scripts/activate
python -u baselines/python_numpy/benchmark.py \
    --data-path reference/minimalESN/MackeyGlass_t17.txt \
    --out-dir profiling \
    --N-list 100,500,1000,2000,5000 \
    --reps 10
```

## Cross-references

- Kernel-share analysis: `codefest/cf02/analysis/kernel_comparison.md`
- Arithmetic intensity & roofline: `codefest/cf02/analysis/ai_calculation.md`
- Raw cProfile: `codefest/cf02/profiling/project_profile.txt`
- Sweep CSV: `codefest/cf02/profiling/sweep_data.csv`
