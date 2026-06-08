"""
golden_top.py — full N-neuron ESN state-update reference for the M3 cosim.

One reservoir step updates every neuron i:

    x_next[i] = leak_blend( leak_a, x_prev[i],
                            tanh( (W_row_i . x_prev) >> FRAC_W + win_term[i] ) )

This reuses the *bit-exact* per-neuron M2 golden (tb/m2/golden.py) so the
multi-neuron reference inherits the same Q15 / PWL-tanh / leak-blend semantics
the DUT implements. The cosim asserts the DUT's per-neuron XNEXT (read back
over AXI) matches this vector element-by-element.

N is the reservoir size. The hardware is MAC_WIDTH-lane streaming, so an
N-element row is delivered as ceil(N/MAC_WIDTH) AXIS beats; N here only sets
how many weights/states the host generates and streams.
"""
import sys
from pathlib import Path

# pull in the frozen M2 per-neuron golden
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'm2'))
from golden import state_update_golden, float_to_q, sign_extend  # noqa: E402

import numpy as np


def gen_network(n, data_w=16, acc_w=40, seed=2026):
    """Deterministically build an ESN-realistic reservoir step.

    Returns a dict with:
        W        : list[n][n] signed Q-format reservoir weights (row-major)
        x_prev   : list[n]    signed Q-format prior reservoir state
        win_term : list[n]    signed ACC_W-extended Win-projection per neuron
        leak_a   : signed Q-format leak coefficient
    All integers are already quantized to Q1.(data_w-1).
    """
    rng = np.random.default_rng(seed)
    frac_w = data_w - 1

    # Reservoir weights: small, signed, mean ~0 (spectral-radius-friendly).
    W = [[float_to_q(float(rng.uniform(-0.2, 0.2)), data_w) for _ in range(n)]
         for _ in range(n)]
    # Prior reservoir state, bounded by tanh range.
    x_prev = [float_to_q(float(rng.uniform(-0.8, 0.8)), data_w) for _ in range(n)]
    # Per-neuron Win @ [1,u] contribution, sign-extended into ACC_W bits
    # (matches the corrected RTL/AXIL win_term contract).
    win_term = [sign_extend(float_to_q(float(rng.uniform(-0.1, 0.1)), data_w), acc_w)
                for _ in range(n)]
    leak_a = float_to_q(0.3, data_w)

    return {'W': W, 'x_prev': x_prev, 'win_term': win_term, 'leak_a': leak_a,
            'n': n, 'data_w': data_w, 'acc_w': acc_w, 'frac_w': frac_w}


def state_update_top(net):
    """Compute the full x_next vector for one reservoir step."""
    n      = net['n']
    W      = net['W']
    x_prev = net['x_prev']
    data_w = net['data_w']
    acc_w  = net['acc_w']
    frac_w = net['frac_w']
    leak_a = net['leak_a']

    x_next = []
    for i in range(n):
        xi = state_update_golden(W[i], x_prev, x_prev[i], net['win_term'][i],
                                 leak_a, data_w, acc_w, frac_w)
        x_next.append(xi)
    return x_next


if __name__ == '__main__':
    net = gen_network(64)
    xn = state_update_top(net)
    print(f"golden_top self-test: N={net['n']}")
    print(f"  x_next[0:8] = {xn[:8]}")
    print(f"  min={min(xn)}  max={max(xn)}  nonzero={sum(1 for v in xn if v)}")
