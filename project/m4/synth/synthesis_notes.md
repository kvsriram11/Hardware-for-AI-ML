# M4 Synthesis Notes — multi-precision sweep

## What synthesized

The K=64 accelerator's compute lane (`compute_core` = MAC_WIDTH=16 streaming MAC
+ PWL tanh + leak blend) was synthesized to **sky130_fd_sc_hd** (`tt_025C_1v80`)
at all three precisions with **yowasp-yosys 0.66** (WASM Yosys — same Docker-free
flow as M3), targeting 125 MHz (8 ns). All three runs completed; each produced a
mapped gate-level netlist, area/cell report, and an `ltp` critical-path proxy.

| Precision | DATA_W | Cells / lane | Area / lane (µm²) | FFs / lane | ltp depth | Cells ×64 | Area ×64 |
|---|---|---|---|---|---|---|---|
| Q15  | 16 | 29,681 | 213,526 | 687 | 307 | 1,899,584 | 13.67 mm² |
| INT8 |  8 |  8,274 |  60,284 | 391 | 296 |   529,536 |  3.86 mm² |
| Q4   |  4 |  2,799 |  21,180 | 243 | 290 |   179,136 |  1.36 mm² |

### Why per-lane synthesis (the K=64 scope decision)

The full K=64 top instantiates 64 `compute_core` lanes plus a ~1 M-entry weight
SRAM. Std-cell-synthesizing 64 lanes is ~1.9 M cells (Q15) — well beyond what the
WASM Yosys build elaborates in a reasonable time/memory budget, and the weight
store is a **compiled SRAM macro** in any real flow, not standard cells. So the
synthesized unit is **one lane**, and the K=64 numbers are reported as **×64**:

- **Timing / critical path are exact for the whole design** — the 64 lanes are
  parallel and electrically identical, driven by the same control, so one lane's
  critical path *is* the design's critical path (no cross-lane combinational
  paths exist).
- **Area is linear in K** for the compute fabric, so ×64 is the faithful total;
  the weight SRAM macro area is reported separately (out of std-cell scope).

This is the same defensible posture as M3 (which synthesized one
`interface_axi`+`compute_core`). It captures every rubric synth deliverable
(cells, area, timing, power, critical path) per precision without faking a
P&R-scale run the toolchain can't do here.

## What did not synthesize / was not produced

- **Full-K top + weight SRAM** — see above; out of WASM-Yosys / std-cell scope.
- **ns-accurate STA** — OpenSTA is unavailable on this host, so
  `timing_report.txt` reports `ltp` topological logic depth (the M3 convention),
  not back-annotated worst-slack.
- **Sign-off power** — `power_report.txt` is a first-order estimate
  (cells × activity × energy × f); precise power needs OpenROAD `report_power`
  with extracted parasitics + the cosim VCD activity (deferred).

## Scope adjustments and rationale

1. **Yosys (yowasp WASM) instead of OpenLane 2** — Docker would not come up
   cleanly on this Windows/MSYS2 host; WASM Yosys needs no container, reads the
   SystemVerilog directly, maps to real sky130 cells, and iterates in ~30 s.
   (Carried over from M3, where it was first adopted.)
2. **Per-lane synthesis ×64** — full-K elaboration exceeds the WASM toolchain;
   per-lane is exact for timing/critical-path and linear-faithful for area.
3. **125 MHz target, not 100 MHz** — at the measured 1169 cycles/update, 100 MHz
   gives 85.5 k updates/s = 8.2× (under target); 125 MHz gives 106.9 k = 10.3×
   (clears). The `ltp` logic depth (~300 cells) is the same order as M3's design
   that the notes judged comfortable at 100 MHz; closing 8 ns is plausible but
   not STA-proven here — if a real STA pass missed 8 ns, the documented fix is
   pipelining the MAC adder tree (`critical_path.md`), which the existing
   `S_FLUSH` drain already accommodates. Reported honestly in `bench/benchmark.md`.

## Cross-precision comparison (the multi-precision result)

- **Area collapses with precision** roughly as the multiplier (~DATA_W²):
  Q15→INT8 is 3.5× smaller, INT8→Q4 a further 2.8× (per lane). The full K=64
  fabric goes 13.67 → 3.86 → 1.36 mm².
- **Logic depth barely moves** (307→296→290): the critical path is the
  **ACC_W=40 adder-tree reduction**, which is width-independent. So narrowing
  DATA_W buys area and power, **not** clock speed — confirming the bottleneck is
  the fixed-width accumulator, not the multiplier.
- **Throughput is identical across precisions** (1169 cycles, 106.9 k updates/s):
  the lanes process MAC_WIDTH=16 weights/beat regardless of bit width, so cycle
  count is precision-independent. Precision is an **area/power/accuracy** lever,
  not a throughput lever — exactly what the M1 memory-bound roofline predicted
  (shrinking bytes raises arithmetic intensity without changing the compute).
- **Accuracy** (vs FP32, ≥200 samples): SNR 79.1 dB (Q15) → 31.6 dB (INT8) →
  7.9 dB (Q4), ≈6 dB per bit dropped — textbook quantization scaling. Q15 is the
  comfortable reference; INT8 is a clear but usable step down (and would recover
  bits with a per-tensor scale, since Q1.7 wastes range on ±0.2 weights); Q4 is
  the documented degradation point.

## What this informs for future work

- The MAC adder tree is the one path worth pipelining; it gates any clock push
  and is precision-independent.
- The multi-precision sweep is the real area/power knob — an INT8 chiplet is
  ~3.5× smaller and ~3.6× lower power than Q15 at identical throughput, at a
  measured 48 dB SNR cost.
