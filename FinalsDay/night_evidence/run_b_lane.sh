#!/bin/bash
# Lane B on the pod: pull the 712M depth-7 shuffle, train k96b from scratch (96 sb, cosine 0.0005, the measured +9 recipe),
# then the exact fc_b continuation on top (k96b_ft: resume k96b-96, start 97, 104 sb, clean_d10). Exports + ACC_BOUND.
# usage: bash run_b_lane.sh <gcp target> [loader_threads=4]
set -u; GCP="$1"; TH=${2:-4}; cd ~/chess; S=~/chess/logs/b_lane.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py
mkdir -p ~/chess/data/bullet_shuf; log "pulling the 712M shuffle from $GCP"
rsync -az --partial -e "ssh -o StrictHostKeyChecking=no" "$GCP:~/chess/data/stage/bullet_shuf/" ~/chess/data/bullet_shuf/ && log "shuffle pulled: $(du -sh ~/chess/data/bullet_shuf | cut -f1)" || { log "SHUFFLE PULL FAILED"; exit 1; }
while [ ! -x $T ]; do sleep 30; done
# wait for the A-lane's GPU arms to finish (they log 'ARM a2lite trained' or FAILED) so two trainings do not share the GPU
while ! grep -q "ARM a2lite trained\|ARM a2lite FAILED\|A-lane done" ~/chess/logs/a_lane.status 2>/dev/null; do sleep 30; done
log "ARM k96b: from scratch, 8 shuffle files, 96 sb cosine 0.0005"
$T --data ~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin \
   --hidden 1024 --act screlu --wdl 0 --lr 0.0005 --lr-schedule cosine --superbatches 96 --save-rate 96 --threads $TH --device 0 --out $CK --net-id k96b > ~/chess/logs/train_k96b.log 2>&1 && log "ARM k96b trained" || { log "ARM k96b FAILED"; exit 1; }
$V $X --checkpoint $CK/k96b-96 --hidden 1024 --act screlu --out $NETS/nnue_k96b.safetensors 2>&1 | tee -a $S
log "ARM k96b_ft: resume k96b-96, fc_b schedule (start 97, 104 sb) on clean_d10"
$T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/k96b-96 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads $TH --device 0 --out $CK --net-id k96b_ft > ~/chess/logs/train_k96b_ft.log 2>&1 && log "ARM k96b_ft trained" || { log "ARM k96b_ft FAILED"; exit 1; }
$V $X --checkpoint $CK/k96b_ft-104 --hidden 1024 --act screlu --out $NETS/nnue_k96b_ft.safetensors 2>&1 | tee -a $S
for ID in k96b k96b_ft; do $V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_$ID.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("$ID ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
done
ssh -o StrictHostKeyChecking=no $GCP 'mkdir -p ~/chess/data/stage/nets_night ~/chess/data/stage/ckpt_night'; rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_k96b.safetensors $NETS/nnue_k96b_ft.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/k96b-96 $CK/k96b_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null
log "B-lane done (nets + checkpoints mirrored)"
