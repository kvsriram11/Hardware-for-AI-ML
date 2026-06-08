# Interface Selection — Host ↔ Chiplet

## Host platform

Reference host: Intel i7-1165G7 (Tiger Lake) Win11 laptop for baseline measurement. 
FPGA emulation target: Digilent Zybo Z7 (Zynq-7010, ARM Cortex-A9 + Artix-7 fabric) — 
the chiplet is wrapped as an AXI peripheral on the PS-PL bridge for hardware bring-up.

## Interface chosen: AXI4-Stream (data) + AXI4-Lite (control)

- **AXI4-Stream slave**: streams input scalar `u` per timestep
- **AXI4-Stream master**: streams reservoir state `x` back when requested (typically once per N steps)
- **AXI4-Lite slave**: control register file (start, status, mode), weight-load doorbell, reset

## Bandwidth check

Per state update (Q15 precision, N=1000, target 1.5M updates/sec):

- Input `u` stream: 2 bytes/update × 1.5e6 = 3 MB/s
- Output `x` stream (every step, worst case): 2002 bytes × 1.5e6 = 3 GB/s
- Realistic mixed case (x read once per N steps): ~30 MB/s

Available on Zynq PS-PL bridge: AXI4 at 100-150 MHz × 32 bits = 400-600 MB/s per channel. 
Available on PCIe Gen3 x1 (chiplet bring-up to laptop via FT2232H-style bridge): ~1 GB/s. 
**Both have 10-100× margin over realistic load.**

## Alternatives considered

**(1) AXI4-Full memory-mapped**: rejected. Address generation is overkill for a streaming kernel where 
every transaction is a single scalar. Would add register-file complexity for no throughput benefit.

**(2) APB**: rejected. Single-cycle handshake protocol; throughput tops out around 100 MB/s per Hz of clock. 
Adequate for control registers but cannot sustain the data stream. AXI4-Lite gives APB-like simplicity at higher rates.

**(3) AXI4-Stream only (no AXI4-Lite)**: rejected. Weight loading and run-control need addressable, 
non-streaming reads/writes. Stream-only forces in-band protocol parsing which complicates host driver.

**(4) Custom serial protocol (SPI / UART)**: rejected. Achievable rates are 1-100 Mbps; 
the 3 MB/s minimum is borderline at SPI but UART is 100× too slow. 
More importantly, AXI is the standard for IP-block reuse on Zynq and ASIC SoCs; 
a non-AXI interface forecloses standard-flow integration.

**(5) AXI4-Stream + AXI4-Lite (chosen)**: stream protocol for hot path, lite protocol for control, 
standard Zynq IP integration, ~10× BW margin at all expected loads.
