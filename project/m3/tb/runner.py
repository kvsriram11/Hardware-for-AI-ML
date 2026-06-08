"""
Cocotb 2.0 runner for the M3 integrated top.

Usage:
    python runner.py            # N=64 reservoir cosim
    python runner.py --waves    # + FST waveform dump
    python runner.py --n 32     # smaller reservoir
"""
import argparse
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

THIS = Path(__file__).resolve().parent
RTL2 = THIS.parents[1] / 'rtl' / 'm2'
RTL3 = THIS.parents[1] / 'rtl' / 'm3'

RTL_SOURCES = [
    RTL2 / 'mac_array.sv',
    RTL2 / 'tanh_pwl.sv',
    RTL2 / 'leak_blend.sv',
    RTL2 / 'compute_core.sv',
    RTL2 / 'interface.sv',
    RTL3 / 'top.sv',
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-w', type=int, default=16)
    p.add_argument('--mac-width', type=int, default=16)
    p.add_argument('--acc-w', type=int, default=40)
    p.add_argument('--n', type=int, default=64, help='reservoir size N')
    p.add_argument('--sim', default='icarus')
    p.add_argument('--waves', action='store_true')
    args = p.parse_args()

    build_dir = THIS / 'sim_build' / f"top_DW{args.data_w}"
    build_dir.mkdir(parents=True, exist_ok=True)

    os.environ['DATA_W']      = str(args.data_w)
    os.environ['MAC_WIDTH']   = str(args.mac_width)
    os.environ['ACC_W']       = str(args.acc_w)
    os.environ['N_RESERVOIR'] = str(args.n)
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
