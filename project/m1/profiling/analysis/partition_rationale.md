# Partition Rationale — HW/SW Split

## Hardware (chiplet) handles

- **State-update datapath**: 16-wide parallel MAC array, fixed-point (parameterized by DATA_W; 
Q15 reference plus INT8 and Q4 sweep). Inputs `Win @ [1,u]` and `W @ x` are accumulated then passed through 
a piecewise-linear tanh approximation and the leak blend `(1-a)x + a·z`.
- **On-chip W and Win storage**: SRAM holds the full reservoir matrix W (N=1000, 2 MB at Q15) 
and input projection Win (4 KB at Q15). Loaded once over AXI at startup; resident thereafter.
- **Reservoir state buffer**: ping-pong x[t-1] / x[t] in SRAM (4 KB at Q15) so reads and writes 
can overlap without false dependencies.
- **AXI4-Stream slave** for input scalars `u`; **AXI4-Stream master** for output state `x` (when read back); 
**AXI4-Lite slave** for control/status registers and weight loading mode.

## Software (host) handles

- **Spectral radius normalization** (`linalg.eig(W) * 1.25/rho`). Runs once at construction. 
O(N³). No benefit to acceleration since it is amortized over a deployment of 10⁵+ steps.
- **Ridge regression readout training** (`linalg.solve(X·Xᵀ + λI, X·Yᵀ)`). Runs once at training. O(N³).
- **Weight quantization and loading**: SW computes the FP32→Q15 (or INT8 / Q4) conversion of W and Win, 
then streams the quantized values to chiplet SRAM through the AXI4-Lite weight-load path.
- **Verification harness**: SW maintains a bit-exact fixed-point golden reference and compares 
chiplet output to it for cocotb regression.
- **Input scalar feed and output collection**: SW feeds `u` per step over AXI4-Stream and collects `x` 
when the readout layer needs to fire (typically 1× per timestep or 1× per N timesteps).

## Bound type

Memory-bound. Analytical AI = 0.50 FLOP/byte (no-reuse) ≪ ridge point 3.50 FLOP/byte. 
Measured CPU sustains 8.93 GFLOP/s, about 5% of the 179.2 GFLOP/s peak compute — 
confirming the bottleneck is data movement, not arithmetic units.

## Interface bandwidth requirement

Per state update, the chiplet exchanges with the host:

- 1 input scalar `u` in (4 bytes at FP32, 2 bytes at Q15)
- Optionally 1 reservoir state `x` out (N elements × DATA_W bits)

At target rate 1.5M updates/sec, Q15 precision, no x-readback:

- BW = 1.5e6 × 2 bytes/update = **3 MB/s** (input scalar only)

If x is read back every step at Q15:

- BW = 1.5e6 × (2 + 1000×2) bytes = **3 GB/s** (full x echo, worst case)

In practice the readout layer fires once per N steps, not every step, so realistic interface BW is **~30 MB/s**. 
Either way, AXI4-Stream over a standard host PCIe Gen3 x1 link (~1 GB/s) or AXI over a Zynq PS-PL bridge (~3-4 GB/s) 
provides ample margin. **The interface is not the bottleneck.**

## Why this partition is correct

All recurring work goes to HW; all O(1)-setup work stays in SW; the on-die SRAM eliminates the DRAM round-trip 
that bounded the CPU. The host only needs to feed scalars and occasionally collect state. This is the cleanest 
HW/SW boundary the kernel structure supports.
