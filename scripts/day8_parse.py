#!/usr/bin/env python3
"""Collect Yosys/nextpnr results under build/synth/<tag> into CSV on stdout.
Usage: day8_parse.py <outdir> <target_mhz> <device>"""
import csv
import json
import os
import re
import sys

root, target, device = sys.argv[1], float(sys.argv[2]), sys.argv[3]
CAP = {"25k": 24288, "45k": 43848, "85k": 83640}   # approximate logic-cell capacity per device

COLS = ["lanes", "seed", "yosys_lut4", "yosys_ff", "yosys_carry", "yosys_dsp", "yosys_bram",
        "yosys_latch", "pnr_comb", "pnr_ff", "pnr_mult", "pnr_bram", "fmax_mhz",
        "target_mhz", "timing_met", "device", "status", "comb_avail", "note"]


def yosys_counts(netlist):
    out = {"latch": 0}
    try:
        data = json.load(open(netlist))
    except (OSError, ValueError):
        return out
    mods = data.get("modules", {})
    top = mods.get("gemm_wb") or next(iter(mods.values()), {})
    for cell in top.get("cells", {}).values():
        t = cell.get("type", "")
        out[t] = out.get(t, 0) + 1
        if any("LATCH" in str(v) for v in cell.get("parameters", {}).values()):
            out["latch"] += 1
    return out


def pnr(report, logpath):
    util, avail, fmax, note = {}, {}, None, ""
    try:
        r = json.load(open(report))
        for k, v in r.get("utilization", {}).items():
            if isinstance(v, dict):
                util[k] = v.get("used", 0)
                avail[k] = v.get("available")
        vals = [v for v in r.get("fmax", {}).values() if isinstance(v, dict) and "achieved" in v]
        if vals:
            fmax = min(float(v["achieved"]) for v in vals)
    except (OSError, ValueError):
        pass
    text = ""
    try:
        text = open(logpath, errors="ignore").read()
    except OSError:
        pass
    if fmax is None:
        hits = re.findall(r"Max frequency for clock '[^']*': ([0-9.]+) MHz", text)
        if hits:
            fmax = float(hits[-1])
    for key in ("TRELLIS_COMB", "TRELLIS_FF", "MULT18X18D", "DP16KD"):
        hits = re.findall(key + r":\s+(\d+)/\s*(\d+)", text)
        if hits:
            util.setdefault(key, int(hits[-1][0]))
            avail.setdefault(key, int(hits[-1][1]))
    m = re.search(r"ERROR: (.*)", text)
    if m:
        note = m.group(1)[:120]
    return util, avail, fmax, note


w = csv.writer(sys.stdout)
w.writerow(COLS)
for ldir in sorted(os.listdir(root)):
    m = re.fullmatch(r"L(\d+)", ldir)
    if not m:
        continue
    lanes = int(m.group(1))
    yc = yosys_counts(os.path.join(root, ldir, "netlist.json"))
    for sdir in sorted(os.listdir(os.path.join(root, ldir))):
        ms = re.fullmatch(r"s(\d+)", sdir)
        if not ms:
            continue
        base = os.path.join(root, ldir, sdir)
        util, avail, fmax, note = pnr(os.path.join(base, "report.json"),
                                      os.path.join(base, "nextpnr.log"))
        comb = util.get("TRELLIS_COMB", "")
        cap = avail.get("TRELLIS_COMB") or CAP.get(device, "")
        if fmax is not None:
            status = "ok"
        else:
            used = comb if comb != "" else yc.get("LUT4", 0)
            status = "no-fit" if cap and used and used > cap else "failed"
        met = "" if fmax is None else ("yes" if fmax >= target else "no")
        w.writerow([lanes, int(ms.group(1)), yc.get("LUT4", 0), yc.get("TRELLIS_FF", 0),
                    yc.get("CCU2C", 0), yc.get("MULT18X18D", 0),
                    yc.get("DP16KD", 0) + yc.get("PDPW16KD", 0), yc.get("latch", 0),
                    comb, util.get("TRELLIS_FF", ""), util.get("MULT18X18D", ""),
                    util.get("DP16KD", ""), "" if fmax is None else f"{fmax:.2f}", target, met,
                    device, status, cap, note])
