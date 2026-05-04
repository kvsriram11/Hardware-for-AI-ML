# Milestone 2 — How to Reproduce

ECE 510 Spring 2026 — Sriram Kamarajugadda
Hardware Accelerator for ESN Reservoir State Update

This folder contains the M2 deliverables: synthesizable RTL for the compute core and the AXI interface, cocotb testbenches for both, simulation logs proving everything passes, a representative waveform, and the precision write-up.

## What's in here

```
project/m2/
├── rtl/
│   ├── q15_mac.sv          Q15 multiply-accumulate unit
│   ├── q15_tanh.sv         7-segment piecewise-linear tanh
│   ├── q15_blend.sv        leak-rate blend (1-a)*x_prev + a*tanh
│   ├── compute_core.sv     top-level FSM that runs one neuron's update
│   └── interface.sv        AXI4-Lite + AXI4-Stream wrapper around compute_core
├── tb/
│   ├── test_q15_mac.py
│   ├── test_q15_tanh.py
│   ├── test_q15_blend.py
│   ├── test_compute_core.py    M2-graded testbench for the compute core
│   ├── test_interface.py       M2-graded testbench for the AXI wrapper
│   ├── dump_waves.sv           waveform-dumping shim (sim only)
│   ├── Makefile                runs q15_mac (default)
│   ├── Makefile.q15_tanh
│   ├── Makefile.q15_blend
│   ├── Makefile.compute_core
│   └── Makefile.interface
├── sim/
│   ├── compute_core_run.log    full transcript, 3/3 PASS
│   ├── interface_run.log       full transcript, 2/2 PASS
│   └── waveform.png            GTKWave capture of compute_core
├── precision.md                Q15 rationale + tanh error analysis
└── README.md                   you are here
```

`compute_core.sv` and `interface.sv` are the two top-level modules the M2 grader scrapes for. The three sub-modules (`q15_mac`, `q15_tanh`, `q15_blend`) are instantiated inside `compute_core` and each have their own standalone testbench so I can verify them in isolation before integration.

## Tools and versions

Everything was developed and tested on Windows 11 in Git Bash:

- **Icarus Verilog 12.0** at `C:\iverilog\bin\iverilog.exe` — the simulator
- **Python 3.14.4** at `C:\Python314\python.exe`
- **cocotb 2.0.1** (system-wide install at `C:\Python314\Lib\site-packages\cocotb`)
- **cocotb-bus 0.3.0** — used for AXI4-Lite handshaking in `test_interface.py`
- **GTKWave 3.3.100** at `C:\ProgramData\chocolatey\bin\gtkwave.exe` — waveform viewer
- **GNU Make** via Chocolatey

Linux/macOS should work the same way, just with different paths. The only OS-specific piece is the install location of cocotb; everything else is Make + iverilog + Python.

## Setup from a clean clone

If you've never run this on this machine before:

```bash
# Clone (skip if you already have it)
git clone https://github.com/kvsriram11/Hardware-for-AI-ML.git
cd Hardware-for-AI-ML

# Verify Icarus and Python are on PATH
which iverilog        # expect /c/iverilog/bin/iverilog or similar
python --version      # expect Python 3.11+

# Install cocotb (system-wide preferred; --user is fine if you don't have admin)
pip install cocotb cocotb-bus

# Sanity-check the install
python -c "import cocotb, cocotb_bus, pygpi; print('cocotb OK')"
which cocotb-config
```

If `cocotb-config` isn't found by Git Bash, the install probably went to a user-only location and the corresponding `Scripts/` directory isn't on PATH. Easiest fix is to install with admin (`pip install cocotb cocotb-bus` from a Run-as-Administrator terminal) so it lands in the system Python directory which Git Bash sees by default.

## Running the testbenches

From `project/m2/tb/`:

```bash
# The two M2-graded testbenches:
make -f Makefile.compute_core      # 3/3 PASS, ~1 second
make -f Makefile.interface         # 2/2 PASS, ~1 second

# The three sub-module testbenches (built bottom-up during development):
make                               # q15_mac, 4/4 PASS
make -f Makefile.q15_tanh          # q15_tanh, 3/3 PASS
make -f Makefile.q15_blend         # q15_blend, 4/4 PASS
```

Each Makefile uses its own `SIM_BUILD` directory (e.g. `sim_build_compute_core/`, `sim_build_interface/`) so they don't collide with each other or with prior runs. To force a clean rebuild of one of them:

```bash
rm -rf sim_build_compute_core
make -f Makefile.compute_core
```

Re-running the simulations and capturing the logs:

```bash
make -f Makefile.compute_core 2>&1 | tee ../sim/compute_core_run.log
make -f Makefile.interface    2>&1 | tee ../sim/interface_run.log
```

## Regenerating the waveform

