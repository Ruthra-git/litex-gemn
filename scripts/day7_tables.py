#!/usr/bin/env python3
"""Day 7 tables from a firmware log or the raw ZCSV file, compared with the Day 6 bare-metal run."""
import sys

src = sys.argv[1]
base = sys.argv[2] if len(sys.argv) > 2 else "docs/day6_raw.csv"
z, off, offl, ctr = {}, [], [], []
for line in open(src, errors="ignore"):
    p = line.strip().split(",")
    if p[0] != "ZCSV" or len(p) < 4:
        continue
    kind = p[1]
    if kind == "day7":
        z[int(p[3])] = [int(x) for x in p[4:9]]      # sw, blk, dma, dmai, ok
    elif kind == "offload":
        off.append(p[2:8])                           # lanes, n, mode, cycles, bg, pct
    elif kind == "offload_long":
        offl.append(p[2:8])                          # lanes, k, mode, cycles, bg, pct
    elif kind == "ctr":
        ctr.append([int(x) for x in p[2:7]])         # lanes, k, cycles, xfers, waits

bm = {}
try:
    for line in open(base):
        p = line.strip().split(",")
        if p[0] == "CSV" and p[1] == "day6":
            bm[int(p[3])] = [int(x) for x in p[4:10]]  # sw, blk, pio, dma, dmai, ok
except OSError:
    pass

BARE_CTR = {1: 74, 4: 188, 8: 340}
print("| LANES | K steps | DMA cycles | transfers | stall cycles | bare-metal cycles (Day 6) |")
print("|---|---|---|---|---|---|")
for lanes, k, cyc, xf, wt in ctr:
    print(f"| {lanes} | {k} | {cyc} | {xf} | {wt} | {BARE_CTR.get(k, 'n/a')} |")

print()
print("| N | Zephyr naive | Zephyr blocked | Zephyr DMA poll | Zephyr DMA irq | bare-metal DMA poll | Zephyr/bare poll | irq extra per descriptor (Zephyr) | irq extra per descriptor (bare-metal) | match |")
print("|---|---|---|---|---|---|---|---|---|---|")
for n in sorted(z):
    sw, blk, dma, dmai, ok = z[n]
    desc = (n // 4) ** 2
    zx = (dmai - dma) // desc
    b = bm.get(n)
    if b:
        ratio = f"{dma / b[3]:.2f}x"
        bx = (b[4] - b[3]) // desc
        bdma = b[3]
    else:
        ratio, bx, bdma = "n/a", "n/a", "n/a"
    print(f"| {n} | {sw} | {blk} | {dma} | {dmai} | {bdma} | {ratio} | {zx} | {bx} | {'yes' if ok else 'NO'} |")

print()
print("Per-tile offload (N=64, 256 descriptors)")
print()
print("| LANES | N | mode | cycles | background iterations | CPU available |")
print("|---|---|---|---|---|---|")
for lanes, n, mode, cyc, bgd, pct in off:
    print(f"| {lanes} | {n} | {mode} | {cyc} | {bgd} | {pct}% |")

print()
print("Long descriptor offload (one descriptor)")
print()
print("| LANES | K steps | mode | cycles | background iterations | CPU available |")
print("|---|---|---|---|---|---|")
for lanes, k, mode, cyc, bgd, pct in offl:
    print(f"| {lanes} | {k} | {mode} | {cyc} | {bgd} | {pct}% |")
