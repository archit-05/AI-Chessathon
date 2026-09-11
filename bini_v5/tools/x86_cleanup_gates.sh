#!/bin/bash
# On the x86 box: kill leftover gate processes (arena and runners) without matching this script's own command line.
for p in $(ps -eo pid,args | grep -E "[h]arness/runner\.py|[a]rena_par\.py" | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
sleep 1
echo "gate procs left: $(ps -eo args | grep -cE '[h]arness/runner\.py|[a]rena_par\.py')"
