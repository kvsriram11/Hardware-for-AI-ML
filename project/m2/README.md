# Milestone 2: How to Reproduce

ECE 510 Spring 2026  
Sriram Kamarajugadda  
Hardware Accelerator for ESN Reservoir State Update

This folder contains the M2 deliverables. It includes synthesizable RTL for the compute core and AXI interface, cocotb testbenches, simulation logs showing that the tests pass, a representative waveform, and the precision write-up.

## What's in here

```text
project/m2/
├── rtl/
│   ├── q15_mac.sv          Q15 multiply-accumulate unit
│   ├── q15_tanh.sv         7-segment piecewise-linear tanh
│   ├── q15_blend.sv        leak-rate blend: (1-a)*x_prev + a*tanh
│   ├── compute_core.sv     top-level FSM for one neuron update
│   └── interface.sv        AXI4-Lite + AXI4-Stream wrapper around compute_core
├── tb/
│   ├── test_q15_mac.py
│   ├── test_q15_tanh.py
│   ├── test_q15_blend.py
│   ├── test_compute_core.py    M2-graded testbench for the compute core
│   ├── test_interface.py       M2-graded testbench for the AXI wrapper
│   ├── dump_waves.sv           waveform dumping shim for simulation
│   ├── Makefile                runs q15_mac by default
│   ├── Makefile.q15_tanh
│   ├── Makefile.q15_blend
│   ├── Makefile.compute_core
│   └── Makefile.interface
├── sim/
│   ├── compute_core_run.log    full transcript, 3/3 PASS
│   ├── interface_run.log       full transcript, 2/2 PASS
│   └── waveform.png            GTKWave capture of compute_core
├── precision.md                Q15 rationale and tanh error analysis
└── README.md                   this file
```

`compute_core.sv` and `interface.sv` are the two top-level modules needed for M2 grading. The three smaller modules, `q15_mac`, `q15_tanh`, and `q15_blend`, are instantiated inside `compute_core`.

Each smaller module also has its own standalone testbench. I used this bottom-up approach so I could verify each block separately before testing the full compute core.

## Tools and versions

Everything was developed and tested on Windows 11 using Git Bash.

- **Icarus Verilog 12.0** at `C:\iverilog\bin\iverilog.exe`
- **Python 3.14.4** at `C:\Python314\python.exe`
- **cocotb 2.0.1** installed at `C:\Python314\Lib\site-packages\cocotb`
- **cocotb-bus 0.3.0**, used for AXI4-Lite handshaking in `test_interface.py`
- **GTKWave 3.3.100** at `C:\ProgramData\chocolatey\bin\gtkwave.exe`
- **GNU Make** through Chocolatey

Linux and macOS should work in the same general way, but the paths will be different. The only system-specific part is the cocotb install location. The rest is just Make, Icarus Verilog, and Python.

## Setup from a clean clone

Run these steps if this is the first time running the project on the machine.

```bash
# Clone the repository. Skip this if it is already cloned.
git clone https://github.com/kvsriram11/Hardware-for-AI-ML.git
cd Hardware-for-AI-ML

# Check that Icarus Verilog and Python are on PATH.
which iverilog
python --version

# Install cocotb.
pip install cocotb cocotb-bus

# Sanity check the install.
python -c "import cocotb, cocotb_bus, pygpi; print('cocotb OK')"
which cocotb-config
```

Expected results:

```text
which iverilog       should show something like /c/iverilog/bin/iverilog
python --version     should show Python 3.11 or newer
```

If `cocotb-config` is not found in Git Bash, cocotb was probably installed in a user-only Python location and the related `Scripts/` directory is not on PATH.

The easiest fix is to install cocotb from an Administrator terminal:

```bash
pip install cocotb cocotb-bus
```

That usually places it in the system Python directory, which Git Bash can find more easily.

## Running the testbenches

From this directory:

```bash
cd project/m2/tb
```

Run the two M2-graded testbenches:

```bash
make -f Makefile.compute_core
make -f Makefile.interface
```

Expected results:

```text
compute_core: 3/3 PASS
interface:    2/2 PASS
```

Run the smaller module testbenches:

```bash
make
make -f Makefile.q15_tanh
make -f Makefile.q15_blend
```

Expected results:

```text
q15_mac:   4/4 PASS
q15_tanh:  3/3 PASS
q15_blend: 4/4 PASS
```

Each Makefile uses a separate simulation build directory. This prevents the testbenches from interfering with each other.

To force a clean rebuild:

```bash
rm -rf sim_build_compute_core
make -f Makefile.compute_core
```

To rerun the simulations and save the logs:

```bash
make -f Makefile.compute_core 2>&1 | tee ../sim/compute_core_run.log
make -f Makefile.interface    2>&1 | tee ../sim/interface_run.log
```

## Regenerating the waveform

`Makefile.compute_core` includes `dump_waves.sv`. This shim calls `$dumpfile` and `$dumpvars`, so Icarus Verilog generates a VCD file every time the compute core testbench runs.

