"""
Dump W and Win arrays as raw float32 binaries that benchmark.c can mmap-load.
Same seed/RNG as benchmark.py to ensure C and Python operate on identical weights.
"""
import numpy as np
from pathlib import Path
from scipy import linalg

OUT = Path(__file__).resolve().parent / 'weights'
OUT.mkdir(exist_ok=True)
SEED = 42

def make_normalized(N, target_rho=1.25, seed=SEED):
    rng = np.random.RandomState(seed)
    Win = ((rng.rand(N, 1 + 1) - 0.5) * 1.0).astype(np.float32)
    W = (rng.rand(N, N) - 0.5).astype(np.float32)
    rho = float(max(abs(linalg.eig(W.astype(np.float64))[0])))
    W = (W * (target_rho / rho)).astype(np.float32)
    return W, Win

for N in [100, 500, 1000, 2000]:
    print(f"Dumping N={N}...")
    W, Win = make_normalized(N)
    W.tofile(OUT / f"W_N{N}.bin")
    Win.tofile(OUT / f"Win_N{N}.bin")
    print(f"  W: {W.shape} {W.dtype} → {W.nbytes/1e6:.2f} MB")
    print(f"  Win: {Win.shape} {Win.dtype} → {Win.nbytes:.0f} bytes")

print("\nDONE")
