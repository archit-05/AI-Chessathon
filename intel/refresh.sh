#!/bin/bash
# Refresh the opponent dossiers and the strategy report in one command:
#   1. scrape.py   - leaderboard, the current top-N team pages (+ Opus Carlsen) and any game pages not yet cached
#   2. analyse.py  - Stockfish 19 at 120k nodes per new position (cached by FEN in raw/evals.jsonl)
#   3. report.py   - dossiers <rank>_<Bot>.txt, 00_summary.txt, history/summary_<stamp>.{txt,json}
#   4. strategy.py - STRATEGY.txt (reverse-engineered profiles + what it means for our build)
# Everything runs under nice -n 15 with a single Stockfish process.  Safe to re-run; only new games cost time.
# Usage: ./refresh.sh             full refresh, analysis in the foreground (first run takes hours)
#        ./refresh.sh --auto      scrape, start the analysis in the background if none is running, render, commit intel/
#        ./refresh.sh --no-scrape re-analyse and re-render only
#        ./refresh.sh --report    re-render only (e.g. after editing notes/*.txt)
set -euo pipefail
cd "$(dirname "$0")"
PY="$(cd .. && pwd)/aichessathon-starter/.venv/bin/python"
[ -x "$PY" ] || PY=python3
MODE="${1:-full}"
if [ "$MODE" = "full" ] || [ "$MODE" = "--auto" ]; then
    nice -n 15 "$PY" scrape.py
fi
if [ "$MODE" = "full" ] || [ "$MODE" = "--no-scrape" ]; then
    nice -n 15 "$PY" analyse.py
elif [ "$MODE" = "--auto" ]; then
    if pgrep -f "analyse.py" >/dev/null; then
        echo "analysis already running; rendering with what is cached so far"
    else
        mkdir -p logs
        nohup nice -n 15 "$PY" analyse.py > "logs/analyse_$(date +%Y%m%d_%H%M).log" 2>&1 &
        echo "analysis started in the background (pid $!)"
        sleep 20
    fi
fi
nice -n 15 "$PY" report.py
nice -n 15 "$PY" strategy.py > /dev/null
echo "strategy report: $(pwd)/STRATEGY.txt"
if [ "$MODE" = "--auto" ]; then
    git -C .. add intel
    if ! git -C .. diff --cached --quiet; then
        git -C .. commit -q -m "intel: refresh $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && echo "committed"
    fi
fi
