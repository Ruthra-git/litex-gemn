#!/usr/bin/env python3
"""Print per-module LUT4 counts from a hierarchical Yosys stat file (own logic only)."""
import re
import sys

text = open(sys.argv[1], errors="ignore").read()
res = {}
for block in ("\n" + text).split("\n=== ")[1:]:
    m = re.match(r"(\S+) ===", block)
    if not m:
        continue
    name = m.group(1)
    lut = re.search(r"\bLUT4\s+(\d+)", block)
    for key in ("gemm_core", "gemm_dma", "gemm_wb"):
        if key in name and lut:
            res[key] = int(lut.group(1))
if len(res) != 3:
    sys.exit(1)
print(f"Own-logic LUT4 per module at LANES=4 (hierarchical Yosys statistics): "
      f"gemm_core {res['gemm_core']}, gemm_dma {res['gemm_dma']}, gemm_wb {res['gemm_wb']}")
