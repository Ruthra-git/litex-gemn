#!/usr/bin/env python3
"""Mutation check: inject small RTL bugs into a copy of rtl/ and confirm the cocotb suites catch them.
Usage: scripts/mutation_check.py [--lanes 4] [--only id ...] [--min-score 0.85]
Writes docs/day9_mutation.md; exit 1 if score < --min-score or any mutant is invalid."""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TB = os.path.join(ROOT, "tb")
SUITES = ("core", "wb", "dma")

# id, file, exact text (must occur exactly once), replacement, description
MUTANTS = [
    ("dma_a_step", "gemm_dma.v", "a_ptr <= a_ptr + 32'd4;", "a_ptr <= a_ptr + 32'd8;",
     "A pointer advances 8 bytes per K step instead of 4"),
    ("dma_b_step", "gemm_dma.v", "b_ptr <= b_ptr + {b_str[29:0], 2'b00};", "b_ptr <= b_ptr + {b_str[28:0], 3'b000};",
     "B pointer advances 8 rows per K step instead of 4"),
    ("dma_no_acc", "gemm_dma.v", "first ? accf : 1'b1", "first ? accf : 1'b0",
     "later K steps do not accumulate"),
    ("dma_cstr_chk", "gemm_dma.v", "c_str[1:0] != 2'b00", "1'b0",
     "C stride alignment check removed"),
    ("dma_cwords", "gemm_dma.v", "if (idx == 5'd15) begin", "if (idx == 5'd14) begin",
     "C write-back stops one word early"),
    ("core_acc_mode", "gemm_core.v", "acc_mode <= accumulate;", "acc_mode <= 1'b0;",
     "accumulate request ignored"),
    ("core_done_early", "gemm_core.v", "if (cyc == NCYC - 1) begin", "if (cyc == NCYC - 2) begin",
     "DONE one cycle early"),
    ("core_cycles", "gemm_core.v", "cycles   <= 16'd1;", "cycles   <= 16'd0;",
     "cycle counter starts at 0"),
    ("core_sign", "gemm_core.v", "+ dot4p(opa[32*o1 +: 32], opb[32*o1 +: 32])",
     "- dot4p(opa[32*o1 +: 32], opb[32*o1 +: 32])", "dot product subtracted"),
    ("core_bytes", "gemm_core.v", "a1 = a[15:8];", "a1 = a[23:16];",
     "A byte lane 1 taken from lane 2"),
    ("wb_irq", "gemm_wb.v", "(done & ~dma_busy)", "(done)",
     "core DONE raises the interrupt during a DMA"),
    ("wb_dma_start", "gemm_wb.v", "dma_start_p <= wb_dat_w[0];", "dma_start_p <= wb_dat_w[1];",
     "DMA start bit moved"),
    ("wb_version", "gemm_wb.v", "16'h0006", "16'h0007", "INFO version changed"),
]

def run_suite(rtl, dut, lanes, tag, timeout):
    results = os.path.join(TB, "results.xml")
    if os.path.exists(results):
        os.remove(results)
    suffix = "_" + tag
    build = os.path.join(TB, f"sim_build_{dut}_L{lanes}{suffix}")
    try:
        subprocess.run(["make", "-C", TB, f"DUT={dut}", f"LANES={lanes}", f"RTL_DIR={rtl}", f"SUFFIX={suffix}"],
                       capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        shutil.rmtree(build, ignore_errors=True)
        return "killed", dut + " (timeout)"
    compiled = os.path.exists(os.path.join(build, "sim.vvp"))
    shutil.rmtree(build, ignore_errors=True)
    if not compiled:
        return "invalid", "compile error"
    xml = open(results).read() if os.path.exists(results) else ""
    if not xml or "<failure" in xml or "<error" in xml:
        return "killed", dut
    return "pass", dut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lanes", type=int, default=4)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--min-score", type=float, default=0.85)
    args = ap.parse_args()

    rows = []
    for mid, fname, old, new, desc in MUTANTS:
        if args.only and mid not in args.only:
            continue
        mdir = os.path.join(ROOT, "build", "mutants", mid)
        shutil.rmtree(mdir, ignore_errors=True)
        shutil.copytree(os.path.join(ROOT, "rtl"), mdir)
        path = os.path.join(mdir, fname)
        src = open(path).read()
        n = src.count(old)
        if n != 1:
            rows.append((mid, desc, "INVALID", f"pattern found {n} times", 0.0))
            print(f"{mid:16s} INVALID (pattern found {n} times)")
            continue
        open(path, "w").write(src.replace(old, new))
        t0 = time.time()
        status, by = "SURVIVED", "-"
        for dut in SUITES:
            res, info = run_suite(mdir, dut, args.lanes, mid, args.timeout)
            if res == "invalid":
                status, by = "INVALID", info
                break
            if res == "killed":
                status, by = "KILLED", info
                break
        dt = time.time() - t0
        rows.append((mid, desc, status, by, dt))
        print(f"{mid:16s} {status:9s} by {by:22s} {dt:5.1f}s")
        shutil.rmtree(mdir, ignore_errors=True)

    killed = sum(r[2] == "KILLED" for r in rows)
    survived = sum(r[2] == "SURVIVED" for r in rows)
    invalid = sum(r[2] == "INVALID" for r in rows)
    score = killed / (killed + survived) if (killed + survived) else 0.0
    with open(os.path.join(ROOT, "docs", "day9_mutation.md"), "w") as f:
        f.write(f"# Mutation check (LANES={args.lanes})\n\n")
        f.write("| Mutant | Injected bug | Result | Caught by | Time (s) |\n|---|---|---|---|---|\n")
        for mid, desc, st, by, dt in rows:
            f.write(f"| {mid} | {desc} | {st} | {by} | {dt:.1f} |\n")
        f.write(f"\nScore: {killed}/{killed + survived} killed ({100 * score:.0f}%), "
                f"{survived} survived, {invalid} invalid\n")
    print(f"Score: {killed}/{killed + survived} killed ({100 * score:.0f}%), {survived} survived, {invalid} invalid")
    sys.exit(0 if (score >= args.min_score and invalid == 0) else 1)


if __name__ == "__main__":
    main()
