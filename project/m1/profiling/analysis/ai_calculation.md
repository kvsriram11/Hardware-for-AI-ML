# Arithmetic Intensity — State Update Kernel

## Kernel definition

From minimalESN.py (Mantas Lukoševičius), the recurring state update per timestep is:

```
x[t] = (1-a) * x[t-1] + a * tanh( Win @ [1,u] + W @ x[t-1] )
```

where `Win ∈ R^(N×2)`, `W ∈ R^(N×N)`, `x ∈ R^N`, `a ∈ R` (leak rate), `u ∈ R` (input).

## Operation count per step (analytical)

| Operation | FLOPs at N=1000 | General N |
|---|---|---|
| Win @ [1,u] (matvec) | 4,000 | 2·(2N) = 4N |
| W @ x (matvec) | 2,000,000 | 2·N² |
| Pre-activation add | 1,000 | N |
| tanh elementwise | 1,000 | N (conservative; Padé ~4N) |
| Leak blend (1-a)x + a·z | 3,000 | 3N |
| **Total** | **2,009,000** | **2N² + 9N** |

## Byte movement per step (analytical)

Assuming FP32 (4 bytes/element). Two reuse models bracket reality:

**No-reuse lower bound** (every load misses to DRAM):
- Read W: 4N² bytes
- Read x: 4N bytes
- Read Win: 8N bytes
- Read u: 4 bytes
- Write x: 4N bytes
- **Total: 4N² + 16N + 4 bytes**

**Full-reuse upper bound** (W cache-resident across steps):
- Read x + Read Win + Read u + Write x = **16N + 4 bytes**

## Arithmetic intensity per N

| N | FLOPs | No-reuse bytes | AI (no-reuse) | AI (full-reuse) | W size | Fits L3 (12MB)? |
|---|---|---|---|---|---|---|
| 100 | 20,900 | 41,604 | 0.502 | 13.03 | 0.04 MB | ✓ |
| 500 | 504,500 | 1,008,004 | 0.500 | 63.03 | 1.00 MB | ✓ |
| 1000 | 2,009,000 | 4,016,004 | 0.500 | 125.53 | 4.00 MB | ✓ |
| 2000 | 8,018,000 | 16,032,004 | 0.500 | 250.53 | 16.00 MB | ✗ |
| 5000 | 50,045,000 | 100,080,004 | 0.500 | 625.53 | 100.00 MB | ✗ |

## Measured performance vs roofline (N=1000)

- Measured per-step time: **224.9 µs**
- Achieved compute: **8.93 GFLOP/s**
- Peak compute (i7-1165G7, FP32 1 core): 179.2 GFLOP/s
- Peak DRAM BW: 51.2 GB/s
- Ridge point: 3.50 FLOP/byte

## Dominant kernel identification

Per `sweep_data.csv` (full sweep, see also `kernel_comparison.md`):

- At N=100: state update = **98.4%** of recurring-step time (canonical 4000-step run).
- At N=1000: state update = **52.6%** (spectral norm at 43.9%, but one-shot).
- At N=5000: state update = **29.4%** (spectral norm 66.3% but still one-shot).

**For the accelerator target (deployment, >>10⁴ steps), state update → 100% of recurring work.** Spectral norm and readout training are one-shot setup costs amortized to zero. The accelerator therefore targets the state update kernel.
