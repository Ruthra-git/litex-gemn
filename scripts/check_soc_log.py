#!/usr/bin/env python3
"""Check a Day 6 SoC firmware log: functional self-tests plus the Day 8 DMA cycle model.
Usage: check_soc_log.py <log> [--lanes N] [--tol 0.05]"""
import argparse
import re
import sys

ap = argparse.ArgumentParser()
ap.add_argument("log")
ap.add_argument("--lanes", type=int)
ap.add_argument("--tol", type=float, default=0.05)
a = ap.parse_args()

text = open(a.log, errors="ignore").read().replace("\r", "")
lines = text.splitlines()
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


m = re.search(r"ID ok, LANES=(\d+)", text)
lanes = a.lanes or (int(m.group(1)) if m else None)
check("LANES identified", lanes is not None, f"LANES={lanes}")

if lanes:
    step = 64 // lanes + 22
    check("RESULT: PASS present", "RESULT: PASS" in text)
    for name in ("DMA known-answer tests", "DMA random 4x4 tiles", "DMA error path", "IRQ line"):
        ok = any(l.startswith(name) and l.rstrip().endswith("PASS") for l in lines)
        check(name + " PASS", ok)
    mm = re.search(r"after flush = (\d+)", text)
    check("coherency: 0 stale words after flush", mm and mm.group(1) == "0", mm.group(0) if mm else "not found")
    matches = [l for l in lines if l.strip().startswith("match:")]
    check("every method matches at every size", len(matches) == 5 and all(" NO" not in l for l in matches),
          f"{len(matches)} match lines")

    for l in lines:
        p = l.strip().split(",")
        if p[:2] == ["CSV", "dmactr"]:
            k, cyc, xf = int(p[3]), int(p[4]), int(p[5])
            check(f"counters K={k}: transfers = 8K+16", xf == 8 * k + 16, str(xf))
            model = 36 + step * k
            check(f"counters K={k}: cycles within 8 of model {model}", abs(cyc - model) <= 8, str(cyc))

    rows = {}
    for l in lines:
        p = l.strip().split(",")
        if p[:2] == ["CSV", "day6"]:
            rows[int(p[3])] = [int(x) for x in p[4:9]]   # naive, blocked, pio, dma poll, dma irq
    check("sizes N=4,8,16,32,64 all present", sorted(rows) == [4, 8, 16, 32, 64], str(sorted(rows)))
    if 64 in rows:
        sw, blk, pio, dma, dmai = rows[64]
        pred = 256 * (36 + step * 16) + 12414
        check(f"N=64 DMA within {100 * a.tol:.0f}% of model {pred}", abs(dma - pred) <= a.tol * pred, str(dma))
        check("N=64 ordering dma < pio < blocked < naive", dma < pio < blk < sw)
    for n, (sw, blk, pio, dma, dmai) in sorted(rows.items()):
        if n >= 8:
            check(f"N={n}: interrupt completion slower than polling", dmai > dma, f"{dmai} vs {dma}")

bad = 0
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")
    bad += not ok
print(f"SOC CHECK {'FAILED' if bad else 'OK'} ({len(results) - bad}/{len(results)} checks) LANES={lanes}")
sys.exit(1 if bad else 0)
