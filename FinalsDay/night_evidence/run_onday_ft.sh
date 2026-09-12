#!/bin/bash
# On-day fine-tune (pretrain plan §8): resume a chosen checkpoint, <= 3 sb at lr 0.0003 on clean_d10 (+ optional
# targeted data at --spice pct), export with bound + sanity, mirror. usage: run_onday_ft.sh <ckpt_dir> <net_id> [spice.bin:pct] [sb=3]
set -u; CKD="$1"; ID="$2"; SPICE="${3:-}"; SB=${4:-3}; cd ~/chess; S=~/chess/logs/onday_$ID.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py
DATA=~/chess/data/ft/clean_d10_shuf.bin
if [ -n "$SPICE" ]; then $V bini_v7/tools/mix_corpus.py ~/chess/data/ft/onday_$ID.bin --base $DATA --spice "$SPICE" 2>&1 | tee -a $S || { log "mix refused"; exit 1; }; DATA=~/chess/data/ft/onday_$ID.bin; fi
log "on-day fine-tune $ID from $CKD: $SB sb at lr 0.0003 on $DATA"
$T --data $DATA --resume $CKD --start-superbatch 1 --superbatches $SB --lr 0.0003 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate $SB --threads 6 --device 0 --out $CK --net-id $ID > ~/chess/logs/train_$ID.log 2>&1 && log "trained" || { log "FAILED"; exit 1; }
$V $X --checkpoint $CK/$ID-$SB --hidden 1024 --act screlu --out $NETS/nnue_$ID.safetensors 2>&1 | tee -a $S
$V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_$ID.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("$ID ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_$ID.safetensors forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null; log "done: $NETS/nnue_$ID.safetensors"
