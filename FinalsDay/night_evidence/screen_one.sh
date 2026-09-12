#!/bin/bash
# Screen one net vs fc_b at 30k (576 games) when it exists and no other gate is running; then mirror. usage: screen_one.sh <id>
set -u; ID="$1"; cd ~/chess; S=~/chess/logs/screen_queue.status; V=~/chess/venv/bin/python; E=~/chess/bini_astra_v5_noc2b; NG=~/chess/bini_v65/tools/node_gate.py; O=~/chess/bini_v65/tools/curated.epd; NETS=~/chess/data/nets
# which lane produces this net decides which status file means "it will never come"
case "$ID" in bp144*) LANE=~/chess/logs/c3_lane.status; DONE="C3-lane done\|FAILED\|not run";; bp96*) LANE=~/chess/logs/c2_lane.status; DONE="C2-lane done\|FAILED\|not run";; bp*) LANE=~/chess/logs/c_lane.status; DONE="C-lane done\|FAILED\|stop C";; *) LANE=/dev/null; DONE="__never__";; esac
while [ ! -f $NETS/nnue_$ID.safetensors ]; do sleep 60; grep -q "$DONE" $LANE 2>/dev/null && [ ! -f $NETS/nnue_$ID.safetensors ] && { echo "$(date '+%F %T') SKIP $ID (not produced)" >> $S; exit 0; }; done
while ps -eo args | grep -q "[n]ode_gate.py --engine"; do sleep 30; done
$V $NG --engine $E --a "BINI_NNUE=$NETS/nnue_$ID.safetensors" --b "BINI_NNUE=$NETS/nnue_fcb.safetensors" --openings $O --games 576 --nodes 30000 --workers 4 --tt-bits 22 --out ~/chess/gates/${ID}_30k > ~/chess/gates/${ID}_30k.stdout 2>&1
echo "$(date '+%F %T') SCREEN $ID vs fc_b: $(grep -E '^\S+ \[' ~/chess/gates/${ID}_30k.log | tail -1)" >> $S
rsync -az -e "ssh -o StrictHostKeyChecking=no" ~/chess/gates/ forge@8.228.62.35:~/chess/data/stage/nets_night/ 2>/dev/null
