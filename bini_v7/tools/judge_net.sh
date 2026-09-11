#!/bin/bash
# Judge a trained net (V5 Plan s3.1): slope on the held-out site chunk -> scale-matched export ->
# candidate dir (V4 engine + this net, so the net is judged alone) -> N-game pilot on the VM at
# 5 s + 0.05 s vs V4 (generators paused meanwhile) -> tally.
#   bash tools/judge_net.sh ../data/nnue_v5p.pt v5p [games=40]
set -uo pipefail
cd "$(dirname "$0")/.."
PY=../aichessathon-starter/.venv/bin/python
PT=${1:?path to .pt}; NAME=${2:?candidate name}; GAMES=${3:-40}
ARCH=${ARCH:---buckets 8 --hidden 512 --act crelu --out-buckets 1}
say() { echo "$(date '+%F %T') $*"; }
SF="${PT%.pt}.safetensors"
CAND=../bini_cand_$NAME
if [ "${SKIP_LOCAL:-0}" = "1" ]; then say "skipping local steps for $NAME"; else
slope=$(BINI_NNUE=$SF $PY tools/net_diag.py ../data/site_labelled/chunk_0001.npz --scale 0.85 --n 18675 2>/dev/null | tee ../data/diag_$NAME.log | grep -o "scale slope pred/label [0-9.]*" | awk '{print $4}')
ratio=$($PY -c "print(round(1.305/float('${slope:-1.305}'),3))")
say "$NAME slope $slope -> out-scale $ratio; diag: $(grep -E 'MAE|all' ../data/diag_$NAME.log | head -2 | tr '\n' ' ' | cut -c1-160)"
$PY tools/export_from_pt.py "$PT" "../data/nnue_${NAME}_s.safetensors" $ARCH --out-scale "$ratio" 2>&1 | tail -1
rm -rf "$CAND" && rsync -a --exclude __pycache__ --exclude tests/arena --exclude submission.zip ../bini_v4final/ "$CAND/" && cp "../data/nnue_${NAME}_s.safetensors" "$CAND/nnue.safetensors"
BINI_NNUE=$CAND/nnue.safetensors $PY tests/test_nnue.py 2>&1 | tail -1
( cd "$CAND" && $PY tests/test_blunders.py 3000 2>&1 | tail -2 )
fi
if [ "${SKIP_VM:-0}" = "1" ]; then say "$NAME candidate ready at $CAND (VM games skipped)"; exit 0; fi
say "pilot on the VM: $GAMES games at 5 s vs V4"
rsync -a --exclude __pycache__ "$CAND/" priorcrypto-vm:chess/bini_cand_$NAME/
ssh -o BatchMode=yes priorcrypto-vm "bash -s" <<REMOTE
set -e
cd ~/chess
# pause the generators (SIGSTOP), play, resume (SIGCONT)
pkill -STOP -f "selfplay_sf.py --out" || true; pkill -STOP -x stockfish || true
cd bini_v4final && BINI_TT_BITS=22 nice -n 5 ../aichessathon-starter/.venv/bin/python tools/arena_par.py --agent ../bini_cand_$NAME --opponent ../bini_v4final --games $GAMES --workers 4 --base-ms 5000 --inc-ms 50 --openings tools/curated.epd > ../gates/pilot_$NAME.log 2>&1 || true
pkill -CONT -f "selfplay_sf.py --out" || true; pkill -CONT -x stockfish || true
grep -E "^\[" ../gates/pilot_$NAME.log | tail -1
REMOTE
say "$NAME pilot done"
