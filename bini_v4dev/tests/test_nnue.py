"""Gate 4a: the numba NNUE forward pass (with incremental updates through a random game)
matches a float re-implementation of the quantised network to within rounding, and the
incremental accumulators never drift from a fresh refresh."""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402
import numpy as np  # noqa: E402

import bini_board as B  # noqa: E402
import bini_engine as E  # noqa: E402
import bini_nnue as N  # noqa: E402
import bini_search as S  # noqa: E402


def reference_eval(w1, b1, w2, b2, board: chess.Board) -> int:
    acc = [b1.astype(np.int64).copy(), b1.astype(np.int64).copy()]
    kings = {0: board.king(chess.WHITE), 1: board.king(chess.BLACK)}
    for p in range(2):
        ksq = kings[p] if p == 0 else kings[p] ^ 56
        kid = int(N.KB_TABLE[ksq])
        for sq, piece in board.piece_map().items():
            colour = 0 if piece.color == chess.WHITE else 1
            kind = (piece.piece_type - 1) * 2 + (0 if colour == p else 1)
            s = sq if p == 0 else sq ^ 56
            if kid & 1:
                s ^= 7
            acc[p] += w1[(kid >> 1) * 768 + kind * 64 + s].astype(np.int64)
    stm = 0 if board.turn == chess.WHITE else 1
    h_stm = np.clip(acc[stm], 0, N.QA)
    h_n = np.clip(acc[1 - stm], 0, N.QA)
    if N.ACT_SQ:
        h_stm = h_stm * h_stm
        h_n = h_n * h_n
    ob = N.out_bucket(len(board.piece_map()))
    total = int(np.dot(h_stm, w2[ob, :N.HIDDEN].astype(np.int64)) + np.dot(h_n, w2[ob, N.HIDDEN:].astype(np.int64)) + int(b2[ob]))
    return total // int(b2[N.NO])


def main() -> None:
    eng = E.Engine(use_nnue=True)
    assert eng.use_nnue, "nnue.safetensors missing"
    E.warm_up(eng)
    rng = random.Random(11)
    checked = 0
    for g in range(60):
        board = chess.Board()
        eng.new_game()
        eng.set_position(board.fen(), [])
        for ply in range(rng.randint(10, 120)):
            moves = list(board.legal_moves)
            if not moves:
                break
            # walk the engine's incremental path: make the move on the engine, do not refresh
            m = rng.choice(moves)
            mv = B.uci_to_move(eng.bb, eng.st, eng.pcs, m.uci())
            assert mv != 0
            assert B.make(eng.bb, eng.st, eng.pcs, mv, eng.ub, eng.ui)
            N.nnue_after_make(eng.bb, eng.st, eng.pcs, eng.acc, eng.ui, mv, eng.w1, eng.b1, eng.c_acc, eng.c_pcs, eng.c_valid)
            board.push(m)
            inc = int(N.nnue_eval(eng.bb, eng.st, eng.acc, eng.w2, eng.b2))
            ref = reference_eval(eng.w1, eng.b1, eng.w2, eng.b2, board)
            assert inc == ref, (inc, ref, board.fen(), m.uci())
            checked += 1
            if eng.st[B.S_PLY] > B.MAX_PLY - 4:
                break
    print(f"nnue incremental == reference on {checked} positions across 60 random games: ok")
    # the search must run with the NNUE on
    eng.new_game(); eng.set_position("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", [])
    mv, sc, d = eng.think(1000, 1500, log=False)
    print(f"nnue search: {mv} {sc}cp depth {d} nodes {int(eng.info[S.I_NODES])}")


if __name__ == "__main__":
    main()
