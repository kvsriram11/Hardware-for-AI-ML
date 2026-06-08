#!/usr/bin/env python3
"""
cosim_vcd_to_png.py — annotated AXI cosim waveform for the M3 deliverable.

Parses tb/m3/sim_build/top_DW16/waves.vcd and renders the FIRST neuron's
full AXI transaction, with the three rubric-required regions marked:

    HOST WRITE   — AXIL register writes (XPREV / WIN_T / CTRL.start)
    COMPUTE      — AXIS beats streamed + compute_core FSM MAC->...->DONE
    HOST READ    — AXIL read of XNEXT

Output: sim/cosim_waveform.png  (150 DPI, 16x6.5 in)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

THIS = Path(__file__).resolve().parent
VCD  = THIS / "sim_build" / "top_DW16" / "waves.vcd"
OUT  = THIS.parents[1] / "sim" / "cosim_waveform.png"

# (display name, vcd signal name, is_bus)
TARGETS = [
    ("clk",            "clk",            False),
    ("axil_awvalid",   "s_axil_awvalid", False),
    ("axil_wvalid",    "s_axil_wvalid",  False),
    ("axil_arvalid",   "s_axil_arvalid", False),
    ("axil_rvalid",    "s_axil_rvalid",  False),
    ("axis_tvalid",    "s_axis_tvalid",  False),
    ("axis_tready",    "s_axis_tready",  False),
    ("axis_tlast",     "s_axis_tlast",   False),
    ("state",          "state",          True),
    ("done",           "done",           False),
]
STATE_NAMES = {0: "IDLE", 1: "MAC", 2: "FLUSH", 3: "ACTIVATE",
               4: "BLEND", 5: "DONE"}


def parse_vcd(path):
    """name -> sorted [(time_ps, value)], first symbol seen per name.
    Also returns araddr stream for region detection and timescale (ps)."""
    want = {sig for _, sig, _ in TARGETS} | {"s_axil_araddr"}
    sym2name = {}
    timescale_ps = 1.0
    changes = {}

    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()

    defining = True
    cur_time = 0
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if defining:
            if line.startswith("$timescale"):
                body = line.replace("$timescale", "").replace("$end", "").strip()
                if not body:
                    body = lines[i].strip(); i += 1
                timescale_ps = _ts_to_ps(body)
            elif line.startswith("$var"):
                p = line.split()
                sym, name = p[3], p[4]
                if name in want and name not in changes:
                    sym2name[sym] = name
                    changes[name] = []
            elif line.startswith("$enddefinitions"):
                defining = False
            continue
        c = line[0]
        if c == "#":
            cur_time = int(line[1:])
        elif c in "01xz":
            name = sym2name.get(line[1:])
            if name is not None:
                changes[name].append((cur_time, line[0]))
        elif c in "bB":
            val, sym = line[1:].split()
            name = sym2name.get(sym)
            if name is not None:
                changes[name].append((cur_time, val))
    return timescale_ps, changes


def _ts_to_ps(s):
    s = s.strip().lower()
    for u, m in (("fs", .001), ("ps", 1), ("ns", 1000), ("us", 1e6), ("ms", 1e9)):
        if s.endswith(u):
            return float(s[:-len(u)].strip() or "1") * m
    return 1.0


def bin_to_int(b):
    return None if any(ch in "xz" for ch in b) else int(b, 2)


def value_at(seq, t):
    cur = seq[0][1] if seq else None
    for tt, v in seq:
        if tt <= t:
            cur = v
        else:
            break
    return cur


def first_rise(seq, after=0.0):
    for tt, v in seq:
        if tt > after and v == "1":
            return tt
    return None


def transitions_in(seq, t0, t1):
    out = [(t0, value_at(seq, t0))]
    for tt, v in seq:
        if t0 < tt <= t1:
            out.append((tt, v))
    return out


def main():
    if not VCD.exists():
        raise SystemExit(f"VCD not found: {VCD}")
    ts_ps, ch = parse_vcd(VCD)
    f = ts_ps / 1000.0  # tick -> ns

    def ns(seq):
        return [(t * f, v) for t, v in seq]

    nsc = {name: ns(seq) for name, seq in ch.items()}

    # --- region boundaries for neuron 0 ---
    t_write = first_rise(nsc["s_axil_awvalid"])           # first AXIL write
    t_comp  = first_rise(nsc["s_axis_tvalid"])            # first AXIS beat
    t_done  = first_rise(nsc["done"], after=t_comp or 0)  # compute_core done
    # XNEXT read: first time araddr == 0x14 after done
    t_read = None
    for tt, v in nsc.get("s_axil_araddr", []):
        iv = bin_to_int(v)
        if iv == 0x14 and (t_done is None or tt >= t_done - 5):
            t_read = tt
            break
    if t_read is None:
        t_read = (t_done or 0) + 30
    # end window a bit after the read's rvalid
    r_after = first_rise(nsc["s_axil_rvalid"], after=t_read)
    win_t1 = (r_after or t_read) + 25
    win_t0 = (t_write or 0) - 10

    print(f"window {win_t0:.0f}-{win_t1:.0f} ns | write@{t_write} "
          f"compute@{t_comp} done@{t_done} read@{t_read}")

    # --- draw ---
    n_sig = len(TARGETS)
    row_h, gap, hi = 1.0, 0.35, 0.7
    fig, ax = plt.subplots(figsize=(16, 6.5))
    y_ticks, y_labels = [], []

    for idx, (label, sig, is_bus) in enumerate(TARGETS):
        base = (n_sig - 1 - idx) * (row_h + gap)
        y_ticks.append(base + hi / 2)
        y_labels.append(label)
        segs = transitions_in(nsc[sig], win_t0, win_t1)
        if not is_bus:
            xs, ys = [], []
            for k, (tt, v) in enumerate(segs):
                lvl = base + (hi if v == "1" else 0.0)
                xs += [max(tt, win_t0)]; ys += [lvl]
                nxt = segs[k + 1][0] if k + 1 < len(segs) else win_t1
                xs += [nxt]; ys += [lvl]
            ax.plot(xs, ys, color="#1565c0", lw=1.3)
            ax.axhline(base, color="0.9", lw=0.4, zorder=0)
        else:
            dt = min(1.5, 0.015 * (win_t1 - win_t0))
            ylo, yhi, ym = base, base + hi, base + hi / 2
            for k, (tt, v) in enumerate(segs):
                a = max(tt, win_t0)
                b = segs[k + 1][0] if k + 1 < len(segs) else win_t1
                iv = bin_to_int(v)
                lab = STATE_NAMES.get(iv, v) if iv is not None else "x"
                ax.plot([a + dt, b - dt], [yhi, yhi], color="#2e7d32", lw=1.2)
                ax.plot([a + dt, b - dt], [ylo, ylo], color="#2e7d32", lw=1.2)
                ax.plot([a, a + dt], [ym, yhi], color="#2e7d32", lw=1.2)
                ax.plot([a, a + dt], [ym, ylo], color="#2e7d32", lw=1.2)
                ax.plot([b - dt, b], [yhi, ym], color="#2e7d32", lw=1.2)
                ax.plot([b - dt, b], [ylo, ym], color="#2e7d32", lw=1.2)
                if b - a > dt * 2.2:
                    ax.text((a + b) / 2, ym, lab, ha="center", va="center",
                            fontsize=7, color="#1b5e20", fontweight="bold")

    y_top = n_sig * (row_h + gap)
    # region shading
    regions = [
        ("HOST WRITE", win_t0, t_comp, "#1565c0"),
        ("COMPUTE",    t_comp, (t_done or t_read), "#2e7d32"),
        ("HOST READ",  (t_done or t_read), win_t1, "#b71c1c"),
    ]
    for name, a, b, color in regions:
        if a is None or b is None or b <= a:
            continue
        ax.add_patch(Rectangle((a, -0.4), b - a, y_top + 0.3, color=color,
                               alpha=0.06, zorder=0))
        ax.axvline(a, color=color, lw=1.0, ls="--", alpha=0.5)
        ax.text((a + b) / 2, y_top + 0.25, name, ha="center", va="bottom",
                fontsize=11, color=color, fontweight="bold")

    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=9, fontweight="bold")
    ax.set_xlim(win_t0, win_t1)
    ax.set_ylim(-0.5, y_top + 0.9)
    ax.set_xlabel("time (ns)", fontsize=11)
    ax.set_title("M3 cosim — top.sv, neuron 0 AXI transaction "
                 "(host-write → compute → host-read)",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="0.92", lw=0.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    legend = [Line2D([0], [0], color="#1565c0", lw=1.3, label="1-bit signal"),
              Line2D([0], [0], color="#2e7d32", lw=1.3, label="FSM state bus")]
    ax.legend(handles=legend, loc="lower right", fontsize=8, framealpha=0.9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
