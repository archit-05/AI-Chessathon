"""Hand-crafted tapered evaluation for Bini (the fallback when the NNUE is not in use).

Every table below is generated at import from a few named terms, so the numbers are ours and
the intent is readable: centralisation, pawn advancement, king shelter in the middlegame and
king activity in the endgame. Scores are centipawns from the side to move's point of view.
"""

from __future__ import annotations

import os

import numpy as np
from numba import njit

from bini_board import (
    BLACK,
    KING_ATT,
    KNIGHT_ATT,
    PAWN_ATT,
    S_SIDE,
    SQBB,
    WHITE,
    ZERO,
    bishop_att,
    lsb,
    popcount,
    rook_att,
)

U64 = np.uint64

# material, middlegame / endgame (index by piece type 1..6)
MAT_MG = np.array([0, 82, 337, 365, 477, 1025, 0], dtype=np.int64)
MAT_EG = np.array([0, 94, 281, 297, 512, 936, 0], dtype=np.int64)
# plain values for SEE and move ordering
SEE_VALUE = np.array([0, 100, 320, 330, 500, 950, 20000], dtype=np.int64)
PHASE_INC = np.array([0, 0, 1, 1, 2, 4, 0], dtype=np.int64)
PHASE_MAX = 24

TEMPO = 12


def _centre_dist(sq: int) -> float:
    r, f = divmod(sq, 8)
    return max(abs(f - 3.5), abs(r - 3.5)) - 0.5  # 0 for the four centre squares, 3 for corners


def _build_tables() -> tuple[np.ndarray, np.ndarray]:
    """PST_MG / PST_EG indexed by (piece_code - 1) * 64 + square, black mirrored."""
    mg = np.zeros(12 * 64, dtype=np.int64)
    eg = np.zeros(12 * 64, dtype=np.int64)
    pawn_adv_mg = [0, 0, 4, 9, 18, 32, 55, 0]
    pawn_adv_eg = [0, 0, 8, 16, 30, 55, 95, 0]
    for sq in range(64):
        r, f = divmod(sq, 8)
        cd = _centre_dist(sq)
        # pawn: advance, prefer central pawns advanced, discourage f/g/h pawns wandering early
        p_mg = pawn_adv_mg[r] + (12 if (f in (3, 4) and 3 <= r <= 4) else 0) - (6 if (f in (0, 7) and r == 1) else 0)
        if r == 1 and f in (3, 4):
            p_mg -= 12  # unmoved d/e pawns block development
        p_eg = pawn_adv_eg[r] + (4 if f in (3, 4) else 0)
        # knight: strong centralisation, rim penalty
        n_mg = int(28 - 14 * cd)
        n_eg = int(18 - 9 * cd)
        if r == 0:
            n_mg -= 10
        # bishop: mild centralisation, long diagonals, back rank slightly negative
        b_mg = int(16 - 6 * cd) + (6 if (r == f or r + f == 7) and cd <= 1 else 0)
        b_eg = int(14 - 5 * cd)
        if r == 0:
            b_mg -= 8
        # rook: seventh rank, central files
        r_mg = (18 if r == 6 else 0) + (5 if f in (3, 4) else 0) - (4 if f in (0, 7) and r == 0 else 0)
        r_eg = 8 if r == 6 else 0
        # queen: slight centralisation, not out early
        q_mg = int(6 - 3 * cd) - (8 if r >= 4 else 0)
        q_eg = int(10 - 4 * cd)
        # king: shelter in the middlegame, centre in the endgame
        k_mg = (24 if (r == 0 and f in (1, 2, 6, 7)) else 0) + (-10 if (r == 0 and f in (3, 4)) else 0)
        k_mg -= 35 * r  # any advance of the king in the middlegame is punished
        k_mg -= int(8 * (3 - cd)) if r > 0 else 0
        k_eg = int(36 - 14 * cd)
        for code, vmg, veg in ((1, p_mg, p_eg), (2, n_mg, n_eg), (3, b_mg, b_eg), (4, r_mg, r_eg), (5, q_mg, q_eg), (6, k_mg, k_eg)):
            mg[(code - 1) * 64 + sq] = vmg
            eg[(code - 1) * 64 + sq] = veg
            msq = (7 - r) * 8 + f
            mg[(code + 6 - 1) * 64 + msq] = vmg
            eg[(code + 6 - 1) * 64 + msq] = veg
    return mg, eg


PST_MG, PST_EG = _build_tables()

