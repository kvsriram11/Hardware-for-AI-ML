# ESN Compute Core — HDL Module (COPT Part B)

## Module: `esn_core.sv`

Top-level compute core for the Echo State Network reservoir state update kernel:

```
x(t) = (1 − a)·x(t−1) + a·tanh(W_res·x(t−1) + W_in·u(t))
```

**Parameters**

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `DATA_W`  | 16      | Element bit-width (16 = INT16/Q15, 8 = INT8, 32 = FP32 stub) |
| `ACC_W`   | 32      | Accumulator width (always 32-bit) |
| `N`       | 1000    | Reservoir size |

**Pipeline stages (stubs, filled in M2)**

1. MAC accumulator — `W_res·x(t−1)` sparse dot product + `W_in·u(t)` injection  
2. Piecewise-linear tanh — saturation clip placeholder (`esn_tanh.sv` M2)  
3. Leak-rate blend — Q15 multiply-add placeholder (`esn_blend.sv` M2)

**Testbench:** `test_esn_core.py` (cocotb)  
Run: `make SIM=icarus`

---

## Interface Choice: AXI4-Stream + AXI4-Lite

The accelerator exposes an **AXI4-Stream** data path for streaming weight/state
vectors and an **AXI4-Lite** control bus for configuration registers (leak rate,
spectral radius, run/done flags).

**Bandwidth justification (from M1 roofline analysis):**  
The ESN reservoir update kernel has an arithmetic intensity of **0.25 FLOP/byte**,
placing it firmly in the memory-bound regime on both CPU and the target FPGA SoC.
The dominant data movement is the 1000-element state vector (8 KB at FP64,
2 KB at INT16) plus the sparse W_res matrix read once per update. At the target
throughput of 20 GFLOP/s the required memory bandwidth is only
`20 / 0.25 = 80 GB/s` — far beyond off-chip DDR — so the design keeps
**all state on-chip in SRAM** and streams only scalar inputs and outputs across
the SoC interconnect. The measured required interface bandwidth for a 1000-neuron
update is approximately **0.00016 GB/s** (one 16-bit scalar in, one 16-bit scalar
out per update cycle), which is easily handled by a single AXI4-Stream channel.
AXI4-Lite is chosen for control because the register set is small (<16 registers)
and infrequently accessed; full AXI4 burst capability is unnecessary for control.

## Precision Plan

| Variant        | `DATA_W` | Status        |
|----------------|----------|---------------|
| FP32           | 32       | M2 baseline   |
| **INT16/Q15**  | **16**   | **Primary**   |
| INT8           | 8        | Stretch goal  |
