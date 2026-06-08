# Kernel Comparison — Why State Update

## Three candidate kernels in minimalESN

From minimalESN.py, three computationally non-trivial kernels exist:

1. **Spectral radius normalization** — `linalg.eig(W)` then `W *= 1.25/rho`. One-shot at construction.
2. **State update** — `x = (1-a)x + a·tanh(Win@[1,u] + W@x)`. Runs `train_len + test_len` = 4000 times in the canonical script. **Runs O(steps) in deployment, where steps can be 10⁶+.**
3. **Ridge regression readout** — `linalg.solve(X·X.T + reg·I, X·Yt.T)`. One-shot at training.

## Measured time-share per kernel (sweep)

| N | spectral_norm (ms, 1×) | state_update (µs/step) | state_total at 4000 steps (ms) | readout (ms, 1×) | state-share | spectral-share | readout-share |
|---|---|---|---|---|---|---|---|
| 100 | 4.7 | 89.0 | 356.0 | 0.9 | 98.4% | 1.3% | 0.3% |
| 500 | 181.3 | 139.8 | 559.2 | 15.6 | 74.0% | 24.0% | 2.1% |
| 1000 | 751.7 | 224.9 | 899.6 | 59.9 | 52.6% | 43.9% | 3.5% |
| 2000 | 6239.7 | 916.6 | 3666.4 | 316.4 | 35.9% | 61.0% | 3.1% |
| 5000 | 41200.6 | 4571.4 | 18285.6 | 2679.3 | 29.4% | 66.3% | 4.3% |

## Why state update wins as accelerator target

**1. Recurrence vs one-shot.** State update is the only kernel that runs every timestep. Spectral norm runs once at network construction; readout training runs once on the collected state matrix. Accelerators win by amortizing per-invocation overhead across many calls. A one-shot kernel has nothing to amortize.

**2. Deployment dominance.** In the canonical script the network runs for 4000 steps and the kernel-share table above gives state update 29-98% depending on N. In any realistic deployment (control, signal processing, online prediction) the step count is 10⁵-10⁷. At those step counts the spectral-norm and readout shares collapse to <0.1% and state update → 100% of recurring work.

**3. Asymptotic complexity at the per-step level.** State update is O(N²) per step (dominated by `W@x`). Spectral normalization is O(N³) one-shot — heavy at high N, but amortized. Readout solve is O(N³) one-shot — same argument.

**4. Streaming structure.** State update is inherently sequential (`x[t]` depends on `x[t-1]`) but each step has high internal parallelism (N independent MAC chains). This maps cleanly to a MAC-array accelerator with a host AXI4-Stream interface — exactly what the M1 partition rationale targets.

**Decision: accelerate `state_update`. Keep spectral_norm and readout in SW.**
