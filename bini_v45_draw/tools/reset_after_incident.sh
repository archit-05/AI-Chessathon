#!/bin/bash
# After the working-copy deletion: stop the v4o3 gate (every game since 06:05 crashes on a dead
# cwd), kill every queued script that was started from the deleted directory, clean orphans,
# then restart the proxy queue from the restored directory.
cd "/Users/architbhardwaj/Desktop/AI Chessathon/bini_v4" || exit 1
for pat in "gate_v4o3_when_ready.sh" "gate_v4b2_conditional.sh" "morning_proxies.sh" "soft_proxy_after.sh" "gate.sh ../bini_v4o3" "arena_par.py --agent ../bini_v4o3"; do
  for p in $(ps -Ao pid,args | grep -F -- "$pat" | grep -v grep | grep -v reset_after | awk '{print $1}'); do kill "$p" 2>/dev/null; done
done
sleep 2
for p in $(ps -Ao pid,args | grep "harness/runner.py" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
for p in $(ps -Ao pid,ppid,args | grep "spawn_main" | grep -v grep | awk '$2 == 1 {print $1}'); do kill "$p" 2>/dev/null; done
sleep 3
echo "engines left: $(ps -Ao args | grep -c '[h]arness/runner.py'); load: $(uptime | sed 's/.*load averages*: *//')"
# proxies: both gates are decided; start the real-clock proxy queue now from a live cwd
PY=../aichessathon-starter/.venv/bin/python
cat > /tmp/proxy_queue.sh <<'EOF'
#!/bin/bash
cd "/Users/architbhardwaj/Desktop/AI Chessathon/bini_v4" || exit 1
PY=../aichessathon-starter/.venv/bin/python
run_pair() { d=$1; n=$2; t=$3; echo "$(date '+%F %T') proxy $t"; ( cd "$d" && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes $n --start 0 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_${t}_a.log 2>&1 ) & ( cd "$d" && BINI_TT_BITS=24 $PY tools/proxy_match.py --games 20 --nodes $n --start 20 --stockfish /opt/homebrew/bin/stockfish > ../data/proxy_${t}_b.log 2>&1 ) & wait; echo "$(date '+%F %T') $t: $(grep 'PROXY MATCH' ../data/proxy_${t}_a.log | cut -c1-60) | $(grep 'PROXY MATCH' ../data/proxy_${t}_b.log | cut -c1-60)"; }
run_pair ../bini_v4o2 20000 v4o2_20k
run_pair ../bini_v4o2 40000 v4o2_40k
run_pair ../bini_v3b 40000 v3_40k
run_pair ../bini_v4o2_soft 40000 v4o2soft_40k
echo "$(date '+%F %T') morning proxies done"
EOF
nohup bash /tmp/proxy_queue.sh > ../data/morning_proxies.log 2>&1 < /dev/null &
echo "proxy queue restarted"
