#!/bin/bash
# Overnight chain on the GPU box (Wed 02:20 -> ~08:00). Labelling continues via label_keeper.sh.
# GPU0: C0 finishes -> judge; P3 (512 CReLU, wdl 0.75) -> judge; 05:30 P2b (1024 SCReLU, 8 out buckets, wdl 0.75) -> judge.
# GPU1: after stage0 -> 03:35 P1 (512 CReLU) -> judge; P2 (1024 SCReLU, 8 out buckets) -> judge.
# Every run trains on every own-label shard present at its start; every judge is 576 games at 30k nodes vs v3b,
# serialised through a lock. Results: ~/chess/logs/overnight2.log (grep RESULT).
cd ~/chess; P=/venv/main/bin/python; V=~/chess/venv/bin/python; D=~/chess/data; G=~/chess/gates; L=~/chess/logs
log(){ echo "$(date '+%F %T') $*" >> $L/overnight2.log; }
judge(){ name=$1; net=$2; log "judge $name vs v3b (576 @30k) on $(ls $D/labelled | wc -l) shards"
  ( cd bini_v5 && flock $G/judge.lock $V tools/node_gate.py --engine . --a "BINI_NNUE=$net" --b "BINI_NNUE=$D/nnue_v3b.safetensors" --openings tools/curated.epd --games 576 --nodes 30000 --workers 24 --tt-bits 22 --out $G/${name}_vs_v3b > $G/${name}_vs_v3b.stdout 2>&1 )
  log "RESULT $name vs v3b: $(grep -E '^\S+ \[' $G/${name}_vs_v3b.log | tail -n 1)"; }
train(){ gpu=$1; name=$2; shift 2; log "train $name on GPU$gpu ($(ls $D/labelled | wc -l) shards): $*"
  ( cd bini_v5 && CUDA_VISIBLE_DEVICES=$gpu $P tools/train_nnue.py --data ../data/labelled --out ../data/nnue_$name.safetensors --buckets 8 --rows-per-chunk 200000 --batch 16384 "$@" > $L/train_$name.log 2>&1 )
  log "train $name done: $(grep -E 'val' $L/train_$name.log | tail -n 1)"; }
wait_for(){ while pgrep -f "$1" > /dev/null; do sleep 60; done; }
sleep_until(){ t=$(date -d "$1" +%s); n=$(date +%s); [ $t -gt $n ] && sleep $((t-n)); }
log "overnight chain started"
( wait_for "nnue_c0.safetensors"; log "C0 finished: $(grep val $L/train_c0.log | tail -n 1)"; judge c0 $D/nnue_c0.safetensors
  train 0 p3 --hidden 512 --act crelu --epochs 6 --lr 2e-3 --wdl 0.75; judge p3 $D/nnue_p3.safetensors
  sleep_until "04:30"; train 0 p2b --hidden 1024 --act screlu --out-buckets 8 --epochs 6 --lr 2e-3 --wdl 0.75; judge p2b $D/nnue_p2b.safetensors ) &
( wait_for "stage0.sh"; log "stage0 done: $(grep -h -E '^\S+ \[' $G/s0_v3b_vs_v3.log $G/s0_v3b_vs_v2.log $G/p1pilot_vs_v3b.log 2>/dev/null | tail -n 3 | tr '\n' ' | ')"
  sleep_until "02:35"; train 1 p1 --hidden 512 --act crelu --epochs 6 --lr 2e-3; judge p1 $D/nnue_p1.safetensors
  sleep_until "03:30"; train 1 p2 --hidden 1024 --act screlu --out-buckets 8 --epochs 6 --lr 2e-3; judge p2 $D/nnue_p2.safetensors ) &
wait; log "overnight chain done"
