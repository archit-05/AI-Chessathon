#!/bin/bash
# pause|resume the self-play generators and labellers on a box (SIGSTOP/SIGCONT); the patterns live here, never inline
PAT="selfplay_sf.py|label_fens.py|label_positions.py|peer_label.py"
case "$1" in
  pause) for p in $(pgrep -f "$PAT"); do kill -STOP $p; done; echo "paused $(pgrep -f "$PAT" | wc -l)";;
  resume) for p in $(pgrep -f "$PAT"); do kill -CONT $p; done; echo resumed;;
esac
