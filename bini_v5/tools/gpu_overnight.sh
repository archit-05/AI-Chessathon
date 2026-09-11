#!/bin/bash
# GPU overnight orchestrator — runs on the Vast.ai box (2× RTX 5090, 92 CPU quota)
# Kicks off: bullet build, binpack download, position extraction, Stockfish labelling,
# and then training runs. Designed to be idempotent and resumable.
# Usage: nohup bash ~/chess/bini_v5/tools/gpu_overnight.sh > ~/chess/logs/overnight.log 2>&1 &
set -u
cd ~/chess
source ~/.cargo/env 2>/dev/null
export PATH="$HOME/.cargo/bin:/usr/local/bin:$PATH"
mkdir -p logs data/own data/binpacks data/extracted_fens data/labelled

TS() { date '+%F %T'; }
log() { echo "$(TS) $*"; }

log "=== GPU OVERNIGHT START ==="
log "GPUs: $(nvidia-smi --query-gpu=name --format=csv,noheader | tr '\n' ', ')"
log "CPUs: $(nproc) cores"
log "RAM: $(free -g | awk '/^Mem:/{print $2}') GB"

# ---- STEP 1: Build bullet trainer (background) ----
if [ ! -f bullet/target/release/examples/simple ]; then
    log "Building bullet trainer with CUDA..."
    (
        cd bullet
        # Set CUDA_PATH for bullet's build
        export CUDA_PATH=/usr/local/cuda
        cargo build --release --features cuda --example simple \
            --example 3_input_buckets \
            --example 2_output_buckets \
            --example advanced \
            > ~/chess/logs/bullet_build.log 2>&1
        if [ $? -eq 0 ]; then
            log "BULLET BUILD SUCCESS"
            ls -la target/release/examples/simple target/release/examples/3_input_buckets 2>/dev/null
        else
            log "BULLET BUILD FAILED — check logs/bullet_build.log"
            tail -30 ~/chess/logs/bullet_build.log
        fi
    ) &
    BULLET_PID=$!
    log "Bullet build started (PID $BULLET_PID)"
else
    log "Bullet already built, skipping"
fi

# ---- STEP 2: Download public Stockfish training binpacks (background) ----
# These are the files the Stockfish team trains their own nets on
(
    cd data/binpacks
    log "Checking public binpack availability..."
    
    # Try the standard mirrors for recent Stockfish training data
    # test80-2024-02 is a well-known filtered training set
    for URL in \
        "https://data.stockfishchess.org/nn-data/test80-2024-02-feb-2tb7p.min-v2.v6.binpack" \
        "https://data.stockfishchess.org/nn-data/test80-2024-01-jan-2tb7p.v6.binpack" \
        "https://robotmoon.com/nnue-training-data/test80-2024-02-feb-2tb7p.min-v2.v6.binpack"; do
        FNAME=$(basename "$URL")
        if [ -f "$FNAME" ]; then
            log "Binpack $FNAME already present ($(du -h $FNAME | cut -f1))"
            break
        fi
        log "Trying to download $FNAME from $(echo $URL | cut -d/ -f3)..."
        wget -q --show-progress --timeout=30 --tries=2 -O "$FNAME.tmp" "$URL" 2>&1 | tail -5
        if [ $? -eq 0 ] && [ -s "$FNAME.tmp" ]; then
            mv "$FNAME.tmp" "$FNAME"
            log "Downloaded $FNAME ($(du -h $FNAME | cut -f1))"
            break
        else
            rm -f "$FNAME.tmp"
            log "Failed from $(echo $URL | cut -d/ -f3), trying next..."
        fi
    done
    
    # Also try a smaller file as fallback
    if ! ls *.binpack >/dev/null 2>&1; then
        log "Main binpacks not available, trying alternative sources..."
        # Try the Lc0 training data repository
        for URL in \
            "https://data.stockfishchess.org/nn-data/test80-2024-08-aug-2tb7p.v6.min-v2.binpack" \
            "https://huggingface.co/datasets/stockfishchess/nnue-training-data/resolve/main/test80-2024-02.binpack"; do
            FNAME=$(basename "$URL")
            if [ -f "$FNAME" ]; then break; fi
            log "Trying $URL..."
            timeout 300 wget -q --show-progress -O "$FNAME.tmp" "$URL" 2>&1 | tail -3
            if [ $? -eq 0 ] && [ -s "$FNAME.tmp" ]; then
                mv "$FNAME.tmp" "$FNAME"
                log "Downloaded $FNAME ($(du -h $FNAME | cut -f1))"
                break
            fi
            rm -f "$FNAME.tmp"
        done
    fi
    
    ls -lh *.binpack 2>/dev/null || log "WARNING: No binpacks downloaded — bullet Route A deferred to morning"
) > logs/binpack_download.log 2>&1 &
BINPACK_PID=$!
log "Binpack download started (PID $BINPACK_PID)"

