#!/bin/bash
# Game-based checkpoint of a training run's current export (V5 Plan 18:15): scale-match on the x86
# box (torch there, never on the training Mac), build the candidate (V4 engine + net), exactness +
# blunder set on the x86 box, then N games at 5 s vs V3's net with the generators paused.
#   bash tools/checkpoint_gate.sh <name> <games>      (expects ../data/<name>.pt and .safetensors, already on $BOX:chess/data/)
set -uo pipefail
cd "$(dirname "$0")/.."
BOX=${BOX:-$(ssh -o BatchMode=yes -o ConnectTimeout=5 gcp-x86b true 2>/dev/null && echo gcp-x86b || echo gcp-x86)}
NAME=$1; GAMES=${2:-40}
say() { echo "$(date '+%F %T') $*"; }
ssh -o BatchMode=yes $BOX "bash -s" <<REMOTE > ../data/ckpt_${NAME}_x86.log 2>&1
cd ~/chess/bini_v5
P=../aichessathon-starter/.venv/bin/python
slope=\$(BINI_NNUE=~/chess/data/$NAME.safetensors nice -n 5 \$P tools/net_diag.py ~/chess/data/site_labelled/chunk_0001.npz --scale 0.85 --n 18675 2>/dev/null | tee ~/chess/data/diag_$NAME.log | grep -o "scale slope pred/label [0-9.]*" | awk '{print \$4}')
ratio=\$(\$P -c "print(round(1.305/float('\${slope:-1.305}'),3))")
echo "slope \$slope ratio \$ratio"
grep -E "MAE|pieces" ~/chess/data/diag_$NAME.log | head -3
~/chess/venv/bin/python tools/export_from_pt.py ~/chess/data/$NAME.pt ~/chess/data/${NAME}_s.safetensors --buckets 8 --hidden 512 --act crelu --out-buckets 1 --out-scale "\$ratio" 2>&1 | tail -1
REMOTE
cat ../data/ckpt_${NAME}_x86.log
scp -q $BOX:chess/data/${NAME}_s.safetensors ../data/${NAME}_s.safetensors
CAND=../bini_cand_$NAME
rm -rf "$CAND" && rsync -a --exclude __pycache__ --exclude tests/arena --exclude submission.zip ../bini_v4final/ "$CAND/" && cp ../data/${NAME}_s.safetensors "$CAND/nnue.safetensors" && cp tests/pos/blunders.epd "$CAND/tests/pos/blunders.epd"
rsync -a --exclude __pycache__ "$CAND/" $BOX:chess/bini_cand_$NAME/
say "exactness + blunder set on x86"
ssh -o BatchMode=yes $BOX "bash ~/chess/bini_v5/tools/x86_quiet_run.sh ~/chess/bini_cand_$NAME bash -c 'P=../aichessathon-starter/.venv/bin/python; \$P tests/test_nnue.py 2>&1 | tail -1; \$P tests/test_blunders.py 3000 2>&1 | tail -1'"
say "$GAMES games at 5 s vs V3's net on x86"
bash tools/x86_gate.sh bini_cand_$NAME bini_v4final $GAMES ckpt_$NAME 5000 50
say "CHECKPOINT $NAME DONE"
