#!/bin/bash
while :; do
  S=$(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes runpod 'tail -1 ~/chess/logs/c4_lane.status | cut -c1-120; grep -E "SCREEN bp240_d7_ft|SKIP bp240_d7_ft" ~/chess/logs/screen_queue.status | tail -1; grep -E "^\S+ \[" ~/chess/gates/bp240_d7_ft_30k.log 2>/dev/null | tail -1' 2>/dev/null | tr "\n" " | ")
  echo "$(date '+%H:%M') $S" | cut -c1-320
  echo "$S" | grep -q "SCREEN bp240_d7_ft\|SKIP bp240_d7_ft\|FAILED" && break
  sleep 600
done
echo "BP240 DONE $(date)"
