"""Bitboard chess position for the Bini engine, compiled with numba.

Layout (all state lives in three numpy arrays so jitted functions can mutate it):

  bb  : uint64[16]   0..5 white P N B R Q K, 6..11 black P N B R Q K,
                     12 white occupancy, 13 black occupancy, 14 all occupancy, 15 zobrist key
  st  : int64[8]     S_SIDE (0 white / 1 black), S_CASTLE (bits 1 WK, 2 WQ, 4 BK, 8 BQ),
                     S_EP (square or -1), S_HALF (halfmove clock), S_PLY (search ply, 0 at root)
  pcs : int64[64]    mailbox, 0 empty, 1..6 white P..K, 7..12 black P..K

Squares are a1=0 .. h8=63 (file = sq & 7, rank = sq >> 3), the same as python-chess.

Move encoding (int64):
  bits 0-5 from, 6-11 to, 12-14 promotion piece type (2 N, 3 B, 4 R, 5 Q, 0 none),
  bit 15 en passant, bit 16 castling, bit 17 double pawn push, bit 18 capture (ordering only).

DTYPE RULE: numba silently promotes mixed uint64/int64 arithmetic to float64. Every bitboard
expression stays in uint64 (constants wrapped with U64), every index and counter stays int64.
Shift counts are uint64. Never add an int64 to a uint64.
"""

from __future__ import annotations

import numpy as np
from numba import njit

from bini_magics import BISHOP_BITS, BISHOP_MAGIC, ROOK_BITS, ROOK_MAGIC

U64 = np.uint64
ZERO = U64(0)
ONE = U64(1)

S_SIDE, S_CASTLE, S_EP, S_HALF, S_PLY = 0, 1, 2, 3, 4

WHITE, BLACK = 0, 1
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6

MF_EP = 1 << 15
MF_CASTLE = 1 << 16
MF_DOUBLE = 1 << 17
MF_CAPTURE = 1 << 18

MAX_PLY = 128
MOVES_PER_PLY = 256

FILE_A = U64(0x0101010101010101)
FILE_H = U64(0x8080808080808080)
RANK_1 = U64(0x00000000000000FF)
RANK_2 = U64(0x000000000000FF00)
RANK_3 = U64(0x0000000000FF0000)
RANK_6 = U64(0x0000FF0000000000)
RANK_7 = U64(0x00FF000000000000)
RANK_8 = U64(0xFF00000000000000)
NOT_A = ~FILE_A
NOT_H = ~FILE_H

# ----------------------------------------------------------------------------------------------
# Tables (built once at import with plain Python / numpy, then frozen into the jitted code)
# ----------------------------------------------------------------------------------------------

SQBB = np.array([1 << i for i in range(64)], dtype=np.uint64)


def _knight_table() -> np.ndarray:
    t = np.zeros(64, dtype=np.uint64)
    for sq in range(64):
        r, f = divmod(sq, 8)
        m = 0
        for dr, df in ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)):
            rr, ff = r + dr, f + df
            if 0 <= rr < 8 and 0 <= ff < 8:
                m |= 1 << (rr * 8 + ff)
        t[sq] = m
    return t


def _king_table() -> np.ndarray:
    t = np.zeros(64, dtype=np.uint64)
    for sq in range(64):
        r, f = divmod(sq, 8)
        m = 0
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                rr, ff = r + dr, f + df
                if 0 <= rr < 8 and 0 <= ff < 8:
                    m |= 1 << (rr * 8 + ff)
        t[sq] = m
    return t


def _pawn_table() -> np.ndarray:
    """PAWN_ATT[colour, sq] = squares attacked by a pawn of that colour standing on sq."""
    t = np.zeros((2, 64), dtype=np.uint64)
    for sq in range(64):
        r, f = divmod(sq, 8)
        for colour, dr in ((WHITE, 1), (BLACK, -1)):
            m = 0
            rr = r + dr
            if 0 <= rr < 8:
                if f > 0:
                    m |= 1 << (rr * 8 + f - 1)
                if f < 7:
                    m |= 1 << (rr * 8 + f + 1)
            t[colour, sq] = m
    return t


