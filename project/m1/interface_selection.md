# Interface Selection

## Project Title

Structured-Sparse Hardware Accelerator for Efficient Reservoir State Update in Streaming Inference

---

# Overview

This document selects the primary external interface for the proposed Echo State Network (ESN) accelerator and evaluates whether interface bandwidth limits performance at the target operating point.

The selected interface must support streaming data movement efficiently while remaining practical for FPGA prototyping and future ASIC-style integration.

---

# 1. Selected Interface

## Primary Interface: AXI4-Stream

AXI4-Stream is selected as the main data-path interface for the accelerator.

## Reason for Selection

The ESN accelerator processes sequential timestep data and naturally matches a streaming execution model. AXI4-Stream is appropriate because it provides:

- low-overhead continuous data transfer
- simple valid/ready handshake
- no address phase during streaming transfers
- compatibility with FPGA IP ecosystems
- scalable data widths
- straightforward connection to DMA or host logic

## Control Interface (Secondary)

Configuration registers such as start, mode, sparsity settings, and status can be handled separately through AXI4-Lite. However, the primary bandwidth analysis in this document focuses on AXI4-Stream.

---

# 2. Assumed Host Platform

The assumed deployment platform is an **FPGA SoC prototype environment**.

Example architecture:

- host processor or embedded CPU
- AXI interconnect
- AXI4-Lite control path
- AXI4-Stream data path
- custom ESN accelerator RTL block

This is consistent with common Xilinx / Intel FPGA development flows and practical course prototyping environments.

---

# 3. Target Operating Point

From the roofline model, the projected hardware accelerator target is:

- Throughput = **20 GFLOP/s**

Each ESN state update requires:

- **2,008,000 FLOPs per update**

Estimated update rate:

`20e9 / 2.008e6 = 9,960 updates/s`

Approximately:

**10,000 updates/s**

---

# 4. Required Interface Bandwidth

## Preferred Architecture: On-Chip State Memory

The reservoir state vector is stored locally inside accelerator SRAM / BRAM.

External traffic per update includes only:

- input sample `u(t)` = 8 bytes
- output scalar / reduced output = 8 bytes

Total transfer per update:

`16 bytes/update`

Required bandwidth:

`10,000 updates/s × 16 bytes/update`

`= 160,000 bytes/s`

`= 0.16 MB/s`

`= 0.00016 GB/s`

## Final Required Bandwidth

**0.00016 GB/s**

---

# 5. AXI4-Stream Rated Bandwidth

Assume a modest implementation:

- Data width = 32 bits = 4 bytes
- Clock frequency = 100 MHz

Rated bandwidth:

`4 bytes × 100e6 transfers/s`

`= 400,000,000 bytes/s`

`= 400 MB/s`

`= 0.40 GB/s`

## Final Rated Bandwidth

**0.40 GB/s**

---

# 6. Bottleneck Analysis

Compare:

- Required bandwidth = **0.00016 GB/s**
- Available bandwidth = **0.40 GB/s**

Utilization:

`0.00016 / 0.40 = 0.0004`

`= 0.04%`

Therefore, the selected AXI4-Stream interface provides far more bandwidth than required.

## Bottleneck Status

The proposed accelerator is **not interface-bound** at the target operating point.

The dominant limitations are expected to remain inside the compute kernel or memory hierarchy rather than the external stream interface.

---

# 7. Impact of Poorer Partitioning (Reference Case)

If the full 1000-element state vector were transferred externally every update:

- previous state = 8000 bytes
- updated state = 8000 bytes
- scalar input/output ≈ 16 bytes

Total:

`16,016 bytes/update`

Bandwidth at 10,000 updates/s:

`160,160,000 bytes/s`

`= 160.16 MB/s`

`= 0.16016 GB/s`

This would still fit within the 0.40 GB/s interface, but with much lower margin.

This further justifies keeping the reservoir state on-chip.

---

# 8. Final Decision

AXI4-Stream is selected as the primary interface because it matches the streaming ESN workload, provides sufficient bandwidth headroom, and integrates cleanly with FPGA-based accelerator systems.

The accelerator is **not interface-bound** under the proposed architecture.
