#!/bin/bash
# every 10 min: pull the VM shard to the Mac, push Mac + VM shards to GCP (seeds for the finishing job and inputs to the merge)
SP="$1"
while true; do
  scp -q priorcrypto-vm:chess/bookbuild/sfbook_vm.jsonl "$SP/out/sfbook_vm.jsonl" 2>/dev/null
  rsync -az "$SP/out/sfbook_mac.jsonl" gcp-x86:~/chess/bookbuild/sfbook_mac.jsonl 2>/dev/null
  [ -s "$SP/out/sfbook_vm.jsonl" ] && rsync -az "$SP/out/sfbook_vm.jsonl" gcp-x86:~/chess/bookbuild/sfbook_vm.jsonl 2>/dev/null
  echo "$(date +%H:%M) synced mac=$(wc -l < "$SP/out/sfbook_mac.jsonl" 2>/dev/null) vm=$(wc -l < "$SP/out/sfbook_vm.jsonl" 2>/dev/null)" >> "$SP/out/book_sync.log"
  sleep 600
done