After running the compute core testbench, open the waveform using:

```bash
gtkwave compute_core_waves.vcd
```

In GTKWave, expand `compute_core` in the SST panel and drag these signals into the waveform window:

```text
clk
rst
start
state
w_data
x_data
mac_acc
pre_act
tanh_out
blend_out
x_new
x_new_valid
done
```

Then zoom to fit and save the image using `File > Print to File > PNG`. The current `sim/waveform.png` was captured this way.

## What you should see

The compute core test should end with:

```text
** test_compute_core.test_basic_update       PASS
** test_compute_core.test_two_back_to_back   PASS
** test_compute_core.test_realistic_n64      PASS
** TESTS=3 PASS=3 FAIL=0 SKIP=0
```

The `basic_N16_update` test reports:

```text
x_new = 3335
```

This is `0.1018` in Q15 and matches the NumPy golden result bit-exactly.

The interface test should end with:

```text
** test_interface.test_axil_write_read_basic   PASS
** test_interface.test_full_neuron_via_axi     PASS
** TESTS=2 PASS=2 FAIL=0 SKIP=0
```

The `test_full_neuron_via_axi` test programs the core through AXI4-Lite, streams 16 operand pairs through AXI4-Stream, polls `STATUS`, and reads `X_NEW` back through AXI4-Lite.

It returns the same value:

```text
x_new = 3335
```

This is the correct consistency check. The interface is only moving data in and out. It should not change the compute result.

## A few Icarus Verilog warnings you may see

```text
q15_blend.sv:114: sorry: constant selects in always_* processes are not currently supported
compute_core.sv:225/265: vvp.tgt sorry: Case unique/unique0 qualities are ignored
interface.sv:254/300: vvp.tgt sorry: Case unique/unique0 qualities are ignored
```

These are Icarus Verilog 12 limitations, not RTL bugs.

Icarus falls back to safe behavior, and the simulations still pass against the NumPy golden reference. Verilator and commercial simulators should not complain about these in the same way.

For M3 synthesis, OpenLane will use Yosys, which handles these constructs properly.

## Deviations from the M1 plan

Three things changed from the M1 plan. These were deliberate changes.

### 1. Hardware precision

M1 listed FP32 as the M2 baseline and Q15 as a later research variant. I changed this and built the hardware directly in Q15. The software reference still uses `numpy.float32` as the golden model for checking quantization error.

The reason is based on the M1 roofline analysis. The kernel is memory-bound, with arithmetic intensity around `0.25 FLOP/byte` and a CPU ridge point around `3.5 FLOP/byte`.

FP32 hardware would not help reduce memory traffic. It would actually make the data movement larger compared to Q15. Since Q15 cuts the operand width in half, it is a better match for this kernel.

Also, building a full IEEE-754 FP32 datapath within the M2 time budget, while also completing the AXI interface and FSM, was not a good engineering trade-off.

The full precision reasoning is included in `precision.md`.

### 2. Compute core scope

M1 suggested that the compute core would handle the full 1000-neuron reservoir update internally. In M2, I implemented a single-neuron core instead.

The software calls this core multiple times to compute the full reservoir update.

The reason is that M2 is mainly graded on correctness against a golden reference, not full throughput. A single-neuron FSM is easier to verify, easier to defend, and still synthesizable.

The full multi-neuron design needs SRAM, address generation, and more control logic. That belongs more naturally in M3, once I have synthesis numbers and a clearer architecture direction.

### 3. AXI testbench library

At first, I tried to verify the AXI4-Lite interface using manual signal toggling. Two attempts ran into timing bugs that were hard to separate from RTL bugs.

I switched to the `AXI4LiteMaster` driver from `cocotb-bus`. This helped find both a testbench issue and a real RTL issue.

The testbench issue was that my reset sequence was overwriting the driver's `BREADY=1` initialization.

The RTL issue was that `s_axis_tready` was tied to `core_busy`, but the FSM only consumes data in `S_ACCUM`. Because of that, stream beats sent during `S_LOAD` were being dropped.

Both issues are fixed now.

The older codefest tests still use manual handshaking. For M2, the graded AXI4-Lite testbench uses `cocotb-bus`. AXI4-Stream is still manually driven because `cocotb-bus 0.3.0` does not include an AXI-Stream master.

## What's coming after M2

For M3, due May 24, the plan is to run OpenLane 2 synthesis on `compute_core.sv` and `interface.sv`. I will collect area and timing reports and run end-to-end co-simulation against the Mackey-Glass software baseline.

For M4, due June 7, the plan is to complete the full design package, run a multi-precision sweep, and compare Q15 against Q7 and possibly INT4. I will also compare the hardware results against the M1 software baseline and include everything in the final design report.

The architecture revisit suggested by Prof. Teuscher will happen between M2 and M3. At that point, I will have actual synthesis numbers to guide the next design decisions.
