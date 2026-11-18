#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../tb"
for DUT in core wb dma; do
  for L in ${LANES_LIST:-4 8 16}; do
    echo "=== DUT=$DUT LANES=$L ==="
    rm -f results.xml
    make DUT=$DUT LANES=$L
    [ -f results.xml ] || { echo "no results.xml at DUT=$DUT LANES=$L"; exit 1; }
    if grep -q "<failure" results.xml; then
      echo "FAILED at DUT=$DUT LANES=$L"; exit 1
    fi
  done
done
echo "ALL PASSED"
