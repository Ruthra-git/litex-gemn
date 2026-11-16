#!/usr/bin/env python3
"""Merge the Day 8 synthesis sweep with SoC cycle counts into a trade-off table.
Usage: day8_tradeoff.py <resources.csv> <day6 log or csv> [more logs ...]"""
import csv
import statistics
import sys

rows = list(csv.DictReader(open(sys.argv[1])))
by = {}
for r in rows:
    by.setdefault(int(r["lanes"]), []).append(r)

cyc = {}
for path in sys.argv[2:]:
    try:
        lines = open(path, errors="ignore").read().splitlines()
    except OSError:
        continue
    for line in lines:
        p = line.strip().split(",")
        if len(p) < 7 or p[0] != "CSV":
            continue
        if p[1] == "day6" and p[3] == "64":
            cyc.setdefault(int(p[2]), {})["n64"] = [int(x) for x in p[4:9]]   # sw, blk, pio, dma, dmai
        elif p[1] == "dmactr":
            cyc.setdefault(int(p[2]), {}).setdefault("k", {})[int(p[3])] = int(p[4])


def med(rs, key):
    v = []
    for r in rs:
        try:
            v.append(float(r[key]))
        except (TypeError, ValueError):
            pass
    return statistics.median(v) if v else None


MACS_64 = 64 * 64 * 64
print("| LANES | COMB | FF | MULT | Fmax median (min-max) MHz | cycles per K step | DMA cycles N=64 | MAC/cycle | speedup vs blocked SW | speedup per 1000 COMB | MMAC/s at Fmax |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for l in sorted(by):
    rs = by[l]
    comb, ff, mult, fmax = med(rs, "pnr_comb"), med(rs, "pnr_ff"), med(rs, "pnr_mult"), med(rs, "fmax_mhz")
    fl = [float(r["fmax_mhz"]) for r in rs if r["fmax_mhz"]]
    rng = f"{min(fl):.1f}-{max(fl):.1f}" if fl else "n/a"
    c = cyc.get(l, {})
    k = c.get("k", {})
    kstep = f"{(k[8] - k[1]) / 7:.1f}" if 1 in k and 8 in k else "n/a"
    if "n64" in c:
        sw, blk, pio, dma, dmai = c["n64"]
        macs = MACS_64 / dma
        sp = blk / dma
        per_k = f"{sp / (comb / 1000):.2f}" if comb else "n/a"
        mm = f"{macs * fmax:.0f}" if fmax else "n/a"
        print(f"| {l} | {comb:.0f} | {ff:.0f} | {mult:.0f} | {fmax:.1f} ({rng}) | {kstep} | {dma} | {macs:.2f} | {sp:.2f}x | {per_k} | {mm} |")
    else:
        print(f"| {l} | {comb} | {ff} | {mult} | {fmax} ({rng}) | {kstep} | missing | | | | |")
print()
print("Notes: resource and clock figures are Yosys + nextpnr-ecp5 estimates (accelerator only, out-of-context, seed medians). Cycles come from the simulated SoC (shared clock, ideal-ish memory). MMAC/s at Fmax is an accelerator-limited upper bound that ignores the CPU's own maximum clock.")
