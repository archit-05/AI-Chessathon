#!/bin/bash
# Mac -> new RunPod pod: turn a fresh pod into a real-clock comparison worker (ship_bp336_v11 vs ship_v85_v11, 120+0.5).
# usage: provision_gate_pod.sh <host> <port> <seed> [workers=8] [games=120]
set -u; H="$1"; P="$2"; SEED="$3"; W=${4:-8}; N=${5:-120}
SP="/private/tmp/claude-501/-Users-architbhardwaj-Desktop-AI-Chessathon/edc9c181-8258-4c54-8a6f-0a83813055f3/scratchpad"
S="ssh -o BatchMode=yes -o StrictHostKeyChecking=no -p $P root@$H"
$S 'mkdir -p ~/chess/gates ~/chess/logs && (python3.12 --version || python3 --version) 2>&1 | head -1; nproc; cat /sys/fs/cgroup/cpu.max 2>/dev/null'
rsync -az -e "ssh -o StrictHostKeyChecking=no -p $P" "$SP/newpod/aichessathon-starter" "$SP/cands/ship_v85_v11" "$SP/cands/ship_bp336_v11" root@$H:~/chess/
rsync -az -e "ssh -o StrictHostKeyChecking=no -p $P" "$SP/newpod/arena_par.py" "$SP/newpod/curated.epd" root@$H:~/chess/arena_tools/
$S 'cd ~/chess && PY=$(command -v python3.12 || command -v python3) && $PY -m venv venv && ./venv/bin/pip -q install "numba==0.67.0" "numpy==2.5.2" "chess==1.11.2" && ln -sfn ~/chess/venv aichessathon-starter/.venv && sed -i "s/^INIT_BUDGET_S = .*/INIT_BUDGET_S = 30.0/" aichessathon-starter/harness/rules.py && mkdir -p ship_bp336_v11/tools && cp arena_tools/arena_par.py arena_tools/curated.epd ship_bp336_v11/tools/ && ./venv/bin/python -c "import numba, numpy, chess; print(\"venv ok\", numba.__version__, numpy.__version__, chess.__version__)"'
$S "cd ~/chess && (setsid nohup ./venv/bin/python ship_bp336_v11/tools/arena_par.py --agent ~/chess/ship_bp336_v11 --opponent ~/chess/ship_v85_v11 --games $N --base-ms 120000 --inc-ms 500 --workers $W --seed $SEED --openings ship_bp336_v11/tools/curated.epd --pgn-out gates/bp336_vs_v85pkg_seed$SEED.pgn --stats-out gates/bp336_vs_v85pkg_seed$SEED.stats.jsonl > gates/bp336_vs_v85pkg_seed$SEED.log 2>&1 < /dev/null &); sleep 2; echo \"arena started: \$(ps -eo args | grep -c '[a]rena_par.py --agent')\""
echo "pod $H:$P is a comparison worker (seed $SEED, $W workers). Collect with: scp -P $P root@$H:chess/gates/bp336_vs_v85pkg_seed$SEED.stats.jsonl"
