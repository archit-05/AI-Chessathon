#!/bin/bash
# A3-site on the pod: clean_d10 + 5 % all-band depth-16 site labels, exact fc_b schedule from k96-96. Waits for the
# site_all corpus and for the B-lane's GPU use to finish.  usage: bash run_a3_site.sh <gcp target>
set -u; GCP="$1"; cd ~/chess; S=~/chess/logs/a3_site.status; export PATH=/usr/local/cuda/bin:$HOME/.cargo/bin:$PATH
log() { echo "$(date '+%F %T') $*" | tee -a $S; }
T=~/chess/bini_v7/tools/bullet_trainer/target/release/bini_bullet_trainer; CK=~/chess/data/ckpt; NETS=~/chess/data/nets; V=~/chess/venv/bin/python; X=~/chess/bini_v7/tools/bullet_export.py
log "waiting for site_all.npz and the GPU"
while [ ! -f ~/chess/data/ft/site_all.npz ]; do sleep 30; done
$V bini_v7/tools/bulletformat.py convert ~/chess/data/ft/site_all.npz ~/chess/data/ft/site_all.bin > /dev/null 2>&1 && log "site_all converted: $($V bini_v7/tools/bulletformat.py info ~/chess/data/ft/site_all.bin | head -1 | cut -c1-120)"
$V bini_v7/tools/mix_corpus.py ~/chess/data/ft/a3site.bin --base ~/chess/data/ft/clean_d10_shuf.bin --spice ~/chess/data/ft/site_all.bin:5 2>&1 | tee -a $S || { log "mix refused"; exit 1; }
while ! grep -q "ARM k96b_ft trained\|FAILED\|B-lane done" ~/chess/logs/b_lane.status 2>/dev/null; do sleep 30; done
log "ARM a3site: clean_d10 + 5% site depth-16, fc_b schedule"
$T --data ~/chess/data/ft/a3site.bin --resume $CK/k96-96 --start-superbatch 97 --superbatches 104 --lr 0.0005 --lr-schedule cosine --hidden 1024 --act screlu --wdl 0 --save-rate 104 --threads 4 --device 0 --out $CK --net-id a3site > ~/chess/logs/train_a3site.log 2>&1 && log "ARM a3site trained" || { log "ARM a3site FAILED"; exit 1; }
$V $X --checkpoint $CK/a3site-104 --hidden 1024 --act screlu --out $NETS/nnue_a3site.safetensors 2>&1 | tee -a $S
$V - <<PYEOF 2>&1 | tee -a $S
import sys, numpy as np; sys.path.insert(0, "$HOME/chess/bini_astra_v5_noc2b"); from bini_nnue import read_safetensors
t,_ = read_safetensors(__import__("pathlib").Path("$NETS/nnue_a3site.safetensors")); b = int(np.abs(t["b1"]).max()) + 32*int(np.abs(t["w1"]).max())
print("a3site ACC_BOUND", b, "int16 OK" if b < 32767 else "INT32 FALLBACK (slower)")
PYEOF
rsync -az -e "ssh -o StrictHostKeyChecking=no" $NETS/nnue_a3site.safetensors ~/chess/logs/ $GCP:~/chess/data/stage/nets_night/ 2>/dev/null; log "A3-site done"
