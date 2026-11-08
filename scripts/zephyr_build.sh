
#!/usr/bin/env bash
# Usage: scripts/zephyr_build.sh hello|app

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-app}"

source "$ROOT/scripts/zephyr_env.sh"

case "$APP" in
    hello)
        SRC="$ROOT/zephyr/hello"
        OVERLAY="$ROOT/build/zephyr/hello.overlay"
        ;;
    app)
        SRC="$ROOT/zephyr/app"
        OVERLAY="$ROOT/build/zephyr/app.overlay"
        ;;
    *)
        echo "Usage: $0 hello|app"
        exit 1
        ;;
esac

[ -f "$OVERLAY" ] || {
    echo "ERROR: Overlay not found: $OVERLAY"
    echo "Run scripts/zephyr_overlay.sh first."
    exit 1
}

BUILD="$ROOT/build/zephyr_$APP"

rm -f "$BUILD/zephyr/zephyr.bin"

cd "$ZEPHYR_BASE"

xargs < "$ROOT/build/zephyr/soc.conf" \
    west build -p always \
    -b litex_vexriscv \
    "$SRC" \
    -d "$BUILD" \
    -- \
    -DDTC_OVERLAY_FILE="$OVERLAY" \
    -DEXTRA_CFLAGS="${GEMM_EXTRA_CFLAGS:-}"

[ -f "$BUILD/zephyr/zephyr.bin" ] || {
    echo "ERROR: zephyr.bin was not generated."
    exit 1
}

echo "SUCCESS: Zephyr binary generated."
ls -lh "$BUILD/zephyr/zephyr.bin"
