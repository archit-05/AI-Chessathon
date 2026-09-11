#!/bin/bash
# Kill orphaned game processes of a stopped gate: runner.py processes (and their engine
# children) whose command line names the candidate directory given as $1, plus pool workers
# whose parent has died. Run from a script so the pattern is not in the caller's own command line.
cand=$1
for p in $(ps -Ao pid,args | grep "harness/runner.py" | grep -- "$cand" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
for p in $(ps -Ao pid,ppid,args | grep "spawn_main" | grep -v grep | awk '$2 == 1 {print $1}'); do kill "$p" 2>/dev/null; done
sleep 2
echo "engines now: $(ps -Ao args | grep -c '[h]arness/runner.py')"
