"""
Cocotb 2.0 runner for the M4 K=64 accelerator top.

Usage:
    python runner.py --data-w 16     # Q15
    python runner.py --data-w 8      # INT8
    python runner.py --data-w 4      # Q4
    python runner.py --data-w 16 --waves

Emits the $readmemh weight/x/win hex files (one-time preload) into the test
dir before simulation, then runs the N=1000 cosim.
"""
import argparse
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

THIS = Path(__file__).resolve().parent
RTL2 = THIS.parents[1] / 'rtl' / 'm2'
RTL4 = THIS.parents[1] / 'rtl' / 'm4'

# M2 leaf modules (frozen) + M4 compute_core copy + M4 top
RTL_SOURCES = [
    RTL2 / 'mac_array.sv',
    RTL2 / 'tanh_pwl.sv',
    RTL2 / 'leak_blend.sv',
    RTL4 / 'compute_core.sv',
    RTL4 / 'top.sv',
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-w', type=int, default=16)
    p.add_argument('--mac-width', type=int, default=16)
    p.add_argument('--acc-w', type=int, default=40)
    p.add_argument('--n', type=int, default=1000)
    p.add_argument('--k', type=int, default=64)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--sim', default='icarus')
    p.add_argument('--waves', action='store_true')
    args = p.parse_args()

    build_dir = THIS / 'sim_build' / f"top_DW{args.data_w}"
    build_dir.mkdir(parents=True, exist_ok=True)

    # ---- emit $readmemh preload files into the test dir (vvp cwd) ----
    sys.path.insert(0, str(THIS))
    from golden_top import gen_network, emit_hex
    net = gen_network(args.n, args.data_w, args.acc_w, args.seed)
    emit_hex(net, THIS, mac_width=args.mac_width, k=args.k)

    os.environ['DATA_W']      = str(args.data_w)
    os.environ['MAC_WIDTH']   = str(args.mac_width)
    os.environ['ACC_W']       = str(args.acc_w)
    os.environ['N_RESERVOIR'] = str(args.n)
    os.environ['SEED']        = str(args.seed)
    os.environ['PYTHONPATH']  = str(THIS) + os.pathsep + os.environ.get('PYTHONPATH', '')

    runner = get_runner(args.sim)
    runner.build(
        sources=[str(s) for s in RTL_SOURCES],
        hdl_toplevel='top',
        build_dir=str(build_dir),
        parameters={
            'DATA_W':    args.data_w,
            'MAC_WIDTH': args.mac_width,
            'ACC_W':     args.acc_w,
            'FRAC_W':    args.data_w - 1,
            'K':         args.k,
            'N':         args.n,
        },
        build_args=['-g2012'],
        always=True,
    )
    result = runner.test(
        hdl_toplevel='top',
        test_module='test_top',
        build_dir=str(build_dir),
        waves=args.waves,
        test_dir=str(THIS),
    )
    print(f"\n=== runner.py: test result = {result} ===")
    return 0


if __name__ == '__main__':
    sys.exit(main())
