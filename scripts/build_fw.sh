#!/usr/bin/env bash
# Build fw/main.c on top of LiteX's bare-metal demo scaffold (Makefile, linker script, isr).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/sim"
[ -f "$BUILD/software/include/generated/variables.mak" ] || { echo "Run scripts/gen_soc.sh first"; exit 1; }
DEMO="$(python3 -c 'import litex, os; print(os.path.join(os.path.dirname(litex.__file__), "soc/software/demo"))')"
OUT="$ROOT/build/fw"
rm -rf "$OUT" && mkdir -p "$OUT"
cp -r "$DEMO"/. "$OUT"/
cp "$ROOT/fw/main.c" "$ROOT/fw/gemm_regs.h" "$OUT"/
sed -i 's/>[[:space:]]*sram/> main_ram/g' "$OUT/linker.ld"
cd "$OUT"
BUILD_DIR="$BUILD" make
cp demo.bin "$ROOT/build/gemm_fw.bin"
echo "Built $ROOT/build/gemm_fw.bin"
