"""Engine driver: owns the position, the tables and the clock; runs iterative deepening.

Python here is cheap: one call per iteration into the jitted search. Everything hot is in
bini_search.py.
"""

from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np

import bini_board as B
import bini_nnue as N
import bini_search as S

VERSION = "bini-2.0"


class Engine:
    def __init__(self, use_nnue: bool = True, tt_bits: int | None = None) -> None:
        self.bb, self.st, self.pcs = B.new_position()
        self.ub, self.ui = B.new_undo()
        self.mv = B.new_move_stack()
        self.acc = N.new_accumulators()
        self.tt_key, self.tt_data = S.new_tt()
        self.killers, self.history, self.counters, self.scores, self.info, self.hist = S.new_search_tables()
        self.tlim = np.zeros(2, dtype=np.float64)
        self.age = 0
        self.nps_estimate = 400_000.0
        self.w1, self.b1, self.w2, self.b2 = N.W1, N.B1, N.W2, N.B2
        self.use_nnue = bool(use_nnue and N.LOADED)
        self.info[S.I_USE_NNUE] = 1 if self.use_nnue else 0
        self.info[S.I_CONTEMPT] = 20

    # ------------------------------------------------------------------ position handling
    def set_position(self, fen: str, history_keys: list[int]) -> None:
        """history_keys: zobrist keys of earlier game positions, oldest first (root excluded)."""
        B.set_fen(self.bb, self.st, self.pcs, fen)
        n = len(history_keys)
        if n + 1 > self.hist.shape[0]:
            self.hist = np.zeros(n + 256, dtype=np.uint64)
        for i, k in enumerate(history_keys):
            self.hist[i] = np.uint64(k)
        self.hist[n] = self.bb[15]
        self.info[S.I_HIST_N] = n + 1
        self.info[S.I_ROOT_SIDE] = int(self.st[B.S_SIDE])
        if self.use_nnue:
            N.nnue_refresh(self.bb, self.st, self.pcs, self.acc, self.w1, self.b1)

    def key(self) -> int:
        return int(self.bb[15])

    def play_uci(self, uci: str) -> bool:
        m = B.uci_to_move(self.bb, self.st, self.pcs, uci)
        if m == 0:
            return False
        ok = B.make(self.bb, self.st, self.pcs, m, self.ub, self.ui)
        if ok:
            self.st[B.S_PLY] = 0  # keep the root at ply 0
        return bool(ok)

    def legal_moves(self) -> list[str]:
        n = B.gen_moves(self.bb, self.st, self.pcs, self.mv, 0, False)
        out = []
        for i in range(n):
            m = int(self.mv[i])
            if B.make(self.bb, self.st, self.pcs, m, self.ub, self.ui):
                B.unmake(self.bb, self.st, self.pcs, self.ub, self.ui)
                out.append(B.move_to_uci(m))
        return out

    def static_eval(self) -> int:
        return int(S.evaluate(self.bb, self.st, self.pcs, self.acc, self.info, self.w2, self.b2))

    # ------------------------------------------------------------------ search
    def new_game(self) -> None:
        self.tt_key[:] = 0
        self.tt_data[:] = 0
        self.killers[:] = 0
        self.history[:] = 0
        self.counters[:] = 0
        self.age = 0

    def think(self, soft_ms: float, hard_ms: float, max_depth: int = 64, log: bool = True) -> tuple[str, int, int]:
        """Iterative deepening. Returns (uci, score_cp, depth)."""
        start = time.perf_counter()
        self.tlim[0] = start + hard_ms / 1000.0
        self.age = (self.age + 1) & 255
        self.killers[:] = 0
        info = self.info
        info[S.I_NODES] = 0
        info[S.I_ABORT] = 0
        info[S.I_SELDEPTH] = 0
        info[S.I_TT_HITS] = 0
        info[S.I_SINGULAR] = 0
        info[S.I_MULTICUT] = 0
        info[S.I_QS_TTCUT] = 0
        info[S.I_EXCL_NODES] = 0
        # history ages between moves so old knowledge fades
        self.history //= 2

        n_legal, only = S.count_legal(self.bb, self.st, self.pcs, self.mv, self.ub, self.ui)
        if n_legal == 0:
            return "0000", 0, 0
        if n_legal == 1:
            return B.move_to_uci(int(only)), 0, 1

        best_move = 0
        best_score = 0
        completed_depth = 0
        prev_best = 0
        stable = 0
        gc_was_enabled = gc.isenabled()
        gc.disable()
        last_iter_s = 0.0
        try:
            depth = 1
            alpha, beta = -S.INF, S.INF
            window = 25
            while depth <= max_depth:
                info[S.I_ROOT_MOVE] = 0
                info[S.I_ROOT_DONE] = 0
                iter_start = time.perf_counter()
                score = S.search(self.bb, self.st, self.pcs, self.mv, self.ub, self.ui, self.acc, self.tt_key, self.tt_data, self.killers, self.history, self.counters, self.scores, info, self.tlim, self.hist, self.w1, self.b1, self.w2, self.b2, depth, alpha, beta, self.age)
                self.st[B.S_PLY] = 0
                if info[S.I_ABORT]:
                    # trust a fully searched, alpha-raising root move from the aborted iteration
                    # only if it is the same move we already trusted or it was searched first
                    rm = int(info[S.I_ROOT_MOVE])
                    if rm != 0 and int(info[S.I_ROOT_DONE]) == 1 and best_move == 0:
                        best_move = rm
                    break
                if score <= alpha or score >= beta:
                    # aspiration fail: widen and repeat this depth
                    if score <= alpha:
                        alpha = max(-S.INF, alpha - window)
                    else:
                        beta = min(S.INF, beta + window)
                    window *= 2
                    if window > 800:
                        alpha, beta = -S.INF, S.INF
                    continue
                rm = int(info[S.I_ROOT_MOVE])
                if rm != 0:
                    best_move = rm
                    best_score = int(score)
                    completed_depth = depth
                    if rm == prev_best:
                        stable += 1
                    else:
                        stable = 0
                    prev_best = rm
                elapsed = (time.perf_counter() - start) * 1000.0
                if log:
                    print(f"{VERSION} d{depth}/{int(info[S.I_SELDEPTH])} {B.move_to_uci(best_move)} {best_score}cp {int(info[S.I_NODES])}n {elapsed:.0f}ms", file=sys.stderr)
                if abs(best_score) > S.MATE_IN_MAX:
                    if best_score > 0 and depth >= (S.MATE - best_score):
                        break
                    if depth >= 8 and best_score > 0:
                        break
                # time management: a new iteration starts only if it is predicted to finish
                # inside the soft budget (the next iteration costs ~2x the last one), so the
                # real spend tracks the budget instead of overrunning to the hard limit
                last_iter_s = time.perf_counter() - iter_start
                factor = 1.0
                if stable >= 3:
                    factor = 0.6
                elif stable == 0 and depth >= 6:
                    factor = 1.3
                if abs(best_score) > 400 and stable >= 2 and depth >= 10:
                    factor *= 0.6  # decided position: save the clock for when it is needed
                if elapsed >= soft_ms * factor:
                    break
                if depth >= 6 and elapsed + 2.0 * last_iter_s * 1000.0 > soft_ms * factor:
                    break
                depth += 1
                window = 25
                alpha = best_score - window
                beta = best_score + window
                if depth <= 4:
                    alpha, beta = -S.INF, S.INF
        finally:
            if gc_was_enabled:
                gc.enable()
        elapsed = time.perf_counter() - start
        nodes = int(info[S.I_NODES])
        if elapsed > 0.05 and nodes > 0:
            self.nps_estimate = 0.7 * self.nps_estimate + 0.3 * (nodes / elapsed)
        if best_move == 0:
            # should not happen; fall back to the first legal move
            best_move = int(only) if n_legal == 1 else B.uci_to_move(self.bb, self.st, self.pcs, self.legal_moves()[0])
        return B.move_to_uci(best_move), best_score, completed_depth


def warm_up(engine: Engine) -> float:
    """Compile every jitted path with the real argument types. Returns seconds taken."""
    t0 = time.perf_counter()
    B.warm_up()
    engine.set_position("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [])
    saved = engine.info[S.I_USE_NNUE]
    for flag in (0, 1):
        engine.info[S.I_USE_NNUE] = flag
        if flag == 1:
            N.nnue_refresh(engine.bb, engine.st, engine.pcs, engine.acc, engine.w1, engine.b1)
        engine.think(50, 150, max_depth=4, log=False)
        engine.static_eval()
    engine.info[S.I_USE_NNUE] = saved
    # castling + promotion + en passant paths through the NNUE update
    engine.set_position("r3k2r/pP1p1ppp/8/2pP4/8/8/P1P1PPPP/R3K2R w KQkq c6 0 1", [])
    engine.think(30, 100, max_depth=3, log=False)
    engine.new_game()
    return time.perf_counter() - t0
