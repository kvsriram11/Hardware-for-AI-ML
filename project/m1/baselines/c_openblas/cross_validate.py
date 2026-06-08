"""
Cross-validate C+OpenBLAS final state against Python.
Runs the exact same kernel as benchmark.c using the dumped weights,
computes final state L2 norm, compares to C output.
"""
import json
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = ROOT / 'baselines' / 'c_openblas' / 'weights'
DATA = np.loadtxt(ROOT / 'reference' / 'minimalESN' / 'MackeyGlass_t17.txt').astype(np.float32)

leak = np.float32(0.3)
results = []

for N in [100, 500, 1000, 2000]:
    W = np.fromfile(WEIGHTS / f'W_N{N}.bin', dtype=np.float32).reshape(N, N)
    Win = np.fromfile(WEIGHTS / f'Win_N{N}.bin', dtype=np.float32).reshape(N, 2)
    x = np.zeros((N,), dtype=np.float32)
    # 4000 steps full run, matches benchmark.c
    total_steps = 4000
    for t in range(total_steps):
        u = DATA[t] if t < len(DATA) else np.float32(0.0)
        u_vec = np.array([1.0, u], dtype=np.float32)
        pre = Win @ u_vec + W @ x
        x = (np.float32(1.0) - leak) * x + leak * np.tanh(pre)
    py_l2 = float(np.sqrt(np.sum(x.astype(np.float64) ** 2)))
    results.append({'N': N, 'py_l2': py_l2})
    print(f"N={N}: Python final ||x|| = {py_l2:.9f}")

# Compare to C values from c_results.json
with open(ROOT / 'baselines' / 'c_openblas' / 'c_results.json', encoding='utf-8') as f:
    c_res = json.load(f)

print("\n=== Cross-validation ===")
print(f"{'N':>5} | {'C ||x||':>14} | {'Py ||x||':>14} | {'|diff|':>10} | {'rel %':>8}")
print("-" * 65)
all_pass = True
for c, py in zip(c_res['sweep'], results):
    c_l2 = c['final_state_l2_norm']
    diff = abs(c_l2 - py['py_l2'])
    rel = 100.0 * diff / py['py_l2']
    ok = rel < 0.5  # tolerance: 0.5% rel diff allowed (FP rounding)
    all_pass &= ok
    flag = '✓' if ok else '✗'
    print(f"{c['N']:>5} | {c_l2:>14.9f} | {py['py_l2']:>14.9f} | {diff:>10.6f} | {rel:>7.4f}% {flag}")

print()
print("VALIDATION: " + ("PASS — C matches Python within FP tolerance" if all_pass else "FAIL"))
