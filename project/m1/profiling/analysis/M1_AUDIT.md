# M1 Audit & Copy-List

| Status | Tag | Local Path | GitHub Path | Notes |
|---|---|---|---|---|
| ✓ | PROF | `docs/heilmeier.md` | `project/heilmeier.md` | Q1/Q2/Q3 refined; Q2 references profiling |
| ✓ | PROF | `docs/sw_baseline.md` | `project/m1/sw_baseline.md` | Platform, median of ≥10 runs, throughput, memory |
| ✓ | PROF | `profiling/cprofile/project_profile.txt` | `codefest/cf02/profiling/project_profile.txt` | Raw cProfile output |
| ✓ | PROF | `profiling/analysis/ai_calculation.md` | `codefest/cf02/analysis/ai_calculation.md` | Analytical FLOPs+bytes+AI, dominant kernel |
| ✓ | PROF | `profiling/analysis/roofline_project.png` | `codefest/cf02/profiling/roofline_project.png` | Ridge+SW+HW points, log axes |
| ✓ | PROF | `profiling/analysis/partition_rationale.md` | `codefest/cf02/analysis/partition_rationale.md` | HW/SW split, bound type, interface BW, ≥200 words |
| ✓ | PROF | `docs/interface_selection.md` | `project/m1/interface_selection.md` | Interface choice, BW calc, comparison, host |
| ✓ | PROF | `docs/system_diagram.png` | `project/m1/system_diagram.png` | Host, interface, chiplet boundary, compute, memory |
| ✓ | ADD | `profiling/analysis/kernel_comparison.md` | `codefest/cf02/analysis/kernel_comparison.md` | state vs readout vs spectral |
| ✓ | ADD | `profiling/cprofile/sweep_data.csv` | `codefest/cf02/profiling/sweep_data.csv` | Size sweep N∈{100..5000} |
| ✓ | ADD | `baselines/c_openblas/benchmark.md` | `project/m1/c_openblas/benchmark.md` | C+BLAS doc + validation table |
| ✓ | ADD | `baselines/c_openblas/benchmark.c` | `project/m1/c_openblas/benchmark.c` | C source |
| ✓ | ADD | `baselines/c_openblas/dump_weights.py` | `project/m1/c_openblas/dump_weights.py` | Weight binary dumper |
| ✓ | ADD | `baselines/c_openblas/cross_validate.py` | `project/m1/c_openblas/cross_validate.py` | C/Python equivalence check |
| ✓ | ADD | `baselines/c_openblas/c_results.json` | `project/m1/c_openblas/c_results.json` | C benchmark capture |
| ✓ | ADD | `profiling/analysis/roofline_sweep.png` | `codefest/cf02/profiling/roofline_sweep.png` | Sweep roofline with both baselines |
