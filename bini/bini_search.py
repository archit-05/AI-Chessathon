"""Alpha-beta search for Bini, compiled with numba.

Principal variation search with iterative deepening driven from Python (bini_engine.py), a
transposition table, killer / counter / history move ordering, null-move pruning, late move
reductions and pruning, reverse futility and futility pruning, a quiescence search with SEE and
delta pruning, check extension, mate-distance pruning, repetition and fifty-move detection.

All mutable state is passed in as numpy arrays; nothing jitted touches Python objects.
"""

from __future__ import annotations

import math
import time

import numpy as np
from numba import njit, objmode

from bini_board import (
    BLACK,
    KING,
    MAX_PLY,
    MF_CAPTURE,
    MF_CASTLE,
    MF_EP,
    MOVES_PER_PLY,
    PAWN,
    S_HALF,
    S_PLY,
    S_SIDE,
    SQBB,
    WHITE,
    ZERO,
    attackers_to,
    gen_moves,
    in_check,
    lsb,
    make,
    make_null,
    unmake,
    unmake_null,
)
from bini_eval import SEE_VALUE, evaluate_hce
from bini_nnue import nnue_copy, nnue_eval, nnue_move_piece, nnue_push

U64 = np.uint64

MATE = 30000
MATE_IN_MAX = MATE - MAX_PLY
INF = 32000
DRAW = 0

# info[] slots
I_NODES, I_ABORT, I_ROOT_MOVE, I_ROOT_SCORE, I_ROOT_DONE, I_SELDEPTH, I_ROOT_SIDE, I_CONTEMPT, I_USE_NNUE, I_TT_HITS, I_HIST_N, I_ROOT_MOVES, I_NMP_OFF = range(13)
INFO_SIZE = 16

TT_EXACT, TT_LOWER, TT_UPPER = 1, 2, 3
TT_BITS = 23  # 2^23 entries * 16 bytes = 128 MB
TT_SIZE = 1 << TT_BITS
TT_MASK = U64(TT_SIZE - 1)

# TT data packing: move 19 bits | score+32768 17 bits | depth 8 bits | flag 2 bits | age 8 bits
_SCORE_SHIFT = 19
_DEPTH_SHIFT = 36
_FLAG_SHIFT = 44
_AGE_SHIFT = 46

LMR_TABLE = np.zeros((64, 64), dtype=np.int64)
for _d in range(1, 64):
    for _m in range(1, 64):
        LMR_TABLE[_d, _m] = int(0.75 + math.log(_d) * math.log(_m) / 2.25)

LMP_TABLE = np.array([0, 5, 8, 12, 18, 26], dtype=np.int64)
FUTILITY_MARGIN = np.array([0, 110, 200, 300, 420], dtype=np.int64)
RFP_MARGIN = 75
HISTORY_MAX = 1 << 20


def new_tt() -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(TT_SIZE, dtype=np.uint64), np.zeros(TT_SIZE, dtype=np.int64)


def new_search_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    killers = np.zeros((MAX_PLY + 8, 2), dtype=np.int64)
    history = np.zeros(2 * 64 * 64, dtype=np.int64)
    counters = np.zeros(2 * 64 * 64, dtype=np.int64)
    scores = np.zeros((MAX_PLY + 8) * MOVES_PER_PLY, dtype=np.int64)
    info = np.zeros(INFO_SIZE, dtype=np.int64)
    hist = np.zeros(1024, dtype=np.uint64)
    return killers, history, counters, scores, info, hist


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------


@njit(cache=False, boundscheck=False)
def evaluate(bb, st, pcs, acc, info, w2, b2):
    if info[I_USE_NNUE] != 0:
        return nnue_eval(bb, st, acc, w2, b2)
    return evaluate_hce(bb, st, pcs)


@njit(cache=False, boundscheck=False)
def nnue_after_make(st, pcs, acc, ui, mv, w1):
    """Update the accumulator stack for the move just made (st[S_PLY] already incremented)."""
    ply = st[S_PLY] - 1
    side = 1 - st[S_SIDE]
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    landed = pcs[to]
    moved = (PAWN + side * 6) if promo != 0 else landed
    captured = ui[ply, 0]
    capsq = to
    if mv & MF_EP:
        capsq = to - 8 if side == WHITE else to + 8
    nnue_push(acc, ply, side, mv, moved, captured, landed if promo != 0 else 0, capsq, w1)
    if mv & MF_CASTLE:
        rook = 4 + side * 6
        if to == 6:
            nnue_move_piece(acc, ply + 1, rook, 7, 5, w1)
        elif to == 2:
            nnue_move_piece(acc, ply + 1, rook, 0, 3, w1)
        elif to == 62:
            nnue_move_piece(acc, ply + 1, rook, 63, 61, w1)
        else:
            nnue_move_piece(acc, ply + 1, rook, 56, 59, w1)


