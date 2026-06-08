"""
ESN baseline benchmark for M1 redo.
Measures three candidate kernels independently:
  1. State update (recurring, runs ~4000 times in minimalESN)
  2. Spectral radius normalization (one-shot setup)
  3. Ridge regression readout (one-shot training)

Outputs:
  - median-of-N timings per kernel per reservoir size
  - cProfile of full minimalESN run
  - kernel-share breakdown
  - validation MSE vs golden run

Usage: python benchmark.py [--N-list 100,500,1000,2000,5000] [--reps 10]
"""
import argparse
import cProfile
import pstats
import io
import json
import time
import sys
from pathlib import Path
import numpy as np
from scipy import linalg

# Force single-thread BLAS for honest single-core baseline
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

# Reproducibility
SEED = 42

def make_esn(N, in_size=1, leak=0.3, spectral_radius=1.25, seed=SEED):
    """Build a minimalESN-equivalent reservoir of size N."""
    rng = np.random.RandomState(seed)
    Win = (rng.rand(N, 1 + in_size) - 0.5) * 1.0
    W = rng.rand(N, N) - 0.5
    return Win, W, leak

def normalize_spectral(W, target=1.25):
    """K1: spectral radius normalization (eigenvalue computation)."""
    rho = max(abs(linalg.eig(W)[0]))
    return W * (target / rho)

def state_update(x, u, Win, W, leak):
    """K2: single state-update step (the recurring kernel).
    x = (1-a)*x + a*tanh(Win @ [1,u] + W @ x)
    """
    u_vec = np.vstack((1.0, u))            # (2, 1)
    pre = np.dot(Win, u_vec) + np.dot(W, x)  # (N, 1)
    return (1.0 - leak) * x + leak * np.tanh(pre)

def collect_states(Win, W, leak, data, train_len, init_len):
    """Run the reservoir over training data, collect state matrix X."""
    N = W.shape[0]
    in_size = 1
    X = np.zeros((1 + in_size + N, train_len - init_len))
    x = np.zeros((N, 1))
    for t in range(train_len):
        u = data[t]
        x = state_update(x, u, Win, W, leak)
        if t >= init_len:
            X[:, t - init_len] = np.vstack((1.0, u, x))[:, 0]
    return X, x

def train_readout(X, Yt, reg=1e-8):
    """K3: ridge regression for readout weights."""
    return linalg.solve(np.dot(X, X.T) + reg * np.eye(X.shape[0]),
                        np.dot(X, Yt.T)).T

