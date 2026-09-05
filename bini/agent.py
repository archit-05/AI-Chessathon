"""AI Chessathon entry point for Bini.

    get_move(fen, time_left_ms) -> uci

Everything heavy compiles at import (inside the 90 s init budget). The wrapper reconstructs the
game history from the FENs it is handed (for repetition detection), budgets the clock, runs the
engine, validates the reply with python-chess and falls back to a tiny python-chess search if
anything at all goes wrong. A game is never lost to a crash or an illegal move.
"""

from __future__ import annotations

import gc
import os
import sys
import threading
import time

import chess

os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")

_T_IMPORT = time.perf_counter()

import numpy as np  # noqa: E402

import bini_board as B  # noqa: E402
import bini_engine as E  # noqa: E402
import bini_search as S  # noqa: E402

INCREMENT_MS = 500
RESERVE_MS = 1500          # never plan to dip below this
MIN_THINK_MS = 8
COMPILE_JOIN_S = 75.0      # hedge: hand back control before the init budget even if compiling


class GameState:
    """Tracks the game from the FENs we are asked about."""

    def __init__(self) -> None:
        self.board: chess.Board | None = None   # position after our last reply
        self.keys: list[int] = []               # zobrist keys of all earlier positions
        self.move_number = 0                    # our move count this game
        self.scratch = B.new_position()

    def _key(self, board: chess.Board) -> int:
        bb, st, pcs = self.scratch
        B.set_fen(bb, st, pcs, board.fen())
        return int(bb[15])

    def update(self, fen: str) -> chess.Board:
        board = chess.Board(fen)
        if self.board is not None:
            found = False
            for m in self.board.legal_moves:
                self.board.push(m)
                if self.board.board_fen() == board.board_fen() and self.board.turn == board.turn and self.board.castling_rights == board.castling_rights:
                    found = True
                    break
                self.board.pop()
            if found:
                # the position after the opponent's move is `board`; record its predecessor
                self.keys.append(self._key_before_last(board))
            else:
                self.board = None
                self.keys = []
                self.move_number = 0
        if self.board is None:
            self.board = board.copy()
        else:
            self.board = board.copy()
        return board

    def _key_before_last(self, board: chess.Board) -> int:
        # self.board currently equals the new position (opponent's move pushed); the position
        # before it is the one after our last reply, whose key we stored when we replied.
        return self._pending_key

    def record_reply(self, board: chess.Board, uci: str) -> None:
        # store the key of the position we were asked about, then the position after our move
        self.keys.append(self._key(board))
        after = board.copy()
        after.push(chess.Move.from_uci(uci))
        self._pending_key = self._key(after)
        self.board = after
        self.move_number += 1


_state = GameState()
_engine: E.Engine | None = None
_ready = threading.Event()
_compile_seconds = 0.0


def _build() -> None:
    global _engine, _compile_seconds
    eng = E.Engine(use_nnue=True)
    _compile_seconds = E.warm_up(eng)
    _engine = eng
    _ready.set()


def _fallback_move(board: chess.Board, budget_s: float) -> str:
    """python-chess 2-ply material search, only used if the jitted engine is unavailable."""
    values = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}

    def material(b: chess.Board) -> int:
        s = 0
        for pt, v in values.items():
            s += v * (len(b.pieces(pt, b.turn)) - len(b.pieces(pt, not b.turn)))
        return s

    deadline = time.perf_counter() + budget_s
    best, best_score = None, -10**9
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: (board.is_capture(m), m.promotion is not None), reverse=True)
    for m in moves:
        board.push(m)
        if board.is_checkmate():
            board.pop()
            return m.uci()
        worst = 10**9
        for r in board.legal_moves:
            board.push(r)
            worst = min(worst, material(board) if not board.is_checkmate() else 10**6)
            board.pop()
            if time.perf_counter() > deadline:
                break
        if not any(True for _ in board.legal_moves):
            worst = 0 if not board.is_check() else 10**6
        board.pop()
        score = worst if worst != 10**9 else material(board)
        if score > best_score:
            best_score, best = score, m
        if time.perf_counter() > deadline:
            break
    return (best or moves[0]).uci()


def _budget(time_left_ms: int, move_number: int) -> tuple[float, float]:
    """Soft and hard limits in milliseconds for this move."""
    if time_left_ms < 4000:
        # emergency: spend a fraction of what is left, whatever the increment turns out to be
        soft = min(0.4 * INCREMENT_MS, 0.05 * time_left_ms)
        hard = min(0.8 * INCREMENT_MS, 0.15 * time_left_ms)
        return max(MIN_THINK_MS, soft), max(MIN_THINK_MS, hard)
    mtg = max(16.0, 42.0 - 0.5 * move_number)
    soft = time_left_ms / mtg + 0.6 * INCREMENT_MS
    hard = min(3.0 * soft, 0.25 * time_left_ms, time_left_ms - RESERVE_MS)
    soft = min(soft, hard)
    return max(MIN_THINK_MS, soft), max(MIN_THINK_MS, hard)


def get_move(fen: str, time_left_ms: int) -> str:
    t0 = time.perf_counter()
    board = _state.update(fen)
    legal = list(board.legal_moves)
    if not legal:
        return "0000"
    if len(legal) == 1:
        uci = legal[0].uci()
        _state.record_reply(board, uci)
        return uci
    soft, hard = _budget(time_left_ms, _state.move_number)
    uci = None
    try:
        if not _ready.is_set():
            # still compiling (should not happen): wait a little, then use the fallback
            _ready.wait(timeout=max(0.0, min(hard / 1000.0 * 0.5, 2.0)))
        if _ready.is_set() and _engine is not None:
            eng = _engine
            if _state.move_number == 0:
                eng.new_game()
            eng.set_position(fen, _state.keys)
            overhead = (time.perf_counter() - t0) * 1000.0
            cand, score, depth = eng.think(soft, max(MIN_THINK_MS, hard - overhead), log=False)
            if chess.Move.from_uci(cand) in board.legal_moves:
                uci = cand
                spent = (time.perf_counter() - t0) * 1000.0
                print(f"{E.VERSION} m{_state.move_number + 1} d{depth} {cand} {score}cp {int(eng.info[S.I_NODES])}n {spent:.0f}ms left {time_left_ms}ms", file=sys.stderr, flush=True)
            else:
                print(f"{E.VERSION} ILLEGAL candidate {cand} in {fen}", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001 - any engine failure falls through to the fallback
        print(f"{E.VERSION} engine error: {exc!r}", file=sys.stderr, flush=True)
    if uci is None:
        remaining = min(1.5, (hard - (time.perf_counter() - t0) * 1000.0) / 1000.0, 0.08 * time_left_ms / 1000.0)
        remaining = max(0.01, remaining)
        uci = _fallback_move(board, remaining)
        if chess.Move.from_uci(uci) not in board.legal_moves:
            uci = legal[0].uci()
    _state.record_reply(board, uci)
    return uci


# ---- build at import: compile inside the init budget, but never hold the ready line hostage
_thread = threading.Thread(target=_build, daemon=True)
_thread.start()
_thread.join(timeout=COMPILE_JOIN_S)
gc.collect()
gc.freeze()
if _ready.is_set():
    print(f"{E.VERSION} ready: import+compile {time.perf_counter() - _T_IMPORT:.1f}s (compile {_compile_seconds:.1f}s), nnue={'on' if _engine is not None and _engine.use_nnue else 'off'}", file=sys.stderr, flush=True)
else:
    print(f"{E.VERSION} WARNING: still compiling after {COMPILE_JOIN_S:.0f}s, fallback engine active", file=sys.stderr, flush=True)
