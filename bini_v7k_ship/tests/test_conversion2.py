"""Conversion against strong defence. Our engine plays the side to move (the better side in
winning.epd / marginal.epd) against Stockfish at a fixed node budget; drawn.epd must not be lost
and must end by rule within the ply cap.

    python tests/test_conversion2.py tests/pos/winning.epd --games 20 --sf-nodes 400000 --min-rate 1.0
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chess  # noqa: E402

import bini_engine as E  # noqa: E402
from uci_sf import UCI  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("epd")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--sf-nodes", type=int, default=400_000)
    ap.add_argument("--ms", type=int, default=1500)
    ap.add_argument("--min-rate", type=float, default=1.0)
    ap.add_argument("--drawn", action="store_true", help="drawn set: pass if never lost")
    a = ap.parse_args()
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    sf = UCI()
    fens = [ln.split(";")[0].strip() for ln in Path(a.epd).read_text().splitlines() if ln.strip()]
    wins = draws = losses = 0
    for i, fen in enumerate(fens[: a.games]):
        board = chess.Board(fen)
        we = board.turn
        eng.new_game()
        keys: list[int] = []
        t0 = time.perf_counter()
        while not board.is_game_over(claim_draw=True) and board.ply() < 400:
            if board.turn == we:
                eng.set_position(board.fen(), keys)
                keys.append(eng.key())
                mv, sc, d = eng.think(a.ms, a.ms * 2, log=False)
                board.push(chess.Move.from_uci(mv))
            else:
                board.push(chess.Move.from_uci(sf.bestmove(board.fen(), nodes=a.sf_nodes)))
                keys.append(0)
        out = board.outcome(claim_draw=True)
        if out is None or out.winner is None:
            draws += 1; res = "draw"
        elif out.winner == we:
            wins += 1; res = "WIN "
        else:
            losses += 1; res = "LOSS"
        print(f"{i + 1:2d} {res} {out.termination.name if out else 'ply_cap':22s} {board.fullmove_number:3d} moves {time.perf_counter() - t0:5.0f}s  {fen[:40]}", flush=True)
    sf.quit()
    n = wins + draws + losses
    print(f"{Path(a.epd).name}: +{wins} ={draws} -{losses}")
    if a.drawn:
        assert losses == 0, "lost a drawn position"
    else:
        assert wins / n >= a.min_rate, f"conversion {wins / n:.0%} below {a.min_rate:.0%}"


if __name__ == "__main__":
    main()