def _slide(sq: int, occ: int, dirs: tuple[tuple[int, int], ...]) -> int:
    r, f = divmod(sq, 8)
    att = 0
    for dr, df in dirs:
        rr, ff = r + dr, f + df
        while 0 <= rr < 8 and 0 <= ff < 8:
            bit = 1 << (rr * 8 + ff)
            att |= bit
            if occ & bit:
                break
            rr += dr
            ff += df
    return att


_ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def _mask(sq: int, rook: bool) -> int:
    r, f = divmod(sq, 8)
    m = 0
    if rook:
        for rr in range(1, 7):
            if rr != r:
                m |= 1 << (rr * 8 + f)
        for ff in range(1, 7):
            if ff != f:
                m |= 1 << (r * 8 + ff)
    else:
        for dr, df in _BISHOP_DIRS:
            rr, ff = r + dr, f + df
            while 0 < rr < 7 and 0 < ff < 7:
                m |= 1 << (rr * 8 + ff)
                rr += dr
                ff += df
    return m


def _magic_tables(rook: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    magics = ROOK_MAGIC if rook else BISHOP_MAGIC
    bits = ROOK_BITS if rook else BISHOP_BITS
    dirs = _ROOK_DIRS if rook else _BISHOP_DIRS
    masks = np.zeros(64, dtype=np.uint64)
    shifts = np.zeros(64, dtype=np.uint64)
    offsets = np.zeros(64, dtype=np.uint64)
    magic_arr = np.zeros(64, dtype=np.uint64)
    total = sum(1 << b for b in bits)
    table = np.zeros(total, dtype=np.uint64)
    off = 0
    for sq in range(64):
        mask = _mask(sq, rook)
        masks[sq] = mask
        shifts[sq] = 64 - bits[sq]
        offsets[sq] = off
        magic_arr[sq] = magics[sq]
        sub = 0
        while True:
            idx = ((sub * magics[sq]) & 0xFFFFFFFFFFFFFFFF) >> (64 - bits[sq])
            att = _slide(sq, sub, dirs)
            cur = int(table[off + idx])
            if cur != 0 and cur != att:
                raise RuntimeError(f"bad magic for square {sq}")
            table[off + idx] = att
            sub = (sub - mask) & mask
            if sub == 0:
                break
        off += 1 << bits[sq]
    return masks, magic_arr, shifts, offsets, table


KNIGHT_ATT = _knight_table()
KING_ATT = _king_table()
PAWN_ATT = _pawn_table()
R_MASK, R_MAGIC, R_SHIFT, R_OFF, R_TABLE = _magic_tables(True)
B_MASK, B_MAGIC, B_SHIFT, B_OFF, B_TABLE = _magic_tables(False)

# squares strictly between two squares on a line (for castling emptiness we use explicit masks)
_DEBRUIJN = U64(0x03F79D71B4CB0A89)
DEBRUIJN_TABLE = np.zeros(64, dtype=np.int64)
for _i in range(64):
    _idx = (((1 << _i) * 0x03F79D71B4CB0A89) & 0xFFFFFFFFFFFFFFFF) >> 58
    if DEBRUIJN_TABLE[_idx] != 0 and _i != 0:
        raise RuntimeError("de Bruijn table collision")
    DEBRUIJN_TABLE[_idx] = _i

# castling rights that survive a move touching a square
CASTLE_MASK = np.full(64, 15, dtype=np.int64)
CASTLE_MASK[0] = 15 & ~2   # a1
CASTLE_MASK[4] = 15 & ~3   # e1
CASTLE_MASK[7] = 15 & ~1   # h1
CASTLE_MASK[56] = 15 & ~8  # a8
CASTLE_MASK[60] = 15 & ~12  # e8
CASTLE_MASK[63] = 15 & ~4  # h8

_rng = np.random.default_rng(20260905)
ZOB_PIECE = _rng.integers(0, 2**63, size=12 * 64, dtype=np.int64).astype(np.uint64) * U64(2) + ONE
ZOB_CASTLE = _rng.integers(0, 2**63, size=16, dtype=np.int64).astype(np.uint64) * U64(2) + ONE
ZOB_EP = _rng.integers(0, 2**63, size=8, dtype=np.int64).astype(np.uint64) * U64(2) + ONE
ZOB_SIDE = U64(int(_rng.integers(0, 2**63)) * 2 + 1)
ZOB_CASTLE[0] = ZERO  # no rights hashes to nothing; keeps set_fen and make consistent

# ----------------------------------------------------------------------------------------------
# Bit helpers
# ----------------------------------------------------------------------------------------------


@njit(cache=False, boundscheck=False)
def lsb(b):
    """Index of the least significant set bit. b must be non-zero."""
    return DEBRUIJN_TABLE[((b & (~b + ONE)) * _DEBRUIJN) >> U64(58)]


@njit(cache=False, boundscheck=False)
def popcount(b):
    b = b - ((b >> ONE) & U64(0x5555555555555555))
    b = (b & U64(0x3333333333333333)) + ((b >> U64(2)) & U64(0x3333333333333333))
    b = (b + (b >> U64(4))) & U64(0x0F0F0F0F0F0F0F0F)
    return np.int64((b * U64(0x0101010101010101)) >> U64(56))


@njit(cache=False, boundscheck=False)
def rook_att(sq, occ):
    return R_TABLE[R_OFF[sq] + (((occ & R_MASK[sq]) * R_MAGIC[sq]) >> R_SHIFT[sq])]


@njit(cache=False, boundscheck=False)
def bishop_att(sq, occ):
    return B_TABLE[B_OFF[sq] + (((occ & B_MASK[sq]) * B_MAGIC[sq]) >> B_SHIFT[sq])]


@njit(cache=False, boundscheck=False)
def attacked(bb, sq, by):
    """Is square sq attacked by side `by` (0 white, 1 black)?"""
    off = by * 6
    if PAWN_ATT[1 - by, sq] & bb[off]:
        return True
    if KNIGHT_ATT[sq] & bb[off + 1]:
        return True
    if KING_ATT[sq] & bb[off + 5]:
        return True
    occ = bb[14]
    bq = bb[off + 2] | bb[off + 4]
    if bq != ZERO and (bishop_att(sq, occ) & bq) != ZERO:
        return True
    rq = bb[off + 3] | bb[off + 4]
    if rq != ZERO and (rook_att(sq, occ) & rq) != ZERO:
        return True
    return False


@njit(cache=False, boundscheck=False)
def attackers_to(bb, sq, occ):
    """All pieces of both colours attacking sq, given occupancy occ (for SEE)."""
    a = (PAWN_ATT[BLACK, sq] & bb[0]) | (PAWN_ATT[WHITE, sq] & bb[6])
    a |= KNIGHT_ATT[sq] & (bb[1] | bb[7])
    a |= KING_ATT[sq] & (bb[5] | bb[11])
    a |= bishop_att(sq, occ) & (bb[2] | bb[8] | bb[4] | bb[10])
    a |= rook_att(sq, occ) & (bb[3] | bb[9] | bb[4] | bb[10])
    return a


@njit(cache=False, boundscheck=False)
def in_check(bb, st):
    side = st[S_SIDE]
    return attacked(bb, lsb(bb[5 + side * 6]), 1 - side)


# ----------------------------------------------------------------------------------------------
# Move generation
# ----------------------------------------------------------------------------------------------


@njit(cache=False, boundscheck=False)
def _add(mv, n, frm, to, promo, flags):
    mv[n] = frm | (to << 6) | (promo << 12) | flags
    return n + 1


@njit(cache=False, boundscheck=False)
def gen_moves(bb, st, pcs, mv, base, captures_only):
    """Write pseudo-legal moves into mv[base:], return the count.

    captures_only also includes queen promotions (the quiescence set).
    """
    side = st[S_SIDE]
    them = 1 - side
    us_off = side * 6
    occ_us = bb[12 + side]
    occ_them = bb[12 + them]
    occ = bb[14]
    empty = ~occ
    n = base

    # ---- pawns
    pawns = bb[us_off]
    if side == WHITE:
        # captures
        t = ((pawns & NOT_A) << U64(7)) & occ_them
        while t:
            to = lsb(t)
            t &= t - ONE
            if to >= 56:
                n = _add(mv, n, to - 7, to, QUEEN, MF_CAPTURE)
                if not captures_only:
                    n = _add(mv, n, to - 7, to, ROOK, MF_CAPTURE)
                    n = _add(mv, n, to - 7, to, BISHOP, MF_CAPTURE)
                    n = _add(mv, n, to - 7, to, KNIGHT, MF_CAPTURE)
            else:
                n = _add(mv, n, to - 7, to, 0, MF_CAPTURE)
        t = ((pawns & NOT_H) << U64(9)) & occ_them
        while t:
            to = lsb(t)
            t &= t - ONE
            if to >= 56:
                n = _add(mv, n, to - 9, to, QUEEN, MF_CAPTURE)
                if not captures_only:
                    n = _add(mv, n, to - 9, to, ROOK, MF_CAPTURE)
                    n = _add(mv, n, to - 9, to, BISHOP, MF_CAPTURE)
                    n = _add(mv, n, to - 9, to, KNIGHT, MF_CAPTURE)
            else:
                n = _add(mv, n, to - 9, to, 0, MF_CAPTURE)
        # pushes
        single = (pawns << U64(8)) & empty
        t = single & RANK_8
        while t:
            to = lsb(t)
            t &= t - ONE
            n = _add(mv, n, to - 8, to, QUEEN, 0)
            if not captures_only:
                n = _add(mv, n, to - 8, to, ROOK, 0)
                n = _add(mv, n, to - 8, to, BISHOP, 0)
                n = _add(mv, n, to - 8, to, KNIGHT, 0)
        if not captures_only:
            t = single & ~RANK_8
            while t:
                to = lsb(t)
                t &= t - ONE
                n = _add(mv, n, to - 8, to, 0, 0)
            t = ((single & RANK_3) << U64(8)) & empty
            while t:
                to = lsb(t)
                t &= t - ONE
                n = _add(mv, n, to - 16, to, 0, MF_DOUBLE)
    else:
        t = ((pawns & NOT_H) >> U64(7)) & occ_them
        while t:
            to = lsb(t)
            t &= t - ONE
            if to < 8:
                n = _add(mv, n, to + 7, to, QUEEN, MF_CAPTURE)
                if not captures_only:
                    n = _add(mv, n, to + 7, to, ROOK, MF_CAPTURE)
                    n = _add(mv, n, to + 7, to, BISHOP, MF_CAPTURE)
                    n = _add(mv, n, to + 7, to, KNIGHT, MF_CAPTURE)
            else:
                n = _add(mv, n, to + 7, to, 0, MF_CAPTURE)
        t = ((pawns & NOT_A) >> U64(9)) & occ_them
        while t:
            to = lsb(t)
            t &= t - ONE
            if to < 8:
                n = _add(mv, n, to + 9, to, QUEEN, MF_CAPTURE)
                if not captures_only:
                    n = _add(mv, n, to + 9, to, ROOK, MF_CAPTURE)
                    n = _add(mv, n, to + 9, to, BISHOP, MF_CAPTURE)
                    n = _add(mv, n, to + 9, to, KNIGHT, MF_CAPTURE)
            else:
                n = _add(mv, n, to + 9, to, 0, MF_CAPTURE)
        single = (pawns >> U64(8)) & empty
        t = single & RANK_1
        while t:
            to = lsb(t)
            t &= t - ONE
            n = _add(mv, n, to + 8, to, QUEEN, 0)
            if not captures_only:
                n = _add(mv, n, to + 8, to, ROOK, 0)
                n = _add(mv, n, to + 8, to, BISHOP, 0)
                n = _add(mv, n, to + 8, to, KNIGHT, 0)
        if not captures_only:
            t = single & ~RANK_1
            while t:
                to = lsb(t)
                t &= t - ONE
                n = _add(mv, n, to + 8, to, 0, 0)
            t = ((single & RANK_6) >> U64(8)) & empty
            while t:
                to = lsb(t)
                t &= t - ONE
                n = _add(mv, n, to + 16, to, 0, MF_DOUBLE)
    # en passant
    ep = st[S_EP]
    if ep >= 0:
        t = PAWN_ATT[them, ep] & pawns
        while t:
            frm = lsb(t)
            t &= t - ONE
            n = _add(mv, n, frm, ep, 0, MF_EP | MF_CAPTURE)

    # ---- knights, bishops, rooks, queens
    for pt in range(1, 5):
        t = bb[us_off + pt]
        while t:
            frm = lsb(t)
            t &= t - ONE
            if pt == 1:
                a = KNIGHT_ATT[frm]
            elif pt == 2:
                a = bishop_att(frm, occ)
            elif pt == 3:
                a = rook_att(frm, occ)
            else:
                a = rook_att(frm, occ) | bishop_att(frm, occ)
            c = a & occ_them
            while c:
                to = lsb(c)
                c &= c - ONE
                n = _add(mv, n, frm, to, 0, MF_CAPTURE)
            if not captures_only:
                q = a & empty
                while q:
                    to = lsb(q)
                    q &= q - ONE
                    n = _add(mv, n, frm, to, 0, 0)

    # ---- king
    ksq = lsb(bb[us_off + 5])
    a = KING_ATT[ksq]
    c = a & occ_them
    while c:
        to = lsb(c)
        c &= c - ONE
        n = _add(mv, n, ksq, to, 0, MF_CAPTURE)
    if not captures_only:
        q = a & empty
        while q:
            to = lsb(q)
            q &= q - ONE
            n = _add(mv, n, ksq, to, 0, 0)
        # castling: rights, empty path, king not in check, transit squares not attacked
        rights = st[S_CASTLE]
        if side == WHITE:
            if (rights & 1) and ksq == 4 and (occ & U64(0x60)) == ZERO:
                if (not attacked(bb, 4, them)) and (not attacked(bb, 5, them)) and (not attacked(bb, 6, them)):
                    n = _add(mv, n, 4, 6, 0, MF_CASTLE)
            if (rights & 2) and ksq == 4 and (occ & U64(0x0E)) == ZERO:
                if (not attacked(bb, 4, them)) and (not attacked(bb, 3, them)) and (not attacked(bb, 2, them)):
                    n = _add(mv, n, 4, 2, 0, MF_CASTLE)
        else:
            if (rights & 4) and ksq == 60 and (occ & U64(0x6000000000000000)) == ZERO:
                if (not attacked(bb, 60, them)) and (not attacked(bb, 61, them)) and (not attacked(bb, 62, them)):
                    n = _add(mv, n, 60, 62, 0, MF_CASTLE)
            if (rights & 8) and ksq == 60 and (occ & U64(0x0E00000000000000)) == ZERO:
                if (not attacked(bb, 60, them)) and (not attacked(bb, 59, them)) and (not attacked(bb, 58, them)):
                    n = _add(mv, n, 60, 58, 0, MF_CASTLE)
    return n - base


# ----------------------------------------------------------------------------------------------
# Make / unmake
# ----------------------------------------------------------------------------------------------
# Undo storage per ply: ub[ply] = previous zobrist key (uint64);
# ui[ply, 0] captured piece code, 1 castling, 2 ep, 3 halfmove, 4 move


@njit(cache=False, boundscheck=False)
def make(bb, st, pcs, mv, ub, ui):
    """Play mv. Returns True if legal (own king not left in check); otherwise the move is
    undone before returning False."""
    side = st[S_SIDE]
    them = 1 - side
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    ply = st[S_PLY]
    piece = pcs[frm]
    cap = pcs[to]
    key = bb[15]

    ub[ply] = key
    ui[ply, 1] = st[S_CASTLE]
    ui[ply, 2] = st[S_EP]
    ui[ply, 3] = st[S_HALF]
    ui[ply, 4] = mv

    if st[S_EP] >= 0:
        key ^= ZOB_EP[st[S_EP] & 7]
    key ^= ZOB_CASTLE[st[S_CASTLE]]

    if mv & MF_EP:
        capsq = to - 8 if side == WHITE else to + 8
        cap = pcs[capsq]
        bb[cap - 1] ^= SQBB[capsq]
        bb[12 + them] ^= SQBB[capsq]
        pcs[capsq] = 0
        key ^= ZOB_PIECE[(cap - 1) * 64 + capsq]
    elif cap != 0:
        bb[cap - 1] ^= SQBB[to]
        bb[12 + them] ^= SQBB[to]
        key ^= ZOB_PIECE[(cap - 1) * 64 + to]
    ui[ply, 0] = cap

    move_bb = SQBB[frm] | SQBB[to]
    bb[piece - 1] ^= move_bb
    bb[12 + side] ^= move_bb
    key ^= ZOB_PIECE[(piece - 1) * 64 + frm] ^ ZOB_PIECE[(piece - 1) * 64 + to]
    pcs[frm] = 0
    pcs[to] = piece

    if promo != 0:
        newp = promo + side * 6
        bb[piece - 1] ^= SQBB[to]
        bb[newp - 1] |= SQBB[to]
        pcs[to] = newp
        key ^= ZOB_PIECE[(piece - 1) * 64 + to] ^ ZOB_PIECE[(newp - 1) * 64 + to]

    if mv & MF_CASTLE:
        if to == 6:
            rf, rt = 7, 5
        elif to == 2:
            rf, rt = 0, 3
        elif to == 62:
            rf, rt = 63, 61
        else:
            rf, rt = 56, 59
        rook = pcs[rf]
        rbb = SQBB[rf] | SQBB[rt]
        bb[rook - 1] ^= rbb
        bb[12 + side] ^= rbb
        pcs[rf] = 0
        pcs[rt] = rook
        key ^= ZOB_PIECE[(rook - 1) * 64 + rf] ^ ZOB_PIECE[(rook - 1) * 64 + rt]

    # en passant square only when an enemy pawn could capture (matches python-chess keys)
    st[S_EP] = -1
    if mv & MF_DOUBLE:
        epsq = (frm + to) >> 1
        if PAWN_ATT[side, epsq] & bb[them * 6]:
            st[S_EP] = epsq
            key ^= ZOB_EP[epsq & 7]

    st[S_CASTLE] = st[S_CASTLE] & CASTLE_MASK[frm] & CASTLE_MASK[to]
    key ^= ZOB_CASTLE[st[S_CASTLE]]

    if cap != 0 or piece == PAWN + side * 6:
        st[S_HALF] = 0
    else:
        st[S_HALF] += 1

    st[S_SIDE] = them
    key ^= ZOB_SIDE
    st[S_PLY] = ply + 1
    bb[14] = bb[12] | bb[13]
    bb[15] = key

    if attacked(bb, lsb(bb[5 + side * 6]), them):
        unmake(bb, st, pcs, ub, ui)
        return False
    return True


@njit(cache=False, boundscheck=False)
def unmake(bb, st, pcs, ub, ui):
    ply = st[S_PLY] - 1
    st[S_PLY] = ply
    mv = ui[ply, 4]
    them = st[S_SIDE]
    side = 1 - them
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    cap = ui[ply, 0]

    piece = pcs[to]
    if promo != 0:
        bb[piece - 1] ^= SQBB[to]
        piece = PAWN + side * 6
        bb[piece - 1] |= SQBB[to]
    move_bb = SQBB[frm] | SQBB[to]
    bb[piece - 1] ^= move_bb
    bb[12 + side] ^= move_bb
    pcs[frm] = piece
    pcs[to] = 0

    if mv & MF_EP:
        capsq = to - 8 if side == WHITE else to + 8
        bb[cap - 1] |= SQBB[capsq]
        bb[12 + them] |= SQBB[capsq]
        pcs[capsq] = cap
    elif cap != 0:
        bb[cap - 1] |= SQBB[to]
        bb[12 + them] |= SQBB[to]
        pcs[to] = cap

    if mv & MF_CASTLE:
        if to == 6:
            rf, rt = 7, 5
        elif to == 2:
            rf, rt = 0, 3
        elif to == 62:
            rf, rt = 63, 61
        else:
            rf, rt = 56, 59
        rook = pcs[rt]
        rbb = SQBB[rf] | SQBB[rt]
        bb[rook - 1] ^= rbb
        bb[12 + side] ^= rbb
        pcs[rt] = 0
        pcs[rf] = rook

    st[S_SIDE] = side
    st[S_CASTLE] = ui[ply, 1]
    st[S_EP] = ui[ply, 2]
    st[S_HALF] = ui[ply, 3]
    bb[14] = bb[12] | bb[13]
    bb[15] = ub[ply]


@njit(cache=False, boundscheck=False)
def make_null(bb, st, ub, ui):
    """Pass the move (for null-move pruning). Saved like a normal move with mv = 0."""
    ply = st[S_PLY]
    key = bb[15]
    ub[ply] = key
    ui[ply, 0] = 0
    ui[ply, 1] = st[S_CASTLE]
    ui[ply, 2] = st[S_EP]
    ui[ply, 3] = st[S_HALF]
    ui[ply, 4] = 0
    if st[S_EP] >= 0:
        key ^= ZOB_EP[st[S_EP] & 7]
        st[S_EP] = -1
    key ^= ZOB_SIDE
    st[S_SIDE] = 1 - st[S_SIDE]
    st[S_HALF] += 1
    st[S_PLY] = ply + 1
    bb[15] = key


@njit(cache=False, boundscheck=False)
def unmake_null(bb, st, ub, ui):
    ply = st[S_PLY] - 1
    st[S_PLY] = ply
    st[S_SIDE] = 1 - st[S_SIDE]
    st[S_CASTLE] = ui[ply, 1]
    st[S_EP] = ui[ply, 2]
    st[S_HALF] = ui[ply, 3]
    bb[15] = ub[ply]


@njit(cache=False, boundscheck=False)
def compute_key(bb, st, pcs):
    key = ZERO
    for sq in range(64):
        p = pcs[sq]
        if p != 0:
            key ^= ZOB_PIECE[(p - 1) * 64 + sq]
    key ^= ZOB_CASTLE[st[S_CASTLE]]
    if st[S_EP] >= 0:
        key ^= ZOB_EP[st[S_EP] & 7]
    if st[S_SIDE] == BLACK:
        key ^= ZOB_SIDE
    return key


@njit(cache=False, boundscheck=False)
def perft(bb, st, pcs, mv, ub, ui, depth):
    if depth == 0:
        return 1
    base = st[S_PLY] * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, False)
    total = 0
    for i in range(n):
        m = mv[base + i]
        if make(bb, st, pcs, m, ub, ui):
            total += perft(bb, st, pcs, mv, ub, ui, depth - 1)
            unmake(bb, st, pcs, ub, ui)
    return total