def time_median(fn, reps, *args, **kwargs):
    """Run fn(*args) reps times, return median + all timings."""
    ts = []
    result = None
    for _ in range(reps):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        t1 = time.perf_counter()
        ts.append(t1 - t0)
    ts.sort()
    return ts[len(ts) // 2], ts, result

def kernel_breakdown(N, train_len, test_len, init_len, reps, data):
    """Time the three kernels at this N."""
    Win, W, leak = make_esn(N)

    # K1: spectral normalization (one-shot)
    t_spec, ts_spec, W_norm = time_median(normalize_spectral, reps, W)

    # K2: state update (single-step; will be multiplied by total steps)
    x = np.zeros((N, 1))
    t_state, ts_state, _ = time_median(state_update, reps, x, data[0], Win, W_norm, leak)

    # K3: readout training (one-shot)
    # Need a state matrix first - do a quick collect_states to get realistic X
    X, x_final = collect_states(Win, W_norm, leak, data, train_len, init_len)
    Yt = data[None, init_len + 1: train_len + 1]
    t_read, ts_read, Wout = time_median(train_readout, reps, X, Yt)

    # Estimate full-run kernel shares (state runs train_len+test_len times)
    total_steps = train_len + test_len
    total_state_time = t_state * total_steps
    total_other = t_spec + t_read
    grand_total = total_state_time + total_other

    return {
        'N': N,
        'spectral_norm_s': t_spec,
        'spectral_norm_all_s': ts_spec,
        'state_update_per_step_s': t_state,
        'state_update_all_per_step_s': ts_state,
        'state_update_total_s_at_N_steps': total_state_time,
        'readout_train_s': t_read,
        'readout_train_all_s': ts_read,
        'projected_total_time_s': grand_total,
        'kernel_share_state_pct': 100.0 * total_state_time / grand_total,
        'kernel_share_spectral_pct': 100.0 * t_spec / grand_total,
        'kernel_share_readout_pct': 100.0 * t_read / grand_total,
        'total_steps_assumed': total_steps,
    }

def run_full_minimalesn(data, N=1000, train_len=2000, test_len=2000, init_len=100, seed=SEED):
    """Equivalent to minimalESN.py end-to-end. Returns MSE and timing."""
    Win, W, leak = make_esn(N, seed=seed)
    W = normalize_spectral(W)

    X, x = collect_states(Win, W, leak, data, train_len, init_len)
    Yt = data[None, init_len + 1: train_len + 1]
    Wout = train_readout(X, Yt)

    # Generative testing
    Y = np.zeros((1, test_len))
    u = data[train_len]
    for t in range(test_len):
        x = state_update(x, u, Win, W, leak)
        y = np.dot(Wout, np.vstack((1.0, u, x)))
        Y[:, t] = y[:, 0]
        u = y[0, 0]

    error_len = 500
    mse = float(np.sum((data[train_len + 1: train_len + error_len + 1] - Y[0, :error_len])**2) / error_len)
    return mse, Y

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--N-list', default='100,500,1000,2000,5000')
    p.add_argument('--reps', type=int, default=10)
    p.add_argument('--data-path', default='../../reference/minimalESN/MackeyGlass_t17.txt')
    p.add_argument('--out-dir', default='../../profiling')
    args = p.parse_args()

    N_list = [int(x) for x in args.N_list.split(',')]
    out_dir = Path(args.out_dir)
    (out_dir / 'cprofile').mkdir(parents=True, exist_ok=True)
    (out_dir / 'analysis').mkdir(parents=True, exist_ok=True)

    print(f"Loading data from {args.data_path}")
    data = np.loadtxt(args.data_path)
    print(f"Data length: {len(data)}")
    print(f"NumPy: {np.__version__}")
    print(f"Platform: {sys.platform}, Python: {sys.version.split()[0]}")
    print(f"BLAS threads: OPENBLAS_NUM_THREADS={os.environ.get('OPENBLAS_NUM_THREADS')}")

    # --- Sweep: per-kernel timing per N ---
    print("\n=== KERNEL TIMING SWEEP ===")
    sweep_results = []
    for N in N_list:
        print(f"\n--- N={N} ---")
        r = kernel_breakdown(N, train_len=2000, test_len=2000, init_len=100,
                             reps=args.reps, data=data)
        sweep_results.append(r)
        print(f"  spectral_norm:     {r['spectral_norm_s']*1e3:>10.3f} ms (one-shot)")
        print(f"  state_update/step: {r['state_update_per_step_s']*1e6:>10.3f} us")
        print(f"  state_update_total({r['total_steps_assumed']} steps): {r['state_update_total_s_at_N_steps']*1e3:>10.3f} ms")
        print(f"  readout_train:     {r['readout_train_s']*1e3:>10.3f} ms (one-shot)")
        print(f"  projected_total:   {r['projected_total_time_s']*1e3:>10.3f} ms")
        print(f"  KERNEL SHARES: state={r['kernel_share_state_pct']:.1f}%, "
              f"spectral={r['kernel_share_spectral_pct']:.1f}%, "
              f"readout={r['kernel_share_readout_pct']:.1f}%")

    # Save sweep CSV
    csv_path = out_dir / 'cprofile' / 'sweep_data.csv'
    with open(csv_path, 'w') as f:
        f.write("N,spectral_norm_s,state_update_per_step_s,state_update_total_s,readout_train_s,projected_total_s,share_state_pct,share_spectral_pct,share_readout_pct\n")
        for r in sweep_results:
            f.write(f"{r['N']},{r['spectral_norm_s']:.9f},{r['state_update_per_step_s']:.9f},"
                    f"{r['state_update_total_s_at_N_steps']:.9f},{r['readout_train_s']:.9f},"
                    f"{r['projected_total_time_s']:.9f},{r['kernel_share_state_pct']:.3f},"
                    f"{r['kernel_share_spectral_pct']:.3f},{r['kernel_share_readout_pct']:.3f}\n")
    print(f"\nWrote {csv_path}")

    # Save full sweep JSON (includes all reps)
    json_path = out_dir / 'cprofile' / 'sweep_data.json'
    with open(json_path, 'w') as f:
        json.dump(sweep_results, f, indent=2)
    print(f"Wrote {json_path}")

    # --- cProfile of full canonical run at N=1000 ---
    print("\n=== FULL CPROFILE: N=1000 canonical minimalESN run ===")
    profiler = cProfile.Profile()
    profiler.enable()
    mse, Y = run_full_minimalesn(data, N=1000)
    profiler.disable()

    print(f"Canonical MSE = {mse:.6e}")

    # Dump cProfile result
    profile_path = out_dir / 'cprofile' / 'project_profile.txt'
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).strip_dirs().sort_stats('cumulative')
    s.write("=== cProfile of minimalESN canonical run (N=1000) ===\n")
    s.write(f"Python: {sys.version.split()[0]}\n")
    s.write(f"NumPy: {np.__version__}\n")
    s.write(f"BLAS threads forced to 1\n")
    s.write(f"Canonical validation MSE: {mse:.6e}\n\n")
    s.write("--- Top 40 by cumulative time ---\n")
    ps.print_stats(40)
    s.write("\n--- Top 40 by tottime ---\n")
    ps2 = pstats.Stats(profiler, stream=s).strip_dirs().sort_stats('tottime')
    ps2.print_stats(40)
    with open(profile_path, 'w') as f:
        f.write(s.getvalue())
    print(f"Wrote {profile_path}")

    # --- Median-of-reps wall-clock at N=1000 (for sw_baseline.md headline number) ---
    print("\n=== HEADLINE TIMING: full minimalESN run at N=1000, median of 10 ===")
    full_times = []
    for i in range(10):
        t0 = time.perf_counter()
        mse_i, _ = run_full_minimalesn(data, N=1000, seed=SEED + i)
        t1 = time.perf_counter()
        full_times.append(t1 - t0)
        print(f"  run {i+1}: {t1-t0:.4f}s (MSE={mse_i:.3e})")
    full_times.sort()
    median = full_times[5]
    print(f"\n  MEDIAN: {median:.4f}s")
    print(f"  MIN:    {full_times[0]:.4f}s")
    print(f"  MAX:    {full_times[-1]:.4f}s")

    # Update sweep CSV with headline
    headline_path = out_dir / 'cprofile' / 'headline_n1000.json'
    with open(headline_path, 'w') as f:
        json.dump({
            'N': 1000,
            'all_times_s': full_times,
            'median_s': median,
            'min_s': full_times[0],
            'max_s': full_times[-1],
            'reps': 10,
            'canonical_mse': mse,
            'numpy_version': np.__version__,
            'python_version': sys.version.split()[0],
            'blas_threads': 1,
        }, f, indent=2)
    print(f"Wrote {headline_path}")

    print("\n=== DONE ===")

if __name__ == '__main__':
    main()
