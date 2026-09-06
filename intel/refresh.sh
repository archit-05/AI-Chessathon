#!/bin/bash
# Refresh the opponent dossiers and the strategy report in one command:
#   1. scrape.py   - leaderboard, the current top-N team pages (+ Opus Carlsen), game pages not yet cached
#                    (PGN, opening, site review, the site's per-position evaluations)
#   2. analyse.py  - per-move facts from the site's embedded evaluations (Stockfish 16 depth 16; no engine, ~1 min)
#   3. report.py   - dossiers <rank>_<Bot>.txt, 00_summary.txt, history/summary_<stamp>.{txt,json}
#   4. strategy.py - STRATEGY.txt; full and --auto runs also archive the next strategy/Strategy_N.txt
# Usage: ./refresh.sh             full refresh (network + site-based analysis + render + numbered strategy)
#        ./refresh.sh --auto      the same, then commit intel/ (what the three-hourly schedule runs)
#        ./refresh.sh --no-scrape re-analyse and re-render without touching the network
#        ./refresh.sh --report    re-render only (e.g. after editing notes/*.txt); no numbered entry
#        ./refresh.sh --deep      optional: our own Stockfish 19 pass at 120k nodes (one niced process,
#                                 hours; cached in raw/evals.jsonl) instead of the site's evaluations
set -euo pipefail
cd "$(dirname "$0")"
PY="$(cd .. && pwd)/aichessathon-starter/.venv/bin/python"
[ -x "$PY" ] || PY=python3
MODE="${1:-full}"
if [ "$MODE" = "full" ] || [ "$MODE" = "--auto" ]; then
    nice -n 15 "$PY" scrape.py
fi
if [ "$MODE" = "--deep" ]; then
    nice -n 15 "$PY" analyse.py --source sf
elif [ "$MODE" != "--report" ]; then
    nice -n 15 "$PY" analyse.py --source site | tail -3
fi
nice -n 15 "$PY" report.py
if [ "$MODE" = "full" ] || [ "$MODE" = "--auto" ]; then
    nice -n 15 "$PY" strategy.py --archive | tail -1
else
    nice -n 15 "$PY" strategy.py > /dev/null
fi
echo "strategy report: $(pwd)/STRATEGY.txt"
if [ "$MODE" = "--auto" ]; then
    git -C .. add intel
    if ! git -C .. diff --cached --quiet; then
        git -C .. commit -q -m "intel: refresh $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && echo "committed"
    fi
fi
