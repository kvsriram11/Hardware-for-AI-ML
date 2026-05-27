"""
plot_waveform.py — Parse dump.vcd (FST-converted) and render cosim_waveform.png

Renders three regions from the M3 co-simulation:
  Region A (    0 – 180 ns)  : Host AXI4-Lite writes  (config + CTRL start)
  Region B (  180 – 1465 ns) : AXI4-Stream operand stream + internal compute
  Region C ( 1465 – 1550 ns) : Host AXI4-Lite reads   (STATUS poll + X_NEW)

Usage:
  python plot_waveform.py [path_to_vcd] [output_png]
Defaults:
  vcd  : ../tb/sim_build/dump.vcd
  png  : cosim_waveform.png  (same dir as this script)
"""

import sys
import os
import collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ---------------------------------------------------------------------------
# VCD parser
# ---------------------------------------------------------------------------

def parse_vcd(path):
    """Return (timescale_ps, signals_dict, changes_dict).

    signals_dict : {id_char: (name, width)}
    changes_dict : {id_char: [(time_ps, value_int_or_None), ...]}
    """
    signals = {}   # id -> (name, width)
    changes = collections.defaultdict(list)

    in_header = True
    current_scope = []
    time_ps = 0

    with open(path, "r") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            # Header section
            if line.startswith("$var"):
                parts = line.split()
                # $var wire 1 ! clk $end
                if len(parts) >= 5:
                    width = int(parts[2])
                    id_char = parts[3]
                    name = parts[4]
                    signals[id_char] = (name, width)
                continue

            if line.startswith("$"):
                continue  # skip other header keywords

            # Time stamp
            if line.startswith("#"):
                time_ps = int(line[1:])
                continue

            # Scalar value change: 0! or 1! or x!
            if len(line) >= 2 and line[0] in "01xXzZ":
                val_char = line[0]
                id_char  = line[1:]
                if id_char in signals:
                    v = 1 if val_char == "1" else (0 if val_char == "0" else None)
                    changes[id_char].append((time_ps, v))
                continue

            # Vector value change: b0001 !
            if line.startswith("b") or line.startswith("B"):
                parts = line.split()
                if len(parts) == 2:
                    bin_str = parts[0][1:]
                    id_char = parts[1]
                    if id_char in signals:
                        try:
                            v = int(bin_str.replace("x","0").replace("z","0"), 2)
                        except ValueError:
                            v = None
                        changes[id_char].append((time_ps, v))
                continue

    return signals, dict(changes)


def make_step_arrays(changes, end_time_ps, start_time_ps=0):
    """Convert [(t, v)] list into step-function arrays for plotting."""
    times, vals = [], []
    prev_v = 0
    for t, v in changes:
        if t < start_time_ps:
            prev_v = v if v is not None else prev_v
            continue
        if not times:
            times.append(start_time_ps)
            vals.append(prev_v)
        times.append(t)
        vals.append(v if v is not None else prev_v)
        if v is not None:
            prev_v = v
    if not times:
        times = [start_time_ps, end_time_ps]
        vals  = [prev_v, prev_v]
    else:
        times.append(end_time_ps)
        vals.append(vals[-1])
    return np.array(times, dtype=float), np.array(vals, dtype=float)


def find_id(signals, target_name):
    for id_char, (name, width) in signals.items():
        if name == target_name:
            return id_char
    return None


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

REGION_A_NS = (0,    180)
REGION_B_NS = (180,  1465)
REGION_C_NS = (1465, 1550)
PS_PER_NS   = 1000

COLORS = {
    "valid":   "#2196F3",   # blue
    "ready":   "#4CAF50",   # green
    "data":    "#FF9800",   # orange
    "clk":     "#9E9E9E",   # grey
}

