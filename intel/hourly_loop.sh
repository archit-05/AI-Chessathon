#!/bin/bash
# Hourly intel loop: at :41 past every hour, scrape + analyse + render (no Stockfish, no engine),
# append a 15-line snapshot to logs/hourly.log, regenerate the V5 brief in place, commit intel/.
#
#   nohup ./hourly_loop.sh >> logs/hourly_loop.out 2>&1 &
#
# One niced process at a time; stop it with:  kill <pid>   (pid is in logs/hourly_loop.pid)
set -u
cd "$(dirname "$0")"
PY="$(cd .. && pwd)/aichessathon-starter/.venv/bin/python"
[ -x "$PY" ] || PY=python3
BRIEF="${BRIEF:-$(ls -1 V5_INTEL_*.txt 2>/dev/null | tail -1)}"
[ -n "$BRIEF" ] || BRIEF="V5_INTEL_$(date '+%Y%m%d_%H%M').txt"
mkdir -p logs
echo $$ > logs/hourly_loop.pid
echo "hourly loop started $(date '+%F %T'), pid $$, brief $BRIEF"

while true; do
    # sleep until the next :41
    now_m=$(date '+%-M'); now_s=$(date '+%-S')
    wait_s=$(( ((41 - now_m + 60) % 60) * 60 - now_s ))
    [ "$wait_s" -le 0 ] && wait_s=$((wait_s + 3600))
    sleep "$wait_s"

    echo "=== $(date '+%F %T') refresh ==="
    if nice -n 15 ./refresh.sh >> logs/hourly_refresh.out 2>&1; then
        # keep the ladder history going (refresh.sh itself does not archive the leaderboard)
        cp raw/leaderboard.json "raw/ladder/leaderboard_$(date '+%Y%m%d_%H%M').json" 2>/dev/null
        {
            nice -n 15 "$PY" v5_brief.py --snapshot
            echo ""
        } >> logs/hourly.log 2>&1
        nice -n 15 "$PY" v5_brief.py --out "$BRIEF"
        git -C .. add intel
        if ! git -C .. diff --cached --quiet -- intel; then
            git -C .. commit -q -m "intel: hourly refresh $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- intel && echo "committed"
        fi
    else
        echo "refresh failed at $(date '+%F %T'); see logs/hourly_refresh.out" >> logs/hourly.log
    fi
done
