"""
Cocotb 2.0 runner — drives Icarus from Python directly.

Usage:
    python runner.py compute_core
    python runner.py interface
    python runner.py compute_core --data-w 8     # for INT8 sweep
    python runner.py compute_core --data-w 4     # for Q4 sweep
"""
import argparse
import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_runner

THIS = Path(__file__).resolve().parent
RTL  = THIS.parents[1] / 'rtl' / 'm2'

RTL_SOURCES = [
    RTL / 'mac_array.sv',
    RTL / 'tanh_pwl.sv',
    RTL / 'leak_blend.sv',
    RTL / 'compute_core.sv',
    RTL / 'interface.sv',
]

TARGETS = {
    'compute_core': {
        'toplevel': 'compute_core',
        'module':   'test_compute_core',
    },
    'interface': {
        'toplevel': 'interface_axi',
        'module':   'test_interface',
    },
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('target', choices=sorted(TARGETS.keys()))
    p.add_argument('--data-w', type=int, default=16)
    p.add_argument('--mac-width', type=int, default=16)
    p.add_argument('--acc-w', type=int, default=40)
    p.add_argument('--sim', default='icarus')
    p.add_argument('--waves', action='store_true', help='dump VCD waveform')
    args = p.parse_args()

    tgt = TARGETS[args.target]

    # Per-precision build dir so different DATA_W runs don't trample
    build_dir = THIS / 'sim_build' / f"{args.target}_DW{args.data_w}"
    build_dir.mkdir(parents=True, exist_ok=True)

    # Export parameters to test scripts via env
    os.environ['DATA_W']    = str(args.data_w)
    os.environ['MAC_WIDTH'] = str(args.mac_width)
    os.environ['ACC_W']     = str(args.acc_w)

    # Inject TB dir onto PYTHONPATH so 'import golden' works inside cocotb
    os.environ['PYTHONPATH'] = str(THIS) + os.pathsep + os.environ.get('PYTHONPATH', '')

    runner = get_runner(args.sim)
    runner.build(
        sources=[str(s) for s in RTL_SOURCES],
        hdl_toplevel=tgt['toplevel'],
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
        hdl_toplevel=tgt['toplevel'],
        test_module=tgt['module'],
        build_dir=str(build_dir),
        waves=args.waves,
        test_dir=str(THIS),
    )
    print(f"\n=== runner.py: test result = {result} ===")
    # cocotb 2.0 returns a path to results.xml on success, or raises on infra fail
    return 0


if __name__ == '__main__':
    sys.exit(main())
