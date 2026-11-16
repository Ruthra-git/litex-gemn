#!/usr/bin/env bash
# Run the simulation with the console captured to a log file (the terminal stays interactive).
# Usage: [GEMM_LANES=8] scripts/run_sim_logged.sh docs/day6_run_L8.log
set -e
cd "$(dirname "$0")/.."
LOG="${1:?usage: run_sim_logged.sh <logfile>}"
script -q -f -c "./scripts/run_sim.sh" "$LOG"
tr -d '\r' < "$LOG" > "$LOG.clean" && mv "$LOG.clean" "$LOG"
echo "saved $LOG ($(grep -c '^CSV' "$LOG") CSV lines)"
