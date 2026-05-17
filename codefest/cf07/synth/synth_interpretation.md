# Synthesis Interpretation — CF06 Crossbar MAC

**Codefest 7 — CLLM Deliverable, Option B (CF06 fallback)**  
**ECE 410/510: Hardware for AI and ML, Spring 2026**  
**Design:** `crossbar_mac` (4×4 binary-weight crossbar MAC, 16-bit weight register, combinational outputs)  
**Tool:** OpenLane 2.3.10 (sky130A PDK)

---

## (a) Clock period and worst-case slack

The flow ran at a **10.0 ns clock period (100 MHz)** with default 2 ns I/O external delays and 0.25 ns clock uncertainty. Setup slack is corner-dependent:

| Corner | Setup WNS | Hold WNS | Verdict |
|---|---|---|---|
| `nom_tt_025C_1v80` (typical) | **+1.79 ns** | +0.42 ns | PASSES |
| `nom_ss_100C_1v60` (slow) | **−1.84 ns** | +1.09 ns | **FAILS setup** |
| `nom_ff_n40C_1v95` (fast) | +3.27 ns | +0.17 ns | PASSES |

At the slow PVT corner the design has **140 setup violations** with a total negative slack (TNS) of −60.6 ns. Hold timing is clean at every corner (no violations). The resizer flagged `[RSZ-0062] Unable to repair all setup violations`, meaning OpenROAD's automated buffer insertion and gate sizing could not close the slow-corner timing within its iteration budget.

## (b) Critical path

The single worst path is purely combinational from input to output:

```
Startpoint: in0[3]   (input port clocked by clk)
Endpoint:   out2[9]  (output port clocked by clk)
Slack:      −1.842 ns at nom_ss_100C_1v60
```

Walking the path produces 16 logic levels. The dominant cell types along it are:

- **`sky130_fd_sc_hd__xnor2_2`** — three instances, implementing the binary weight `W ∈ {+1, −1}` sign-flip on the 8-bit signed inputs.
- **`sky130_fd_sc_hd__or4_4` / `nor4_1`** — wide 4-input OR / NOR gates that reduce the four partial products per output column.
- **`sky130_fd_sc_hd__o31a_1`, `o311a_4`, `a21o_1`, `o21ai_4`** — complex AOI/OAI gates that pack add/select logic into single cells.
- **`sky130_fd_sc_hd__nand2_2`, `nand2b_4`** — used at the input and output stages.
- **`buf_6`** — two timing-repair buffers inserted by the resizer.

The violator list shows that **all 140 violators are input→output (combinational) paths**, never register→register (`Reg to Reg Paths: N/A` in summary). The deepest paths originate from `in0[3]` and `in1[1]` — these bits feed the MSB of multiple partial products, hitting the deepest level of the 4-input sum tree.

## (c) Total cell area and top contributors

Post-PnR area metrics from `final/metrics.csv`:

- **Total instances:** 1,386 (post-PnR, including taps and fillers)
- **Std-cell logic area:** 9,167.54 µm²
- **Die area:** 22,500 µm² (150 × 150 µm)
- **Core utilization:** 51.6%

The Yosys pre-PnR statistics (`stat.rpt`) show 768 cells with a chip area of 8,130.30 µm², of which only 5.17% (420 µm²) is sequential logic. The remaining ~95% is the combinational MAC datapath. The top contributors by instance count:

| Rank | Cell | Count | Role |
|---|---|---|---|
| 1 | `mux2_1` | 100 | Binary weight {+1,−1} select on each partial product |
| 2 | `xnor2_2` | 95 | Sign-flip / XOR sum |
| 3 | `nor2_2` | 71 | Sum-tree reduction |
| 4 | `xor2_2` | 68 | MAC datapath |
| 5 | `nand2_2` | 63 | General glue |

Of the sequential cells, **16 `dfrtp_2` flip-flops** match the expected `w_reg[15:0]` weight register exactly — no unintended flop inference. The flow added ~1,000 µm² of timing-repair buffers (156 `class:timing_repair_buffer` cells) during post-route fix-up, on top of the Yosys-reported 8,130 µm².

## (d) Failed constraints and warnings worth investigating

The single most actionable warning is **`[RSZ-0062] Unable to repair all setup violations`** at the slow corner, which is consistent with the −1.84 ns WNS. Other notable items from `warning.log`:

- **15 max-fanout violations**, constant across all corners. A high-fanout net (likely a `w_reg` bit driving every MAC column, or `in0[3]`/`in1[1]` driving multiple partial products) is exceeding the default fanout limit and needs buffering or replication.
- **4 max-slew violations** at the slow corner only. Caused by long unbuffered nets along the failing paths — the same paths flagged by the resizer.
- **140 setup violations** at slow, 0 at typical and fast. The design is *only* failing slow-corner sign-off; typical and fast are comfortable.
- **`PNR_SDC_FILE` and `SIGNOFF_SDC_FILE` were not defined**, so OpenLane used a generic fallback SDC. A custom SDC could tighten I/O delays and remove the artificial 4 ns the fallback charges to input+output delay (out of the 10 ns budget), which would meaningfully change the slack picture.
- 8 `[DRT-0349]` LEF58_ENCLOSURE warnings during detailed routing — harmless, related to PDK-tool version mismatch.

Zero DRC errors, zero LVS errors, zero antenna violations — physical sign-off is clean.
