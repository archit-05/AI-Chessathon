"""Build training chunks from whole games: sample positions from PGN games and label them with a
local Stockfish at fixed depth. Output matches tools/stream_lichess.py chunks (pieces, stm, cp,
depth, quiet), so tools/train_nnue.py can mix them with the Lichess evaluation data.

    python tools/label_positions.py games.pgn out_dir --positions 5000000 --depth 10 --workers 8

Legal under the rules: labelling training positions with an existing engine is allowed; nothing
from Stockfish ships in the zip.
"""

from __future__ import annotations

import argparse
import random
import sys
from multiprocessing import Pool
from pathlib import Path

import chess
import chess.engine
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


def label(args: tuple[list[str], int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    fens, depth = args
    eng = chess.engine.SimpleEngine.popen_uci("stockfish")
    eng.configure({"Threads": 1, "Hash": 32})
    n = len(fens)
    pieces = np.zeros((n, 64), dtype=np.uint8)
    stm = np.zeros(n, dtype=np.uint8)
    cps = np.zeros(n, dtype=np.int16)
    depths = np.full(n, depth, dtype=np.uint8)
    quiet = np.zeros(n, dtype=np.uint8)
    k = 0
    for fen in fens:
        board = chess.Board(fen)
        if board.is_check():
            continue
        info = eng.analyse(board, chess.engine.Limit(depth=depth))
        score = info["score"].white()
        cp = score.score(mate_score=3000)
        if cp is None:
            continue
        pv = info.get("pv", [])
        q = 1
        if pv:
            m = pv[0]
            if board.is_capture(m) or m.promotion is not None:
                q = 0
        for sq, pc in board.piece_map().items():
            pieces[k, sq] = CODES[pc.symbol()]
        stm[k] = 0 if board.turn else 1
        cps[k] = max(-3000, min(3000, cp))
        quiet[k] = q
        k += 1
    eng.quit()
    return pieces[:k], stm[:k], cps[:k], depths[:k], quiet[:k]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("out")
    ap.add_argument("--positions", type=int, default=2_000_000)
    ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--skip-plies", type=int, default=10)
    ap.add_argument("--take-prob", type=float, default=0.25)
    ap.add_argument("--chunk", type=int, default=500_000)
    ap.add_argument("--start-chunk", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    print("collecting positions...", flush=True)
    fens = game_fens(a.pgn, a.skip_plies, a.take_prob, a.positions, seed=1)
    print(f"{len(fens):,} positions sampled; labelling at depth {a.depth} with {a.workers} workers", flush=True)
    batch = 2000
    jobs = [(fens[i : i + batch], a.depth) for i in range(0, len(fens), batch)]
    bufs: list[tuple] = []
    buffered = 0
    chunk_id = a.start_chunk
    done = 0
    with Pool(a.workers) as pool:
        for res in pool.imap_unordered(label, jobs):
            bufs.append(res)
            buffered += len(res[2])
            done += batch
            if done % 50_000 < batch:
                print(f"  {done:,}/{len(fens):,}", flush=True)
            if buffered >= a.chunk:
                np.savez(out / f"chunk_{chunk_id:04d}.npz", pieces=np.concatenate([b[0] for b in bufs]), stm=np.concatenate([b[1] for b in bufs]), cp=np.concatenate([b[2] for b in bufs]), depth=np.concatenate([b[3] for b in bufs]), quiet=np.concatenate([b[4] for b in bufs]))
                print(f"chunk {chunk_id} written ({buffered})", flush=True)
                chunk_id += 1
                bufs, buffered = [], 0
    if buffered:
        np.savez(out / f"chunk_{chunk_id:04d}.npz", pieces=np.concatenate([b[0] for b in bufs]), stm=np.concatenate([b[1] for b in bufs]), cp=np.concatenate([b[2] for b in bufs]), depth=np.concatenate([b[3] for b in bufs]), quiet=np.concatenate([b[4] for b in bufs]))
        print(f"chunk {chunk_id} written ({buffered})", flush=True)


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
