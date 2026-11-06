#!/usr/bin/env bash
# Build a firmware source from fw/ on top of LiteX's bare-metal demo scaffold.
# Usage: scripts/build_fw.sh [source.c]   (default: main.c)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-main.c}"
BUILD="$ROOT/build/sim"
[ -f "$BUILD/software/include/generated/variables.mak" ] || { echo "Run scripts/gen_soc.sh first"; exit 1; }
[ -f "$ROOT/fw/$SRC" ] || { echo "fw/$SRC not found"; exit 1; }
DEMO="$(python3 -c 'import litex, os; print(os.path.join(os.path.dirname(litex.__file__), "soc/software/demo"))')"
OUT="$ROOT/build/fw"
rm -rf "$OUT" && mkdir -p "$OUT"
cp -r "$DEMO"/. "$OUT"/
cp "$ROOT/fw/$SRC" "$OUT/main.c"
cp "$ROOT/fw/gemm_regs.h" "$OUT"/
sed -i 's/>[[:space:]]*sram/> main_ram/g' "$OUT/linker.ld"
if grep -q '^void isr(void)' "$ROOT/fw/$SRC"; then
    sed -i '/common.mak/a LDFLAGS += -Wl,--allow-multiple-definition' "$OUT/Makefile"
fi
rm -f "$ROOT/build/gemm_fw.bin"   # never leave a stale binary behind
cd "$OUT"
BUILD_DIR="$BUILD" make
cp demo.bin "$ROOT/build/gemm_fw.bin"
echo "Built $ROOT/build/gemm_fw.bin from fw/$SRC"