# ----------------------------------------------------------------------------------------------
# Python-side helpers
# ----------------------------------------------------------------------------------------------

_PIECE_CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}
_CODE_CHARS = ".PNBRQKpnbrqk"


def new_position() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return np.zeros(16, dtype=np.uint64), np.zeros(8, dtype=np.int64), np.zeros(64, dtype=np.int64)


def new_undo() -> tuple[np.ndarray, np.ndarray]:
    return np.zeros(MAX_PLY + 8, dtype=np.uint64), np.zeros((MAX_PLY + 8, 5), dtype=np.int64)


def new_move_stack() -> np.ndarray:
    return np.zeros((MAX_PLY + 8) * MOVES_PER_PLY, dtype=np.int64)


def set_fen(bb: np.ndarray, st: np.ndarray, pcs: np.ndarray, fen: str) -> None:
    parts = fen.split()
    bb[:] = 0
    pcs[:] = 0
    st[:] = 0
    rows = parts[0].split("/")
    for r, row in enumerate(rows):
        rank = 7 - r
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
            else:
                code = _PIECE_CODES[ch]
                sq = rank * 8 + f
                pcs[sq] = code
                bb[code - 1] |= U64(1) << U64(sq)
                f += 1
    st[S_SIDE] = WHITE if parts[1] == "w" else BLACK
    rights = 0
    if len(parts) > 2 and parts[2] != "-":
        for ch in parts[2]:
            rights |= {"K": 1, "Q": 2, "k": 4, "q": 8}.get(ch, 0)
    st[S_CASTLE] = rights
    st[S_EP] = -1
    if len(parts) > 3 and parts[3] != "-":
        epsq = (ord(parts[3][0]) - 97) + (int(parts[3][1]) - 1) * 8
        # only keep the square if a pawn can actually capture there (see make)
        side = st[S_SIDE]
        if PAWN_ATT[1 - side, epsq] & bb[side * 6]:
            st[S_EP] = epsq
    st[S_HALF] = int(parts[4]) if len(parts) > 4 else 0
    st[S_PLY] = 0
    bb[12] = bb[0] | bb[1] | bb[2] | bb[3] | bb[4] | bb[5]
    bb[13] = bb[6] | bb[7] | bb[8] | bb[9] | bb[10] | bb[11]
    bb[14] = bb[12] | bb[13]
    bb[15] = compute_key(bb, st, pcs)


