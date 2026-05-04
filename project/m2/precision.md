# Numerical Format and Precision

ECE 510 Spring 2026 — Sriram Kamarajugadda
Hardware Accelerator for ESN Reservoir State Update — M2

## What format I picked

Q15 fixed-point. 16-bit signed operands, 15 fractional bits, range `[-1, +1)`. Multiplications produce Q30 (15 + 15 = 30 fractional bits) which I keep in a 32-bit signed accumulator until I'm ready to scale back to Q15 by arithmetic right-shifting 15 bits. Rounding is just truncation toward negative infinity, which is what `>>>` on a signed value does in SystemVerilog without any extra logic.

A few values worth knowing:
- `+0.5` → `0x4000`
- `-1.0` → `0x8000`
- `+1.0` (saturated) → `0x7FFF`
- The project's leak rate `a = 0.3` → `0x2666` = 9830, which is actually 0.29999... in real terms (off by about 1.2e-5, fine).

`DATA_W = 16` and `ACC_W = 32` are parameters in every RTL module so the same code can be re-parameterized to Q7 or other widths later (M3/M4 plan).

## Why Q15 and not FP32

The big reason is the M1 roofline. The kernel sits at 0.25 FLOP/byte while my CPU's ridge point is 3.5 FLOP/byte, so it's memory-bound — data movement, not compute, is the bottleneck. Halving operand width from 32-bit (FP32) to 16-bit (Q15) cuts SRAM size and AXI traffic in half per neuron update. That's a real win for a memory-bound kernel.

Area is the other reason. A real IEEE-754 FP32 multiplier is something like 4–6× the gates of a Q15 integer multiplier before you even start handling denormals and rounding modes. None of that area is doing useful work when the kernel is memory-bound — it's just spending silicon on precision the workload doesn't care about.

I should be straightforward about a deviation from my M1 plan here: M1 said FP32 in M2 with Q15 as the "research variant." I flipped that. Hardware is Q15 directly, and FP32 lives in NumPy as the golden reference for measuring quantization error. Two reasons. First, an IEEE-754 FP32 datapath in 12 hours of M2 budget alongside the AXI interface and FSM was not a defensible trade-off. Second, reservoir-computing-on-chip papers compare quantized hardware against a software FP reference all the time — there's no requirement for FP32 to be in hardware to make a publishable comparison. This deviation is also called out in the M2 README.

## Why Q15 and not Q7 or Q31

Q7 (8-bit) is a real candidate for M3/M4. The Codefest 4 quantization study I did earlier (`codefest/cf04/cman_quantization.md`) showed INT8 symmetric quantization on a 4×4 weight matrix had MAE 0.0043 — small enough that the ESN should still work. The risk is accumulator overflow at N=1000: with Q7 operands and a 32-bit accumulator I'd have only ~17 bits of headroom, which is fine for typical reservoir activations (|x| < 0.5) but tight for adversarial inputs. Q15 with the same accumulator gives me 17 bits of margin even at full-scale, so it's the safer first cut.

Q31 (32-bit fixed-point) doesn't really make sense — same area pain as FP32 but worse precision than FP32, no advantage.

## How much error does Q15 introduce

The dominant error source is the piecewise-linear (PWL) tanh in `q15_tanh.sv`. It's a 7-segment approximation with breakpoints at ±0.5, ±1, ±2, slopes 1, 0.625, 0.25, 0 (the references trace back to Amin, Curtis & Hayes-Gill 1997). I picked dyadic slopes on purpose so the whole thing maps to shifts and adds — no multipliers needed inside tanh.

`test_q15_tanh.test_quantization_err` measures the PWL output against `math.tanh()` on 1000 evenly spaced samples in `[-3, +3]`:

- Mean Absolute Error: **0.026**
- Maximum Absolute Error: **0.073**

That's the actual hardware-faithful error including the bit-slicing inside the slope helpers, not just the ideal PWL math (which would be ~0.05). The worst point is around `|x| ≈ 0.75` where the slope-0.625 segment runs furthest from the true tanh curve. Errors near zero (identity region) and saturation regions (`|x| ≥ 2`) are below 0.005.

The other error source is truncation in the leak blend (`q15_blend.sv`) — the right-shift-by-15 throws away about 3e-5 per blend operation. That's two orders of magnitude smaller than the tanh error and gets buried by it in the end-to-end output.

For the full single-neuron update, error is bounded by tanh PWL plus a tiny accumulation term from N=1000 truncation events (`O(N × 2^-30) ≈ 10^-6`, negligible).

## Is that error acceptable

For ESNs, yes. Reservoirs aren't sensitive to small activation distortion the way feedforward classifiers are — the dynamics are dominated by recurrent coupling and spectral-radius scaling, not by the exact tanh values. Published reservoir-computing-on-chip work (Penkovsky 2018, Soures and Kudithipudi 2019) uses PWL or LUT tanh approximations with similar or larger maximum errors and reports negligible task accuracy degradation on chaotic time-series benchmarks, including the same Mackey-Glass sequence I'm using as the M1 software baseline (which got MSE 1.026e-6 against ground truth).

I picked the 0.075 threshold for the testbench because it's the actual measured hardware error rounded up — strictly tighter than what the published references tolerate. M3 will run end-to-end Mackey-Glass through the synthesized core in co-simulation and compare MSE directly to the M1 software baseline. If that MSE blows up by more than ~10× I'll need to revisit the tanh approximation, but I don't expect it to.

## Forward plan

Per Prof. Teuscher's guidance, multi-precision exploration is the M3/M4 research direction. The same compute core gets re-parameterized at `DATA_W = 8` (Q7) and probably one other point, and I measure how lower precision affects area, power, throughput, and end-to-end ESN MSE. The Q15 numbers from this milestone are the baseline that the alternative precisions get compared against.
