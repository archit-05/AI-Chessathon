"""Batch labelling with Leela (lc0) on a GPU box (Project Prometheus s4): one evaluator for every
position. K lc0 processes (UCI, `go nodes 1`, UCI_ShowWDL) evaluate FENs from --fens or sampled
from --pgn; each position becomes (pieces, stm, cp, depth, quiet) exactly like our other chunks,
with cp = 400 * logit(win probability from the WDL) clipped to +-3000 (so sigmoid(cp/400) in the
trainer recovers Leela's win probability), depth = 1, quiet = 1 unless Leela's move is a capture
or promotion. Positions in check are skipped.

    python tools/label_leela.py --pgn ~/chess/data/elite/lichess_elite_2025-05.pgn --out ~/chess/data/leela/elite05 \
        --positions 20000000 --workers 12 --lc0 ~/chess/lc0/build/release/lc0 --weights ~/chess/data/leela/net.pb.gz
"""
from __future__ import annotations

import argparse
import math
import multiprocessing as mp
import random
import subprocess
import sys
import time
from pathlib import Path

import chess
import chess.pgn
import numpy as np

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}


def game_fens(pgn_path: str, skip_plies: int, take_prob: float, limit: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    fens: list[str] = []
    with open(pgn_path, errors="replace") as fh:
        while len(fens) < limit:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            board = game.board()
            for ply, mv in enumerate(game.mainline_moves()):
                board.push(mv)
                if ply >= skip_plies and not board.is_game_over() and rng.random() < take_prob:
                    fens.append(board.fen())
    return fens


class Lc0:
    def __init__(self, exe: str, weights: str, backend: str) -> None:
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd(f"setoption name WeightsFile value {weights}")
        self.cmd(f"setoption name Backend value {backend}")
        self.cmd("setoption name UCI_ShowWDL value true")
        self.cmd("setoption name Threads value 1")
        self.cmd("setoption name MinibatchSize value 1")
        self.cmd("isready"); self.wait("readyok")

    def cmd(self, s: str) -> None:
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()

    def wait(self, token: str) -> str:
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("lc0 died")
            if line.startswith(token):
                return line

    def eval(self, fen: str) -> tuple[float, str] | None:
        self.cmd(f"position fen {fen}"); self.cmd("go nodes 1")
        wdl = None; best = None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("lc0 died")
            if line.startswith("info") and " wdl " in line:
                t = line.split(); i = t.index("wdl"); wdl = (int(t[i + 1]), int(t[i + 2]), int(t[i + 3]))
            if line.startswith("bestmove"):
                best = line.split()[1] if len(line.split()) > 1 else None
                break
        if wdl is None:
            return None
        w, d, l = wdl
        p = (w + 0.5 * d) / 1000.0  # side to move's win probability
        return p, best


def worker(args) -> tuple:
    fens, exe, weights, backend = args
    eng = Lc0(exe, weights, backend)
    n = len(fens)
    pieces = np.zeros((n, 64), dtype=np.uint8); stm = np.zeros(n, dtype=np.uint8)
    cps = np.zeros(n, dtype=np.int16); depths = np.ones(n, dtype=np.uint8); quiet = np.zeros(n, dtype=np.uint8)
    k = 0
    for fen in fens:
        board = chess.Board(fen)
        if board.is_check():
            continue
        r = eng.eval(fen)
        if r is None:
            continue
        p, best = r
        p = min(0.9995, max(0.0005, p))
        cp_stm = 400.0 * math.log(p / (1.0 - p))
        cp_white = cp_stm if board.turn else -cp_stm
        q = 1
        if best and best != "0000":
            m = chess.Move.from_uci(best)
            if board.is_capture(m) or m.promotion is not None:
                q = 0
        for sq, pc in board.piece_map().items():
            pieces[k, sq] = CODES[pc.symbol()]
        stm[k] = 0 if board.turn else 1
        cps[k] = int(max(-3000, min(3000, round(cp_white))))
        quiet[k] = q
        k += 1
    eng.cmd("quit")
    return pieces[:k], stm[:k], cps[:k], depths[:k], quiet[:k]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pgn"); ap.add_argument("--fens")
    ap.add_argument("--out", required=True)
    ap.add_argument("--positions", type=int, default=5_000_000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--skip-plies", type=int, default=10)
    ap.add_argument("--take-prob", type=float, default=0.5)
    ap.add_argument("--chunk", type=int, default=500_000)
    ap.add_argument("--start-chunk", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--lc0", default=str(Path.home() / "chess/lc0/build/release/lc0"))
    ap.add_argument("--weights", default=str(Path.home() / "chess/data/leela/net.pb.gz"))
    ap.add_argument("--backend", default="cuda-fp16")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.fens:
        fens = [l.strip() for l in open(a.fens) if l.strip()][: a.positions]
    else:
        print("collecting positions...", flush=True)
        fens = game_fens(a.pgn, a.skip_plies, a.take_prob, a.positions, a.seed)
    print(f"{len(fens):,} positions; Leela with {a.workers} workers, backend {a.backend}", flush=True)
    batch = 5000
    jobs = [(fens[i:i + batch], a.lc0, a.weights, a.backend) for i in range(0, len(fens), batch)]
    bufs: list[tuple] = []; buffered = 0; chunk_id = a.start_chunk; done = 0
    def flush():
        nonlocal bufs, buffered, chunk_id
        if not bufs:
            return
        np.savez(out / f"chunk_{chunk_id:04d}.npz", pieces=np.concatenate([b[0] for b in bufs]), stm=np.concatenate([b[1] for b in bufs]), cp=np.concatenate([b[2] for b in bufs]), depth=np.concatenate([b[3] for b in bufs]), quiet=np.concatenate([b[4] for b in bufs]))
        chunk_id += 1; bufs = []; buffered = 0
    with mp.Pool(a.workers) as pool:
        for res in pool.imap_unordered(worker, jobs):
            bufs.append(res); buffered += len(res[1]); done += batch
            if buffered >= a.chunk:
                flush()
            if done % 50000 == 0:
                print(f"  {done:,}/{len(fens):,}  {done / (time.time() - t0):.0f} pos/s  chunks {chunk_id}", flush=True)
    flush()
    print(f"done: {chunk_id - a.start_chunk} chunks -> {out} in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