# ---- STEP 3: Extract positions from elite PGNs for labelling ----
log "Extracting positions from elite PGNs..."
/venv/main/bin/python - <<'PYEOF'
"""Extract FENs from Lichess elite PGNs (one per line, with game result) for Stockfish labelling."""
import chess
import chess.pgn
import io
import os
import sys
import time
import zipfile
from pathlib import Path

OUT = Path(os.path.expanduser("~/chess/data/extracted_fens"))
OUT.mkdir(parents=True, exist_ok=True)
ELITE = Path(os.path.expanduser("~/chess/data/elite"))

MIN_PLY = 8
STRIDE = 2  # keep every 2nd position
SHARD_SIZE = 200_000
total = 0
shard_id = 0
buf = []
t0 = time.time()

def flush_shard():
    global shard_id, buf
    if not buf:
        return
    out_path = OUT / f"shard_{shard_id:06d}.fen"
    tmp = OUT / f"shard_{shard_id:06d}.fen.tmp"
    with open(tmp, 'w') as f:
        for line in buf:
            f.write(line + '\n')
    os.rename(tmp, out_path)
    shard_id += 1
    buf = []

for zf_path in sorted(ELITE.glob("*.zip")):
    print(f"Processing {zf_path.name}...", flush=True)
    try:
        with zipfile.ZipFile(zf_path) as zf:
            for name in zf.namelist():
                if not name.endswith('.pgn'):
                    continue
                with zf.open(name) as raw:
                    text = io.TextIOWrapper(raw, encoding='utf-8', errors='replace')
                    games = 0
                    while True:
                        game = chess.pgn.read_game(text)
                        if game is None:
                            break
                        result_str = game.headers.get("Result", "*")
                        result = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(result_str)
                        if result is None:
                            continue
                        board = game.board()
                        moves = list(game.mainline_moves())
                        if len(moves) < 20:
                            continue
                        for ply, move in enumerate(moves):
                            if ply >= MIN_PLY and ply % STRIDE == 0 and not board.is_check():
                                fen = board.fen()
                                buf.append(f"{fen}\t{result}")
                                total += 1
                                if len(buf) >= SHARD_SIZE:
                                    flush_shard()
                            board.push(move)
                        games += 1
                        if games % 10000 == 0:
                            elapsed = time.time() - t0
                            print(f"  {games} games, {total} positions, {total/max(elapsed,1):.0f}/s, {shard_id} shards", flush=True)
    except Exception as e:
        print(f"Error processing {zf_path}: {e}", flush=True)

# Also process unzipped PGN if present
for pgn_path in sorted(ELITE.glob("*.pgn")):
    print(f"Processing {pgn_path.name}...", flush=True)
    with open(pgn_path) as f:
        games = 0
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            result_str = game.headers.get("Result", "*")
            result = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}.get(result_str)
            if result is None:
                continue
            board = game.board()
            moves = list(game.mainline_moves())
            if len(moves) < 20:
                continue
            for ply, move in enumerate(moves):
                if ply >= MIN_PLY and ply % STRIDE == 0 and not board.is_check():
                    fen = board.fen()
                    buf.append(f"{fen}\t{result}")
                    total += 1
                    if len(buf) >= SHARD_SIZE:
                        flush_shard()
                board.push(move)
            games += 1
            if games % 10000 == 0:
                elapsed = time.time() - t0
                print(f"  {games} games, {total} positions, {total/max(elapsed,1):.0f}/s, {shard_id} shards", flush=True)

flush_shard()
elapsed = time.time() - t0
print(f"EXTRACTION DONE: {total} positions in {shard_id} shards, {elapsed:.0f}s", flush=True)
PYEOF

# ---- STEP 4: Start Stockfish labelling fleet ----
log "Starting Stockfish labelling fleet..."
WORKERS=40  # use 40 of our 92 CPU quota for labelling (conservative)
DEPTH=7

/venv/main/bin/python - "$WORKERS" "$DEPTH" <<'PYEOF'
"""Simple multi-process Stockfish labeller: reads FEN shards, labels at fixed depth,
writes npz chunks compatible with train_nnue.py's load_chunk()."""
import multiprocessing as mp
import numpy as np
import os
import subprocess
import sys
import time
from pathlib import Path

