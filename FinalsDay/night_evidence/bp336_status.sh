#!/bin/bash
# the 13:20 decision input: merge the three boxes' ship_bp336-vs-ship_v85 stats pair-wise
SP="/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad"; D="$SP/out/bp336"; mkdir -p "$D"
rsync -az -e "ssh -o BatchMode=yes" gcp-x86:~/chess/gates/bp336_vs_v85pkg_gcp.stats.jsonl "$D/gcp.stats.jsonl" 2>/dev/null
rsync -az -e "ssh -o BatchMode=yes" priorcrypto-vm:chess/gates/bp336_vs_v85pkg_vm.stats.jsonl "$D/vm.stats.jsonl" 2>/dev/null
rsync -az -e "ssh -o BatchMode=yes" runpod:chess/gates/bp336_vs_v85pkg_pod.stats.jsonl "$D/pod.stats.jsonl" 2>/dev/null; rsync -az -e "ssh -o BatchMode=yes" runpod:chess/gates/bp336_vs_v85pkg_pod2.stats.jsonl "$D/pod2.stats.jsonl" 2>/dev/null
# extra pods: one "host port seed" per line in $SP/out/extra_pods.txt
[ -f "$SP/out/extra_pods.txt" ] && while read -r H P SEED; do [ -n "$H" ] && rsync -az -e "ssh -o BatchMode=yes -o StrictHostKeyChecking=no -p $P" root@$H:chess/gates/bp336_vs_v85pkg_seed$SEED.stats.jsonl "$D/pod_$H.stats.jsonl" 2>/dev/null; done < "$SP/out/extra_pods.txt"
echo "=== ship_bp336 vs ship_v85, all boxes, $(date '+%H:%M') ==="; python3 "$SP/merge_gate.py" $(ls "$D"/*.stats.jsonl 2>/dev/null)
