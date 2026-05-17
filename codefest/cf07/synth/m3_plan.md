# M3 Plan — Project Core Synthesis

**Codefest 7 — Option B (CF06 fallback)**  
**ECE 410/510, Spring 2026**

## Lessons applied from the CF06 synthesis

Three takeaways from the `crossbar_mac` run apply directly to my project core (Reservoir Computing chiplet accelerator):

1. **Drop the generic SDC.** The fallback SDC charged 4 ns to I/O delay out of a 10 ns budget. For M3, I will write a custom SDC with realistic I/O constraints so slack reflects the actual datapath.
2. **Sign off at the slow corner, not typical.** The crossbar passed typical (+1.79 ns) but failed slow (−1.84 ns) by 140 paths. I will target slow-corner closure from the start and budget pessimism into the clock period.
3. **Long combinational paths fail first.** The crossbar's 16-level input→output MAC path was the single biggest source of violators. For my reservoir core's MVM, the state-update path will be similarly deep; I will pipeline the matrix-vector update across at least one register stage before synthesizing.

## Synthesis attempt for the project core

**Target date:** Wed May 21, 2026 (3 days before M3).

**Expected differences vs. the crossbar fallback:**

- **Size:** ~5–10× larger. The crossbar is 1,386 instances at 9,168 µm²; a 16×16 (or larger) sparse-aware reservoir update unit with INT8 datapath will likely exceed 10K cells and need a bigger die (300×300 µm minimum).
- **Critical path location:** reg→reg through the sparse-MAC sum tree, *not* input→output. Adding the pipeline stage shifts the failure mode from combinational depth to register-to-register routing.
- **Precision:** INT8 (not the 1-bit weights of the crossbar). Wider multipliers, deeper sum tree, more MUX area.
- **Sequential fraction:** much higher than 5%, since the pipeline register, CSR index buffer, and state register all add flops.

I will keep the 10 ns clock target initially and tighten only if slow-corner slack is comfortably positive after the first run.
