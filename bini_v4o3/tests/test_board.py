"""Gate 1: perft on the standard suite and a differential test against python-chess.

Run:  uv run python tests/test_board.py [n_random_positions]
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chess  # noqa: E402
import numpy as np  # noqa: E402

import bini_board as B  # noqa: E402

PERFT_SUITE = [
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", [20, 400, 8902, 197281, 4865609]),
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039, 97862, 4085603]),
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238, 674624]),
    ("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467, 422333]),
    ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379, 2103487]),
    ("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", [46, 2079, 89890, 3894594]),
]


def legal_ucis(bb, st, pcs, mv, ub, ui) -> list[str]:
    n = B.gen_moves(bb, st, pcs, mv, 0, False)
    out = []
    for i in range(n):
        m = int(mv[i])
        if B.make(bb, st, pcs, m, ub, ui):
            B.unmake(bb, st, pcs, ub, ui)
            out.append(B.move_to_uci(m))
    return sorted(out)


def capture_ucis(bb, st, pcs, mv, ub, ui) -> list[str]:
    n = B.gen_moves(bb, st, pcs, mv, 0, True)
    out = []
    for i in range(n):
        m = int(mv[i])
        if B.make(bb, st, pcs, m, ub, ui):
            B.unmake(bb, st, pcs, ub, ui)
            out.append(B.move_to_uci(m))
    return sorted(out)


def check_same(board: chess.Board, bb, st, pcs) -> None:
    assert B.to_fen_board(pcs) == board.board_fen(), (B.to_fen_board(pcs), board.board_fen())
    assert st[B.S_SIDE] == (0 if board.turn else 1)
    rights = 0
    if board.has_kingside_castling_rights(chess.WHITE):
        rights |= 1
    if board.has_queenside_castling_rights(chess.WHITE):
        rights |= 2
    if board.has_kingside_castling_rights(chess.BLACK):
        rights |= 4
    if board.has_queenside_castling_rights(chess.BLACK):
        rights |= 8
    assert st[B.S_CASTLE] == rights, (st[B.S_CASTLE], rights, board.fen())
    ep = board.ep_square if board.has_legal_en_passant() else None
    # ours keeps ep whenever a pawn stands to capture, python-chess only when the capture is legal
    if ep is not None:
        assert st[B.S_EP] == ep, (st[B.S_EP], ep, board.fen())
    for i in range(12):
        assert bb[12] == (bb[0] | bb[1] | bb[2] | bb[3] | bb[4] | bb[5])
    assert bb[14] == (bb[12] | bb[13])
    assert bb[15] == B.compute_key(bb, st, pcs), "incremental key drifted"


def main() -> None:
    n_random = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    t0 = time.perf_counter()
    B.warm_up()
    print(f"compile {time.perf_counter() - t0:.2f}s")

    bb, st, pcs = B.new_position()
    ub, ui = B.new_undo()
    mv = B.new_move_stack()

    # ---- perft
    total_nodes = 0
    t0 = time.perf_counter()
    for fen, counts in PERFT_SUITE:
        for depth, expect in enumerate(counts, start=1):
            B.set_fen(bb, st, pcs, fen)
            got = B.perft(bb, st, pcs, mv, ub, ui, depth)
            total_nodes += got
            status = "ok" if got == expect else f"FAIL expected {expect}"
            if got != expect:
                print(f"perft d{depth} {fen}: got {got} {status}")
                raise SystemExit(1)
    dt = time.perf_counter() - t0
    print(f"perft suite ok: {total_nodes:,} leaf nodes in {dt:.2f}s ({total_nodes / dt / 1e6:.2f} M leaves/s)")

    # ---- differential random walks
    rng = random.Random(7)
    positions = 0
    t0 = time.perf_counter()
    while positions < n_random:
        board = chess.Board()
        # random start variety: sometimes drop to a random legal middlegame by playing fast
        for _ in range(rng.randint(0, 120)):
            moves = list(board.legal_moves)
            if not moves or board.is_game_over():
                break
            # bias toward captures/promotions/castles to hit the rare paths
            weights = []
            for m in moves:
                w = 1.0
                if board.is_capture(m):
                    w += 2.0
                if m.promotion:
                    w += 6.0
                if board.is_castling(m):
                    w += 6.0
                if board.is_en_passant(m):
                    w += 10.0
                weights.append(w)
            m = rng.choices(moves, weights)[0]
            board.push(m)
            B.set_fen(bb, st, pcs, board.fen())
            ours = legal_ucis(bb, st, pcs, mv, ub, ui)
            theirs = sorted(x.uci() for x in board.legal_moves)
            if ours != theirs:
                print("MISMATCH", board.fen())
                print(" ours  ", ours)
                print(" theirs", theirs)
                raise SystemExit(1)
            caps = capture_ucis(bb, st, pcs, mv, ub, ui)
            their_caps = sorted(
                x.uci() for x in board.legal_moves
                if (board.is_capture(x) and x.promotion in (None, chess.QUEEN))
                or x.promotion == chess.QUEEN
            )
            if caps != their_caps:
                print("CAPTURE MISMATCH", board.fen())
                print(" ours  ", caps)
                print(" theirs", their_caps)
                raise SystemExit(1)
            # make/unmake round trip through every legal move, compare state after make
            for uci in ours:
                m = B.uci_to_move(bb, st, pcs, uci)
                assert m != 0
                snapshot = (bb.copy(), st.copy(), pcs.copy())
                assert B.make(bb, st, pcs, m, ub, ui)
                b2 = board.copy()
                b2.push(chess.Move.from_uci(uci))
                check_same(b2, bb, st, pcs)
                B.unmake(bb, st, pcs, ub, ui)
                assert np.array_equal(bb, snapshot[0]) and np.array_equal(st, snapshot[1]) and np.array_equal(pcs, snapshot[2]), ("unmake drift", uci, board.fen())
            positions += 1
            if positions >= n_random:
                break
    dt = time.perf_counter() - t0
    print(f"differential ok: {positions:,} positions, every legal move made/unmade, in {dt:.1f}s")


if __name__ == "__main__":
    main()