def plot_region(ax, changes, signals, sig_ids, region_ns, title, colors_map):
    """Draw waveforms for one region panel."""
    t0_ps = region_ns[0] * PS_PER_NS
    t1_ps = region_ns[1] * PS_PER_NS

    n = len(sig_ids)
    offsets = list(range(n - 1, -1, -1))   # top signal at highest y

    for idx, (label, id_char) in enumerate(sig_ids):
        off = offsets[idx]
        ch  = changes.get(id_char, [])
        t, v = make_step_arrays(ch, t1_ps, t0_ps)

        color = colors_map.get(label, "#607D8B")

        # Clip to region
        mask = (t >= t0_ps) & (t <= t1_ps)
        t_plot = t[mask]
        v_plot = v[mask]

        if len(t_plot) < 2:
            # Extend if needed
            t_plot = np.array([t0_ps, t1_ps], dtype=float)
            v_plot = np.array([v_plot[0] if len(v_plot) else 0,
                               v_plot[0] if len(v_plot) else 0], dtype=float)

        t_ns = t_plot / PS_PER_NS
        ax.step(t_ns, v_plot * 0.7 + off, where="post", color=color, linewidth=1.2)
        ax.fill_between(t_ns, off, v_plot * 0.7 + off,
                        step="post", alpha=0.18, color=color)
        ax.text(region_ns[0] - (region_ns[1] - region_ns[0]) * 0.02,
                off + 0.35, label, ha="right", va="center", fontsize=7,
                color=color, fontweight="bold")

    ax.set_xlim(region_ns[0], region_ns[1])
    ax.set_ylim(-0.3, n)
    ax.set_yticks([])
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4)
    ax.set_xlabel("Time (ns)", fontsize=7)
    ax.tick_params(axis="x", labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    # Region shading
    ax.axvspan(region_ns[0], region_ns[1], alpha=0.04, color="steelblue")


def main():
    vcd_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "tb", "sim_build", "dump.vcd")
    out_png = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(__file__), "cosim_waveform.png")

    vcd_path = os.path.abspath(vcd_path)
    out_png  = os.path.abspath(out_png)

    print(f"Parsing {vcd_path} ...")
    signals, changes = parse_vcd(vcd_path)

    print(f"  Signals found: {len(signals)}")

    # Map names to IDs
    def gid(name):
        return find_id(signals, name)

    # -----------------------------------------------------------------------
    # Region A signals: AXI4-Lite write channel
    # -----------------------------------------------------------------------
    sig_A = [
        ("clk",          gid("clk")),
        ("axil_awvalid", gid("s_axil_awvalid")),
        ("axil_awready", gid("s_axil_awready")),
        ("axil_wvalid",  gid("s_axil_wvalid")),
        ("axil_wready",  gid("s_axil_wready")),
        ("axil_bvalid",  gid("s_axil_bvalid")),
        ("axil_bready",  gid("s_axil_bready")),
    ]
    sig_A = [(lbl, id_) for lbl, id_ in sig_A if id_ is not None]

    # -----------------------------------------------------------------------
    # Region B signals: AXI4-Stream operand stream
    # -----------------------------------------------------------------------
    sig_B = [
        ("clk",          gid("clk")),
        ("axis_tvalid",  gid("s_axis_tvalid")),
        ("axis_tready",  gid("s_axis_tready")),
        ("axis_tlast",   gid("s_axis_tlast")),
        ("core_busy",    gid("core_busy")),
        ("core_done",    gid("core_done")),
    ]
    sig_B = [(lbl, id_) for lbl, id_ in sig_B if id_ is not None]

    # -----------------------------------------------------------------------
    # Region C signals: AXI4-Lite read channel
    # -----------------------------------------------------------------------
    sig_C = [
        ("clk",          gid("clk")),
        ("axil_arvalid", gid("s_axil_arvalid")),
        ("axil_arready", gid("s_axil_arready")),
        ("axil_rvalid",  gid("s_axil_rvalid")),
        ("axil_rready",  gid("s_axil_rready")),
    ]
    sig_C = [(lbl, id_) for lbl, id_ in sig_C if id_ is not None]

    colors_map = {
        "clk":          COLORS["clk"],
        "axil_awvalid": COLORS["valid"],
        "axil_awready": COLORS["ready"],
        "axil_wvalid":  COLORS["valid"],
        "axil_wready":  COLORS["ready"],
        "axil_bvalid":  COLORS["valid"],
        "axil_bready":  COLORS["ready"],
        "axis_tvalid":  COLORS["valid"],
        "axis_tready":  COLORS["ready"],
        "axis_tlast":   COLORS["data"],
        "core_busy":    COLORS["data"],
        "core_done":    "#E91E63",
        "axil_arvalid": COLORS["valid"],
        "axil_arready": COLORS["ready"],
        "axil_rvalid":  COLORS["valid"],
        "axil_rready":  COLORS["ready"],
    }

    # -----------------------------------------------------------------------
    # Layout: 3 panels stacked, width proportional to time span
    # -----------------------------------------------------------------------
    spans = [
        REGION_A_NS[1] - REGION_A_NS[0],   # 180
        REGION_B_NS[1] - REGION_B_NS[0],   # 1285
        REGION_C_NS[1] - REGION_C_NS[0],   # 85
    ]
    total = sum(spans)
    widths = [s / total for s in spans]

    fig = plt.figure(figsize=(14, 8))
    fig.patch.set_facecolor("#FAFAFA")

    gs = fig.add_gridspec(
        1, 3,
        width_ratios=widths,
        wspace=0.35,
        left=0.14, right=0.97,
        top=0.88, bottom=0.12
    )

    ax_a = fig.add_subplot(gs[0])
    ax_b = fig.add_subplot(gs[1])
    ax_c = fig.add_subplot(gs[2])

    plot_region(ax_a, changes, signals, sig_A, REGION_A_NS,
                "Region A\nAXI4-Lite Writes\n(0 – 180 ns)", colors_map)
    plot_region(ax_b, changes, signals, sig_B, REGION_B_NS,
                "Region B\nAXI4-Stream + Compute\n(180 – 1465 ns)", colors_map)
    plot_region(ax_c, changes, signals, sig_C, REGION_C_NS,
                "Region C\nAXI4-Lite Reads\n(1465 – 1550 ns)", colors_map)

    # Legend
    legend_handles = [
        mpatches.Patch(color=COLORS["valid"],  label="valid / request signals"),
        mpatches.Patch(color=COLORS["ready"],  label="ready / accept signals"),
        mpatches.Patch(color=COLORS["data"],   label="data / status signals"),
        mpatches.Patch(color=COLORS["clk"],    label="clock"),
        mpatches.Patch(color="#E91E63",        label="done / completion"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               ncol=5, fontsize=7, framealpha=0.8,
               bbox_to_anchor=(0.55, 0.01))

    # Annotations on each region
    ax_a.annotate("5× AXI-Lite writes\n(N-1, leak, Win*u,\nx_prev, CTRL.start)",
                  xy=(90, len(sig_A) - 0.5), fontsize=6.5,
                  ha="center", va="top",
                  bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", alpha=0.8))

    ax_b.annotate("64 AXIS beats\n(w_k, x_prev_k)\nMAC → tanh → blend",
                  xy=(820, len(sig_B) - 0.5), fontsize=6.5,
                  ha="center", va="top",
                  bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", alpha=0.8))

    ax_c.annotate("STATUS poll\nthen X_NEW read\ndut=golden=−2022",
                  xy=(1507, len(sig_C) - 0.5), fontsize=6.5,
                  ha="center", va="top",
                  bbox=dict(boxstyle="round,pad=0.3", fc="lightyellow", ec="orange", alpha=0.8))

    fig.suptitle(
        "M3 Co-Simulation Waveform — ESN Reservoir State Update Accelerator\n"
        "top.sv | Icarus Verilog 12.0 + cocotb 2.0.1 | PASS: dut=golden=−2022",
        fontsize=10, fontweight="bold", y=0.97
    )

    fig.savefig(out_png, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Saved waveform PNG: {out_png}")


if __name__ == "__main__":
    main()
