# M4 Critical Path -- Q15 (DATA_W=16)

**Unit:** one K=64 lane (`compute_core`). Lanes are parallel and identical, so this lane's path **is** the design's critical path. **Library:** sky130_fd_sc_hd tt_025C_1v80. **Target:** 125 MHz (8 ns). **Tool:** yosys `ltp` on the mapped netlist (OpenSTA unavailable -> topological logic depth is the critical-path proxy, same convention as M3).

## The path (longest topological path = **307** mapped cells)

The deepest register-to-register block is the MAC reduction inside `mac_array`:

- **Start register:** `u_mac.prod_ext_q[*]` -- the MAC_WIDTH=16 stage-1 product registers, each holding one `w_in[i]*x_in[i]` sign-extended to ACC_W=40.
- **Combinational logic (the critical stages):** the adder-tree reduction `tree_sum = sum(prod_ext_q[0..15])` -- a **16-operand, 40-bit signed addition** mapped to a deep chain of sky130 `xor2/xnor2/maj/o21ai/a21oi` carry cells (log2(16)=4 reduction levels x 40-bit carry propagate).
- **End register:** `u_mac.tree_q[*]` -- the stage-2 reduce register that latches `tree_sum`.
- **Next-longest:** `tree_q -> sum_out` (stage-3 accumulate, one 40-bit add).
- A comparable path runs `x_chunk/w_row -> 16x 16x16 signed multipliers -> prod_ext_q`.

## Logic stages
| Stage | From -> To | Logic |
|---|---|---|
| 1 multiply | `x_chunk/w_row` -> `prod_ext_q` | 16x parallel 16x16 signed multiply |
| **2 reduce (critical)** | **`prod_ext_q` -> `tree_q`** | **16-input 40-bit adder tree (tree_sum)** |
| 3 accumulate | `tree_q` -> `sum_out` | one 40-bit add |

## Precision effect
The ACC_W=40 adder tree is **width-independent**, so logic depth barely moves across precisions (Q15=307, INT8=296, Q4=290 cells). What shrinks with DATA_W is **area** (multiplier area ~ DATA_W^2): this lane is 29681 cells / 213526 um^2. The design is depth-bound by the fixed-width accumulator, not the multiplier width.

## What would shorten it
1. **Pipeline the adder tree** (16->8->4->2->1, a flop per level): ~4x depth cut; the existing `S_FLUSH` drain state already absorbs the added latency. Primary lever to push past 125 MHz.
2. **Carry-save accumulation** -- resolve the 40-bit carry once at FLUSH exit.
3. **Narrow ACC_W** (40->32) if N=1000 dynamic range allows.
