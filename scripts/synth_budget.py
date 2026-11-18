#!/usr/bin/env python3
"""Resource-regression gate: synthesize with Yosys (ECP5) and compare with ci/resource_budget.json."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
cfg = json.load(open("ci/resource_budget.json"))
os.makedirs("build/budget", exist_ok=True)


def counts(path):
    mods = json.load(open(path))["modules"]
    top = mods.get("gemm_wb") or next(iter(mods.values()))
    c = {}
    for cell in top["cells"].values():
        c[cell["type"]] = c.get(cell["type"], 0) + 1
    return c


failed = False
print("| LANES | LUT4 | budget | Day 8 baseline | FF | budget | MULT18X18D | budget | status |")
print("|---|---|---|---|---|---|---|---|---|")
for lanes, b in cfg["budgets"].items():
    js = f"build/budget/L{lanes}.json"
    script = (f"read_verilog -sv rtl/gemm_core.v rtl/gemm_dma.v rtl/gemm_wb.v; "
              f"chparam -set LANES {lanes} gemm_wb; synth_ecp5 -top gemm_wb -json {js}")
    r = subprocess.run(["yosys", "-q", "-p", script], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit("yosys failed for LANES=" + lanes)
    c = counts(js)
    lut, ff, dsp = c.get("LUT4", 0), c.get("TRELLIS_FF", 0), c.get("MULT18X18D", 0)
    ok = lut <= b["lut4"] and ff <= b["ff"] and dsp == b["dsp"]
    base = cfg["baseline_lut4"].get(lanes)
    note = "ok" if ok else "OVER BUDGET"
    if base is not None and lut != base:
        note += " (differs from Day 8 baseline)"
    failed |= not ok
    print(f"| {lanes} | {lut} | {b['lut4']} | {base} | {ff} | {b['ff']} | {dsp} | {b['dsp']} | {note} |")
print("BUDGET FAILED" if failed else "BUDGET OK")
sys.exit(1 if failed else 0)
