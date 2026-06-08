# Hardware Accelerator for Echo State Network Inference

**ECE 510 — Hardware for AI/ML — Spring 2026**
**Student:** Venkata Sriram Kamarajugadda (vkamaraj@pdx.edu)
**Instructor:** Prof. Christof Teuscher (teuscher@pdx.edu)
**Institution:** Portland State University

---

## Overview

This repository contains the end-to-end design, verification, synthesis, and characterization of a multi-precision hardware accelerator chiplet for the recurrent state-update kernel of an Echo State Network (ESN) reservoir. The chiplet implements 64 parallel multiply-accumulate (MAC) lanes with on-chip weight residency and is parameterized at three fixed-point precisions: Q15, INT8, and Q4.

At Q15 and a 125 MHz target clock, the design achieves a measured throughput of **106,929 updates/second** on the $N=1000$ ESN state-update kernel, corresponding to a **10.27× speedup** over a single-thread C+OpenBLAS baseline (10,415 updates/s) and **24.0× over Python+NumPy** (4,446 updates/s) on the same Intel i7-1165G7 host. Throughput is precision-independent across the three configurations, validating the memory-bound regime identified by the M1 roofline analysis: silicon area drops from 13.67 mm² (Q15) to 1.36 mm² (Q4) while measured throughput remains constant.

All numbers in this repository are measured: cocotb cosimulation cycle counts converted to wall-clock time using the synthesis target clock, Yosys sky130 cell counts, and SNR computed against an FP32 reference over 200 randomized samples.

---

## Milestones

| # | Path | Description |
|---|------|-------------|
| **M1** | [`project/m1/`](project/m1/) | Software baselines (Python+NumPy, C+OpenBLAS), cProfile and Intel VTune profiling, roofline analysis, AXI interface selection, system block diagram |
| **M2** | [`project/m2/`](project/m2/) | Parameterized compute-core RTL (mac_array, tanh_pwl, leak_blend, compute_core, interface_axi), cocotb verification, 200-sample quantization study |
| **M3** | [`project/m3/`](project/m3/) | Integrated top-level RTL, end-to-end AXI cosimulation (N=64, 64/64 bit-exact), Yosys sky130 synthesis, area + timing + first-order power |
| **M4** | [`project/m4/`](project/m4/) | K=64 parallel-MAC-lane fabric, multi-precision sweep (Q15/INT8/Q4), measured benchmark at N=1000, design justification report |

The final design justification report is at [`project/m4/design_justification.pdf`](project/m4/design_justification.pdf).

---

## Headline Results (M4)

| Implementation | Updates/sec | GFLOP/s | vs. C+OpenBLAS |
|---|---|---|---|
| Python+NumPy (i7-1165G7, 1 thread) | 4,446 | 8.93 | 0.43× |
| C+OpenBLAS (i7-1165G7, 1 thread) | 10,415 | 19.43 | 1.00× |
| Chiplet Q15 @ 100 MHz (conservative) | 85,543 | 171.86 | 8.21× |
| **Chiplet Q15 @ 125 MHz (target)** | **106,929** | **214.82** | **10.27×** |

---

## Tooling

| Tool | Purpose |
|---|---|
| SystemVerilog | RTL implementation |
| Icarus Verilog 12.0 + cocotb 2.0.1 | Simulation and verification |
| `yowasp-yosys` (WebAssembly) + sky130 PDK | Logic synthesis |
| Python 3.12 + NumPy + SciPy | Golden models, software baseline, analysis |
| OpenBLAS 0.3.33 + GCC 16.1 | C+OpenBLAS baseline |
| Intel VTune 2026.1 + cProfile | Hardware-counter and Python-level profiling |

All measurements were taken on an Intel i7-1165G7 (Tiger Lake) under Windows 11.

---

## Reproducibility

Each milestone's `README.md` documents the exact commands required to reproduce its results from a clean checkout. The M4 [`design_justification.pdf`](project/m4/design_justification.pdf) appendix provides a consolidated command list.

---

## Codefest Submissions

The [`codefest/`](codefest/) directory contains earlier course exercises. The most directly project-relevant is `codefest/cf02/` (April 2026), which produced the initial roofline analysis material that informed M1. Other codefests are standalone course exercises.

---

## License

Released under the MIT License, inheriting from the [minimalESN](https://mantas.info/code/simple_esn/) reference implementation (Lukoševičius) where applicable.
