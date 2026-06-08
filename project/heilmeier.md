# Heilmeier Questions (refined)

## Q1 — What are you trying to do? (No jargon.)

Build a small custom chip (a chiplet) that runs the central computation of an Echo State Network — 
a kind of recurrent neural network — much faster and more efficiently than a normal CPU can. 
The chip handles one specific repeated calculation: updating the network's internal state, one step at a time. 
Setup tasks like training the readout weights stay on the host CPU. 
The result is a small, low-power accelerator suited for embedded control or signal-processing applications 
where an ESN runs continuously for millions of steps.

## Q2 — How is it done today, and what are the limits of current practice?

Today the same computation runs on a general-purpose CPU using NumPy with OpenBLAS underneath. 
On an Intel i7-1165G7, single-threaded, the canonical minimalESN reference (N=1000, 4000 steps) 
takes a median of **1.68 seconds** (2381 updates/sec full pipeline; 
4446 updates/sec for the isolated state update kernel).

**Profiling shows two things that matter for our design.**

1. **The state-update kernel is the only computation that recurs in deployment.** 
Spectral-radius normalization and ridge-regression readout training are one-shot setup operations. 
In the canonical 4000-step script, state update is 29-98% of recurring time depending on N 
(see `codefest/cf02/analysis/kernel_comparison.md`); for any realistic deployment of 10^5+ steps it is essentially 100%.

2. **The kernel is memory-bandwidth-bound on the CPU, not compute-bound.** 
Analytical arithmetic intensity is **0.50 FLOP/byte** (no-reuse model), well below the i7-1165G7 ridge point of 3.50 FLOP/byte. 
Sustained throughput is **8.93 GFLOP/s** against 179.2 GFLOP/s peak compute — about 5% of peak. 
The CPU is starving for memory bandwidth, not for arithmetic units. 
This is the bottleneck a custom chiplet can exploit: lower-precision arithmetic and on-chip SRAM for W 
eliminate the DRAM round-trip per step.

## Q3 — What is new in our approach, and why do we think it will be successful?

**Three things distinguish this accelerator from a CPU and from a GPU port of the same kernel:**

1. **Precision specialization.** Because the CPU is memory-bound, halving the bits per weight ~doubles effective throughput. 
We characterize Q15, INT8, and Q4 fixed-point datapaths (FP16 as stretch) and report the area-throughput-accuracy tradeoff. 
GPUs are stuck with FP16/INT8 hardware paths; we go to Q4 with an integer datapath that costs <25% of an INT8 multiplier.

2. **On-chip weight resident.** 
At Q15 the 1000×1000 W matrix is 2 MB, fitting on-die SRAM with margin. 
Win is 4 KB. 
Every state-update step then needs only an x-read, x-write, and one input scalar from the host. 
Effective AI rises by ~100× over the no-reuse CPU model.

3. **Sequential-streaming match.** 
ESN state update is inherently sequential: `x[t]` requires `x[t-1]`. 
GPUs are bad at this — large batch sizes are the only way to fill them, and ESN deployment is single-stream. 
A small chiplet with a 16-wide MAC array clocked at 100 MHz reaches ~1.5M updates/sec without any batching gymnastics — 
about 350× the measured single-thread CPU rate of 4446 updates/sec for isolated state update.

## Q4 — Who cares?

Embedded control loops, online filtering, and edge-deployed sequence prediction where an ESN 
runs continuously at low power and the host CPU can't dedicate a core. 
Also: chiplet integration into larger heterogeneous SoCs where ESN inference is one block among many.

## Q5 — If you're successful, what difference will it make?

A reusable IP block and a characterization study mapping precision against area, throughput, energy, and accuracy — 
enabling system designers to pick the right ESN configuration for their power envelope.

## Q6 — What are the risks?

Quantization error at Q4 may exceed acceptable MSE for some applications; we report the curve. 
On-chip SRAM is limited so very large reservoirs (N≥4096 at FP16) exceed budget; we report the cutoff.

## Q7 — How much will it cost? How long?

Bounded by the ECE 510 milestone schedule; M1-M3 by June 7, M4 by June 7 final submission.

## Q8 — What are the mid-term and final exams?

Mid-term: M3 deliverable shows synthesizable RTL passing co-simulation and producing sky130 timing+area+power reports. 
Final: M4 deliverable benchmark.md shows measured speedup vs CPU baseline at each precision, 
with the roofline updated to include the realized accelerator design point.