def move_to_uci(mv: int) -> str:
    frm = mv & 63
    to = (mv >> 6) & 63
    promo = (mv >> 12) & 7
    s = "abcdefgh"[frm & 7] + str((frm >> 3) + 1) + "abcdefgh"[to & 7] + str((to >> 3) + 1)
    if promo:
        s += "  nbrq"[promo]
    return s


def uci_to_move(bb: np.ndarray, st: np.ndarray, pcs: np.ndarray, uci: str) -> int:
    """Find the generated move matching a UCI string, or 0."""
    mv = np.zeros(MOVES_PER_PLY, dtype=np.int64)
    n = gen_moves(bb, st, pcs, mv, 0, False)
    for i in range(n):
        if move_to_uci(int(mv[i])) == uci:
            return int(mv[i])
    return 0


def to_fen_board(pcs: np.ndarray) -> str:
    rows = []
    for rank in range(7, -1, -1):
        row = ""
        empty = 0
        for f in range(8):
            code = int(pcs[rank * 8 + f])
            if code == 0:
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += _CODE_CHARS[code]
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows)


def warm_up() -> None:
    """Compile every jitted function in this module with the real argument types."""
    bb, st, pcs = new_position()
    ub, ui = new_undo()
    mv = new_move_stack()
    set_fen(bb, st, pcs, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    n = gen_moves(bb, st, pcs, mv, 0, False)
    for i in range(n):
        if make(bb, st, pcs, mv[i], ub, ui):
            unmake(bb, st, pcs, ub, ui)
    gen_moves(bb, st, pcs, mv, 0, True)
    make_null(bb, st, ub, ui)
    unmake_null(bb, st, ub, ui)
    attackers_to(bb, 28, bb[14])
    in_check(bb, st)
    popcount(bb[14])
