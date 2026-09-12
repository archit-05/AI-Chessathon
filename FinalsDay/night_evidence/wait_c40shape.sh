#!/bin/bash
while :; do
  S=$(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes runpod 'grep "SHAPE contempt40" ~/chess/logs/screen_queue.status | tail -1; grep -E "^\S+ \[" ~/chess/gates/c40_30k.log 2>/dev/null | tail -1' 2>/dev/null)
  echo "$(date '+%H:%M') $S" | cut -c1-300
  echo "$S" | grep -q "SHAPE contempt40" && break
  sleep 300
done
echo "C40 SHAPE DONE $(date)"
