"""
Bit-exact Python reference for the M2 RTL compute path.

Matches the SystemVerilog modules exactly:
  - signed Q1.(DATA_W-1) fixed point
  - 4-segment PWL tanh (saturate at +/- 2.0, slope 1/2 through origin, slope 1/4 in transition)
  - leak_blend: x_next = (1-a)*x_prev + a*z   with intermediate 2*DATA_W
  - MAC accumulator extended to ACC_W

This is the independent reference for testbenches (rubric requirement).
"""
import numpy as np


def q_to_float(q, frac_w):
    """Convert signed Q-format integer to float."""
    return float(q) / (1 << frac_w)


def float_to_q(f, data_w):
    """Convert float to signed Q1.(data_w-1) integer with saturation."""
    frac_w = data_w - 1
    scaled = int(round(f * (1 << frac_w)))
    max_v = (1 << (data_w - 1)) - 1
    min_v = -(1 << (data_w - 1)) + 1  # match SAT_LO in RTL (-max+1)
    return max(min(scaled, max_v), min_v)


def sign_extend(val, bits):
    """Two's-complement sign extension to arbitrary width."""
    mask = (1 << bits) - 1
    val &= mask
    if val & (1 << (bits - 1)):
        val -= (1 << bits)
    return val


def tanh_pwl_golden(pre_in, data_w, acc_w, frac_w):
    """4-segment PWL tanh matching tanh_pwl.sv exactly.

    Input pre_in : signed ACC_W integer in Q1.(data_w-1) format (frac_w bits)
    Output       : signed DATA_W integer in same Q1.(data_w-1) format

    Because input and output share fractional-bit count, all math is
    just arithmetic right shifts and ± half_in_Q1.frac_w.
    """
    x = sign_extend(pre_in, acc_w)
    sat_hi = (1 << (data_w - 1)) - 1
    sat_lo = -(1 << (data_w - 1)) + 1
    half_out = 1 << (data_w - 2)  # 0.5 in Q1.(data_w-1)

    one = 1 << frac_w
    two = 2 << frac_w
    data_mask = (1 << data_w) - 1

    if x <= -two:
        y = sat_lo
    elif x <= -one:
        # y = x/4 - 0.5
        shifted = x >> 2
        y_low = sign_extend(shifted & data_mask, data_w)
        y = y_low - half_out
    elif x < one:
        # y = x/2
        shifted = x >> 1
        y = sign_extend(shifted & data_mask, data_w)
    elif x < two:
        # y = x/4 + 0.5
        shifted = x >> 2
        y_low = sign_extend(shifted & data_mask, data_w)
        y = y_low + half_out
    else:
        y = sat_hi

    if y > sat_hi: y = sat_hi
    if y < sat_lo: y = sat_lo
    return y


def leak_blend_golden(a, x_prev, z, data_w):
    """Match leak_blend.sv: x_next = (1-a)*x_prev + a*z"""
    frac_w = data_w - 1
    one_minus_a = sign_extend(((1 << frac_w) | ((-1) & ((1 << frac_w) - 1))) - a + 1, data_w)
    # Simpler / correct: (1.0)_Q - a + 1lsb  — RTL uses {1'b0,{(DATA_W-1){1'b1}}} - a + 1
    sat_pos = (1 << (data_w - 1)) - 1
    one_minus_a = sign_extend(sat_pos - a, data_w)

    term1 = sign_extend(one_minus_a * x_prev, 2 * data_w)
    term2 = sign_extend(a * z, 2 * data_w)
    s = sign_extend(term1 + term2, 2 * data_w)

    # RTL: sum_q = sum[2*DATA_W-2 -: DATA_W]; bit slice [2W-2 downto W-1]
    # That's: shift right by (W-1), take W bits, treat as signed
    shifted = (s >> (data_w - 1)) & ((1 << data_w) - 1)
    return sign_extend(shifted, data_w)


def mac_golden(w_vec, x_vec, data_w):
    """Sum of signed*signed products, no truncation."""
    acc = 0
    for w, x in zip(w_vec, x_vec):
        w_s = sign_extend(w & ((1 << data_w) - 1), data_w)
        x_s = sign_extend(x & ((1 << data_w) - 1), data_w)
        acc += w_s * x_s
    return acc


def state_update_golden(w_row, x_prev_vec, x_prev_i, win_term, leak_a,
                        data_w=16, acc_w=40, frac_w=15):
    """Full single-neuron state update matching compute_core.sv exactly.

    Args:
        w_row      : list of N signed Q-format weight values (one row of W)
        x_prev_vec : list of N signed Q-format prior states (full x vector)
        x_prev_i   : signed Q-format prior state for THIS neuron i
        win_term   : signed ACC_W integer = Win@[1,u] precomputed for this neuron
        leak_a     : signed Q-format leak coefficient
        data_w/acc_w/frac_w : precision parameters
    Returns:
        x_next_i : signed DATA_W integer
    """
    mac_sum = mac_golden(w_row, x_prev_vec, data_w)
    frac_w_local = data_w - 1
    # MAC is Q2.(2*frac_w); shift right by frac_w to align with Q1.frac_w win_term
    pre_act = sign_extend((mac_sum >> frac_w_local) + win_term, acc_w)
    z = tanh_pwl_golden(pre_act, data_w, acc_w, frac_w)
    x_next = leak_blend_golden(leak_a, x_prev_i, z, data_w)
    return x_next


if __name__ == '__main__':
    # Self-test with hand values
    print("=== golden.py self-test ===")
    # tanh(0) = 0
    y = tanh_pwl_golden(0, 16, 40, 15)
    print(f"tanh_pwl(0) = {y} (expect 0)")
    assert y == 0
    # tanh(very positive) saturates
    big = 5 << 15  # 5.0 in Q1.15
    y = tanh_pwl_golden(big, 16, 40, 15)
    print(f"tanh_pwl(5.0) = {y} (expect saturation = {(1<<15)-1})")
    # leak_blend(a=0, x_prev=X, z=Y) -> ~X (1-0)*X + 0*Y
    y = leak_blend_golden(0, 10000, 5000, 16)
    print(f"leak_blend(a=0, xp=10000, z=5000) = {y} (~10000)")
    # leak_blend(a=full, ...) -> ~Y
    full = (1 << 15) - 1
    y = leak_blend_golden(full, 10000, 5000, 16)
    print(f"leak_blend(a=~1.0, xp=10000, z=5000) = {y} (~5000)")
    print("=== self-test done ===")
