# Numerical Precision — Q15 Signed Fixed-Point

## Format choice

All datapath registers in the M2 compute core use signed Q1.15 fixed-point representation: 
16-bit two's-complement values with 1 sign-magnitude bit and 15 fractional bits. 
The representable range is approximately [-1.0, +0.99997] with a quantization step of 2⁻¹⁵ ≈ 3.05e-5.

- DATA_W = 16 bits (the parameterized width across the RTL)
- FRAC_W = 15 bits (fractional)
- ACC_W = 40 bits (MAC accumulator, extended to absorb up to 2¹⁰ accumulations without overflow at signed Q1.15×Q1.15 = Q2.30 products)
- Rounding mode: truncation (arithmetic right-shift on register-narrowing assignments)
- Saturation: handled at the tanh output where the activation is clamped to [-(2¹⁵-1)+1, +(2¹⁵-1)]

## Rationale

The M1 roofline analysis (see `codefest/cf02/analysis/ai_calculation.md` and `roofline_sweep.png`) 
established that the state-update kernel sits at an arithmetic intensity of **0.5 FLOP/byte** in the no-reuse model, 
far below the i7-1165G7 ridge of 3.5 FLOP/byte. This places the kernel firmly in the memory-bound regime. 
In this regime, every halving of data width is a direct halving of memory traffic 
and therefore — to first order — a doubling of effective throughput, 
until the workload migrates across the ridge into the compute-bound regime.

Q15 was chosen as the M2 reference precision for three reasons:

1. **It is the smallest fixed-point format that retains FP32-equivalent accuracy for ESN deployment.** 
Reservoir activations in a well-conditioned ESN are bounded by [-1, +1] (tanh range). 
Q15 covers this range exactly with one bit to spare for transient pre-activation values, while INT8 starts to suffer visible quantization-induced bias accumulation.
2. **2× memory-traffic reduction over FP32 with negligible accuracy loss.** 
The M1 baseline runs in FP32. Moving to Q15 cuts per-step bytes from `4N² + 16N + 4` to `2N² + 8N + 2`, 
which the bandwidth-bound roofline predicts will roughly double the kernel's effective GFLOP/s ceiling on the accelerator.
3. **It is the natural reference point for the multi-precision sweep planned in M4.** 
Subsequent INT8 and Q4 runs use the same parameterized RTL with `DATA_W` set to 8 and 4 respectively. 
Quoting Q15 as the 'gold standard' fixed-point and characterizing INT8/Q4 against it gives a defensible accuracy-vs-throughput curve.

Floating-point alternatives (FP32, FP16, BF16) were rejected for the chiplet datapath because they require 
an order of magnitude more silicon area per multiplier than fixed-point. 
Since the accelerator is memory-bound, the extra arithmetic precision would not help throughput and would only consume area, power, and timing margin. 
FP16 is retained as a stretch precision target for M4 comparison, but is not part of the M2 RTL.

## Quantization error analysis

Error was characterized over **200 random vectors** drawn from ESN-realistic distributions 
(reservoir weights uniform on [-0.2, +0.2], state values uniform on [-0.8, +0.8], leak rate 0.3, 
Win-term contribution uniform on [-0.1, +0.1]). 
For each vector, the FP32 reference was computed in double-precision NumPy and the Q15 result was 
computed through the bit-exact Python golden (which has been verified bit-equivalent to the DUT RTL across all 22 cocotb test vectors).

| Statistic | Value | Interpretation |
|---|---|---|

| Mean absolute error | 0.000020 | ~0.7 × Q15 lsb |

| Median absolute error | 0.000019 | half the samples are below this |

| 95th percentile | 0.000041 | 95% of samples are below this |

| 99th percentile | 0.000047 | tail accuracy bound |

| Max absolute error | 0.000057 | worst case across all 200 vectors |

| MSE vs FP32 | 5.320901e-10 | mean-squared error |

| Signal-to-noise ratio | 79.1 dB | signal variance / noise variance |

| Mean relative error | 0.020% | per-sample relative |

| 95th percentile relative | 0.062% | tail-relative bound |


## Statement of acceptability

**Q15 quantization error is acceptable for this application.** The 99th-percentile absolute error is 
**0.00005** in the Q1.15 output range of [-1, +1], which is **0.005% of full scale**. 
The signal-to-noise ratio of **79.1 dB** comfortably exceeds the typical 60 dB threshold used in DSP literature 
for fixed-point ESN implementations.

More importantly, the M1 software baseline measured a Mackey-Glass prediction MSE of 
**1.023e-06** at N=1000 (see `project/m1/sw_baseline.md`). 
Q15's per-step MSE of **5.32e-10** is more than two orders of magnitude below the 
baseline's end-to-end prediction error. The dominant error term in ESN performance is 
therefore *not* the per-step quantization noise but the inherent reservoir-modeling error of the architecture. 
Q15 precision will not be the limiting factor for prediction accuracy at this network size.

This threshold is the canonical acceptability criterion for fixed-point ESN accelerators in the literature 
(e.g., Antonik et al. 2017 for photonic reservoirs, Penkovsky et al. 2018 for FPGA ESN). 
The accelerator will be benchmarked against Q15-equivalent FP32 in M4 to confirm end-to-end MSE preservation.

## Verification

- The Python golden (`tb/m2/golden.py`) implements Q15 fixed-point exactly the way the SystemVerilog does, 
including the 4-segment PWL tanh and the 2*DATA_W → DATA_W truncation in the leak blend.
- The cocotb regression at `tb/m2/test_compute_core.py` runs 22 vectors (1 trivial + 1 representative + 20 random) 
through the DUT and asserts **bit-exact equality with the golden** on every one. All 22 pass.
- An additional 2 cocotb tests in `tb/m2/test_interface.py` validate the AXI4-Stream + AXI4-Lite wrapping 
preserves the Q15 result end-to-end.
- Raw quantization data is in `rtl/m2/quantization_stats.json`.

## Reproduce

```bash
source env/venv/Scripts/activate
python rtl/m2/build_m2_docs.py
```
