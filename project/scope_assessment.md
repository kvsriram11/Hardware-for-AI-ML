# Project Scope Assessment — Post-CF07

**Project working title:** Structured-Sparse Hardware Accelerator for Efficient Reservoir State Update in Streaming Inference (Chiplet-Based Reservoir Computing Accelerator)  
**Author:** Venkata Sriram Kamarajugadda  
**Date:** May 17, 2026  
**M3 deadline:** May 24, 2026

---

## Current state

Some blocks are RTL-complete, others are not.

**RTL-complete (today):**
- Synthesizable INT8 MAC unit (signed 8-bit inputs, 32-bit accumulator, synchronous active-high reset; verified with Yosys and cocotb)
- 4×4 binary-weight crossbar MAC (CF06 fallback core, used for the CF07 OpenLane run)

**In progress / not yet RTL:**
- Sparse-MVM datapath (CSR-indexed nonzero MAC with structured sparsity hooks)
- Reservoir state register and update controller
- Chiplet-level interconnect and partitioning

A full chiplet-integrated reservoir accelerator is **not** synthesizable by May 24. The honest M3 target is a subset, not the whole architecture.

## What the CF06 synthesis result tells me

The CF07 OpenLane run on the 4×4 binary-weight `crossbar_mac` produced concrete numbers I need to take seriously when scoping M3:

- **1,386 instances, 9,168 µm²** for a 4×4 *1-bit-weight* MAC — a deliberately small block.
- **Setup slack: +1.79 ns typical, −1.84 ns at slow corner.** 140 paths fail slow-corner sign-off at 100 MHz, despite this being a tiny design.
- **Critical path is 16 logic levels deep**, dominated by three XNOR sign-flip gates and 4-input OR/NOR sum-tree reduction. All 140 violators are combinational input→output paths.
- **`[RSZ-0062] Unable to repair all setup violations`** — OpenROAD's automated repair gave up.

Implications for a *real* sparse-MVM core:

1. **Wider precision (INT8 instead of 1-bit) deepens the partial-product sum tree** and adds shift/sign-extend logic. The crossbar's critical path was already 16 levels at 1-bit; INT8 will be significantly deeper.
2. **Sparse CSR indexing adds combinational depth** (address generation, predicate logic) on top of the MAC datapath itself, before reaching the sum tree.
3. **A 100 MHz target is optimistic** if the architecture is unpipelined. CF06 failed slow-corner at 10 ns on a fraction of the logic; a fully unpipelined sparse-MVM at the same target would fail much harder.
4. **The 50% memory-breakeven and ~5× memory-bound speedup from CMAN** mean a sparse MVM only pays off when both compute and indexing fit in the bandwidth budget. The accelerator is justified by memory traffic, not by FLOPs.

## Two scope options for M3

I am keeping both options open for the next 3–4 days and will commit by **Wed May 21, 2026**. Both are honest given current RTL progress.

**Option A — narrow synthesis target, full project scope preserved**
- M3 synthesizable block: the **INT8 MAC + 16-bit weight register** I already have RTL for, possibly with one pipeline stage added at the multiplier output.
- Scope assessment for the full project remains: chiplet-based sparse-MVM reservoir accelerator.
- Justification: this proves the toolchain on real INT8 datapath and gives a concrete area/timing baseline for the larger sparse MVM core. Project scope unchanged.

**Option B — descope to a single fixed-size dense reservoir update**
- Drop sparsity exploitation and chiplet integration for M3. Synthesize a small dense reservoir state update (e.g., 8×8 or 16×16 INT8 MVM with a state register) as the M3 deliverable.
- Add sparsity and CSR handling as post-M3 work.
- Justification: matches the CF06 lesson — closing slow-corner timing on real logic is harder than the RTL suggests, and a dense baseline gives me a clean comparison point before adding the indexing overhead.

I will not pick option B prematurely if option A is achievable; equally, I will not bluff option A if the additional RTL work isn't realistic in the remaining time.

## Clock-period plan for M3

Regardless of which option I pick, the slow-corner result from CF06 changes my target. I will:

- **Start at 15 ns (≈66 MHz)** instead of 10 ns, giving 50% headroom against the kind of slow-corner blowup CF06 exhibited.
- Tighten only if typical-corner slack exceeds +5 ns and slow-corner slack is comfortably positive.
- Use a **custom SDC** rather than the generic fallback (CF07 used the fallback and lost 4 ns of the 10 ns budget to default I/O delays).

## Decision date

**May 21, 2026.** I will commit a follow-up update to this file with the chosen option and a one-line rationale before attempting M3 synthesis.
