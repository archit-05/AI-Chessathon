#!/bin/bash
# Width ladder (insurance for a package/memory constraint): w768 and w512 from scratch on the 712M shuffle (96 sb, cosine
# 0.0005, screlu), each followed by the fc_b-style continuation on clean_d10 (start 97, 104 sb), export + bound + size, mirror.
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/width_ladder.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py
SH="~/chess/data/bullet_shuf/shuffled_0.bin ~/chess/data/bullet_shuf/shuffled_1.bin ~/chess/data/bullet_shuf/shuffled_2.bin ~/chess/data/bullet_shuf/shuffled_3.bin ~/chess/data/bullet_shuf/shuffled_4.bin ~/chess/data/bullet_shuf/shuffled_5.bin ~/chess/data/bullet_shuf/shuffled_6.bin ~/chess/data/bullet_shuf/shuffled_7.bin"
for H in 768 512; do
  log "ARM w$H: from scratch on the shuffle, 96 sb"
  eval $T --data $SH --hidden $H --act screlu --wdl 0 --lr 0.0005 --lr-schedule cosine --superbatches 96 --save-rate 96 --threads 6 --device 0 --out $CK --net-id w$H > ~/chess/logs/train_w$H.log 2>&1 && log "w$H trained" || { log "w$H FAILED"; continue; }
  $T --data ~/chess/data/ft/clean_d10_shuf.bin --resume $CK/w$H-96 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden $H --act screlu --wdl 0 --save-rate 104 --threads 6 --device 0 --out $CK --net-id w${H}_ft > ~/chess/logs/train_w${H}_ft.log 2>&1 && log "w${H}_ft trained" || { log "w${H}_ft FAILED"; continue; }
  $V $X --checkpoint $CK/w${H}_ft-104 --hidden $H --act screlu --out $NETS/nnue_w${H}_ft.safetensors 2>&1 | tee -a $S
  $V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np, os; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_w${H}_ft.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("w${H}_ft ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32", "size", os.path.getsize("$NETS/nnue_w${H}_ft.safetensors"), "bytes")
PYEOF
done
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_w*_ft.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; rsync -az -e "ssh -o StrictHostKeyChecking=no" $CK/w768_ft-104 $CK/w512_ft-104 $GCP:~/chess/data/stage/ckpt_night/ 2>/dev/null; log "width ladder done"
