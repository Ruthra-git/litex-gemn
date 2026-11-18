#!/usr/bin/env python3
"""Run the simulated SoC non-interactively and capture the console until the RESULT line.
Usage: run_fw_sim.py --lanes 4 --out build/ci_soc_L4.log [--bin build/gemm_fw.bin] [--timeout 900]"""
import argparse
import os
import sys

import pexpect

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ap = argparse.ArgumentParser()
ap.add_argument("--lanes", type=int, default=4)
ap.add_argument("--out", required=True)
ap.add_argument("--bin", default="build/gemm_fw.bin")
ap.add_argument("--timeout", type=int, default=900)
args = ap.parse_args()

env = dict(os.environ, GEMM_LANES=str(args.lanes), FW_BIN=args.bin)
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
child = pexpect.spawn("bash", ["scripts/run_sim.sh"], cwd=ROOT, env=env,
                      encoding="utf-8", timeout=args.timeout, dimensions=(50, 200))
verdict = None
with open(args.out, "w") as log:
    child.logfile_read = log
    try:
        child.expect(r"RESULT: (PASS|FAIL)")
        verdict = child.match.group(1)
        child.expect(pexpect.TIMEOUT, timeout=2)      # let trailing output flush
    except (pexpect.TIMEOUT, pexpect.EOF):
        pass
child.sendintr()
child.close(force=True)
text = open(args.out, errors="ignore").read().replace("\r", "")
open(args.out, "w").write(text)
print(f"verdict: {verdict}")
sys.exit(0 if verdict == "PASS" else 1)
