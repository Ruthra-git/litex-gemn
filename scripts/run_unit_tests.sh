#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../tb"
for L in 4 8 16; do
  echo "=== LANES=$L ==="
  make LANES=$L
  if grep -q "<failure" results.xml; then
    echo "FAILED at LANES=$L"; exit 1
  fi
done
echo "ALL PASSED"

