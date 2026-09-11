"""Turn the site's own per-position evaluations (Stockfish 16, depth 16, embedded in every game
page the intel scraper cached) into training chunks in the tools/stream_lichess.py format, plus
`result` for WDL blending.

    python tools/site_labelled.py ../intel/raw/cache/games ../data/site_labelled

Writes chunk_0000.npz (training games) and chunk_0001.npz (held-out games, ~15% by game id) so
the validation set never shares a game with the training set. Positions with the side to move in
check are skipped; mates (+-(10000-n)) clip to +-3000; cp is White's point of view.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

import chess
import chess.pgn
import numpy as np

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}


def main() -> None:
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    split: dict[str, list[list]] = {"train": [[], [], [], [], [], []], "val": [[], [], [], [], [], []]}
    games = skipped = 0
    for f in sorted(src.glob("*.json")):
        try:
            d = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        ev, pgn = d.get("evals"), d.get("pgn")
        if not ev or not ev.get("cp") or not pgn:
            skipped += 1
            continue
        cps, bests = ev["cp"], ev.get("best") or []
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            skipped += 1
            continue
        res = {"1-0": 1, "0-1": -1}.get(game.headers.get("Result", "*"), 0)
        which = "val" if int(hashlib.md5(f.stem.encode()).hexdigest(), 16) % 100 < 15 else "train"
        P, S, C, Q, R, D = split[which]
        board = game.board()
        moves = list(game.mainline_moves())
        for ply in range(len(moves) + 1):
            if ply < len(cps) and cps[ply] is not None and not board.is_check():
                cp = int(cps[ply])
                if abs(cp) >= 9000:
                    cp = 3000 if cp > 0 else -3000
                cp = max(-3000, min(3000, cp))
                row = np.zeros(64, dtype=np.uint8)
                for sq, pc in board.piece_map().items():
                    row[sq] = CODES[pc.symbol()]
                q = 1
                if ply < len(bests) and bests[ply]:
                    try:
                        bm = chess.Move.from_uci(bests[ply])
                        if board.is_capture(bm) or bm.promotion is not None:
                            q = 0
                    except Exception:  # noqa: BLE001
                        pass
                P.append(row); S.append(0 if board.turn else 1); C.append(cp); Q.append(q); R.append(res); D.append(16)
            if ply < len(moves):
                board.push(moves[ply])
        games += 1
    for i, which in enumerate(("train", "val")):
        P, S, C, Q, R, D = split[which]
        np.savez(out / f"chunk_{i:04d}.npz", pieces=np.array(P, dtype=np.uint8), stm=np.array(S, dtype=np.uint8), cp=np.array(C, dtype=np.int16), depth=np.array(D, dtype=np.uint8), quiet=np.array(Q, dtype=np.uint8), result=np.array(R, dtype=np.int8))
        print(f"{which}: {len(C):,} positions -> chunk_{i:04d}.npz")
    print(f"{games} games converted, {skipped} skipped")


if __name__ == "__main__":
    main()