@njit(cache=False, boundscheck=False)
def see(bb, pcs, mv):
    """Static exchange evaluation of a capture (or promotion), from the mover's view."""
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    attacker = pcs[frm]
    side = 0 if attacker <= 6 else 1
    atype = attacker - side * 6
    if mv & MF_EP:
        target_val = SEE_VALUE[PAWN]
    else:
        tp = pcs[to]
        target_val = SEE_VALUE[tp - (6 if tp > 6 else 0)] if tp != 0 else 0
    gain = np.zeros(40, dtype=np.int64)
    d = 0
    gain[0] = target_val
    if promo != 0:
        gain[0] += SEE_VALUE[promo] - SEE_VALUE[PAWN]
        atype = promo
    occ = bb[14]
    from_bb = SQBB[frm]
    if mv & MF_EP:
        capsq = to - 8 if side == WHITE else to + 8
        occ ^= SQBB[capsq]
    cur_val = SEE_VALUE[atype]
    while True:
        d += 1
        gain[d] = cur_val - gain[d - 1]
        if (-gain[d - 1] if -gain[d - 1] > gain[d] else gain[d]) < 0:
            break
        occ ^= from_bb
        side = 1 - side
        att = attackers_to(bb, to, occ) & occ
        from_bb = ZERO
        # least valuable attacker of `side`
        for pt in range(1, 7):
            cand = att & bb[side * 6 + pt - 1]
            if cand != ZERO:
                from_bb = cand & (~cand + U64(1))
                cur_val = SEE_VALUE[pt]
                if pt == PAWN and (to >= 56 or to < 8):
                    cur_val += SEE_VALUE[5] - SEE_VALUE[PAWN]
                break
        if from_bb == ZERO:
            break
        if d >= 38:
            break
    while d > 1:
        d -= 1
        a = -gain[d - 1]
        b = gain[d]
        gain[d - 1] = -(a if a > b else b)
    return gain[0]


@njit(cache=False, boundscheck=False)
def is_repetition(bb, st, ub, hist, hist_n):
    """Has the current position occurred before, on the search path or in the game?"""
    key = bb[15]
    ply = st[S_PLY]
    half = st[S_HALF]
    # search path: positions at ply-2, ply-4, ... (same side to move), no further back than
    # the last irreversible move
    i = ply - 2
    steps = 2
    while i >= 0 and steps <= half:
        if ub[i] == key:
            return True
        i -= 2
        steps += 2
    # game history before the root (hist[hist_n-1] is the root position), continue the count
    j = hist_n - 1 - (ply & 1) - (2 if (ply & 1) == 0 else 1) + 1
    # simpler: walk backwards over history entries with the same parity as the current ply
    j = hist_n - 1
    # hist_n-1 is the root (ply 0); position at ply p has same parity as root when p is even
    if (ply & 1) == 1:
        j -= 1
    while j >= 0 and steps <= half:
        if hist[j] == key:
            return True
        j -= 2
        steps += 2
    return False


@njit(cache=False, boundscheck=False)
def tt_probe(tt_key, tt_data, key):
    idx = key & TT_MASK
    if tt_key[idx] == key:
        return tt_data[idx]
    return 0


@njit(cache=False, boundscheck=False)
def tt_store(tt_key, tt_data, key, mv, score, depth, flag, age, ply):
    idx = key & TT_MASK
    old = tt_data[idx]
    # replace if empty, same key, older, or shallower
    if old != 0 and tt_key[idx] != key:
        old_depth = (old >> _DEPTH_SHIFT) & 255
        old_age = (old >> _AGE_SHIFT) & 255
        if old_age == age and old_depth > depth + 2:
            return
    if score > MATE_IN_MAX:
        score += ply
    elif score < -MATE_IN_MAX:
        score -= ply
    if mv == 0 and tt_key[idx] == key:
        mv = old & 0x7FFFF
    data = (mv & 0x7FFFF) | ((score + 32768) << _SCORE_SHIFT) | (depth << _DEPTH_SHIFT) | (flag << _FLAG_SHIFT) | (age << _AGE_SHIFT)
    tt_key[idx] = key
    tt_data[idx] = data