PASSED_MG = np.array([0, 4, 8, 16, 30, 55, 95, 0], dtype=np.int64)
PASSED_EG = np.array([0, 10, 18, 35, 65, 115, 185, 0], dtype=np.int64)
ISOLATED_MG, ISOLATED_EG = 11, 14
DOUBLED_MG, DOUBLED_EG = 9, 20
BISHOP_PAIR_MG, BISHOP_PAIR_EG = 28, 48
ROOK_OPEN_MG, ROOK_OPEN_EG = 26, 10
ROOK_SEMI_MG, ROOK_SEMI_EG = 12, 6
MOB_MG = np.array([0, 0, 4, 4, 2, 1, 0], dtype=np.int64)
MOB_EG = np.array([0, 0, 3, 4, 4, 3, 0], dtype=np.int64)
SHIELD_MG = 12
KING_OPEN_FILE_MG = 18
ATTACK_WEIGHT = np.array([0, 0, 2, 2, 3, 5, 0], dtype=np.int64)
# king danger by attack units: gentle then steep
KING_DANGER = np.array([0, 0, 2, 5, 9, 15, 22, 31, 42, 55, 70, 87, 106, 127, 150, 175, 200, 225, 250, 275, 300, 320, 340, 360, 380, 400, 420, 440, 460, 480, 500, 520], dtype=np.int64)

FILE_MASK = np.array([0x0101010101010101 << f for f in range(8)], dtype=np.uint64)
ADJ_FILES = np.zeros(8, dtype=np.uint64)
for _f in range(8):
    _m = 0
    if _f > 0:
        _m |= 0x0101010101010101 << (_f - 1)
    if _f < 7:
        _m |= 0x0101010101010101 << (_f + 1)
    ADJ_FILES[_f] = _m
# squares in front of a pawn (same and adjacent files) for passed-pawn tests
FRONT_SPAN = np.zeros((2, 64), dtype=np.uint64)
for _sq in range(64):
    _r, _f = divmod(_sq, 8)
    _files = int(FILE_MASK[_f] | ADJ_FILES[_f])
    _w = 0
    for _rr in range(_r + 1, 8):
        _w |= 0xFF << (_rr * 8)
    _b = 0
    for _rr in range(0, _r):
        _b |= 0xFF << (_rr * 8)
    FRONT_SPAN[0, _sq] = _files & _w
    FRONT_SPAN[1, _sq] = _files & _b
CENTRE_MANHATTAN = np.array([max(abs((s & 7) - 3.5), 0) + max(abs((s >> 3) - 3.5), 0) for s in range(64)]).astype(np.int64)


@njit(cache=False, boundscheck=False)
def _dist(a, b):
    df = (a & 7) - (b & 7)
    dr = (a >> 3) - (b >> 3)
    if df < 0:
        df = -df
    if dr < 0:
        dr = -dr
    return df if df > dr else dr


