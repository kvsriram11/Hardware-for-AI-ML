"""
golden_top.py — full N=1000 ESN reference + hex memory emitters for the M4
K=64 accelerator, parameterized by DATA_W (Q15 / INT8 / Q4).

The per-neuron math is the *frozen, bit-exact* M2 golden (tb/m2/golden.py):
tanh_pwl_golden + leak_blend_golden. The MAC dot-product is computed in exact
integer arithmetic (np.int64) for speed at N=1000, identical to mac_golden.

emit_hex() writes the four $readmemh files top.sv loads, with packing that
matches top.sv's memory indexing exactly.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm2'))
from golden import (tanh_pwl_golden, leak_blend_golden, sign_extend)  # noqa: E402

import numpy as np


def _float_to_q_vec(arr, data_w):
    frac_w = data_w - 1
    scaled = np.round(np.asarray(arr) * (1 << frac_w)).astype(np.int64)
    max_v = (1 << (data_w - 1)) - 1
    min_v = -(1 << (data_w - 1)) + 1
    return np.clip(scaled, min_v, max_v)


def gen_network(n=1000, data_w=16, acc_w=40, seed=2026):
    """Deterministic ESN reservoir step at the requested precision."""
    rng = np.random.default_rng(seed)
    W = _float_to_q_vec(rng.uniform(-0.2, 0.2, size=(n, n)), data_w)
    x_prev = _float_to_q_vec(rng.uniform(-0.8, 0.8, size=n), data_w)
    win_q = _float_to_q_vec(rng.uniform(-0.1, 0.1, size=n), data_w)
    win_term = np.array([sign_extend(int(v) & ((1 << data_w) - 1), acc_w)
                         for v in win_q], dtype=object)
    leak_a = int(_float_to_q_vec([0.3], data_w)[0])
    return {'W': W, 'x_prev': x_prev, 'win_term': win_term, 'leak_a': leak_a,
            'n': n, 'data_w': data_w, 'acc_w': acc_w, 'frac_w': data_w - 1}


def state_update_top(net):
    """Full x_next vector (length n), bit-exact vs the RTL datapath."""
    W, x_prev = net['W'], net['x_prev']
    n, data_w, acc_w, frac_w = net['n'], net['data_w'], net['acc_w'], net['frac_w']
    leak_a = net['leak_a']
    # exact integer MAC for every neuron at once
    mac = (W.astype(np.int64) @ x_prev.astype(np.int64))   # shape (n,)
    x_next = []
    for i in range(n):
        pre = sign_extend(int(mac[i] >> frac_w) + int(net['win_term'][i]), acc_w)
        z = tanh_pwl_golden(pre, data_w, acc_w, frac_w)
        xi = leak_blend_golden(leak_a, int(x_prev[i]), z, data_w)
        x_next.append(xi)
    return x_next


def emit_hex(net, build_dir, mac_width=16, k=64):
    """Write w_mem.hex / x_chunk.hex / x_scalar.hex / win.hex matching top.sv."""
    build_dir = Path(build_dir)
    n, data_w, acc_w = net['n'], net['data_w'], net['acc_w']
    W, x_prev, win_term = net['W'], net['x_prev'], net['win_term']
    mask = (1 << data_w) - 1
    nb      = (n + mac_width - 1) // mac_width      # beats/neuron
    batches = (n + k - 1) // k
    npad    = k * batches
    npc     = nb * mac_width                        # padded weight columns
    cw_hex  = (mac_width * data_w + 3) // 4
    acc_hex = (acc_w + 3) // 4

    def pack_row(vals):
        out = 0
        for i, v in enumerate(vals):
            out |= (int(v) & mask) << (i * data_w)
        return out

    # w_mem: index (L*batches + B)*nb + C
    with open(build_dir / "w_mem.hex", "w") as f:
        for L in range(k):
            for B in range(batches):
                neuron = B * k + L
                row = (list(W[neuron]) + [0] * (npc - n)) if neuron < n else [0] * npc
                for C in range(nb):
                    chunk = row[C * mac_width:(C + 1) * mac_width]
                    f.write(f"{pack_row(chunk):0{cw_hex}x}\n")

    # x_chunk: broadcast x[t-1], nb chunks
    xp = list(x_prev) + [0] * (npc - n)
    with open(build_dir / "x_chunk.hex", "w") as f:
        for C in range(nb):
            f.write(f"{pack_row(xp[C*mac_width:(C+1)*mac_width]):0{cw_hex}x}\n")

    # x_scalar: per-neuron prior state (padded neurons -> 0)
    with open(build_dir / "x_scalar.hex", "w") as f:
        for idx in range(npad):
            v = int(x_prev[idx]) & mask if idx < n else 0
            f.write(f"{v:0{(data_w+3)//4}x}\n")

    # win: per-neuron Win term, ACC_W bits (padded neurons -> 0)
    with open(build_dir / "win.hex", "w") as f:
        amask = (1 << acc_w) - 1
        for idx in range(npad):
            v = int(win_term[idx]) & amask if idx < n else 0
            f.write(f"{v:0{acc_hex}x}\n")


if __name__ == '__main__':
    import time
    for dw in (16, 8, 4):
        t = time.time()
        net = gen_network(1000, dw, 40)
        xn = state_update_top(net)
        print(f"DATA_W={dw}: x_next[0:5]={xn[:5]} "
              f"nonzero={sum(1 for v in xn if v)} ({time.time()-t:.1f}s)")
