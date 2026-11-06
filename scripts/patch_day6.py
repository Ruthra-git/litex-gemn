#!/usr/bin/env python3
import sys

p = "rtl/gemm_wb.v"
s = open(p).read()
edits = [
    ("{16'h0005, 8'd4, LANES8}", "{16'h0006, 8'd4, LANES8}"),
    ("wire [31:0]  dma_cycles;",
     "wire [31:0]  dma_cycles;\n    wire [31:0]  dma_xfers, dma_waits;"),
    (".cycles     (dma_cycles),",
     ".cycles     (dma_cycles),\n        .xfers      (dma_xfers),\n        .waits      (dma_waits),"),
    ("4'd9:    rdata = dma_cycles;",
     "4'd9:    rdata = dma_cycles;\n                4'd10:   rdata = dma_xfers;\n                4'd11:   rdata = dma_waits;"),
]
if "dma_xfers" in s:
    print("gemm_wb.v: already patched")
else:
    for old, new in edits:
        if s.count(old) != 1:
            print("gemm_wb.v NOT patched; expected exactly one match of:", old)
            print("send me: grep -n 'dma_cycles\\|INFO_VAL' rtl/gemm_wb.v")
            sys.exit(1)
    for old, new in edits:
        s = s.replace(old, new)
    open(p, "w").write(s)
    print("gemm_wb.v: patched")

p = "tb/test_gemm_wb.py"
s = open(p).read()
old = "assert (info >> 16) == 0x0005"
if old in s:
    open(p, "w").write(s.replace(old, "assert (info >> 16) == 0x0006"))
    print("test_gemm_wb.py: version check updated to 6")
else:
    print("test_gemm_wb.py: version check not found (already updated?)")
