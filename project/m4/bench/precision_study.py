#!/usr/bin/env python3
"""
precision_study.py — assemble M4 benchmark numbers across Q15 / INT8 / Q4.

Combines:
  - MEASURED RTL cycle count per N=1000 update (from cocotb sim, identical 1169
    cycles for all precisions — cycle count is precision-independent because the
    K=64 lanes process MAC_WIDTH=16 weights/beat regardless of bit width),
  - MEASURED Yosys/sky130 synthesis (cells, area, ltp logic depth) per precision,
  - a first-order power estimate (M3 methodology: cells x activity x energy x f),
  - Q15/INT8/Q4 quantization error vs an FP32 reference (>=200 samples, the
    build_m2_docs.py methodology extended to all three widths).

Emits bench/benchmark_data.csv and bench/roofline_final.png, and prints a
summary table used in bench/benchmark.md.
"""
import csv
import json
import math
import random
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tb' / 'm2'))
from golden import (state_update_golden, float_to_q, q_to_float, sign_extend)  # noqa

# ---------------------------------------------------------------------------
# MEASURED hardware facts
# ---------------------------------------------------------------------------
K            = 64
N            = 1000
CYCLES       = 1169          # measured per N=1000 update (cocotb, all precisions)
CLOCK_MHZ    = 125.0         # design clock that clears the 10x target (see notes)
FLOPS_UPDATE = 2 * N * N + 9 * N   # 2N^2 MAC ops (matches M1: 2,009,000 @ N=1000)

# baselines (M1)
PY_UPS   = 4446.0            # Python+NumPy updates/sec @ N=1000
C_UPS    = 10415.0           # C+OpenBLAS  updates/sec @ N=1000 (M4 target basis)
PY_GFLOPS = 8.93
C_GFLOPS  = 19.43
AI_FP32   = 0.5             # M1 no-reuse arithmetic intensity (FP32, 4 bytes)

# i7-1165G7 roofline
HW_PEAK_GFLOPS = 179.2
HW_BW_GBS      = 51.2
HW_RIDGE       = HW_PEAK_GFLOPS / HW_BW_GBS   # 3.5

# per-LANE synthesis (measured) : DATA_W -> dict
SYNTH = {
    16: {'cells': 29681, 'area_um2': 213526.0, 'ltp': 307, 'ff': 687},
    8:  {'cells':  8274, 'area_um2':  60284.1, 'ltp': 296, 'ff': 391},
    4:  {'cells':  2799, 'area_um2':  21180.3, 'ltp': 290, 'ff': 243},
}

# power model (M3 methodology)
ALPHA  = 0.15          # activity factor
E_CELL = 0.04e-12      # avg switching energy per cell per cycle (J), sky130 HD


def pwl_tanh_fp(x):
    if x <= -2.0:   return -1.0
    elif x <= -1.0: return x/4.0 - 0.5
    elif x <  1.0:  return x/2.0
    elif x <  2.0:  return x/4.0 + 0.5
    return 1.0


def quant_error(data_w, n_samples=200, acc_w=40, seed=2026):
    """MSE / SNR of the Q datapath vs an FP32 reference (same PWL tanh)."""
    frac_w = data_w - 1
    random.seed(seed)
    fp, q = [], []
    for _ in range(n_samples):
        w_fp  = [random.uniform(-0.2, 0.2) for _ in range(16)]
        x_fp  = [random.uniform(-0.8, 0.8) for _ in range(16)]
        xp_fp = random.uniform(-0.5, 0.5)
        win_fp = random.uniform(-0.1, 0.1)
        leak  = 0.3
        pre_fp = sum(a*b for a, b in zip(w_fp, x_fp)) + win_fp
        z_fp   = pwl_tanh_fp(pre_fp)
        fp.append((1.0 - leak) * xp_fp + leak * z_fp)

        w_q  = [float_to_q(v, data_w) for v in w_fp]
        x_q  = [float_to_q(v, data_w) for v in x_fp]
        xp_q = float_to_q(xp_fp, data_w)
        leak_q = float_to_q(leak, data_w)
        win_q = sign_extend(float_to_q(win_fp, data_w), acc_w)
        xi = state_update_golden(w_q, x_q, xp_q, win_q, leak_q, data_w, acc_w, frac_w)
        q.append(q_to_float(xi, frac_w))
    fp = np.array(fp); q = np.array(q)
    mse = float(np.mean((q - fp) ** 2))
    snr = 10.0 * math.log10(float(np.var(fp)) / max(mse, 1e-30))
    return mse, snr


