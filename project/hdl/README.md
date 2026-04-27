# COPT Part B — Project Compute Core HDL

## Module: `esn_core.sv`

This module implements the top-level compute core for the Echo State Network (ESN)
reservoir state update kernel:

```
x(t) = (1 - a) * x(t-1) + a * tanh(W_res * x(t-1) + W_in * u(t))
```

The module includes parameterized data width, on-chip state storage, a
piecewise-linear tanh stub, a leak-rate blend stage, and a synchronous
active-high reset on all registers. It is not fully functional yet —
the tanh and blend stages are stubs to be completed in Milestone 2.

| Parameter | Default | Meaning                                      |
|-----------|---------|----------------------------------------------|
| `DATA_W`  | 16      | Element bit-width (16 = INT16/Q15 primary)   |
| `ACC_W`   | 32      | Accumulator width (fixed at 32-bit)          |
| `N`       | 1000    | Reservoir size (number of neurons)           |

---

## Interface Choice: AXI4-Stream + AXI4-Lite

The accelerator uses **AXI4-Stream** for the data path (streaming weights and
state vectors) and **AXI4-Lite** for the control path (configuration registers
such as leak rate and run/done flags).

AXI4-Lite was chosen for control because the register set is small (fewer than
16 registers) and accessed infrequently. AXI4-Stream was chosen for data because
it maps naturally to the sequential neuron-by-neuron update pattern of the
reservoir, with no need for random addressing.

**Bandwidth justification based on M1 arithmetic intensity:**
The M1 roofline analysis showed the ESN kernel has an arithmetic intensity of
0.25 FLOP/byte, placing it in the memory-bound regime. To avoid off-chip
bandwidth becoming the bottleneck, the entire 1000-element state vector is kept
in on-chip SRAM. Only one scalar input u(t) and one scalar output x_new cross
the interface per reservoir update. At INT16 precision this requires just
2 bytes in and 2 bytes out per update — a required interface bandwidth of
approximately 0.00016 GB/s, which is well within the capacity of a single
AXI4-Stream channel and poses no interface bottleneck risk.

---

## Precision Plan

| Variant       | `DATA_W` | Status              |
|---------------|----------|---------------------|
| FP32          | 32       | M2 functional baseline |
| **INT16/Q15** | **16**   | **Primary research variant** |
| INT8          | 8        | Stretch goal        |

INT16/Q15 was selected as the primary variant because it offers a practical
balance between numerical accuracy and hardware efficiency. The quantization
error analysis in CMAN (Codefest 4) confirms that 16-bit fixed-point
representation preserves sufficient precision for ESN reservoir dynamics,
while halving memory bandwidth and doubling MAC throughput compared to FP32.
