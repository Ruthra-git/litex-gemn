#!/usr/bin/env bash
# Yosys + nextpnr-ecp5 resource/timing sweep of the accelerator over LANES and seeds.
# Usage: [LANES_LIST="4 8 16"] [SEEDS="1 2 3"] [DEVICE=25k] [PACKAGE=CABGA381] [SPEED=6]
#        [TARGET_MHZ=100] [TAG=base] [SYNTH_FLAGS=""] [OOC=1] scripts/synth_sweep.sh
set -e
cd "$(dirname "$0")/.."
LANES_LIST="${LANES_LIST:-4 8 16}"
SEEDS="${SEEDS:-1 2 3}"
DEVICE="${DEVICE:-25k}"
PACKAGE="${PACKAGE:-CABGA381}"
SPEED="${SPEED:-6}"
TARGET_MHZ="${TARGET_MHZ:-100}"
TAG="${TAG:-base}"
SYNTH_FLAGS="${SYNTH_FLAGS:-}"
OOC="${OOC:-1}"
OOC_FLAG=""
[ "$OOC" = "1" ] && OOC_FLAG="--out-of-context"
OUT="build/synth/$TAG"
CORE="${CORE_FILE:-rtl/gemm_core.v}"
mkdir -p "$OUT"

for L in $LANES_LIST; do
  D="$OUT/L$L"
  mkdir -p "$D"
  cat > "$D/synth.ys" <<YSEOF
read_verilog -sv $CORE rtl/gemm_dma.v rtl/gemm_wb.v
chparam -set LANES $L gemm_wb
synth_ecp5 -top gemm_wb $SYNTH_FLAGS -json $D/netlist.json
YSEOF
  echo "== yosys LANES=$L =="
  yosys -q -l "$D/yosys.log" "$D/synth.ys"
  for S in $SEEDS; do
    R="$D/s$S"
    mkdir -p "$R"
    echo "== nextpnr LANES=$L seed=$S =="
    if ! nextpnr-ecp5 --json "$D/netlist.json" "--$DEVICE" --package "$PACKAGE" --speed "$SPEED" \
         --freq "$TARGET_MHZ" --seed "$S" --timing-allow-fail $OOC_FLAG \
         --report "$R/report.json" --log "$R/nextpnr.log" > /dev/null 2>&1; then
      echo "nextpnr failed for LANES=$L seed=$S (see $R/nextpnr.log)"
    fi
  done
done

# critical-path excerpt for the first seed of each LANES value
S1="$(echo $SEEDS | cut -d' ' -f1)"
for L in $LANES_LIST; do
  LOG="$OUT/L$L/s$S1/nextpnr.log"
  N="$(grep -n 'Critical path report for clock' "$LOG" 2>/dev/null | tail -1 | cut -d: -f1)"
  if [ -n "$N" ]; then
    sed -n "${N},$((N+45))p" "$LOG" > "docs/day8_critical_path_${TAG}_L$L.txt"
  fi
done

python3 scripts/day8_parse.py "$OUT" "$TARGET_MHZ" "$DEVICE" > "docs/day8_resources_$TAG.csv"
cat "docs/day8_resources_$TAG.csv"