WORKERS = int(sys.argv[1])
DEPTH = int(sys.argv[2])
FEN_DIR = Path(os.path.expanduser("~/chess/data/extracted_fens"))
OUT_DIR = Path(os.path.expanduser("~/chess/data/labelled"))
INFLIGHT = Path(os.path.expanduser("~/chess/data/extracted_fens/inflight"))
OUT_DIR.mkdir(parents=True, exist_ok=True)
INFLIGHT.mkdir(parents=True, exist_ok=True)

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6,
         "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}

def label_worker(wid):
    """One Stockfish process, claims shards by atomic rename, labels, writes npz."""
    import chess
    sf = subprocess.Popen(
        ["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True, bufsize=1
    )
    def cmd(s):
        sf.stdin.write(s + "\n"); sf.stdin.flush()
    def wait(tok):
        while True:
            line = sf.stdout.readline()
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith(tok):
                return line.strip()
    
    cmd("uci"); wait("uciok")
    cmd("setoption name Threads value 1")
    cmd("setoption name Hash value 16")
    cmd("isready"); wait("readyok")
    
    total = 0
    t0 = time.time()
    
    while True:
        # Claim a shard
        shard = None
        try:
            for f in sorted(FEN_DIR.glob("shard_*.fen")):
                dest = INFLIGHT / f.name
                try:
                    os.rename(f, dest)
                    shard = dest
                    break
                except OSError:
                    continue
        except Exception:
            pass
        
        if shard is None:
            time.sleep(5)
            # Check if there are still shards being produced or inflight
            if not list(FEN_DIR.glob("shard_*.fen")) and not list(INFLIGHT.glob("shard_*.fen")):
                break
            if not list(FEN_DIR.glob("shard_*.fen")):
                # Only inflight shards left (other workers), wait a bit more
                time.sleep(10)
                if not list(FEN_DIR.glob("shard_*.fen")):
                    break
            continue
        
        out_name = shard.stem  # shard_000000
        out_path = OUT_DIR / f"{out_name}.npz"
        if out_path.exists():
            shard.unlink()
            continue
        
        lines = shard.read_text().strip().split('\n')
        P, S, C, Q, R = [], [], [], [], []
        
        cmd("ucinewgame")
        cmd("isready"); wait("readyok")
        
        for line in lines:
            parts = line.split('\t')
            fen = parts[0]
            result = int(parts[1]) if len(parts) > 1 else 0
            
            try:
                board = chess.Board(fen)
            except Exception:
                continue
            if board.is_check() or board.is_game_over():
                continue
            
            cmd(f"position fen {fen}")
            cmd(f"go depth {DEPTH}")
            
            cp_val = None
            best_move = None
            while True:
                line2 = sf.stdout.readline()
                if not line2:
                    raise RuntimeError("stockfish exited")
                if line2.startswith("info") and " score " in line2 and " pv " in line2:
                    t = line2.split()
                    si = t.index("score")
                    if t[si + 1] == "cp":
                        cp_val = int(t[si + 2])
                    else:
                        m = int(t[si + 2])
                        cp_val = 3000 if m > 0 else -3000
                    pi = t.index("pv")
                    best_move = t[pi + 1]
                elif line2.startswith("bestmove"):
                    bm = line2.split()[1]
                    if best_move is None:
                        best_move = bm
                    break
            
            if cp_val is None:
                continue
            
            # cp from White's point of view
            cp_white = cp_val if board.turn == chess.WHITE else -cp_val
            cp_white = max(-3000, min(3000, cp_white))
            
            # Encode pieces
            row = np.zeros(64, dtype=np.uint8)
            for sq, pc in board.piece_map().items():
                row[sq] = CODES[pc.symbol()]
            
            # Quiet: best move is not a capture or promotion
            quiet = 1
            try:
                mv = chess.Move.from_uci(best_move)
                if board.is_capture(mv) or mv.promotion is not None:
                    quiet = 0
            except Exception:
                pass
            
            P.append(row)
            S.append(0 if board.turn == chess.WHITE else 1)
            C.append(cp_white)
            Q.append(quiet)
            R.append(result)
            total += 1
        
        # Write npz
        if P:
            tmp = OUT_DIR / f"{out_name}.tmp.npz"
            np.savez(tmp,
                pieces=np.array(P, dtype=np.uint8),
                stm=np.array(S, dtype=np.uint8),
                cp=np.array(C, dtype=np.int16),
                depth=np.full(len(C), DEPTH, dtype=np.uint8),
                quiet=np.array(Q, dtype=np.uint8),
                result=np.array(R, dtype=np.int8))
            os.rename(tmp, out_path)
        
        shard.unlink()
        elapsed = time.time() - t0
        print(f"w{wid}: {out_name} done, {len(P)} rows, total {total}, {total/max(elapsed,1):.0f}/s", flush=True)
    
    sf.stdin.write("quit\n"); sf.stdin.flush()
    try:
        sf.wait(timeout=5)
    except Exception:
        sf.kill()
    
    elapsed = time.time() - t0
    print(f"w{wid}: DONE — {total} positions in {elapsed:.0f}s ({total/max(elapsed,1):.0f}/s)", flush=True)

if __name__ == "__main__":
    # Wait briefly for the extraction to produce some shards
    waited = 0
    while not list(FEN_DIR.glob("shard_*.fen")) and waited < 120:
        time.sleep(5)
        waited += 5
    
    shards = list(FEN_DIR.glob("shard_*.fen"))
    print(f"Starting {WORKERS} labellers on {len(shards)} shards at depth {DEPTH}", flush=True)
    
    procs = []
    for i in range(WORKERS):
        p = mp.Process(target=label_worker, args=(i,))
        p.start()
        procs.append(p)
    
    for p in procs:
        p.join()
    
    # Report
    npz_files = list(OUT_DIR.glob("*.npz"))
    total_rows = 0
    for f in npz_files:
        try:
            z = np.load(f)
            total_rows += len(z["cp"])
        except Exception:
            pass
    print(f"LABELLING COMPLETE: {len(npz_files)} chunks, {total_rows} total positions", flush=True)
PYEOF

log "Labelling fleet finished or backgrounded"

# ---- STEP 5: Wait for bullet build, then start training ----
if [ -n "${BULLET_PID:-}" ]; then
    log "Waiting for bullet build to complete..."
    wait $BULLET_PID 2>/dev/null
fi

# ---- STEP 6: Start our PyTorch trainer on CUDA ----
log "Checking labelled data volume..."
LABELLED_COUNT=$(ls data/labelled/*.npz 2>/dev/null | wc -l)
log "Found $LABELLED_COUNT labelled chunks"

if [ "$LABELLED_COUNT" -ge 5 ]; then
    log "Starting from-scratch training run on CUDA (Route B: our trainer, our labels)..."
    cd ~/chess
    # Use the /venv/main which has torch+CUDA
    /venv/main/bin/python bini_v5/tools/train_nnue.py \
        --data data/labelled \
        --out data/nnue_prometheus_b1.safetensors \
        --buckets 8 --hidden 512 --act screlu --out-buckets 8 \
        --factorise \
        --epochs 6 --lr 2e-3 --batch 16384 \
        --wdl 0.85 \
        > logs/train_prometheus_b1.log 2>&1 &
    TRAIN_PID=$!
    log "Training started (PID $TRAIN_PID)"
    
    # Also start a 1024-hidden run if we have enough data
    if [ "$LABELLED_COUNT" -ge 20 ]; then
        log "Starting 1024-hidden SCReLU run..."
        /venv/main/bin/python bini_v5/tools/train_nnue.py \
            --data data/labelled \
            --out data/nnue_prometheus_b2_1024.safetensors \
            --buckets 8 --hidden 1024 --act screlu --out-buckets 8 \
            --factorise \
            --epochs 6 --lr 2e-3 --batch 16384 \
            --wdl 0.85 \
            > logs/train_prometheus_b2.log 2>&1 &
        TRAIN2_PID=$!
        log "1024-hidden training started (PID $TRAIN2_PID)"
    fi
else
    log "Not enough labelled data yet ($LABELLED_COUNT chunks), skipping training start"
fi

# Wait for binpack download
if [ -n "${BINPACK_PID:-}" ]; then
    log "Waiting for binpack download..."
    wait $BINPACK_PID 2>/dev/null
    cat logs/binpack_download.log
fi

log "=== GPU OVERNIGHT ORCHESTRATOR DONE ==="
log "Summary:"
log "  Bullet: $([ -f bullet/target/release/examples/simple ] && echo 'BUILT' || echo 'NOT BUILT')"
log "  Binpacks: $(ls data/binpacks/*.binpack 2>/dev/null | wc -l) files"
log "  Labelled chunks: $(ls data/labelled/*.npz 2>/dev/null | wc -l)"
log "  Training: $(ps aux | grep train_nnue | grep -v grep | wc -l) run(s) active"
log "  Disk: $(df -h / | tail -1 | awk '{print $3 " used of " $2}')"
