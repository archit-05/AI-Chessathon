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

VERSION = "bini-5.0"


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
        self.prev_score = 0
        self.prev_score_valid = False
        self.root_guard = 0
        self.w1, self.b1, self.w2, self.b2 = N.W1, N.B1, N.W2, N.B2
        self.use_nnue = bool(use_nnue and N.LOADED)
        self.info[S.I_USE_NNUE] = 1 if self.use_nnue else 0
        self.contempt = 20
        self.info[S.I_CONTEMPT] = self.contempt
        self.info[S.I_CHECK_MASK] = 4095
        # search features under gate: flipped per build copy (or BINI_* env vars for local runs)
        # draw policy (V5): a repetition/fifty-move draw scores -contempt for us while we are better or
        # level, but once we are worse (previous root score <= BINI_DRAW_CP) after our BINI_DRAW_MOVE-th
        # move it scores 0, i.e. we take the draw the top teams offer instead of playing on into a loss
        self.draw_behind = int(os.environ.get("BINI_DRAW_BEHIND", "1")) != 0
        self.draw_cp = int(os.environ.get("BINI_DRAW_CP", "-100"))
        self.draw_move = int(os.environ.get("BINI_DRAW_MOVE", "20"))
        self.move_number = 0  # our move count in the game; the wrapper sets it before think()
        self.info[S.I_QS_CHECKS] = int(os.environ.get("BINI_QS_CHECKS", "0"))
        self.info[S.I_PROBCUT] = int(os.environ.get("BINI_PROBCUT", "0"))
        self.info[S.I_IMPROVING] = int(os.environ.get("BINI_IMPROVING", "0"))
        # V5 search items, each switchable for gating (default on): correction history,
        # continuation history + history pruning + history-driven LMR, SEE pruning in the main search
        self.info[S.I_CORR] = int(os.environ.get("BINI_CORR", "1"))
        self.info[S.I_CONT] = int(os.environ.get("BINI_CONT", "1"))
        self.info[S.I_SEEP] = int(os.environ.get("BINI_SEEP", "1"))
        self.info[S.I_CALIB] = int(os.environ.get("BINI_CALIB", "0"))  # V5 calibration table (bini_calib), gated alone

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

    def pv_line(self, max_plies: int = 8) -> list[str]:
        """Principal variation read back from the transposition table after a search."""
        line: list[str] = []
        made = 0
        for _ in range(max_plies):
            data = int(S.tt_probe(self.tt_key, self.tt_data, self.bb[15]))
            mv = int(S.tt_move(data)) if data != 0 else 0
            if mv == 0 or not B.make(self.bb, self.st, self.pcs, mv, self.ub, self.ui):
                break
            made += 1
            line.append(B.move_to_uci(mv))
            if len(self.legal_moves()) == 0:
                break
        for _ in range(made):
            B.unmake(self.bb, self.st, self.pcs, self.ub, self.ui)
        self.st[B.S_PLY] = 0
        return line

    # ------------------------------------------------------------------ search
    def new_game(self) -> None:
        self.prev_score_valid = False
        self.tt_key[:] = 0
        self.tt_data[:] = 0
        self.killers[:] = 0
        self.history[:] = 0
        self.counters[:] = 0
        self.scores[S.CORR_BASE:] = 0  # correction history is per game
        self.age = 0

    def think(self, soft_ms: float, hard_ms: float, max_depth: int = 64, log: bool = True, max_nodes: int = 0) -> tuple[str, int, int]:
        """Iterative deepening. Returns (uci, score_cp, depth).

        max_nodes > 0 also aborts the search once that many nodes have been counted (checked every
        I_CHECK_MASK nodes, so the abort point is deterministic); 0 leaves the search time-driven.
        """
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
        info[S.I_MAX_NODES] = int(max_nodes) if max_nodes > 0 else 0
        # tiny budgets are checked more often (a stalled machine cost one flag in 600 local games)
        # (a node cap uses the fine interval too, so the deterministic abort lands within 1024 nodes of it)
        info[S.I_CHECK_MASK] = 1023 if (hard_ms < 200.0 or max_nodes > 0) else 4095
        # draw policy: a repetition or fifty-move draw is worth -contempt for us in a level game,
        # but when we are clearly worse (by our own previous score) a draw is welcome: score it 0
        # (the "draw is welcome when clearly worse" rule is held behind BINI_DRAW_BEHIND until it
        # has its own gate against Stockfish 1800-2000, after the endgame bias of the net is fixed)
        info[S.I_CONTEMPT] = 0 if (self.draw_behind and self.prev_score_valid and self.prev_score <= self.draw_cp and self.move_number >= self.draw_move) else self.contempt
        rg_fired = 0
        self.root_guard = 0  # per-move count of root-guard extensions, logged as rg<n>
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
                    factor = 0.75
                elif stable == 0 and depth >= 6:
                    factor = 1.3
                # danger: the score fell since our previous move -> think longer, not shorter
                if self.prev_score_valid and depth >= 8 and best_score < self.prev_score - 25:
                    factor = max(factor, 1.0) * 1.5
                if abs(best_score) > 400 and stable >= 2 and depth >= 10:
                    factor *= 0.6  # decided position: save the clock for when it is needed
                # root guard: a best move that hangs material by static exchange (and is not a
                # mate) is treated as unstable, so the search keeps deepening to the hard limit
                # before committing to it
                # (only in level positions, and for at most two extra iterations: a sound
                # sacrifice with a clear score does not need 7 s of confirmation)
                if best_move != 0 and abs(best_score) <= 150 and depth >= 8 and rg_fired < 2:
                    if S.see(self.bb, self.pcs, best_move) < -150:
                        factor = 2.5
                        rg_fired += 1
                        self.root_guard += 1
                if factor > 2.5:
                    factor = 2.5
                if elapsed >= soft_ms * factor:
                    break
                # a floor of half the budget, so a "stable" move in a slow squeeze still gets depth
                if depth >= 6 and elapsed + 2.0 * last_iter_s * 1000.0 > soft_ms * factor and elapsed >= 0.5 * soft_ms:
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
        self.prev_score = best_score
        self.prev_score_valid = True
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
