#!/bin/bash
# wait for the bp144_ftd screen line (or SKIP) and the width ladder's end
while :; do
  S=$(perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes runpod 'grep -E "SCREEN bp144_ftd|SKIP bp144_ftd" ~/chess/logs/screen_queue.status | tail -1; echo "WL: $(tail -1 ~/chess/logs/width_ladder.status)"' 2>/dev/null)
  echo "$(date '+%H:%M') $S" | cut -c1-300
  echo "$S" | grep -q "bp144_ftd" && break
  sleep 300
done
echo "FTD SCREEN DONE $(date)"
