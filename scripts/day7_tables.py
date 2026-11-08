#!/usr/bin/env python3
"""Generate Day 7 Zephyr and Day 6 bare-metal comparison tables."""
import sys

log = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "docs/day6_raw.csv"

z, off = {}, []

for line in open(log, errors="ignore"):
    p = line.strip().split(",")

    if len(p) > 1 and p[0] == "ZCSV" and p[1] == "day7":
        z[int(p[3])] = [int(x) for x in p[4:9]]

    elif len(p) > 1 and p[0] == "ZCSV" and p[1] == "offload":
        off.append(p[2:])

bm = {}

try:
    for line in open(base, errors="ignore"):
        p = line.strip().split(",")

        if len(p) > 1 and p[0] == "CSV" and p[1] == "day6":
            bm[int(p[3])] = [int(x) for x in p[4:10]]
except OSError:
    pass

print("| N | Zephyr naive | Zephyr blocked | Zephyr DMA poll | Zephyr DMA irq | bare-metal DMA poll | Zephyr/bare DMA poll | match |")
print("|---|---:|---:|---:|---:|---:|---:|---|")

for n in sorted(z):
    sw, blk, dma, dmai, ok = z[n]
    b = bm.get(n)
    bdma = b[3] if b else None
    ratio = f"{dma / bdma:.2f}x" if bdma else "n/a"

    print(
        f"| {n} | {sw} | {blk} | {dma} | {dmai} | "
        f"{bdma if bdma is not None else 'n/a'} | {ratio} | "
        f"{'yes' if ok else 'NO'} |"
    )

print()
print("| LANES | N | mode | DMA cycles | background iterations | CPU available (%) |")
print("|---:|---:|---|---:|---:|---:|")

for lanes, n, mode, cyc, bgd, pct in off:
    print(f"| {lanes} | {n} | {mode} | {cyc} | {bgd} | {pct} |")
