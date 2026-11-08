#!/usr/bin/env bash
# Generate the Zephyr devicetree overlay and Kconfig flags from the simulated SoC's csr.json.
set -e
cd "$(dirname "$0")/.."
source "$HOME/litex/venv/bin/activate"
CSR="$(find build/sim -maxdepth 2 -name csr.json | head -1)"
[ -n "$CSR" ] || { echo "csr.json not found under build/sim (run scripts/gen_soc.sh first)"; exit 1; }
mkdir -p build/zephyr
if command -v litex_json2dts_zephyr >/dev/null 2>&1; then
  litex_json2dts_zephyr --dts build/zephyr/soc.overlay --config build/zephyr/soc.conf "$CSR"
else
  TOOL="$(python3 -c 'import litex,os;print(os.path.join(os.path.dirname(litex.__file__),"tools","litex_json2dts_zephyr.py"))')"
  python3 "$TOOL" --dts build/zephyr/soc.overlay --config build/zephyr/soc.conf "$CSR"
fi
cp build/zephyr/soc.overlay build/zephyr/hello.overlay
cat build/zephyr/soc.overlay zephyr/app/gemm.overlay > build/zephyr/app.overlay
if [ -f zephyr/app/ram.overlay ]; then
  cat zephyr/app/ram.overlay >> build/zephyr/hello.overlay
  cat zephyr/app/ram.overlay >> build/zephyr/app.overlay
fi
echo "CSR file: $CSR"
echo "--- soc.conf ---"
cat build/zephyr/soc.conf