@njit(cache=False, boundscheck=False)
def evaluate_hce(bb, st, pcs):
    """Tapered evaluation from the side to move's point of view."""
    mg = 0
    eg = 0
    phase = 0
    occ = bb[14]
    npm_w = 0
    npm_b = 0

    for side in range(2):
        sign = 1 if side == WHITE else -1
        off = side * 6
        them = 1 - side
        occ_us = bb[12 + side]
        our_pawns = bb[off]
        their_pawns = bb[them * 6]
        ksq = lsb(bb[off + 5])
        eksq = lsb(bb[them * 6 + 5])
        smg = 0
        seg = 0
        attack_units = 0
        king_zone = KING_ATT[eksq] | SQBB[eksq]

        # pawns
        t = our_pawns
        while t:
            sq = lsb(t)
            t &= t - U64(1)
            smg += MAT_MG[1] + PST_MG[off * 64 + sq]
            seg += MAT_EG[1] + PST_EG[off * 64 + sq]
            f = sq & 7
            rel_rank = (sq >> 3) if side == WHITE else 7 - (sq >> 3)
            if (FRONT_SPAN[side, sq] & their_pawns) == ZERO:
                smg += PASSED_MG[rel_rank]
                seg += PASSED_EG[rel_rank]
                # endgame: passed pawn worth more when our king is close and theirs far
                seg += 4 * (_dist(eksq, sq) - _dist(ksq, sq))
            if (ADJ_FILES[f] & our_pawns) == ZERO:
                smg -= ISOLATED_MG
                seg -= ISOLATED_EG
            if (FILE_MASK[f] & our_pawns & ~SQBB[sq]) != ZERO:
                smg -= DOUBLED_MG
                seg -= DOUBLED_EG

        # knights
        t = bb[off + 1]
        while t:
            sq = lsb(t)
            t &= t - U64(1)
            smg += MAT_MG[2] + PST_MG[(off + 1) * 64 + sq]
            seg += MAT_EG[2] + PST_EG[(off + 1) * 64 + sq]
            phase += PHASE_INC[2]
            a = KNIGHT_ATT[sq] & ~occ_us
            m = popcount(a)
            smg += MOB_MG[2] * (m - 4)
            seg += MOB_EG[2] * (m - 4)
            if a & king_zone:
                attack_units += ATTACK_WEIGHT[2]
            if side == WHITE:
                npm_w += MAT_MG[2]
            else:
                npm_b += MAT_MG[2]

        # bishops
        t = bb[off + 2]
        nb = 0
        while t:
            sq = lsb(t)
            t &= t - U64(1)
            nb += 1
            smg += MAT_MG[3] + PST_MG[(off + 2) * 64 + sq]
            seg += MAT_EG[3] + PST_EG[(off + 2) * 64 + sq]
            phase += PHASE_INC[3]
            a = bishop_att(sq, occ) & ~occ_us
            m = popcount(a)
            smg += MOB_MG[3] * (m - 6)
            seg += MOB_EG[3] * (m - 6)
            if a & king_zone:
                attack_units += ATTACK_WEIGHT[3]
            if side == WHITE:
                npm_w += MAT_MG[3]
            else:
                npm_b += MAT_MG[3]
        if nb >= 2:
            smg += BISHOP_PAIR_MG
            seg += BISHOP_PAIR_EG

        # rooks
        t = bb[off + 3]
        while t:
            sq = lsb(t)
            t &= t - U64(1)
            smg += MAT_MG[4] + PST_MG[(off + 3) * 64 + sq]
            seg += MAT_EG[4] + PST_EG[(off + 3) * 64 + sq]
            phase += PHASE_INC[4]
            a = rook_att(sq, occ) & ~occ_us
            m = popcount(a)
            smg += MOB_MG[4] * (m - 7)
            seg += MOB_EG[4] * (m - 7)
            if a & king_zone:
                attack_units += ATTACK_WEIGHT[4]
            f = sq & 7
            if (FILE_MASK[f] & our_pawns) == ZERO:
                if (FILE_MASK[f] & their_pawns) == ZERO:
                    smg += ROOK_OPEN_MG
                    seg += ROOK_OPEN_EG
                else:
                    smg += ROOK_SEMI_MG
                    seg += ROOK_SEMI_EG
            if side == WHITE:
                npm_w += MAT_MG[4]
            else:
                npm_b += MAT_MG[4]

        # queens
        t = bb[off + 4]
        while t:
            sq = lsb(t)
            t &= t - U64(1)
            smg += MAT_MG[5] + PST_MG[(off + 4) * 64 + sq]
            seg += MAT_EG[5] + PST_EG[(off + 4) * 64 + sq]
            phase += PHASE_INC[5]
            a = (rook_att(sq, occ) | bishop_att(sq, occ)) & ~occ_us
            m = popcount(a)
            smg += MOB_MG[5] * (m - 13)
            seg += MOB_EG[5] * (m - 13)
            if a & king_zone:
                attack_units += ATTACK_WEIGHT[5]
            if side == WHITE:
                npm_w += MAT_MG[5]
            else:
                npm_b += MAT_MG[5]

        # king
        smg += PST_MG[(off + 5) * 64 + ksq]
        seg += PST_EG[(off + 5) * 64 + ksq]
        kf = ksq & 7
        # pawn shield: own pawns on the three files around the king, one or two ranks ahead
        if side == WHITE:
            shield = (KING_ATT[ksq] | (KING_ATT[ksq] << U64(8))) & our_pawns & ~(SQBB[ksq] | (SQBB[ksq] >> U64(8)))
        else:
            shield = (KING_ATT[ksq] | (KING_ATT[ksq] >> U64(8))) & our_pawns & ~(SQBB[ksq] | (SQBB[ksq] << U64(8)))
        sh = popcount(shield)
        if sh > 3:
            sh = 3
        smg += SHIELD_MG * sh
        # open files next to the king
        # count open files among the (up to) three around the king
        open_files = 0
        for df in range(-1, 2):
            ff = kf + df
            if 0 <= ff < 8 and (FILE_MASK[ff] & (our_pawns | their_pawns)) == ZERO:
                open_files += 1
        smg -= KING_OPEN_FILE_MG * open_files

        # king danger is charged to the *enemy* king from our attacks; accumulate for the enemy
        if attack_units > 31:
            attack_units = 31
        smg += KING_DANGER[attack_units]

        mg += sign * smg
        eg += sign * seg

    if phase > PHASE_MAX:
        phase = PHASE_MAX

    # endgame knowledge --------------------------------------------------------------------
    w_pawns = bb[0] != ZERO
    b_pawns = bb[6] != ZERO
    if not w_pawns and not b_pawns:
        # no pawns: a side needs at least a rook's worth of advantage to win
        diff = npm_w - npm_b
        if diff < 0:
            diff = -diff
        if diff < MAT_MG[4]:
            eg = eg // 8
            mg = mg // 8
    # mop-up: the stronger side, when the weaker has no pawns, drives the king to the edge
    if not b_pawns and npm_w - npm_b >= MAT_MG[4] - 50:
        bk = lsb(bb[11])
        wk = lsb(bb[5])
        eg += 10 * CENTRE_MANHATTAN[bk] + 4 * (14 - _dist(wk, bk))
    elif not w_pawns and npm_b - npm_w >= MAT_MG[4] - 50:
        bk = lsb(bb[11])
        wk = lsb(bb[5])
        eg -= 10 * CENTRE_MANHATTAN[wk] + 4 * (14 - _dist(wk, bk))

    score = (mg * phase + eg * (PHASE_MAX - phase)) // PHASE_MAX
    if st[S_SIDE] == BLACK:
        score = -score
    return score + TEMPO