@njit(cache=False, boundscheck=False)
def tt_move(data):
    return data & 0x7FFFF


@njit(cache=False, boundscheck=False)
def tt_score(data, ply):
    s = ((data >> _SCORE_SHIFT) & 0x1FFFF) - 32768
    if s > MATE_IN_MAX:
        s -= ply
    elif s < -MATE_IN_MAX:
        s += ply
    return s


@njit(cache=False, boundscheck=False)
def tt_depth(data):
    return (data >> _DEPTH_SHIFT) & 255


@njit(cache=False, boundscheck=False)
def tt_flag(data):
    return (data >> _FLAG_SHIFT) & 3


@njit(cache=False, boundscheck=False)
def mvv_lva(pcs, mv):
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    a = pcs[frm]
    if a > 6:
        a -= 6
    v = pcs[to]
    if v > 6:
        v -= 6
    if mv & MF_EP:
        v = PAWN
    s = SEE_VALUE[v] * 8 - a
    if promo != 0:
        s += SEE_VALUE[promo]
    return s


@njit(cache=False, boundscheck=False)
def pick_next(mv, scores, base, i, n):
    """Selection sort step: bring the best remaining move to slot i."""
    best = i
    bs = scores[base + i]
    for j in range(i + 1, n):
        if scores[base + j] > bs:
            bs = scores[base + j]
            best = j
    if best != i:
        tm = mv[base + i]
        mv[base + i] = mv[base + best]
        mv[base + best] = tm
        ts = scores[base + i]
        scores[base + i] = scores[base + best]
        scores[base + best] = ts
    return mv[base + i]


@njit(cache=False, boundscheck=False)
def check_time(info, tlim):
    if (info[I_NODES] & 4095) == 0:
        with objmode(now="float64"):
            now = time.perf_counter()
        if now >= tlim[0]:
            info[I_ABORT] = 1


# ----------------------------------------------------------------------------------------------
# quiescence
# ----------------------------------------------------------------------------------------------


@njit(cache=False, boundscheck=False)
def qsearch(bb, st, pcs, mv, ub, ui, acc, scores, info, tlim, w1, w2, b2, alpha, beta):
    info[I_NODES] += 1
    check_time(info, tlim)
    if info[I_ABORT] != 0:
        return 0
    ply = st[S_PLY]
    if ply > info[I_SELDEPTH]:
        info[I_SELDEPTH] = ply
    if ply >= MAX_PLY - 1:
        return evaluate(bb, st, pcs, acc, info, w2, b2)

    in_chk = in_check(bb, st)
    best = -INF
    if not in_chk:
        stand = evaluate(bb, st, pcs, acc, info, w2, b2)
        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand
        best = stand

    base = ply * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, not in_chk)
    for i in range(n):
        m = mv[base + i]
        s = mvv_lva(pcs, m) if (m & MF_CAPTURE) or ((m >> 12) & 7) != 0 else 0
        scores[base + i] = s
    legal = 0
    for i in range(n):
        m = pick_next(mv, scores, base, i, n)
        is_cap = (m & MF_CAPTURE) != 0
        promo = (m >> 12) & 7
        if not in_chk and is_cap:
            # delta pruning
            to = (m >> 6) & 63
            v = pcs[to]
            if v > 6:
                v -= 6
            if m & MF_EP:
                v = PAWN
            gainmax = SEE_VALUE[v] + (SEE_VALUE[promo] if promo != 0 else 0)
            if stand + gainmax + 150 <= alpha:
                continue
            if promo == 0 and see(bb, pcs, m) < 0:
                continue
        if not make(bb, st, pcs, m, ub, ui):
            continue
        legal += 1
        if info[I_USE_NNUE] != 0:
            nnue_after_make(st, pcs, acc, ui, m, w1)
        score = -qsearch(bb, st, pcs, mv, ub, ui, acc, scores, info, tlim, w1, w2, b2, -beta, -alpha)
        unmake(bb, st, pcs, ub, ui)
        if info[I_ABORT] != 0:
            return 0
        if score > best:
            best = score
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
    if in_chk and legal == 0:
        return -MATE + ply
    return best


