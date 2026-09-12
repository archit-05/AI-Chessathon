#!/bin/bash
# After the freeze: stop every arena/screen on the boxes (the pods keep billing until Archit terminates them in the RunPod console).
S() { perl -e 'alarm 40; exec @ARGV' ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$@" 2>/dev/null; }
K='ps -eo pid,args | grep "[a]rena_par.py\|[n]ode_gate.py\|[h]arness/runner.py\|[h]arness.runner\|[s]moke_c.sh\|[v]m_bp336\|[p]od_bp336\|[g]cp_after" | awk "{print \$1}" | xargs -r kill; sleep 2; ps -eo pid,args | grep "[h]arness" | awk "{print \$1}" | xargs -r kill -9; echo "$(hostname): arenas left $(ps -eo args | grep -c "[a]rena_par.py")"'
S gcp-x86 "$K"; S priorcrypto-vm "$K"; S runpod "$K"; S -p 22004 root@69.30.85.95 "$K"; S -p 22140 root@194.68.245.198 "$K"
echo "all arenas stopped $(date '+%H:%M'); terminate the three RunPod pods in the console to stop billing"
