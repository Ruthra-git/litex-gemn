#!/usr/bin/env python3
"""Turn the CSV lines of a Day 6 firmware log into markdown tables."""
import sys

def r(a, b):
    return f"{a / b:.2f}x" if b else "n/a"

sizes, ctrs = [], []
for line in open(sys.argv[1], errors="ignore"):
    p = line.strip().split(",")
    if p[0] != "CSV":
        continue
    if p[1] == "day6":
        sizes.append([int(x) for x in p[2:9]] + [p[9]])
    elif p[1] == "dmactr":
        ctrs.append([int(x) for x in p[2:7]])

print("| LANES | N | SW naive | SW blocked | PIO fast | DMA poll | DMA irq | blk vs naive | PIO vs blk | DMA vs blk | DMA vs PIO | match |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for lanes, n, sw, blk, pio, dma, dmai, ok in sizes:
    print(f"| {lanes} | {n} | {sw} | {blk} | {pio} | {dma} | {dmai} | {r(sw, blk)} | {r(blk, pio)} | {r(blk, dma)} | {r(pio, dma)} | {'yes' if ok == '1' else 'NO'} |")
print()
print("| LANES | K steps | DMA cycles | transfers | stall cycles | avg stall per transfer | cycles per transfer |")
print("|---|---|---|---|---|---|---|")
for lanes, k, cyc, xf, wt in ctrs:
    print(f"| {lanes} | {k} | {cyc} | {xf} | {wt} | {wt / xf:.2f} | {cyc / xf:.2f} |")
