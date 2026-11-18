#!/usr/bin/env bash
# Final gate. Run from a clean, committed tree with the OSS CAD Suite environment sourced.
cd "$(dirname "$0")/.."
fail=0
run() { echo "== $*"; "$@" || { echo "FAILED: $*"; fail=1; }; }
[ -z "$(git status --porcelain)" ] || { echo "FAILED: working tree not clean"; fail=1; }
run python3 scripts/day10_consistency.py
run make static
run make budget
run make formal
run make test
run make soc-check
[ $fail -eq 0 ] && echo "RELEASE GATE OK" || echo "RELEASE GATE FAILED"
exit $fail
