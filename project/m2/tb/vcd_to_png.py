#!/usr/bin/env python3
"""
vcd_to_png.py — render a labeled digital-waveform PNG from compute_core's VCD,
for the ECE 510 M2 milestone deliverable.

Parses tb/m2/sim_build/compute_core_DW16/waves.vcd (a real VCD produced by
fst2vcd from the Icarus FST dump), extracts the control + datapath signals of
the compute_core FSM, and draws a GTKWave-style waveform zoomed onto the
test_representative_vector region (the second cocotb test, where `start` first
asserts after t = 160 ns).

Usage:
    python tb/m2/vcd_to_png.py
Output:
    sim/waveform.png   (150 DPI, 16x6 in)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless render
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS = Path(__file__).resolve().parent
VCD  = THIS / "sim_build" / "compute_core_DW16" / "waves.vcd"
OUT  = THIS.parents[1] / "sim" / "waveform.png"

# Signals to extract from the compute_core scope: name -> is_bus
TARGETS = [
    ("clk",         False),
    ("rst_n",       False),
    ("start",       False),
    ("chunk_valid", False),
    ("last_chunk",  False),
    ("done",        False),
    ("x_next_o",    True),
    ("state",       True),
]

# FSM state-register decode (matches typedef enum in compute_core.sv)
STATE_NAMES = {0: "IDLE", 1: "MAC", 2: "FLUSH", 3: "ACTIVATE",
               4: "BLEND", 5: "DONE"}

# Phase annotations keyed by the state value at which the phase begins.
# (state 0/IDLE is intentionally excluded — RESET and LOAD are marked
# explicitly so they don't pile up on the IDLE segments at either end.)
PHASE_BY_STATE = {
    1: "MAC ACCUMULATE",
    2: "FLUSH",
    3: "ACTIVATE",
    4: "BLEND",
    5: "DONE -> x_next ready",
}


# ---------------------------------------------------------------------------
# VCD parsing (hand-rolled — the dump is small and well-formed)
# ---------------------------------------------------------------------------
def parse_vcd(path):
    """Return (timescale_ps, changes) where changes maps signal name ->
    sorted list of (time_ps, value). 1-bit values are '0'/'1'/'x'/'z';
    bus values are the raw binary string (no leading 'b')."""
    sym2name = {}        # vcd symbol -> signal name (compute_core scope only)
    name_width = {}
    timescale_ps = 1
    scope_depth = 0
    in_cc_scope = False

    changes = {name: [] for name, _ in TARGETS}
    want = {name for name, _ in TARGETS}

    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()

    i = 0
    defining = True
    cur_time = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        if defining:
            if line.startswith("$timescale"):
                # value may be on same or next line, e.g. "1ps"
                body = line.replace("$timescale", "").replace("$end", "").strip()
                if not body:
                    body = lines[i].strip(); i += 1
                timescale_ps = _ts_to_ps(body)
            elif line.startswith("$scope"):
                parts = line.split()
                # parts: $scope module <name> $end
                name = parts[2] if len(parts) > 2 else ""
                scope_depth += 1
                if name == "compute_core" and scope_depth == 1:
                    in_cc_scope = True
                elif scope_depth > 1:
                    in_cc_scope = False  # only the top compute_core scope
            elif line.startswith("$upscope"):
                scope_depth -= 1
                in_cc_scope = (scope_depth == 1)
            elif line.startswith("$var"):
                # $var <type> <width> <symbol> <name> [range] $end
                p = line.split()
                width = int(p[2]); sym = p[3]; name = p[4]
                if in_cc_scope and name in want and name not in name_width:
                    sym2name[sym] = name
                    name_width[name] = width
            elif line.startswith("$enddefinitions"):
                defining = False
            continue

        # --- value-change section ---
        c = line[0]
        if c == "#":
            cur_time = int(line[1:])
        elif c in "01xz":
            sym = line[1:]
            name = sym2name.get(sym)
            if name is not None:
                changes[name].append((cur_time, c))
        elif c in "bB":
            # vector: "b<bits> <sym>"
            val, sym = line[1:].split()
            name = sym2name.get(sym)
            if name is not None:
                changes[name].append((cur_time, val))
        elif c in "rR":
            pass  # no real-valued targets

    return timescale_ps, changes, name_width


def _ts_to_ps(s):
    s = s.strip().lower()
    for unit, mult in (("fs", 0.001), ("ps", 1), ("ns", 1000),
                       ("us", 1_000_000), ("ms", 1_000_000_000)):
        if s.endswith(unit):
            num = s[:-len(unit)].strip() or "1"
            return float(num) * mult
    return 1.0


def bin_to_signed(bits, width):
    """Two's-complement signed decimal from a binary string.

    VCD left-extends vectors, so a value shorter than `width` has implicit
    leading zeros; pad to width, then interpret the top bit as the sign."""
    if any(ch in "xz" for ch in bits):
        return None
    bits = bits.zfill(width)[-width:]
    v = int(bits, 2)
    if bits[0] == "1":
        v -= (1 << width)
    return v


def bin_to_int(bits):
    if any(ch in "xz" for ch in bits):
        return None
    return int(bits, 2)


# ---------------------------------------------------------------------------
# Value lookup helpers
# ---------------------------------------------------------------------------
def value_at(seq, t):
    """Last value in seq (list of (time,val)) with time <= t, else first."""
    cur = seq[0][1] if seq else None
    for tt, v in seq:
        if tt <= t:
            cur = v
        else:
            break
    return cur


def transitions_in(seq, t0, t1):
    """Return [(time, value)] covering [t0, t1]: the value active at t0
    followed by every change strictly inside the window."""
    out = [(t0, value_at(seq, t0))]
    for tt, v in seq:
        if t0 < tt <= t1:
            out.append((tt, v))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not VCD.exists():
        raise SystemExit(f"VCD not found: {VCD}")

    ts_ps, changes, widths = parse_vcd(VCD)
    ps_to_ns = ts_ps / 1000.0  # one VCD tick -> ns

    def t_ns(tick):
        return tick * ps_to_ns

    # --- locate representative_vector window: first start rise after 160 ns ---
    start_seq = changes["start"]
    start_rise_ns = None
    for tick, v in start_seq:
        if v == "1" and t_ns(tick) > 160.0:
            start_rise_ns = t_ns(tick)
            break
    if start_rise_ns is None:
        raise SystemExit("no start rising edge found after t=160ns")

    win_t0 = start_rise_ns - 15.0     # a little context before start

    # End the window on this test's result: the first nonzero x_next_o after
    # start. Beyond that the next cocotb test resets x_next_o to 0, so a fixed
    # 200 ns span would overrun the representative cycle and show 0 at the end.
    result_ns = None
    for tick, v in changes["x_next_o"]:
        t = t_ns(tick)
        if t > start_rise_ns and bin_to_signed(v, widths.get("x_next_o", 16)):
            result_ns = t
            break
    win_t1 = (result_ns + 15.0) if result_ns else (win_t0 + 200.0)
    win_t1 = min(win_t1, win_t0 + 200.0)   # never exceed a ~200 ns view
    print(f"timescale: {ts_ps} ps/tick | representative window: "
          f"{win_t0:.0f}-{win_t1:.0f} ns (start @ {start_rise_ns:.0f} ns, "
          f"x_next ready @ {result_ns} ns)")

    # convert all target change streams to ns once
    ns_changes = {n: [(t_ns(tk), v) for tk, v in seq]
                  for n, seq in changes.items()}

    # --- figure layout ---
    fig, ax = plt.subplots(figsize=(16, 6))
    n_sig = len(TARGETS)
    row_h = 1.0
    gap = 0.35
    hi = 0.7  # logic-high height inside a row

    y_labels, y_ticks = [], []

    final_xnext = None

    for idx, (name, is_bus) in enumerate(TARGETS):
        # rows drawn top-to-bottom: first signal on top
        base = (n_sig - 1 - idx) * (row_h + gap)
        y_ticks.append(base + hi / 2)
        y_labels.append(name)
        seq = ns_changes[name]
        segs = transitions_in(seq, win_t0, win_t1)

        if not is_bus:
            # square wave
            xs, ys = [], []
            for k, (tt, v) in enumerate(segs):
                lvl = base + (hi if v == "1" else 0.0)
                xs.append(max(tt, win_t0)); ys.append(lvl)
                nxt = segs[k + 1][0] if k + 1 < len(segs) else win_t1
                xs.append(nxt); ys.append(lvl)
            ax.plot(xs, ys, color="#1565c0", lw=1.6, drawstyle="default")
            ax.axhline(base, color="0.85", lw=0.4, zorder=0)
        else:
            # hexagonal bus
            dt = min(2.0, 0.02 * (win_t1 - win_t0))
            ylo, yhi, ymid = base, base + hi, base + hi / 2
            for k, (tt, v) in enumerate(segs):
                a = max(tt, win_t0)
                b = segs[k + 1][0] if k + 1 < len(segs) else win_t1
                # decode label
                if name == "state":
                    iv = bin_to_int(v)
                    lab = STATE_NAMES.get(iv, v) if iv is not None else "x"
                else:  # x_next_o signed decimal
                    sv = bin_to_signed(v, widths.get(name, 16))
                    lab = str(sv) if sv is not None else "x"
                    if win_t1 - 1 <= b:
                        final_xnext = sv
                # body lines
                ax.plot([a + dt, b - dt], [yhi, yhi], color="#2e7d32", lw=1.4)
                ax.plot([a + dt, b - dt], [ylo, ylo], color="#2e7d32", lw=1.4)
                # opening crossover
                ax.plot([a, a + dt], [ymid, yhi], color="#2e7d32", lw=1.4)
                ax.plot([a, a + dt], [ymid, ylo], color="#2e7d32", lw=1.4)
                # closing crossover
                ax.plot([b - dt, b], [yhi, ymid], color="#2e7d32", lw=1.4)
                ax.plot([b - dt, b], [ylo, ymid], color="#2e7d32", lw=1.4)
                if b - a > dt * 2:
                    ax.text((a + b) / 2, ymid, lab, ha="center", va="center",
                            fontsize=8, color="#1b5e20", fontweight="bold")

    # --- phase annotations from the state stream ---
    state_segs = transitions_in(ns_changes["state"], win_t0, win_t1)
    y_top = n_sig * (row_h + gap)
    seen = set()
    # RESET marker if rst_n low at the window start (per-test reset pulse)
    rst_at = value_at(ns_changes["rst_n"], win_t0)
    if rst_at == "0":
        _phase_mark(ax, win_t0, y_top, "RESET", "#b71c1c")
    # LOAD marker on the start pulse (host streams W row / x chunk)
    _phase_mark(ax, start_rise_ns, y_top, "LOAD", "#6a1b9a")
    for tt, v in state_segs:
        iv = bin_to_int(v)
        if iv in PHASE_BY_STATE and iv not in seen:
            seen.add(iv)
            x = max(tt, win_t0)
            _phase_mark(ax, x, y_top, PHASE_BY_STATE[iv], "#6a1b9a")

    # --- cosmetics ---
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels, fontsize=10, fontweight="bold")
    ax.set_xlim(win_t0, win_t1)
    ax.set_ylim(-0.5, y_top + 0.9)
    ax.set_xlabel("time (ns)", fontsize=11)
    ax.set_title("compute_core FSM — test_representative_vector "
                 f"(x_next = {final_xnext})", fontsize=13, fontweight="bold")
    ax.grid(axis="x", color="0.9", lw=0.5)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    legend = [Line2D([0], [0], color="#1565c0", lw=1.6, label="1-bit signal"),
              Line2D([0], [0], color="#2e7d32", lw=1.6, label="multi-bit bus"),
              Line2D([0], [0], color="#6a1b9a", lw=1.0, ls="--", label="FSM phase")]
    ax.legend(handles=legend, loc="upper right", fontsize=8, framealpha=0.9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150)
    print(f"wrote {OUT}  (x_next_o final = {final_xnext})")


def _phase_mark(ax, x, y_top, text, color):
    ax.axvline(x, color=color, lw=1.0, ls="--", alpha=0.6, zorder=1)
    ax.text(x, y_top + 0.15, text, rotation=90, ha="right", va="top",
            fontsize=7.5, color=color, fontweight="bold")


if __name__ == "__main__":
    main()
