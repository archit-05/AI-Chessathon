#!/bin/bash
# the 13:20 decision input: merge the three boxes' ship_bp336-vs-ship_v85 stats pair-wise
SP="/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad"; D="$SP/out/bp336"; mkdir -p "$D"
scp -q gcp-x86:~/chess/gates/bp336_vs_v85pkg_gcp.stats.jsonl "$D/gcp.stats.jsonl" 2>/dev/null
scp -q priorcrypto-vm:chess/gates/bp336_vs_v85pkg_vm.stats.jsonl "$D/vm.stats.jsonl" 2>/dev/null
scp -q -P 22018 root@63.141.33.33:chess/gates/bp336_vs_v85pkg_pod.stats.jsonl "$D/pod.stats.jsonl" 2>/dev/null
echo "=== ship_bp336 vs ship_v85, all boxes, $(date '+%H:%M') ==="; python3 "$SP/merge_gate.py" $(ls "$D"/*.stats.jsonl 2>/dev/null)
