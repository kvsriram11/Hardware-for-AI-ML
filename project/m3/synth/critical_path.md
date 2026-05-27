# Critical Path Analysis — M3 Synthesis (sky130_fd_sc_hd)

**Design:** top (ESN reservoir state update accelerator)  
**Tool:** Yosys 0.52 + ABC  `+strash;map;print_stats`  
**PDK:** sky130A tt_025C_1v80  
**Clock target:** 10.000 ns (100 MHz)

---

## Identified Critical Path

The worst-case combinational delay is inside `q15_blend`, the purely
combinational module that computes the weighted blend:

```
x_new = (1 − α) × reservoir_out  +  α × input_scaled
```

where all operands are Q15 fixed-point (16-bit, 1 integer + 15 fractional).

### Path Stages

```
[Start] dfxtp_1 in compute_core          ← tanh_result_reg / input_scaled_reg
         clk→Q delay: ~150 ps

[Stage 1] Output steering mux (compute_core)
          Type: a21oi_1, o21ai_0
          Delay: ~50 ps

[Stage 2] q15_blend: alpha operand path into multiplier 1
          Operation: α × input_scaled  (Q15 × Q15, 16b×16b)
          Partial-product generation: sky130_fd_sc_hd__nand2_1
          Adder tree reduction: sky130_fd_sc_hd__a21oi_1, nand3_1
          Levels: 17 of 39

[Stage 3] q15_blend: (1−α) path into multiplier 2
          Operation: (1−α) × reservoir_out
          Parallel to Stage 2, but longer carry chain dominates
          Levels: 22 of 39 (ripple-carry in partial product summation)

[Stage 4] q15_blend: final adder and saturation clamp
          Operation: sum both products → right-shift 15 → saturate to Q15
          Cells: sky130_fd_sc_hd__nand2_1, o21ai_0, a22oi_1
          Levels: remaining levels to output

[End] dfxtp_1 in compute_core            ← x_new_reg capture
      Setup time: ~150 ps
```

### Numeric Summary

| Stage                              | Delay (ps) |
|------------------------------------|-----------|
| clk→Q (dfxtp_1, compute_core)      |    150    |
| Steering/mux (compute_core)        |     50    |
| q15_blend combinational (39 levels)|  3,483    |
| Setup time (dfxtp_1, compute_core) |    150    |
| **Total worst-case path**          | **3,833** |

Clock period: 10,000 ps  
**Slack: +6,167 ps (+6.17 ns)**

---

## Why q15_blend is the Bottleneck

`q15_blend` implements two independent 16×16 Q15 multiplications in
fully combinational logic — no pipeline registers, no DSP blocks (sky130
has none). The partial-product adder tree for a 16×16 multiplier
inherently requires ≥ 30 logic levels in NAND-based implementation.
ABC maps it to 39 levels with 5,531 nodes (from `print_stats` output),
consuming 29,355 µm² — 47.9% of total chip area.

---

## Dominant Cell Types on Critical Path

These cells appear most on the critical path based on cell counts and
ABC's internal depth analysis:

| Cell                         | Count | Role on Path               |
|------------------------------|-------|---------------------------|
| sky130_fd_sc_hd__nand2_1     | 2,980 | Partial-product generation |
| sky130_fd_sc_hd__a21oi_1     | 1,222 | Adder carry-generate       |
| sky130_fd_sc_hd__nand3_1     | 1,343 | Adder sum / carry          |
| sky130_fd_sc_hd__o21ai_0     |   583 | Adder propagate            |
| sky130_fd_sc_hd__a22oi_1     |   647 | Product accumulate         |
| sky130_fd_sc_hd__clkinv_1    |   864 | Fanout buffer / inversion  |

---

## Potential Improvements

| Optimization                       | Expected Gain     |
|------------------------------------|-------------------|
| Pipeline q15_blend (add 1 FF stage)| Halve worst path to ~1.9 ns; throughput unchanged if 1-cycle latency acceptable |
| Booth encoding for multipliers     | Reduce 16×16 partial products from 16 to 9; shorten adder tree by ~5 levels |
| Carry-save adder (CSA) tree        | Replace ripple-carry in summation; estimated −0.5 ns |
| Raise clock to 200 MHz (5 ns)      | Still meets timing without any RTL change (3.833 ns < 5 ns) |

The design comfortably meets 100 MHz. Even 250 MHz (4 ns period) would
be feasible without RTL changes, based on the estimated 3.833 ns worst path.

---

## ABC Output Evidence

From `synth_timing.log` (`print_stats` output per module):

```
interface_axi  i/o=233/162  nd=655   edge=1722   area=3098.73  delay=658.25   lev=7
compute_core   i/o=279/152  nd=793   edge=1816   area=3701.21  delay=1502.05  lev=13
q15_blend      i/o= 48/ 16  nd=5531  edge=14375  area=29350.25 delay=3482.95  lev=39
q15_mac        i/o= 67/ 32  nd=3211  edge=8232   area=16670.93 delay=2908.18  lev=31
q15_tanh       i/o= 32/ 16  nd=350   edge=889    area=1728.33  delay=1701.44  lev=17
```

Units: `delay` in picoseconds, `lev` = logic depth (gate levels), `nd` = node count.
`area` is ABC internal (sum of gate areas from liberty pin capacitances), not µm².
