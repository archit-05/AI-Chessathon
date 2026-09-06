#!/bin/bash
# Refresh the opponent dossiers in one command:
#   1. scrape.py  - leaderboard, the current top-10 team pages (+ Opus Carlsen) and any game pages not yet cached
#   2. analyse.py - Stockfish 19 at 120k nodes per new position (cached by FEN in raw/evals.jsonl)
#   3. report.py  - dossiers <rank>_<Bot>.txt, 00_summary.txt, history/summary_<stamp>.{txt,json}
# Everything runs under nice -n 15 with a single Stockfish process.  Safe to re-run; only new games cost time.
# Usage: ./refresh.sh            (full refresh)
#        ./refresh.sh --no-scrape  (re-analyse and re-render only)
#        ./refresh.sh --report     (re-render only, e.g. after editing notes/*.txt)
set -euo pipefail
cd "$(dirname "$0")"
PY="$(cd .. && pwd)/aichessathon-starter/.venv/bin/python"
[ -x "$PY" ] || PY=python3
MODE="${1:-full}"
if [ "$MODE" = "full" ]; then
    nice -n 15 "$PY" scrape.py
fi
if [ "$MODE" = "full" ] || [ "$MODE" = "--no-scrape" ]; then
    nice -n 15 "$PY" analyse.py
fi
nice -n 15 "$PY" report.py
