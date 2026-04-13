# Heilmeier Questions

## Q1. What are you trying to do?

I am designing a custom co-processor chiplet to accelerate the dominant recurring kernel of an Echo State Network (ESN), using the `minimalESN` Python implementation as the software baseline. The target algorithm is reservoir computing for streaming inference. The specific kernel I am accelerating is the **reservoir state-update computation**:

`x(t) = (1-a)x(t-1) + a * tanh(Wres*x(t-1) + Win*u(t))`

Within this update, the main hardware target is the recurrent matrix-vector multiply `Wres*x(t-1)` together with the surrounding accumulation, tanh, and leak update logic. The proposed chiplet is not intended to replace the full software pipeline. Software will continue to handle setup, reservoir initialization, spectral-radius normalization, readout training, configuration, and orchestration. The chiplet will accelerate the repeated streaming state-update path, which is the part of the ESN computation most suitable for custom hardware.

The planned implementation is a synthesizable SystemVerilog design with on-chip memory for state and weight buffering, a standard hardware interface to the host, and a structured-sparse compute engine intended to reduce memory traffic and improve sustained throughput.

---

## Q2. What is done today, and what are the limits of current practice?

Today, the ESN baseline runs entirely in software on my host CPU using Python, NumPy, and SciPy. The current implementation was benchmarked over 10 runs and achieved a median wall-clock runtime of **7.86 s** for the full baseline execution, with an MSE of approximately **1.026e-06**. This establishes the current software-only reference point.

Profiling shows that the main recurring cost is the ESN reservoir state-update path rather than setup or plotting. In the cleaned profile, the two recurring phases were:

- `collect_states()` = **1.228 s**
- `run_generative()` = **0.762 s**

Together, these phases account for **1.990 s** of the **7.144 s** profiled runtime, which is about **27.9%** of total runtime at the Python-visible level. The largest raw single function in the profile was spectral-radius normalization using `scipy.linalg.eig()`, but that is a one-time initialization step and not the repeated streaming inference workload I want to accelerate.

The arithmetic-intensity analysis of one reservoir state update gave **2,008,000 FLOPs**, **8,032,016 bytes**, and an arithmetic intensity of **0.25 FLOP/byte**. On the roofline for my i7-1165G7 host system, this places the kernel in the **memory-bound** region. The measured software kernel performance is about **4.04 GFLOP/s**, which is far below the host’s theoretical compute ceiling. This shows that current practice is limited not simply because “software is slow,” but because the dense reservoir update moves a large amount of data relative to the useful computation performed. The main limitation of the current software approach is therefore poor efficiency on the repeated reservoir state-update kernel, which is exactly the part targeted for chiplet acceleration.

---

## Q3. What is your approach, and why is it better?

My approach is to move the recurring ESN reservoir state-update kernel into a dedicated co-processor chiplet, while keeping the rest of the algorithm in software. The chiplet will implement a structured-sparse state-update engine in SystemVerilog with a standard host interface, local state/weight storage, and a compute datapath specialized for the ESN update.

The reason this is better is grounded in the roofline and arithmetic-intensity analysis. The current dense software kernel has an arithmetic intensity of only **0.25 FLOP/byte**, so it is strongly memory-bound on my host platform. That means simply relying on general-purpose software execution will not use the available compute resources efficiently. The key improvement is therefore not just “more MACs,” but **less data movement per useful operation**.

The chiplet design improves this in three ways:

- **structured sparsity** reduces the number of active weights and therefore reduces bytes transferred and MAC operations
- **on-chip memory** allows reuse of state and weight data locally instead of repeatedly fetching large vectors and matrices through the external memory hierarchy
- **specialized datapath** performs the matrix-vector multiply, accumulation, tanh approximation, and leak update with a hardware pipeline tailored to the kernel

This approach is better because it targets the actual bottleneck identified in profiling and roofline analysis rather than accelerating unrelated or one-time setup work. It also fits the project goal of a realistic co-processor chiplet connected through a standard interface, rather than an abstract standalone accelerator disconnected from the software system.
