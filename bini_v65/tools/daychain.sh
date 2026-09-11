#!/bin/bash
# Wednesday day chain on the GPU box (times are the box's UTC = London - 1h).
# 11:15 UTC (12:15 London): run A on every own label present: GPU0 a512 = 512 CReLU 16 buckets + factoriser;
#   GPU1 a1024 = 1024 SCReLU 16 buckets + factoriser + 8 output buckets. Both judged vs v3b and vs P1 at 30k nodes.
# 13:15 UTC (14:15 London): run B, same two nets on everything labelled by then (Thursday's V6.1 candidates).
# No result blend, ever. Results: grep RESULT ~/chess/logs/daychain.log
cd ~/chess; P=/venv/main/bin/python; V=~/chess/venv/bin/python; D=~/chess/data; G=~/chess/gates; L=~/chess/logs
log(){ echo "$(date '+%F %T') $*" >> $L/daychain.log; }
judge(){ name=$1; net=$2; ref=$3; refname=$4; log "judge $name vs $refname (576 @30k)"
  ( cd bini_v5 && flock $G/judge.lock $V tools/node_gate.py --engine . --a "BINI_NNUE=$net" --b "BINI_NNUE=$ref" --openings tools/curated.epd --games 576 --nodes 30000 --workers 24 --tt-bits 22 --out $G/${name}_vs_$refname > $G/${name}_vs_$refname.stdout 2>&1 )
  log "RESULT $name vs $refname: $(grep -E '^\S+ \[' $G/${name}_vs_$refname.log | tail -n 1)"; }
train(){ gpu=$1; name=$2; shift 2; log "train $name on GPU$gpu ($(ls $D/labelled | wc -l) shards): $*"
  ( cd bini_v5 && CUDA_VISIBLE_DEVICES=$gpu $P tools/train_nnue.py --data ../data/labelled --out ../data/nnue_$name.safetensors --rows-per-chunk 200000 --batch 16384 "$@" > $L/train_$name.log 2>&1 )
  log "train $name done: $(grep -E 'val' $L/train_$name.log | tail -n 1)"; }
sleep_until(){ t=$(date -d "$1" +%s); n=$(date +%s); [ $t -gt $n ] && sleep $((t-n)); }
runpair(){ tag=$1
  ( train 0 ${tag}512 --buckets 16 --factorise --hidden 512 --act crelu --epochs 6 --lr 2e-3; judge ${tag}512 $D/nnue_${tag}512.safetensors $D/nnue_v3b.safetensors v3b; judge ${tag}512 $D/nnue_${tag}512.safetensors $D/nnue_p1.safetensors p1 ) &
  ( train 1 ${tag}1024 --buckets 16 --factorise --hidden 1024 --act screlu --out-buckets 8 --epochs 6 --lr 2e-3; judge ${tag}1024 $D/nnue_${tag}1024.safetensors $D/nnue_v3b.safetensors v3b; judge ${tag}1024 $D/nnue_${tag}1024.safetensors $D/nnue_p1.safetensors p1 ) &
  wait; }
log "day chain started"
sleep_until "11:15"; runpair a
sleep_until "13:15"; runpair b
log "day chain done"
