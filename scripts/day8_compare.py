#!/usr/bin/env python3
"""Before/after comparison of two Day 8 sweep CSVs (median over seeds, status ok only)."""
import csv
import statistics
import sys


def load(p):
    d = {}
    for r in csv.DictReader(open(p)):
        if r.get("status") == "ok":
            d.setdefault(int(r["lanes"]), []).append(r)
    return d


def med(rs, k):
    return statistics.median(float(r[k]) for r in rs)


a, b = load(sys.argv[1]), load(sys.argv[2])
print("| LANES | COMB before | COMB after | ratio | Fmax before MHz | Fmax after MHz | ratio | MULT before | MULT after |")
print("|---|---|---|---|---|---|---|---|---|")
for l in (4, 8, 16):
    if l in a and l in b:
        ca, cb = med(a[l], "pnr_comb"), med(b[l], "pnr_comb")
        fa, fb = med(a[l], "fmax_mhz"), med(b[l], "fmax_mhz")
        print(f"| {l} | {ca:.0f} | {cb:.0f} | {cb/ca:.2f}x | {fa:.1f} | {fb:.1f} | {fb/fa:.2f}x | "
              f"{med(a[l],'pnr_mult'):.0f} | {med(b[l],'pnr_mult'):.0f} |")
    else:
        print(f"| {l} | n/a | n/a | | | | | | |")
