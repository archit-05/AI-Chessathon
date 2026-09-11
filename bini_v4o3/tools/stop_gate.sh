#!/bin/bash
# Stop a running gate by its candidate directory name ($1) and clean up its game processes.
cand=$1
for p in $(ps -Ao pid,args | grep "arena_par.py" | grep -- "--agent $cand" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
for p in $(ps -Ao pid,args | grep "gate.sh $cand" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
sleep 2
bash "$(dirname "$0")/kill_orphans.sh" "$cand"
