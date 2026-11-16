#!/usr/bin/env python3
"""Sanity checks on a Day 8 sweep CSV. Exit code 1 on hard failures."""
import csv
import statistics
import sys

MIN_FMAX_NOTE = 50.0     # a typical LiteX system clock (my choice, not a requirement)
rows = list(csv.DictReader(open(sys.argv[1])))
hard, warn, finding = [], [], []


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


by = {}
for r in rows:
    by.setdefault(int(r["lanes"]), []).append(r)

ok = {}
for l in (4, 8, 16):
    rs = by.get(l, [])
    good = [r for r in rs if r.get("status") == "ok"]
    ok[l] = good
    if not rs:
        hard.append(f"no rows for LANES={l}")
    elif not good:
        if any(r.get("status") == "no-fit" for r in rs):
            finding.append(f"LANES={l} does not fit the target device (needs about "
                           f"{rs[0]['yosys_lut4']} LUT4, capacity {rs[0]['comb_avail']})")
        else:
            hard.append(f"LANES={l}: place-and-route failed for another reason (see nextpnr.log)")
    elif len(good) < 3:
        warn.append(f"LANES={l}: only {len(good)} successful seed(s)")
    if any((f(r["yosys_latch"]) or 0) > 0 for r in rs):
        hard.append(f"LANES={l}: latch cells in the netlist")


def med(l, key):
    v = [f(r[key]) for r in ok.get(l, []) if f(r[key]) is not None]
    return statistics.median(v) if v else None


print("| LANES | COMB | FF | MULT | BRAM | Fmax median MHz | Fmax spread | device |")
print("|---|---|---|---|---|---|---|---|")
for l in (4, 8, 16):
    if not ok[l]:
        continue
    fm = [f(r["fmax_mhz"]) for r in ok[l]]
    spread = (max(fm) - min(fm)) / statistics.median(fm)
    print(f"| {l} | {med(l,'pnr_comb')} | {med(l,'pnr_ff')} | {med(l,'pnr_mult')} | "
          f"{med(l,'pnr_bram')} | {med(l,'fmax_mhz')} | {spread*100:.1f}% | {ok[l][0]['device']} |")
    if med(l, "pnr_mult") != l:
        warn.append(f"LANES={l}: {med(l,'pnr_mult')} multiplier blocks, expected {l}")
    if (med(l, "pnr_bram") or 0) != 0:
        warn.append(f"LANES={l}: block RAM used, expected none")
    if spread > 0.15:
        warn.append(f"LANES={l}: clock estimate spread across seeds {spread*100:.0f}% (noisy)")
    if med(l, "fmax_mhz") < MIN_FMAX_NOTE:
        warn.append(f"LANES={l}: estimated clock {med(l,'fmax_mhz')} MHz is below {MIN_FMAX_NOTE:.0f} MHz")

combs = [med(l, "pnr_comb") for l in (4, 8, 16)]
if all(c is not None for c in combs) and not (combs[0] < combs[1] < combs[2]):
    warn.append(f"logic does not grow with LANES: {combs}")
ffs = [med(l, "pnr_ff") for l in (4, 8, 16)]
if all(c is not None for c in ffs) and ffs[0] and ffs[2] / ffs[0] > 1.3:
    warn.append(f"flip-flops grow more than 30% from LANES 4 to 16: {ffs}")

print()
for m in finding:
    print("FINDING:", m)
for m in hard:
    print("FAIL:", m)
for m in warn:
    print("WARN:", m)
if hard:
    print("SANITY: FAILED")
    sys.exit(1)
print("SANITY: OK" + (f" ({len(warn)} warning(s), {len(finding)} finding(s))" if warn or finding else ""))
