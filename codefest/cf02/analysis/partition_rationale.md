# HW/SW Partition Proposal

## Project Title

Structured-Sparse Hardware Accelerator for Efficient Reservoir State Update in Streaming Inference

---

# Overview

This document proposes a hardware/software partition for the Echo State Network (ESN) accelerator based on the measured software baseline, arithmetic-intensity analysis, and roofline model.

The goal is to accelerate the dominant recurring workload while preserving software flexibility for setup, training, and system control.

---

# 1. Kernel(s) Selected for Hardware Acceleration

The selected hardware target is the **reservoir state-update kernel**, executed every timestep during state collection and generative inference:

`x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))`

The dominant portion of this kernel is the recurrent matrix-vector multiply:

`Wres * x(t-1)`

This operation is the best hardware candidate because it is:

- repeatedly executed thousands of times
- arithmetic intensive relative to control code
- highly parallel across neurons
- regular and streamable in hardware
- suitable for pipelined multiply-accumulate datapaths
- compatible with structured sparse storage formats

## Roofline Justification

The software kernel has:

- Arithmetic intensity = **0.25 FLOP/byte**
- Measured performance = **4.04 GFLOP/s**

On the Intel i7-1165G7 roofline model:

- Peak compute = **179.2 GFLOP/s**
- Peak memory bandwidth = **51.2 GB/s**
- Ridge point = **3.50 FLOP/byte**

Since:

`0.25 < 3.50`

the current software implementation is **memory-bound**. This means performance is limited more by data movement than by available compute throughput.

Therefore, accelerating the state-update kernel in hardware is justified because custom logic can reduce memory traffic and improve data reuse.

---

# 2. Functions Remaining in Software

The following tasks remain in software:

- ridge regression training of output weights
- parameter loading and model initialization
- host-side control and runtime configuration
- dataset input/output
- profiling, logging, and debugging
- performance monitoring
- optional post-processing / visualization

## Rationale

These tasks are either infrequent, irregular, or easier to modify in software. Keeping them in software reduces hardware complexity and preserves programmability.

---

# 3. Effect of Hardware Design on Bound Type

## Current Software Baseline

The dense software kernel is memory-bound because the recurrent matrix must be repeatedly fetched from memory.

## Proposed Hardware Design

The accelerator changes this behavior through:

- structured sparse weights to reduce nonzero MAC operations
- compressed storage to reduce bytes transferred
- on-chip SRAM / BRAM state buffering
- pipelined parallel MAC units
- local tanh approximation unit
- reuse of state vectors without repeated DRAM fetches

These changes increase effective arithmetic intensity and move the design closer to the roofline limit. The hardware kernel is expected to become **less memory-bound** and more balanced between memory and compute resources.

---

# 4. Interface Bandwidth Requirement

## Target Accelerator Throughput

Assume target hardware throughput:

`20 GFLOP/s`

Each ESN state update requires:

`2,008,000 FLOPs`

Estimated updates per second:

`20e9 / 2.008e6 ≈ 9,960 updates/s`

Approximately:

`10,000 updates/s`

---

## Preferred Architecture: On-Chip State Memory

The reservoir state vector remains inside accelerator memory.

External interface transfers only:

- input sample `u(t)`
- control/configuration registers
- optional output sample or reduced output vector

Assume FP64 input and output scalars:

- input = 8 bytes
- output = 8 bytes

Bandwidth required:

`16 bytes/update × 10,000 updates/s`

`= 160,000 bytes/s`

`= 0.16 MB/s`

`= 0.00016 GB/s`

---

## Interface Comparison

Chosen interface:

- AXI4-Stream for data path
- AXI4-Lite for control registers

Even a modest 32-bit AXI4-Stream interface at 100 MHz supports:

`4 bytes × 100e6 = 400 MB/s`

`= 0.40 GB/s`

This is far greater than the required `0.00016 GB/s`.

Therefore, the proposed accelerator is **not interface-bound** under the on-chip state-storage architecture.

---

# 5. Final Partition Summary

## Hardware

- sparse recurrent matrix-vector engine
- input projection unit
- tanh approximation block
- leak-rate update datapath
- on-chip state memory
- AXI-stream input/output wrapper
- AXI-lite control interface

## Software

- training flow
- initialization
- weight loading
- runtime control
- data management
- verification and monitoring

This partition accelerates the dominant recurring ESN workload while keeping infrequent and flexible tasks in software. It is consistent with the roofline analysis and provides a practical path toward synthesizable SystemVerilog implementation.