# ----------------------------------------------------------------------------------------------
# main search
# ----------------------------------------------------------------------------------------------


@njit(cache=False, boundscheck=False)
def search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, depth, alpha, beta, do_null, age):
    ply = st[S_PLY]
    root = ply == 0
    pv_node = beta - alpha > 1
    if not root:
        # draws by rule, checked before anything else so frontier nodes see them too
        if st[S_HALF] >= 100 or is_repetition(bb, st, ub, hist, info[I_HIST_N]):
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    in_chk = in_check(bb, st)
    if in_chk and depth <= 0:
        depth = 1  # check extension at the frontier
    if depth <= 0:
        return qsearch(bb, st, pcs, mv, ub, ui, acc, scores, info, tlim, w1, w2, b2, alpha, beta)

    info[I_NODES] += 1
    check_time(info, tlim)
    if info[I_ABORT] != 0:
        return 0

    if not root:
        # mate distance pruning
        a = -MATE + ply
        if a > alpha:
            alpha = a
        b = MATE - ply - 1
        if b < beta:
            beta = b
        if alpha >= beta:
            return alpha
    if ply >= MAX_PLY - 1:
        return evaluate(bb, st, pcs, acc, info, w2, b2)

    # transposition table
    key = bb[15]
    data = tt_probe(tt_key, tt_data, key)
    ttm = 0
    if data != 0:
        info[I_TT_HITS] += 1
        ttm = tt_move(data)
        if not pv_node and tt_depth(data) >= depth:
            s = tt_score(data, ply)
            f = tt_flag(data)
            if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
                return s

    static = 0
    if not in_chk:
        static = evaluate(bb, st, pcs, acc, info, w2, b2)

    if not pv_node and not in_chk:
        # reverse futility pruning
        if depth <= 6 and static - RFP_MARGIN * depth >= beta and beta > -MATE_IN_MAX:
            return static
        # null move pruning: only with non-pawn material for the side to move
        if do_null and depth >= 2 and static >= beta and info[I_NMP_OFF] == 0:
            side = st[S_SIDE]
            npm = bb[side * 6 + 1] | bb[side * 6 + 2] | bb[side * 6 + 3] | bb[side * 6 + 4]
            if npm != ZERO:
                r = 3 + depth // 4
                bonus = (static - beta) // 200
                if bonus > 2:
                    bonus = 2
                r += bonus
                make_null(bb, st, ub, ui)
                if info[I_USE_NNUE] != 0:
                    nnue_copy(acc, ply)
                score = -search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, depth - 1 - r, -beta, -beta + 1, False, age)
                unmake_null(bb, st, ub, ui)
                if info[I_ABORT] != 0:
                    return 0
                if score >= beta:
                    if score > MATE_IN_MAX:
                        score = beta
                    # verification: at useful depth, confirm without a null move (zugzwang,
                    # mate threats the reduced search cannot see)
                    if depth >= 6:
                        v = search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, depth - r, beta - 1, beta, False, age)
                        if info[I_ABORT] != 0:
                            return 0
                        if v >= beta:
                            return score
                    else:
                        return score

    # move generation and ordering
    base = ply * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, False)
    side = st[S_SIDE]
    prev_mv = ui[ply - 1, 4] if ply > 0 else 0
    cm = counters[side * 4096 + (prev_mv & 4095)] if prev_mv != 0 else 0
    k0 = killers[ply, 0]
    k1 = killers[ply, 1]
    for i in range(n):
        m = mv[base + i]
        if m == ttm:
            s = 2000000000
        elif (m & MF_CAPTURE) or ((m >> 12) & 7) != 0:
            promo = (m >> 12) & 7
            if promo != 0 and promo != 5:
                s = -5000000 + mvv_lva(pcs, m)  # underpromotions last
            elif see(bb, pcs, m) >= 0:
                s = 1000000000 + mvv_lva(pcs, m)
            else:
                s = -1000000 + mvv_lva(pcs, m)
        elif m == k0:
            s = 900000000
        elif m == k1:
            s = 890000000
        elif m == cm:
            s = 880000000
        else:
            s = history[side * 4096 + (m & 4095)]
        scores[base + i] = s

    best = -INF
    best_move = 0
    alpha_orig = alpha
    legal = 0
    quiets_tried = 0
    futile = (not pv_node) and (not in_chk) and depth <= 4 and static + FUTILITY_MARGIN[depth] <= alpha
    for i in range(n):
        m = pick_next(mv, scores, base, i, n)
        is_cap = (m & MF_CAPTURE) != 0
        promo = (m >> 12) & 7
        quiet = (not is_cap) and promo == 0
        # late move pruning and futility pruning of quiet moves
        if quiet and not pv_node and not in_chk and legal > 0 and best > -MATE_IN_MAX:
            if depth <= 5 and quiets_tried >= LMP_TABLE[depth]:
                continue
            if futile and m != k0 and m != k1 and m != cm:
                continue
        if not make(bb, st, pcs, m, ub, ui):
            continue
        legal += 1
        if info[I_USE_NNUE] != 0:
            nnue_after_make(st, pcs, acc, ui, m, w1)
        if quiet:
            quiets_tried += 1
        gives_check = in_check(bb, st)
        new_depth = depth - 1
        if gives_check and depth <= 3 and not root:
            new_depth += 1
        score = 0
        if legal == 1:
            score = -search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, new_depth, -beta, -alpha, True, age)
        else:
            r = 0
            if quiet and depth >= 3 and legal >= (4 if pv_node else 2) and not in_chk and not gives_check:
                r = LMR_TABLE[depth if depth < 63 else 63, legal if legal < 63 else 63]
                if pv_node:
                    r -= 1
                if m == k0 or m == k1 or m == cm:
                    r -= 1
                if history[side * 4096 + (m & 4095)] > HISTORY_MAX // 8:
                    r -= 1
                if r < 0:
                    r = 0
                if r > new_depth - 1:
                    r = new_depth - 1
                if r < 0:
                    r = 0
            score = -search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, new_depth - r, -alpha - 1, -alpha, True, age)
            if r > 0 and score > alpha and info[I_ABORT] == 0:
                score = -search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, new_depth, -alpha - 1, -alpha, True, age)
            if score > alpha and score < beta and info[I_ABORT] == 0:
                score = -search(bb, st, pcs, mv, ub, ui, acc, tt_key, tt_data, killers, history, counters, scores, info, tlim, hist, w1, w2, b2, new_depth, -beta, -alpha, True, age)
        unmake(bb, st, pcs, ub, ui)
        if info[I_ABORT] != 0:
            return 0
        if score > best:
            best = score
            best_move = m
            if score > alpha:
                alpha = score
                if root:
                    info[I_ROOT_MOVE] = m
                    info[I_ROOT_SCORE] = score
                    info[I_ROOT_DONE] = legal
                if alpha >= beta:
                    if quiet:
                        if killers[ply, 0] != m:
                            killers[ply, 1] = killers[ply, 0]
                            killers[ply, 0] = m
                        if prev_mv != 0:
                            counters[side * 4096 + (prev_mv & 4095)] = m
                        bonus = depth * depth
                        hidx = side * 4096 + (m & 4095)
                        history[hidx] += bonus - history[hidx] * bonus // HISTORY_MAX
                        # penalise the quiet moves tried before this one
                        for j in range(i):
                            pm = mv[base + j]
                            if (pm & MF_CAPTURE) == 0 and ((pm >> 12) & 7) == 0:
                                pidx = side * 4096 + (pm & 4095)
                                history[pidx] -= bonus + history[pidx] * bonus // HISTORY_MAX
                    break
    if root:
        info[I_ROOT_MOVES] = legal
    if legal == 0:
        if in_chk:
            return -MATE + ply
        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    if best >= beta:
        flag = TT_LOWER
    elif best > alpha_orig:
        flag = TT_EXACT
    else:
        flag = TT_UPPER
    tt_store(tt_key, tt_data, key, best_move, best, depth, flag, age, ply)
    return best


@njit(cache=False, boundscheck=False)
def count_legal(bb, st, pcs, mv, ub, ui):
    base = st[S_PLY] * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, False)
    legal = 0
    only = 0
    for i in range(n):
        if make(bb, st, pcs, mv[base + i], ub, ui):
            unmake(bb, st, pcs, ub, ui)
            legal += 1
            only = mv[base + i]
    return legal, only