`Makefile.compute_core` includes the `dump_waves.sv` shim, which calls `$dumpfile` / `$dumpvars` so iverilog produces a VCD on every run. After running the compute_core testbench:

```bash
gtkwave compute_core_waves.vcd
```

In GTKWave, expand `compute_core` in the SST panel, drag the relevant signals (`clk`, `rst`, `start`, `state`, `w_data`, `x_data`, `mac_acc`, `pre_act`, `tanh_out`, `blend_out`, `x_new`, `x_new_valid`, `done`) into the waveform area, zoom to fit, and either `File → Print to File → PNG` or take a Windows screenshot. The current `sim/waveform.png` was captured this way.

## What you should see

`make -f Makefile.compute_core` ends with:

```
** test_compute_core.test_basic_update       PASS
** test_compute_core.test_two_back_to_back   PASS
** test_compute_core.test_realistic_n64      PASS
** TESTS=3 PASS=3 FAIL=0 SKIP=0
```

The `basic_N16_update` test reports `x_new = 3335`, which is `0.1018` in Q15 — matches the NumPy golden bit-exactly.

`make -f Makefile.interface` ends with:

```
** test_interface.test_axil_write_read_basic   PASS
** test_interface.test_full_neuron_via_axi     PASS
** TESTS=2 PASS=2 FAIL=0 SKIP=0
```

The `test_full_neuron_via_axi` test programs the core through AXI4-Lite, streams 16 operand pairs through AXI4-Stream, polls STATUS, and reads `X_NEW` back over AXI4-Lite. It returns the same `x_new = 3335` value as the direct compute-core test, which is the right consistency check — the interface is just plumbing, the answer should not change.

## A few iverilog warnings you'll see (and can ignore)

```
q15_blend.sv:114: sorry: constant selects in always_* processes are not currently supported
compute_core.sv:225/265: vvp.tgt sorry: Case unique/unique0 qualities are ignored
interface.sv:254/300: vvp.tgt sorry: Case unique/unique0 qualities are ignored
```

These are iverilog 12 limitations, not RTL bugs. Iverilog falls back to safe defaults (full-width selects; non-unique case behavior) and the simulations all pass against the NumPy golden, so the behavior is correct. Verilator and commercial simulators don't complain about these. Synthesis (M3, OpenLane) will use Yosys which honors `unique` and constant selects properly.

## Deviations from the M1 plan

Three things changed from what M1 said. All three are deliberate, with reasoning below.

**1. Hardware precision.** M1 listed FP32 as the M2 baseline with Q15 as a "research variant" coming later. I built Q15 in hardware directly and used `numpy.float32` in software as the golden reference for quantization error analysis. Why: the M1 roofline showed the kernel is memory-bound (0.25 FLOP/byte, ridge point 3.5), and FP32 hardware doesn't help with memory traffic — it makes it twice as bad. Halving operand width was the right move for a memory-bound design. Building an IEEE-754 FP32 datapath in 12 hours of M2 budget alongside the AXI interface and FSM was also not a defensible engineering trade-off. Full rationale and quantization error analysis in `precision.md`.

**2. Compute core scope.** M1 implied the compute core would handle the full 1000-neuron reservoir update internally. M2 is a single-neuron core: software calls it 1000 times to compute one timestep. Reason: M2 is graded on correctness against a golden reference, not throughput. A single-neuron core with a clean FSM is verifiable, defensible, and synthesizable; the multi-neuron iteration logic is a memory/control-plane concern that goes with full SRAM and address generation in M3. Per Prof. Teuscher's guidance, the architecture decisions get revisited end-to-end after M2 ships, so locking in single-neuron now leaves all options open for M3 redesign.

**3. AXI testbench library.** M2 originally tried to verify the AXI4-Lite interface with manual signal toggling. Two attempts hit subtle timing bugs that were hard to distinguish from RTL bugs. I switched to `cocotb-bus`'s `AXI4LiteMaster` driver, which exposed both a testbench bug (my reset was overwriting the driver's `BREADY=1` initialization) and a real RTL bug (`s_axis_tready` was tied to `core_busy` but the FSM only consumes data in `S_ACCUM`, so beats sent during `S_LOAD` were silently dropped). Both are fixed. Manual handshake remains in the older codefest tests; the M2 graded testbench uses `cocotb-bus`. AXI4-Stream still uses manual driving since `cocotb-bus 0.3.0` doesn't ship an AXIS master.

## What's coming after M2

M3 (May 24): OpenLane 2 synthesis flow on `compute_core.sv` + `interface.sv`, area/timing reports, end-to-end co-simulation against the Mackey-Glass software baseline. M4 (Jun 7): full design package, multi-precision sweep (Q15 vs Q7 and possibly INT4), benchmark comparison vs the M1 software baseline, and the design report.

The architecture-from-scratch revisit Prof. Teuscher mentioned will happen between M2 and M3, after I have synthesis numbers in hand to inform real decisions.
