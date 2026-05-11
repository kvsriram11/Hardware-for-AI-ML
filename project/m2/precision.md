# Numerical Format and Precision

ECE 510 Spring 2026  
Sriram Kamarajugadda  
Hardware Accelerator for ESN Reservoir State Update  
M2

## What format I picked

I used Q15 fixed-point format.

That means the operands are 16-bit signed values with 15 fractional bits. The range is `[-1, +1)`. When two Q15 numbers are multiplied, the result becomes Q30 because the fractional bits add up: 15 + 15 = 30. I keep this result in a 32-bit signed accumulator and then scale it back to Q15 by doing an arithmetic right shift by 15 bits.

For rounding, I am using simple truncation. In SystemVerilog, this is done using `>>>` on a signed value. I did not add extra rounding logic because the goal here is to keep the hardware simple.

A few useful Q15 values are:

- `+0.5` is `0x4000`
- `-1.0` is `0x8000`
- `+1.0` saturated is `0x7FFF`
- The leak rate `a = 0.3` is represented as `0x2666`, which is 9830 in decimal

The Q15 version of 0.3 is not exactly 0.3. It is about 0.29999, so the error is around `1.2e-5`. That is small enough for this design.

I kept `DATA_W = 16` and `ACC_W = 32` as parameters in the RTL modules. This makes it easier to reuse the same code later for Q7 or other fixed-point formats in M3 or M4.

## Why I used Q15 instead of FP32

The main reason comes from the M1 roofline analysis.

The reservoir update kernel has an arithmetic intensity of about `0.25 FLOP/byte`, while my CPU ridge point is around `3.5 FLOP/byte`. This means the kernel is memory-bound. In simple words, the bottleneck is not the computation itself, but the amount of data being moved.

Using Q15 helps here because it cuts the operand size from 32 bits to 16 bits. Compared to FP32, this reduces SRAM usage and AXI data movement by half for each neuron update. Since the kernel is memory-bound, reducing data movement is a useful improvement.

Area is another reason. A full IEEE-754 FP32 multiplier is much larger than a Q15 integer multiplier. It also needs extra logic for things like rounding modes and special cases. For this workload, that extra hardware does not give enough benefit because the main bottleneck is still memory movement.

I should also mention one change from my M1 plan. In M1, I had planned to use FP32 in M2 and treat Q15 as a research variant. I changed that plan. In this milestone, the hardware is directly built using Q15, while FP32 is used in NumPy as the golden reference for checking quantization error.

There are two reasons for this change.

First, building a full IEEE-754 FP32 datapath within the M2 time budget, while also working on the AXI interface and FSM, was not a good trade-off. Second, many reservoir-computing hardware papers compare quantized hardware against a software floating-point reference. So FP32 does not need to be implemented in hardware to make the comparison meaningful.

This change is also mentioned in the M2 README.

## Why I did not use Q7 or Q31

Q7 is a good candidate for M3 or M4.

In my earlier Codefest 4 quantization study, INT8 symmetric quantization on a 4 by 4 weight matrix gave a mean absolute error of `0.0043`. That is small enough that the ESN should still work in many cases.

The main risk with Q7 is accumulator overflow when the reservoir size is `N = 1000`. With Q7 operands and a 32-bit accumulator, there is only about 17 bits of headroom. That is probably fine for normal reservoir activations where `|x| < 0.5`, but it is tighter for worst-case inputs.

Q15 is safer for the first hardware version because it gives better precision while still keeping the design much smaller than FP32.

Q31 does not make much sense for this project. It uses 32-bit fixed-point values, so it brings back most of the area and memory cost of FP32, but without the flexibility of floating-point representation.

## How much error Q15 introduces

The main error comes from the piecewise-linear tanh approximation in `q15_tanh.sv`.

The tanh block uses 7 segments with breakpoints at `±0.5`, `±1`, and `±2`. The slopes are:

- `1`
- `0.625`
- `0.25`
- `0`

I chose these slopes because they are easy to implement in hardware using shifts and additions. This avoids using multipliers inside the tanh block.

The test `test_q15_tanh.test_quantization_err` compares the hardware-style PWL tanh output against `math.tanh()` using 1000 evenly spaced samples from `[-3, +3]`.

The measured errors are:

- Mean Absolute Error: `0.026`
- Maximum Absolute Error: `0.073`

This is the actual hardware-faithful error. It includes the bit slicing and shift-based logic used inside the slope helpers. It is not just the ideal mathematical PWL error.

The worst error happens around `|x| ≈ 0.75`, where the slope `0.625` segment differs the most from the real tanh curve. Near zero, the identity segment works well. In the saturation region where `|x| ≥ 2`, the error is also very small, usually below `0.005`.

The leak blend block, `q15_blend.sv`, adds a much smaller error. The right shift by 15 bits causes a small truncation error of about `3e-5` per blend operation. This is much smaller than the tanh approximation error, so it is not the dominant source of error.

For a full single-neuron update, the error is mainly from the tanh approximation. The accumulation truncation term across `N = 1000` operations is around `O(N × 2^-30)`, which is about `10^-6`. That is negligible compared to the tanh error.

## Is the error acceptable?

For an ESN, I think this error is acceptable.

Reservoirs are usually not extremely sensitive to small activation approximation errors. The overall behavior is mostly controlled by the recurrent connections, spectral-radius scaling, and leak dynamics. The tanh value does matter, but it does not need to be perfect for the reservoir to work.

Published reservoir-computing hardware work has also used PWL or LUT-based tanh approximations with similar or larger errors, while still showing good results on time-series tasks such as Mackey-Glass.

I used `0.075` as the testbench threshold because the measured maximum hardware error was about `0.073`. So the threshold is slightly above the measured value, but still tight enough to catch unexpected errors.

In M3, I plan to run the full Mackey-Glass sequence through the synthesized core using co-simulation and compare the final MSE against the M1 software baseline. If the MSE increases by more than about 10 times, then I will revisit the tanh approximation. For now, based on the measured error, I do not expect that to happen.

## Forward plan

Following Prof. Teuscher's advise, the next step is multi-precision exploration in M3 or M4.

The same compute core can be re-parameterized to `DATA_W = 8` for Q7. I may also test one more precision point. Then I can compare how precision affects:

- area
- power
- throughput
- end-to-end ESN MSE

The Q15 design from this milestone will act as the baseline for comparing the lower-precision versions.
