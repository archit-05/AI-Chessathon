#!/bin/bash
# Overnight chain on the Mac (Mon 7 -> Tue 8 Sept):
#   wait for v4a -> pull chunks -> v4b fine-tune -> diagnose v4b (slope) -> scale-matched export
#   -> candidate dir bini_v4b -> 300-game gate vs V3 at 6 workers -> v4d (20 epochs, tournament mix)
set -u
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
# never start a gate or a training run on a loaded machine (the contamination rule)
wait_load() { while true; do l=$(uptime | sed 's/.*load averages*: *//' | cut -d' ' -f1 | tr -d ','); ok=$($PY -c "print(1 if float('$l') <= $1 else 0)"); [ "$ok" = "1" ] && return; echo "$(date '+%F %T') load $l > $1, waiting"; sleep 120; done; }
LOG=../data/train_v4a.log
until grep -q "epoch 5 done" "$LOG" && [ "$(grep -c '^exported' "$LOG")" -ge 6 ]; do sleep 120; done
echo "$(date '+%F %T') v4a finished; pulling chunks"
bash tools/pull_selfplay.sh
wait_load 10
echo "$(date '+%F %T') starting v4b"
RESUME=../data/nnue_v4a.pt bash tools/run_v4b.sh > ../data/train_v4b.log 2>&1
echo "$(date '+%F %T') v4b finished"
# scale matching: slope of v4b vs the site labels, relative to v3b's 1.305 (the scale the search
# margins were tuned on); re-export with the ratio, then verify
slope=$(BINI_NNUE=../data/nnue_v4b.safetensors $PY tools/net_diag.py ../data/site_labelled/chunk_0001.npz --scale 0.85 --n 18675 2>/dev/null | grep -o "scale slope pred/label [0-9.]*" | awk '{print $4}')
echo "$(date '+%F %T') v4b slope $slope"
ratio=$($PY -c "print(round(1.305/float('${slope:-1.305}'),3))")
echo "$(date '+%F %T') out-scale ratio $ratio"
$PY tools/export_from_pt.py ../data/nnue_v4b.pt ../data/nnue_v4b_s.safetensors --buckets 8 --hidden 512 --act screlu --out-buckets 8 --factorise --out-scale $ratio
BINI_NNUE=../data/nnue_v4b_s.safetensors $PY tools/net_diag.py ../data/site_labelled/chunk_0001.npz --scale 0.85 --n 18675 2>/dev/null | grep "positions:"
# candidate directory: bini_v4 code + the scale-matched v4b net
rm -rf ../bini_v4b && rsync -a --exclude __pycache__ --exclude tests/arena ../bini_v4/ ../bini_v4b/ && cp ../data/nnue_v4b_s.safetensors ../bini_v4b/nnue.safetensors
BINI_NNUE=../bini_v4b/nnue.safetensors $PY tests/test_nnue.py 2>&1 | tail -1
BINI_NNUE=../bini_v4b/nnue.safetensors $PY tests/test_train_consistency.py ../data/nnue_v4b.pt 2>&1 | tail -1 || true
wait_load 10
echo "$(date '+%F %T') gate v4b vs V3 (two workers)"
BINI_TT_BITS=22 bash tools/gate.sh ../bini_v4b ../bini_v3b 300 10000 100 2 v4b_vs_v3
echo "$(date '+%F %T') refreshing the whole-site set with tonight's rounds"
( cd ../intel && nice -n 10 $PY scrape_all.py --pause 0.3 > ../data/scrape_all_night.log 2>&1 ) || true
tail -1 ../data/scrape_all_night.log
nice -n 10 $PY tools/site_labelled.py ../intel/raw/cache/games ../data/site_all > ../data/site_all_build_night.log 2>&1 || true
tail -2 ../data/site_all_build_night.log
wait_load 10
echo "$(date '+%F %T') starting v4d: 20 epochs from scratch on the tournament-weighted mix"
bash tools/pull_selfplay.sh
bash tools/run_v4d.sh > ../data/train_v4d.log 2>&1
echo "$(date '+%F %T') v4d finished"
echo "$(date '+%F %T') overnight chain done"
