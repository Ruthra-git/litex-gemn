#!/usr/bin/env python3
"""Regenerate docs/figures/*.png, docs/results_table.md and the README results region
from docs/data/results.json."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
R = json.load(open("docs/data/results.json"))
os.makedirs("docs/figures", exist_ok=True)
MACS = 64 ** 3
LANES = ["4", "8", "16"]
dma = R["bare_metal_n64"]["dma_poll"]
blk = R["bare_metal_n64"]["blocked"]
naive = R["bare_metal_n64"]["naive"]
v7 = R["fpga_v07_25f"]

# Figure 1: Zephyr cycles vs N
z = R["zephyr_L4"]
ns = [4, 8, 16, 32, 64]
fig, ax = plt.subplots(figsize=(6.4, 4.2))
for key, label in (("naive", "naive C"), ("blocked", "register-blocked C"),
                   ("dma_poll", "DMA (poll)"), ("dma_irq", "DMA (interrupt)")):
    ax.loglog(ns, [z[key][str(n)] for n in ns], marker="o", label=label)
ax.set_xticks(ns)
ax.set_xticklabels([str(n) for n in ns])
ax.xaxis.set_minor_locator(NullLocator())
ax.set_xlabel("matrix size N (N x N x N int8 GEMM)")
ax.set_ylabel("CPU cycles (simulation)")
ax.set_title("Zephyr driver, LANES=4: cycles vs matrix size")
ax.grid(True, which="both", alpha=0.3)
ax.legend()
fig.tight_layout()
fig.savefig("docs/figures/fig1_zephyr_cycles.png", dpi=150)
plt.close(fig)

# Figure 2: lanes -> speedup and estimated throughput
speed = [blk / dma[l] for l in LANES]
mmacs = [MACS / dma[l] * v7[l]["clock_mhz"] for l in LANES]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6))
a1.bar(LANES, speed)
a1.set_xlabel("LANES")
a1.set_ylabel("speedup vs register-blocked C (N=64)")
for i, v in enumerate(speed):
    a1.text(i, v, f"{v:.2f}x", ha="center", va="bottom")
a2.bar(LANES, mmacs)
a2.set_xlabel("LANES")
a2.set_ylabel("estimated MMAC/s (cycles x nextpnr clock)")
for i, v in enumerate(mmacs):
    a2.text(i, v, f"{v:.0f}", ha="center", va="bottom")
fig.suptitle("Bare-metal DMA, N=64: simulated cycles; clock is an estimate")
fig.tight_layout()
fig.savefig("docs/figures/fig2_lanes.png", dpi=150)
plt.close(fig)

# Figure 3: v0.6 vs v0.7 core on LFE5U-85F
a, b = R["fpga_v06_85f"], R["fpga_v07_85f"]
w, x = 0.38, range(3)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.6))
for ax_, key, ylab in ((a1, "logic", "logic cells"), (a2, "clock_mhz", "estimated clock (MHz)")):
    ax_.bar([i - w / 2 for i in x], [a[l][key] for l in LANES], w, label="v0.6")
    ax_.bar([i + w / 2 for i in x], [b[l][key] for l in LANES], w, label="v0.7")
    ax_.set_xticks(list(x))
    ax_.set_xticklabels(LANES)
    ax_.set_xlabel("LANES")
    ax_.set_ylabel(ylab)
    ax_.legend()
fig.suptitle("Operand-prefetch datapath (v0.7) vs v0.6, LFE5U-85F, Yosys + nextpnr")
fig.tight_layout()
fig.savefig("docs/figures/fig3_v06_vs_v07.png", dpi=150)
plt.close(fig)
# Tables
t = []
t.append("Cycle counts below are from the cycle-accurate simulated SoC (bare-metal firmware, N = 64). "
         "Area and clock are Yosys + nextpnr-ecp5 estimates, not silicon measurements.\n")
t.append("| LANES | DMA cycles (N=64) | MAC/cycle | vs register-blocked C | vs naive C |")
t.append("|---|---|---|---|---|")
for l in LANES:
    t.append(f"| {l} | {dma[l]:,} | {MACS / dma[l]:.2f} | {blk / dma[l]:.2f}x | {naive / dma[l]:.1f}x |")
t.append("")
t.append("| LANES | logic cells (LFE5U-25F) | FF | MULT18X18D | est. clock (MHz) | est. MMAC/s |")
t.append("|---|---|---|---|---|---|")
for l in LANES:
    t.append(f"| {l} | {v7[l]['logic']:,} | {v7[l]['ff']:,} | {v7[l]['mult']} | "
             f"{v7[l]['clock_mhz']:.1f} | {MACS / dma[l] * v7[l]['clock_mhz']:.0f} |")
t.append("")
t.append("| Zephyr driver, LANES=4, N=64 | cycles |")
t.append("|---|---|")
for key, label in (("naive", "naive C"), ("blocked", "register-blocked C"),
                   ("dma_poll", "DMA, poll completion"), ("dma_irq", "DMA, interrupt completion")):
    t.append(f"| {label} | {z[key]['64']:,} |")
table = "\n".join(t)
open("docs/results_table.md", "w").write(table + "\n")

begin, end = "<!-- RESULTS-BEGIN -->", "<!-- RESULTS-END -->"
s = open("README.md").read()
if begin not in s or end not in s:
    raise SystemExit("README.md is missing the RESULTS markers (create README first)")
s = s[:s.index(begin) + len(begin)] + "\n\n" + table + "\n\n" + s[s.index(end):]
open("README.md", "w").write(s)
print("figures, docs/results_table.md and README results region regenerated")
