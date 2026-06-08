# M3 Critical Path

**Design:** `top` (ESN accelerator) · **Library:** `sky130_fd_sc_hd__tt_025C_1v80` · **Target:** 100 MHz (10 ns)
**Tool:** yowasp-yosys `ltp` on the mapped netlist (`synth/top_netlist.v`). OpenSTA was unavailable (see `synthesis_notes.md`), so the critical path is identified from the longest topological path (logic depth in mapped cells) rather than back-annotated ns slack.

## The path

The longest topological path (length **310** mapped cells) threads the FSM control registers and then the MAC datapath. The dominant *single-cycle* register-to-register segment — i.e. the actual timing-critical combinational block — is inside the MAC array:

- **Start register:** `top.u_if.u_cc.u_mac.prod_ext_q[*]` — the 16 stage-1 product registers. Each holds one lane's `w_in[i] * x_in[i]` result, sign-extended to ACC_W = 40 bits.
- **Combinational logic (the critical stages):** the `mac_array` adder-tree reduction `tree_sum = Σ prod_ext_q[0..15]` — a **16-operand, 40-bit-wide signed addition**. After ABC technology mapping this becomes a deep chain of `sky130_fd_sc_hd` `xor2`/`xnor2`/`maj`/`o21ai`/`a21oi` cells implementing carry propagation across 40 bits and log₂(16) ≈ 4 reduction levels. This reduction is the single largest block of combinational gates between any two registers in the design (the netlist's `xnor2_1`/`xor2_1` counts — 5699 and 3123 respectively — are dominated by this adder tree plus the 16 lane multipliers).
- **End register:** `top.u_if.u_cc.u_mac.tree_q[*]` — the stage-2 reduce register that latches `tree_sum`.
- A shorter following segment, `tree_q → sum_out` (the stage-3 accumulator `sum_out <= sum_out + tree_q`, a single 40-bit add), is the next-longest stage.

A comparable-depth path also exists from the streamed inputs `s_axis_tdata` through the 16 parallel **16×16 signed multipliers** into `prod_ext_q`. Multiplier and adder-tree depth are the two competing critical regions; both live in `mac_array`.

## Logic stages (summary)

| Stage | From → To | Logic |
|---|---|---|
| 1 (multiply) | `s_axis_tdata` → `prod_ext_q` | 16× parallel 16×16 signed multiply |
| **2 (reduce, critical)** | **`prod_ext_q` → `tree_q`** | **16-input 40-bit adder tree (`tree_sum`)** |
| 3 (accumulate) | `tree_q` → `sum_out` | single 40-bit add |

## Why it is critical

The reduction adds sixteen 40-bit signed operands in one clock. Carry propagation across 40 bits, repeated over the reduction levels, gives the longest combinational delay in the datapath. At 100 MHz (10 ns) this single-cycle reduction is the budget-limiter; everything else (FSM next-state, AXI handshakes, tanh PWL, leak blend) is shallow by comparison.

## What would shorten it

1. **Pipeline the adder tree (primary fix).** Split the 16-input reduction into registered levels — e.g. 16→8→4→2→1 with a flop between each level (4 pipeline stages). This cuts the worst-case combinational depth roughly 4× at the cost of 3 extra cycles of latency (absorbed by lengthening the existing `S_FLUSH` drain, which already exists for exactly this pipeline-draining purpose). Highest impact, lowest risk.
2. **Pipeline / retime the 16×16 multipliers** (the competing path) so multiply and reduce never share a cycle.
3. **Carry-save accumulation:** keep the running sum in redundant (carry-save) form and resolve the carry only once at `S_FLUSH` exit, removing the full 40-bit carry-propagate from the per-beat path.
4. **Narrow ACC_W** if the application tolerates it (40→32), shortening every adder, though this trades numerical headroom.

The RTL is already structured for option 1: the FSM's `S_FLUSH` state and `flush_cnt` exist to drain a deeper MAC pipeline, so adding tree-reduction pipeline registers is a localized `mac_array` change.
