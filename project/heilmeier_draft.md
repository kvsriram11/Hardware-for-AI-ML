# Heilmeier draft

## Question 1: What are you trying to do?

I am trying to design a hardware accelerator for the main computation inside a reservoir computing model, specifically an Echo State Network used for time-series inference. The workload I will target is spoken digit classification, where an input audio signal is processed as a stream over time.

The part I want to accelerate is the reservoir state update that happens at every time step:
x(t) = f(W_res * x(t-1) + W_in * u(t))

Here, the current input and the previous state are multiplied by fixed weights and combined to produce the next state. I will implement this computation as a synthesizable chiplet in SystemVerilog and connect it to a host system using a standard hardware interface.

---

## Question 2: How is it done today, and what are the limits of current practice?

Today, this computation is usually done in software using CPUs or GPUs through libraries such as NumPy or PyTorch. For example, spoken digit classification using reservoir computing is typically implemented in Python and executed on a general-purpose processor.

This approach works well for development, but it has limitations for streaming workloads. The same matrix-vector computation must be repeated at every time step, and general-purpose processors are not optimized for this specific pattern. They spend extra time on instruction handling and moving data between memory and compute units.

In addition, dense reservoir matrices require a large number of multiply and add operations. This increases both compute cost and memory traffic. For real-time applications like audio processing, this can lead to higher latency and unnecessary energy use.

---

## Question 3: What is new in your approach and why do you think it will be successful?

My approach is to design a hardware accelerator that is specialized for the reservoir state update instead of relying on a general-purpose processor. I will focus only on the dominant kernel and implement it using parallel MAC units and on-chip state storage.

I will also explore using a structured or sparse reservoir instead of a fully dense one. This reduces the number of computations and memory accesses while still keeping the useful dynamics of the reservoir.

The design will be organized as a streaming chiplet with a standard interface, so data can flow in and out continuously. This makes the system more realistic and easier to analyze in terms of throughput and bandwidth.

I think this approach will be successful because reservoir computing uses fixed internal weights, which makes it well suited for hardware implementation. By reducing unnecessary operations and keeping data close to the compute units, the accelerator can achieve better efficiency than a software implementation for the same task.
