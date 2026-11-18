#!/usr/bin/env python3
"""Release consistency checks. Exit 1 on any problem."""
import glob
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
bad = []


def need(cond, msg):
    if not cond:
        bad.append(msg)


REQUIRED = [
    "README.md", "LICENSE", "Makefile", ".github/workflows/ci.yml", ".github/workflows/nightly.yml",
    "docs/ARCHITECTURE.md", "docs/REPRODUCE.md", "docs/SPEC.md", "docs/LOG.md", "docs/VERIFICATION.md",
    "docs/RELEASE_NOTES_v1.0.0.md", "docs/results_table.md", "docs/data/results.json",
    "docs/figures/fig1_zephyr_cycles.png", "docs/figures/fig2_lanes.png", "docs/figures/fig3_v06_vs_v07.png",
    "docs/day9_mutation.md", "docs/day9_summary.md", "docs/day8_results.md",
    "rtl/gemm_core.v", "rtl/gemm_dma.v", "rtl/gemm_wb.v", "formal/gemm_dma.sby", "formal/gemm_dma_props.vh",
    "ci/resource_budget.json",
]
for f in REQUIRED:
    need(os.path.exists(f), f"missing file: {f}")
need(not os.path.exists("rtl/gemm_wb3.v"), "stray rtl/gemm_wb3.v still in rtl/")

# leftovers in public documents and workflows
scan = ["README.md", "docs/ARCHITECTURE.md", "docs/REPRODUCE.md", "docs/VERIFICATION.md",
        "docs/RELEASE_NOTES_v1.0.0.md", "docs/day8_results.md"] + glob.glob(".github/workflows/*.yml")
for f in scan:
    if os.path.exists(f):
        t = open(f, errors="ignore").read()
        need(not re.search(r"\bTODO", t), f"{f}: contains TODO")
        need(not re.search(r"<[a-z]+>", t) or f.endswith(".yml"), f"{f}: contains an unfilled <slot>")

# relative links
link = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
for f in ["README.md"] + glob.glob("docs/*.md"):
    base = os.path.dirname(f)
    for m in link.finditer(open(f, errors="ignore").read()):
        tgt = m.group(1)
        if tgt.startswith(("http://", "https://", "mailto:")):
            continue
        need(os.path.exists(os.path.normpath(os.path.join(base, tgt))), f"{f}: broken link {tgt}")

# results.json against the recorded logs
if os.path.exists("docs/data/results.json"):
    R = json.load(open("docs/data/results.json"))
    for l in ("4", "8", "16"):
        p = f"docs/day6_run_L{l}.log"
        if not os.path.exists(p):
            need(False, f"missing {p}")
            continue
        found = None
        for line in open(p, errors="ignore").read().replace("\r", "").splitlines():
            f_ = line.strip().split(",")
            if f_[:2] == ["CSV", "day6"] and int(f_[3]) == 64:
                found = [int(x) for x in f_[4:9]]
        need(found is not None, f"{p}: no N=64 CSV line")
        if found:
            naive, blk, pio, dma, dmai = found
            need(dma == R["bare_metal_n64"]["dma_poll"][l], f"{p}: DMA poll {dma} differs from results.json")
            if l == "4":
                need(blk == R["bare_metal_n64"]["blocked"], f"{p}: blocked {blk} differs from results.json")
                need(naive == R["bare_metal_n64"]["naive"], f"{p}: naive {naive} differs from results.json")
                need(pio == R["bare_metal_n64"]["pio_fast_L4"], f"{p}: PIO {pio} differs from results.json")
                need(dmai == R["bare_metal_n64"]["dma_irq_L4"], f"{p}: DMA IRQ {dmai} differs from results.json")

# mutation threshold
if os.path.exists("docs/day9_mutation.md"):
    m = re.search(r"Score: (\d+)/(\d+) killed", open("docs/day9_mutation.md").read())
    need(m is not None, "docs/day9_mutation.md has no Score line")
    if m:
        k, n = int(m.group(1)), int(m.group(2))
        need(n > 0 and k / n >= 0.85, f"mutation score {k}/{n} below 85 percent")

for b in bad:
    print("FAIL", b)
print("CONSISTENCY FAILED" if bad else "CONSISTENCY OK")
sys.exit(1 if bad else 0)
