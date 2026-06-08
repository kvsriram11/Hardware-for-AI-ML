#!/usr/bin/env python3
"""
wave_to_png.py — annotated end-to-end M4 waveform (Q15).

Parses tb/m4/waves.vcd (produced by wave_tb.sv: control signals + lane-0
mirrors only) and renders one full N=1000 reservoir update:

    START  ->  COMPUTE (16 batches x ~73 cycles, lane FSM MAC..DONE)  ->  DONE

Output: sim/m4/final_waveform.png  (150 DPI, 16x6.5 in)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D

THIS = Path(__file__).resolve().parent
VCD  = THIS / "waves.vcd"
OUT  = THIS.parents[1] / "sim" / "m4" / "final_waveform.png"

# (label, vcd name, is_bus, decoder)
CSTATE = {0: "IDLE", 1: "START", 2: "STREAM", 3: "WAIT", 4: "DONE"}
LSTATE = {0: "IDLE", 1: "MAC", 2: "FLUSH", 3: "ACTIVATE", 4: "BLEND", 5: "DONE"}
TARGETS = [
    ("start",        "start",          False, None),
    ("busy",         "busy",           False, None),
    ("done",         "done",           False, None),
    ("seq_state",    "cstate",         True,  CSTATE),
    ("batch_cnt",    "batch_cnt",      True,  "dec"),
    ("chunk_cnt",    "chunk_cnt",      True,  "dec"),
    ("lane0_state",  "dbg_lane0_state", True, LSTATE),
    ("lane0_x_next", "dbg_lane0_xnext", True, "sdec"),
]


def parse_vcd(path):
    want = {sig for _, sig, _, _ in TARGETS}
    sym2name, changes, width = {}, {}, {}
    ts_ps = 1.0
    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()
    defining, t, i = True, 0, 0
    while i < len(lines):
        ln = lines[i].strip(); i += 1
        if not ln:
            continue
        if defining:
            if ln.startswith("$timescale"):
                body = ln.replace("$timescale", "").replace("$end", "").strip()
                if not body:
                    body = lines[i].strip(); i += 1
                ts_ps = _ts(body)
            elif ln.startswith("$var"):
                p = ln.split()
                w, sym, nm = int(p[2]), p[3], p[4]
                if nm in want and nm not in changes:
                    sym2name[sym] = nm; changes[nm] = []; width[nm] = w
            elif ln.startswith("$enddefinitions"):
                defining = False
            continue
        c = ln[0]
        if c == "#":
            t = int(ln[1:])
        elif c in "01xz":
            nm = sym2name.get(ln[1:])
            if nm:
                changes[nm].append((t, ln[0]))
        elif c in "bB":
            val, sym = ln[1:].split()
            nm = sym2name.get(sym)
            if nm:
                changes[nm].append((t, val))
    return ts_ps, changes, width


def _ts(s):
    s = s.strip().lower()
    for u, m in (("fs", .001), ("ps", 1), ("ns", 1000), ("us", 1e6), ("ms", 1e9)):
        if s.endswith(u):
            return float(s[:-len(u)].strip() or "1") * m
    return 1.0


def b2i(b):
    return None if any(ch in "xz" for ch in b) else int(b, 2)


def b2s(b, w):
    if any(ch in "xz" for ch in b):
        return None
    b = b.zfill(w)[-w:]
    v = int(b, 2)
    return v - (1 << w) if b[0] == "1" else v


def val_at(seq, t):
    cur = seq[0][1] if seq else None
    for tt, v in seq:
        if tt <= t:
            cur = v
        else:
            break
    return cur


def first(seq, target="1", after=-1):
    for tt, v in seq:
        if tt > after and v == target:
            return tt
    return None


def trans_in(seq, t0, t1):
    out = [(t0, val_at(seq, t0))]
    for tt, v in seq:
        if t0 < tt <= t1:
            out.append((tt, v))
    return out


def main():
    ts_ps, ch, width = parse_vcd(VCD)
    f = ts_ps / 1000.0
    nsc = {n: [(t * f, v) for t, v in s] for n, s in ch.items()}

    t_start = first(nsc["start"]) or 0
    busy = nsc["busy"]
    t_busy0 = first(busy) or t_start
    t_done = first(nsc["done"]) or (t_busy0 + 100)
    win0 = max(0, t_start - 30)
    win1 = t_done + 60

    fig, ax = plt.subplots(figsize=(16, 6.5))
    n_sig = len(TARGETS)
    row_h, gap, hi = 1.0, 0.35, 0.7
    yt, yl = [], []

    for idx, (label, sig, is_bus, dec) in enumerate(TARGETS):
        base = (n_sig - 1 - idx) * (row_h + gap)
        yt.append(base + hi / 2); yl.append(label)
        segs = trans_in(nsc[sig], win0, win1)
        if not is_bus:
            xs, ys = [], []
            for k, (tt, v) in enumerate(segs):
                lvl = base + (hi if v == "1" else 0.0)
                xs += [max(tt, win0)]; ys += [lvl]
                nxt = segs[k + 1][0] if k + 1 < len(segs) else win1
                xs += [nxt]; ys += [lvl]
            ax.plot(xs, ys, color="#1565c0", lw=1.2)
            ax.axhline(base, color="0.9", lw=0.4, zorder=0)
        else:
            dt = min(1.5, 0.004 * (win1 - win0))
            ylo, yhi, ym = base, base + hi, base + hi / 2
            for k, (tt, v) in enumerate(segs):
                a = max(tt, win0)
                b = segs[k + 1][0] if k + 1 < len(segs) else win1
                if dec == "dec":
                    iv = b2i(v); lab = str(iv) if iv is not None else "x"
                elif dec == "sdec":
                    sv = b2s(v, width.get(sig, 16)); lab = str(sv) if sv is not None else "x"
                else:
                    iv = b2i(v); lab = dec.get(iv, "x") if iv is not None else "x"
                for yy in (yhi, ylo):
                    ax.plot([a + dt, b - dt], [yy, yy], color="#2e7d32", lw=1.1)
                ax.plot([a, a + dt], [ym, yhi], color="#2e7d32", lw=1.1)
                ax.plot([a, a + dt], [ym, ylo], color="#2e7d32", lw=1.1)
                ax.plot([b - dt, b], [yhi, ym], color="#2e7d32", lw=1.1)
                ax.plot([b - dt, b], [ylo, ym], color="#2e7d32", lw=1.1)
                if (b - a) > (win1 - win0) * 0.018:
                    ax.text((a + b) / 2, ym, lab, ha="center", va="center",
                            fontsize=6.5, color="#1b5e20", fontweight="bold")

    y_top = n_sig * (row_h + gap)

    # phase regions
    t_busy1 = None
    for tt, v in busy:
        if v == "0" and tt > t_busy0 * 1.0 + 1:
            t_busy1 = tt; break
    t_busy1 = t_busy1 or t_done
    regions = [("START", win0, t_busy0, "#1565c0"),
               ("COMPUTE  (16 batches x ~73 cyc)", t_busy0, t_busy1, "#2e7d32"),
               ("DONE / READOUT", t_busy1, win1, "#b71c1c")]
    for nm, a, b, c in regions:
        if b <= a:
            continue
        ax.add_patch(Rectangle((a, -0.4), b - a, y_top + 0.3, color=c,
                               alpha=0.06, zorder=0))
        ax.axvline(a, color=c, lw=1.0, ls="--", alpha=0.5)
        ax.text((a + b) / 2, y_top + 0.25, nm, ha="center", va="bottom",
                fontsize=10, color=c, fontweight="bold")

    # light batch-boundary markers
    last = None
    for tt, v in nsc["batch_cnt"]:
        if win0 <= tt <= win1 and v != last:
            ax.axvline(tt, color="0.6", lw=0.4, ls=":", alpha=0.5, zorder=0)
            last = v

    ax.set_yticks(yt); ax.set_yticklabels(yl, fontsize=9, fontweight="bold")
    ax.set_xlim(win0, win1); ax.set_ylim(-0.5, y_top + 0.9)
    ax.set_xlabel("time (ns)  —  100 MHz clock", fontsize=11)
    ax.set_title("M4 K=64 accelerator — one full N=1000 reservoir update (Q15)",
                 fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="0.92", lw=0.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    leg = [Line2D([0], [0], color="#1565c0", lw=1.2, label="1-bit signal"),
           Line2D([0], [0], color="#2e7d32", lw=1.2, label="multi-bit bus")]
    ax.legend(handles=leg, loc="lower right", fontsize=8, framealpha=0.9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(); fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT}  window {win0:.0f}-{win1:.0f} ns, done@{t_done:.0f}")


if __name__ == "__main__":
    main()
