#!/bin/bash
# Tuesday afternoon queue (V4.5): drawishness gate -> conversion tests -> clock-softening proxy ->
# training pilot on the decisive mix -> scale-matched export -> grade -> real-clock proxy.
# Everything logs to ../data/afternoon.log; nothing uploads.
cd "/Users/architbhardwaj/Desktop/AI Chessathon/bini_v4" || exit 1
PY=../aichessathon-starter/.venv/bin/python
say() { echo "$(date '+%F %T') $*"; }

# 1. the drawishness 10 s gate
until grep -qE "^\[300/300\]|terminations" ../bini/tests/arena/draw_vs_v4.log 2>/dev/null; do sleep 120; done
say "draw gate: $(grep -E '^\[' ../bini/tests/arena/draw_vs_v4.log | tail -1 | cut -c1-70)"
sleep 20

# 2. conversion tests, both builds in parallel (two processes on an otherwise quiet Mac)
for d in bini_v45_draw bini_v4final; do
  ( cd ../$d && $PY tests/test_conversion2.py tests/pos/drawn.epd --games 6 --sf-nodes 400000 --ms 1000 --drawn > ../data/conv_drawn_$d.log 2>&1; $PY tests/test_conversion2.py tests/pos/marginal.epd --games 40 --sf-nodes 400000 --ms 1000 --min-rate 0 > ../data/conv_marginal_$d.log 2>&1 ) &
done
wait
for d in bini_v45_draw bini_v4final; do say "$d drawn: $(tail -1 ../data/conv_drawn_$d.log | cut -c1-90) | marginal: $(tail -1 ../data/conv_marginal_$d.log | cut -c1-90)"; done

# 3. clock softening at the real clock vs the 20k proxy (baseline: V3's net 46.3%, V4 = same net)
say "proxy v45soft_20k"
( cd ../bini_v45_soft && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v45soft_20k_a.log 2>&1 ) &
( cd ../bini_v45_soft && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v45soft_20k_b.log 2>&1 ) &
wait
say "v45soft_20k: $(grep 'PROXY MATCH' ../data/proxy_v45soft_20k_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_v45soft_20k_b.log | cut -c1-60)"

# 4. training pilot: one epoch on the decisive mix once >= 8 decisive chunks (1.6M rows) are local
until [ "$(ls ../data/selfplay/dec/chunk_*.npz 2>/dev/null | wc -l | tr -d ' ')" -ge 8 ]; do bash tools/pull_selfplay.sh > /dev/null 2>&1; sleep 300; done
say "pilot: $(ls ../data/selfplay/dec/chunk_*.npz | wc -l | tr -d ' ') decisive chunks local, training 1 epoch"
EPOCHS=1 OUT=../data/nnue_v45p.safetensors bash tools/run_v45.sh > ../data/train_v45p.log 2>&1
say "pilot trained: $(grep -E 'epoch|val' ../data/train_v45p.log | tail -2 | tr '\n' ' ' | cut -c1-160)"
slope=$(BINI_NNUE=../data/nnue_v45p.safetensors $PY tools/net_diag.py ../data/site_labelled/chunk_0001.npz --scale 0.85 --n 18675 2>/dev/null | grep -o "scale slope pred/label [0-9.]*" | awk '{print $4}')
ratio=$($PY -c "print(round(1.305/float('${slope:-1.305}'),3))")
say "pilot slope $slope -> out-scale $ratio"
$PY tools/export_from_pt.py ../data/nnue_v45p.pt ../data/nnue_v45p_s.safetensors --buckets 8 --hidden 512 --act crelu --out-buckets 1 --out-scale "$ratio" 2>&1 | tail -1
bash tools/grade_export.sh ../data/nnue_v45p_s.safetensors v45p 2>&1 | tail -4
rm -rf ../bini_v45p && rsync -a --exclude __pycache__ --exclude tests/arena ./ ../bini_v45p/ && cp ../data/nnue_v45p_s.safetensors ../bini_v45p/nnue.safetensors
say "proxy v45p_20k"
( cd ../bini_v45p && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v45p_20k_a.log 2>&1 ) &
( cd ../bini_v45p && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes 20000 --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_v45p_20k_b.log 2>&1 ) &
wait
say "v45p_20k: $(grep 'PROXY MATCH' ../data/proxy_v45p_20k_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_v45p_20k_b.log | cut -c1-60)"
say "afternoon queue done"
