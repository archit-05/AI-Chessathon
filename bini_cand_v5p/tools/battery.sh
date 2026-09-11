#!/bin/bash
# The full battery on an assembled candidate directory ($1, default ../bini_v4final). Run on a
# quiet Mac; every line must pass.
set -u
cd "$(dirname "$0")/.."
D=${1:-../bini_v4final}; PY=../aichessathon-starter/.venv/bin/python
cd "$D"
echo "=== $(date '+%F %T') battery on $D"
echo "--- compile/init x2"; for i in 1 2; do $PY -c "import time; t=time.perf_counter(); import agent; print('init %.1fs ready %s book %d' % (time.perf_counter()-t, agent._ready.is_set(), len(agent._BOOK)))" 2>&1 | grep init; done
echo "--- wrapper state";       $PY tests/test_agent_state.py 2>&1 | tail -3
echo "--- NNUE exactness";      $PY tests/test_nnue.py 2>&1 | grep "== reference"
echo "--- board";               $PY tests/test_board.py 5000 2>&1 | tail -2
echo "--- search gate";         $PY tests/test_search.py 2>&1 | grep -E "mate in|tactics:|gate 2"
echo "--- puzzles 40";          $PY tests/test_tactics.py tests/pos/puzzles.epd --ms 2000 --min-rate 0.9 2>&1 | tail -1
echo "--- blunder set (platform budget)"; $PY tests/test_blunders.py 3800 2>&1 | grep -E "REPEATED|regression"
echo "--- harvest set (our tagged errors, 2.5 s)"; $PY - <<'PYX' 2>&1 | tail -1
import sys; sys.path.insert(0,'.'); import bini_engine as E
from pathlib import Path
eng=E.Engine(use_nnue=True); E.warm_up(eng); rows=[l for l in Path('tests/pos/harvest.epd').read_text().splitlines() if l.strip()]; rep=0
for ln in rows:
    fen,avoid=ln.split(';')[0].strip(), ln.split(';')[1].split()[1]; eng.new_game(); eng.set_position(fen,[]); mv,sc,d=eng.think(2500,5000,log=False); rep+= (mv==avoid)
print(f"harvest: {len(rows)-rep}/{len(rows)} avoided")
PYX
echo "--- torture 10 vs random, then 10 with the fallback forced"; $PY tests/test_vs_random.py 2>&1 | tail -1; BINI_FORCE_FALLBACK=1 $PY tests/test_vs_random.py 2>&1 | tail -1
echo "--- real-clock pressure 10"; $PY tests/pressure_games.py tests/pos/sharp.epd --games 10 2>&1 | tail -3
echo "=== $(date '+%F %T') battery done"