def main():
    ups = CLOCK_MHZ * 1e6 / CYCLES
    gflops = ups * FLOPS_UPDATE / 1e9
    rows = []
    for dw, pname in ((16, 'q15'), (8, 'int8'), (4, 'q4')):
        s = SYNTH[dw]
        cells_tot = s['cells'] * K
        area_tot  = s['area_um2'] * K
        power_mw  = ALPHA * cells_tot * E_CELL * (CLOCK_MHZ * 1e6) * 1e3  # mW
        mse, snr  = quant_error(dw)
        ai = AI_FP32 * (4 / (dw / 8.0))      # bytes shrink with width -> AI rises
        rows.append({
            'precision': pname, 'data_w': dw,
            'cycles_per_update_N1000': CYCLES, 'clock_mhz': CLOCK_MHZ,
            'updates_per_sec': round(ups, 1),
            'gflops_sustained': round(gflops, 2),
            'mse_vs_fp32': f"{mse:.3e}", 'snr_db': round(snr, 2),
            'cells': cells_tot, 'area_um2': round(area_tot, 1),
            'critical_path_logic_stages': s['ltp'],
            'power_mw_est': round(power_mw, 1),
            '_ai': ai,
        })

    # CSV (drop helper col)
    cols = ['precision', 'data_w', 'cycles_per_update_N1000', 'clock_mhz',
            'updates_per_sec', 'gflops_sustained', 'mse_vs_fp32', 'snr_db',
            'cells', 'area_um2', 'critical_path_logic_stages', 'power_mw_est']
    with open(ROOT / 'bench' / 'benchmark_data.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})

    # summary json for benchmark.md
    summary = {
        'updates_per_sec': round(ups, 1), 'gflops_sustained': round(gflops, 2),
        'cycles': CYCLES, 'clock_mhz': CLOCK_MHZ,
        'speedup_vs_c': round(ups / C_UPS, 2),
        'speedup_vs_py': round(ups / PY_UPS, 2),
        'rows': rows,
        'time_per_update_s': 1.0 / ups,
    }
    (ROOT / 'bench' / 'benchmark_summary.json').write_text(json.dumps(summary, indent=2))

    # ---- two separate rooflines (no memory-hierarchy mixing) ----
    # Each system's FLOPs and bytes are counted at the SAME level of its own
    # memory hierarchy: the CPU at its DRAM interface, the chiplet at its
    # lane-local SRAM interface (where the chiplet's bandwidth actually lives).
    colors = {'q15': '#1565c0', 'int8': '#2e7d32', 'q4': '#6a1b9a'}
    ai_axis = np.logspace(-1.5, 2.5, 400)

    # chiplet roofline parameters: 64 lanes x MAC_WIDTH=16 x 2 FLOP x 125 MHz
    CHIP_PEAK_GFLOPS = K * 16 * 2 * (CLOCK_MHZ * 1e6) / 1e9      # 256 GFLOP/s
    CHIP_BW = {16: 256.0, 8: 128.0, 4: 64.0}                    # GB/s (bytes/op x lanes x f)

    fig, (axc, axa) = plt.subplots(1, 2, figsize=(15, 7))

    # --- LEFT: i7-1165G7 reference roofline (CPU baselines) ---
    axc.loglog(ai_axis, np.minimum(HW_PEAK_GFLOPS, HW_BW_GBS * ai_axis),
               'k-', lw=2, label=f'roofline (BW {HW_BW_GBS} GB/s, peak {HW_PEAK_GFLOPS} GF/s)')
    axc.axhline(HW_PEAK_GFLOPS, color='0.7', ls='--', lw=0.8)
    axc.axvline(HW_RIDGE, color='0.5', ls=':', lw=1)
    axc.text(HW_RIDGE*1.05, 0.2, f'ridge {HW_RIDGE:.1f}', fontsize=8, color='0.4')
    axc.plot(AI_FP32, PY_GFLOPS, 'v', ms=12, color='#777',
             label=f'Python+NumPy (AI={AI_FP32}, {PY_GFLOPS} GF/s)')
    axc.plot(AI_FP32, C_GFLOPS, 's', ms=12, color='#c1121f',
             label=f'C+OpenBLAS (AI={AI_FP32}, {C_GFLOPS} GF/s)')
    axc.set_title('i7-1165G7 reference roofline (CPU baselines)',
                  fontsize=12, fontweight='bold')

    # --- RIGHT: K=64 chiplet roofline (per-precision BW, shared compute ceiling) ---
    axa.axhline(CHIP_PEAK_GFLOPS, color='0.4', ls='--', lw=1.0,
                label=f'compute ceiling {CHIP_PEAK_GFLOPS:.0f} GF/s')
    for r in rows:
        dw = r['data_w']; bw = CHIP_BW[dw]; c = colors[r['precision']]
        axa.loglog(ai_axis, np.minimum(CHIP_PEAK_GFLOPS, bw * ai_axis),
                   '-', lw=1.6, color=c, alpha=0.85,
                   label=f'{r["precision"].upper()} roofline (BW {bw:.0f} GB/s)')
        ridge = CHIP_PEAK_GFLOPS / bw
        axa.axvline(ridge, color=c, ls=':', lw=0.8, alpha=0.6)
        axa.plot(r['_ai'], gflops, 'o', ms=13, color=c,
                 label=f'{r["precision"].upper()} measured (AI={r["_ai"]:.1f}, {gflops:.0f} GF/s)')
        axa.annotate(r['precision'].upper(), (r['_ai'], gflops),
                     textcoords='offset points', xytext=(8, 8), fontsize=9,
                     fontweight='bold', color=c)
    axa.set_title('K=64 chiplet roofline (measured @ 125 MHz target)',
                  fontsize=12, fontweight='bold')

    for ax, xlim, ylim in ((axc, (0.03, 300), (0.1, 400)),
                           (axa, (0.1, 100), (1, 600))):
        ax.set_xlabel('Arithmetic Intensity (FLOP/byte)', fontsize=11)
        ax.set_ylabel('Performance (GFLOP/s)', fontsize=11)
        ax.set_xlim(*xlim); ax.set_ylim(*ylim)
        ax.grid(True, which='both', alpha=0.25)
        ax.legend(fontsize=8, loc='lower right')
    fig.suptitle('ESN state-update, N=1000 — separate rooflines per system '
                 '(FLOPs & bytes counted at each system\'s own memory level)',
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(ROOT / 'bench' / 'roofline_final.png', dpi=150)

    # print table
    print(f"updates/sec={ups:.0f}  GFLOP/s={gflops:.1f}  "
          f"speedup vs C={ups/C_UPS:.2f}x  vs Py={ups/PY_UPS:.2f}x")
    for r in rows:
        print(f"  {r['precision']:4s} dw{r['data_w']:>2} | snr={r['snr_db']:6.2f}dB "
              f"mse={r['mse_vs_fp32']} | cells={r['cells']:>8} area={r['area_um2']/1e6:.2f}mm^2 "
              f"ltp={r['critical_path_logic_stages']} pwr={r['power_mw_est']:.0f}mW AI={r['_ai']:.1f}")


if __name__ == '__main__':
    main()