@njit(cache=False, boundscheck=False)
def game_phase(bb):
    phase = 0
    for i in range(1, 5):
        phase += PHASE_INC[i + 1] * (popcount(bb[i]) + popcount(bb[i + 6]))
    if phase > PHASE_MAX:
        phase = PHASE_MAX
    return phase


LIGHT = np.uint64(0x55AA55AA55AA55AA)
DRAWISH = int(os.environ.get("BINI_DRAWISH", "0")) != 0


@njit(cache=False, boundscheck=False)
def endgame_scale(bb, score):
    """Draw knowledge in front of the network: with no pawns on the board a side needs at least
    a rook's worth of extra material to win (KRvKB, KBvK, KNvK, KBvKN and the like are drawn),
    so such scores are divided by 8. Score is from the side to move's view; the rule is
    symmetric so the side does not matter."""
    if bb[0] == ZERO and bb[6] == ZERO:
        npm_w = MAT_MG[2] * popcount(bb[1]) + MAT_MG[3] * popcount(bb[2]) + MAT_MG[4] * popcount(bb[3]) + MAT_MG[5] * popcount(bb[4])
        npm_b = MAT_MG[2] * popcount(bb[7]) + MAT_MG[3] * popcount(bb[8]) + MAT_MG[4] * popcount(bb[9]) + MAT_MG[5] * popcount(bb[10])
        diff = npm_w - npm_b
        if diff < 0:
            diff = -diff
        if diff < MAT_MG[4]:
            return score // 8
        return score
    if not DRAWISH:
        return score
    # V4.5 drawishness scaling (PLAN_V4 s23.8), only for small scores: known drawish material
    # keeps the search's tension when ahead and stops it trading into "won" positions that are
    # not. Queens on the board: no rule applies.
    if score > 150 or score < -150:
        return score
    if bb[4] != ZERO or bb[10] != ZERO:
        return score
    pw = popcount(bb[0])
    pb = popcount(bb[6])
    nw = popcount(bb[1])
    nb = popcount(bb[7])
    bw = popcount(bb[2])
    bbk = popcount(bb[8])
    rw = popcount(bb[3])
    rb = popcount(bb[9])
    minors_w = nw + bw
    minors_b = nb + bbk
    # pure rook ending, one rook each, equal pawns
    if rw == 1 and rb == 1 and minors_w == 0 and minors_b == 0 and pw == pb:
        return score // 2
    # opposite-coloured bishops, no other pieces, up to two pawns difference
    if bw == 1 and bbk == 1 and nw == 0 and nb == 0 and rw == 0 and rb == 0:
        wl = (bb[2] & LIGHT) != ZERO
        bl = (bb[8] & LIGHT) != ZERO
        if wl != bl and (pw - pb <= 2 and pb - pw <= 2):
            return score // 2
    # one minor piece each, two or fewer pawns each
    if minors_w == 1 and minors_b == 1 and rw == 0 and rb == 0 and pw <= 2 and pb <= 2:
        return (score * 3) // 5
    return score
