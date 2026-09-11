"""NNUE-style evaluation for Bini.

Features (per perspective P, i.e. from white's and from black's point of view):
  the perspective's own king square selects one of NB king buckets and a horizontal mirror
  (king on files e-h mirrors the board so all kings live on files a-d); every piece then
  contributes feature  bucket * 768 + kind * 64 + square', with
      kind    = piece_type * 2 + (0 if the piece belongs to P else 1)
      square' = square, ranks flipped for P = black, files flipped if mirrored.
  NB = 1 degenerates to the plain 768-feature net (no buckets, no mirror).

Network: input -> HIDDEN per perspective (shared weights, two accumulators) -> activation
(clipped ReLU, or squared clipped ReLU when the weights file says act = screlu) -> one linear
output chosen by an output bucket (piece count: NO buckets, NO = 1 means a single output),
side to move's accumulator first -> centipawns.

Weights are ours (tools/train_nnue.py) and ship as nnue.safetensors, parsed here with numpy;
torch is never imported at runtime. Accumulators are int32, stacked per search ply. NB, HIDDEN,
the activation and NO are read from the weights file at import so the jitted code compiles for
that shape. Files written by the v2/v3 trainer (w2 one-dimensional, b2 = [bias, scale]) load
unchanged as a clipped-ReLU net with one output bucket.
"""

from __future__ import annotations

import json
import os
import struct
from pathlib import Path

import numpy as np
from numba import njit

from bini_board import BLACK, KING, MAX_PLY, MF_CASTLE, MF_EP, PAWN, S_PLY, S_SIDE, WHITE, lsb, popcount

QA = 255  # input layer scale / clipped ReLU ceiling; the output scale ships in b2[NO]

WEIGHTS_PATH = Path(os.environ.get("BINI_NNUE", str(Path(__file__).resolve().parent / "nnue.safetensors")))


def read_safetensors(path: Path) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Minimal safetensors reader: 8-byte little-endian header length, JSON header, raw data."""
    raw = path.read_bytes()
    (hlen,) = struct.unpack("<Q", raw[:8])
    header = json.loads(raw[8 : 8 + hlen].decode("utf-8"))
    base = 8 + hlen
    dtypes = {"I16": np.int16, "I32": np.int32, "F32": np.float32, "I8": np.int8}
    out: dict[str, np.ndarray] = {}
    for name, meta in header.items():
        if name == "__metadata__":
            continue
        start, end = meta["data_offsets"]
        arr = np.frombuffer(raw[base + start : base + end], dtype=dtypes[meta["dtype"]])
        out[name] = arr.reshape(meta["shape"]).copy()
    return out, header.get("__metadata__", {})


def _load(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, int, int, int]:
    t, meta = read_safetensors(path)
    w1 = np.ascontiguousarray(t["w1"], dtype=np.int16)
    b1 = np.ascontiguousarray(t["b1"], dtype=np.int32)
    w2 = np.ascontiguousarray(t["w2"], dtype=np.int16)
    b2 = np.ascontiguousarray(t["b2"], dtype=np.int32)
    hidden = w1.shape[1]
    nb = w1.shape[0] // 768
    if w2.ndim == 1:  # v2/v3 format: one output, b2 = [bias, scale]
        w2 = w2.reshape(1, -1)
    no = w2.shape[0]
    assert w1.shape == (nb * 768, hidden) and b1.shape == (hidden,) and w2.shape == (no, 2 * hidden)
    assert b2.shape == (no + 1,) and b2[no] > 0, "weights file needs b2 = [bias per output bucket..., output scale]"
    act_sq = 1 if str(meta.get("act", "crelu")).lower() == "screlu" else 0
    return w1, b1, np.ascontiguousarray(w2), b2, nb, hidden, no, act_sq


LOADED = False
if WEIGHTS_PATH.exists():
    W1, B1, W2, B2, NB, HIDDEN, NO, ACT_SQ = _load(WEIGHTS_PATH)
    LOADED = True
else:
    NB, HIDDEN, NO, ACT_SQ = 8, 512, 1, 0
    W1 = np.zeros((NB * 768, HIDDEN), dtype=np.int16)
    B1 = np.zeros(HIDDEN, dtype=np.int32)
    W2 = np.zeros((NO, 2 * HIDDEN), dtype=np.int16)
    B2 = np.array([0, QA * 32], dtype=np.int32)


def _king_table(nb: int) -> np.ndarray:
    """KB_TABLE[king square from the perspective's own view] = bucket * 2 + mirror."""
    t = np.zeros(64, dtype=np.int64)
    if nb == 1:
        return t
    assert nb in (8, 16), "only 1, 8 or 16 king buckets are defined"
    for sq in range(64):
        r, f = divmod(sq, 8)
        mirror = 1 if f >= 4 else 0
        ff = f ^ 7 if mirror else f  # 0..3
        if nb == 8:
            if r == 0:
                bucket = 0 if ff < 2 else 1
            elif r == 1:
                bucket = 2 if ff < 2 else 3
            elif r <= 3:
                bucket = 4 if ff < 2 else 5
            else:
                bucket = 6 if ff < 2 else 7
        else:
            # 16 buckets: ranks 1, 2, 3, 4-8 (0..3) x files a, b, c, d (0..3)
            rr = r if r < 3 else 3
            bucket = rr * 4 + ff
        t[sq] = bucket * 2 + mirror
    return t


KB_TABLE = _king_table(NB)


def out_bucket(piece_count: int) -> int:
    """Output bucket from the number of pieces on the board (1..32)."""
    if NO == 1:
        return 0
    return min(NO - 1, (piece_count - 1) * NO // 32)


def new_accumulators() -> np.ndarray:
    return np.zeros((MAX_PLY + 8, 2, HIDDEN), dtype=np.int32)


def new_cache() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per (perspective, king id) cached accumulator with the piece placement it was built from.
    A refresh (king changes bucket, or a new root) then costs only the squares that differ from
    the cached placement instead of every piece on the board."""
    return (np.zeros((2, NB * 2, HIDDEN), dtype=np.int32), np.zeros((2, NB * 2, 64), dtype=np.int64), np.zeros((2, NB * 2), dtype=np.int64))


@njit(cache=False, boundscheck=False)
def king_id(bb, p):
    ksq = lsb(bb[5 + p * 6])
    if p == BLACK:
        ksq ^= 56
    return KB_TABLE[ksq]


@njit(cache=False, boundscheck=False)
def _feature(p, code, sq, kid):
    colour = 0 if code <= 6 else 1
    t = code - 1 - colour * 6
    kind = t * 2 + (0 if colour == p else 1)
    if p == BLACK:
        sq ^= 56
    if kid & 1:
        sq ^= 7
    return (kid >> 1) * 768 + kind * 64 + sq


@njit(cache=False, boundscheck=False)
def nnue_refresh_persp(bb, pcs, acc, ply, p, w1, b1, c_acc, c_pcs, c_valid):
    kid = king_id(bb, p)
    if c_valid[p, kid] == 0:
        for h in range(HIDDEN):
            c_acc[p, kid, h] = b1[h]
        for sq in range(64):
            code = pcs[sq]
            c_pcs[p, kid, sq] = code
            if code == 0:
                continue
            f = _feature(p, code, sq, kid)
            for h in range(HIDDEN):
                c_acc[p, kid, h] += w1[f, h]
        c_valid[p, kid] = 1
    else:
        for sq in range(64):
            old = c_pcs[p, kid, sq]
            new = pcs[sq]
            if old == new:
                continue
            if old != 0:
                f = _feature(p, old, sq, kid)
                for h in range(HIDDEN):
                    c_acc[p, kid, h] -= w1[f, h]
            if new != 0:
                f = _feature(p, new, sq, kid)
                for h in range(HIDDEN):
                    c_acc[p, kid, h] += w1[f, h]
            c_pcs[p, kid, sq] = new
    for h in range(HIDDEN):
        acc[ply, p, h] = c_acc[p, kid, h]


@njit(cache=False, boundscheck=False)
def nnue_refresh(bb, st, pcs, acc, w1, b1, c_acc, c_pcs, c_valid):
    """Recompute both accumulators for the current ply (through the per-bucket cache)."""
    ply = st[S_PLY]
    nnue_refresh_persp(bb, pcs, acc, ply, 0, w1, b1, c_acc, c_pcs, c_valid)
    nnue_refresh_persp(bb, pcs, acc, ply, 1, w1, b1, c_acc, c_pcs, c_valid)


@njit(cache=False, boundscheck=False)
def nnue_after_make(bb, st, pcs, acc, ui, mv, w1, b1, c_acc, c_pcs, c_valid):
    """Fill acc[ply+1] after `mv` was made (st[S_PLY] has already been incremented)."""
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
    castle = (mv & MF_CASTLE) != 0
    if castle:
        rook = 4 + side * 6
        if to == 6:
            rf, rt = 7, 5
        elif to == 2:
            rf, rt = 0, 3
        elif to == 62:
            rf, rt = 63, 61
        else:
            rf, rt = 56, 59
    else:
        rook, rf, rt = 0, 0, 0
    for p in range(2):
        kid = king_id(bb, p)
        if moved == KING + p * 6:
            old = KB_TABLE[frm ^ (56 if p == BLACK else 0)]
            if old != kid:
                nnue_refresh_persp(bb, pcs, acc, ply + 1, p, w1, b1, c_acc, c_pcs, c_valid)
                continue
        f_from = _feature(p, moved, frm, kid)
        f_to = _feature(p, landed, to, kid)
        if captured != 0:
            f_cap = _feature(p, captured, capsq, kid)
            for h in range(HIDDEN):
                acc[ply + 1, p, h] = acc[ply, p, h] - w1[f_from, h] + w1[f_to, h] - w1[f_cap, h]
        else:
            for h in range(HIDDEN):
                acc[ply + 1, p, h] = acc[ply, p, h] - w1[f_from, h] + w1[f_to, h]
        if castle:
            r_from = _feature(p, rook, rf, kid)
            r_to = _feature(p, rook, rt, kid)
            for h in range(HIDDEN):
                acc[ply + 1, p, h] += w1[r_to, h] - w1[r_from, h]


@njit(cache=False, boundscheck=False)
def nnue_copy(acc, ply):
    for p in range(2):
        for h in range(HIDDEN):
            acc[ply + 1, p, h] = acc[ply, p, h]


@njit(cache=False, boundscheck=False)
def nnue_eval(bb, st, acc, w2, b2):
    ply = st[S_PLY]
    stm = st[S_SIDE]
    ob = 0
    if NO > 1:
        ob = (popcount(bb[14]) - 1) * NO // 32
        if ob > NO - 1:
            ob = NO - 1
    total = np.int64(0)
    for h in range(HIDDEN):
        v = acc[ply, stm, h]
        if v < 0:
            v = 0
        elif v > QA:
            v = QA
        if ACT_SQ != 0:
            v = v * v
        total += np.int64(v) * np.int64(w2[ob, h])
    for h in range(HIDDEN):
        v = acc[ply, 1 - stm, h]
        if v < 0:
            v = 0
        elif v > QA:
            v = QA
        if ACT_SQ != 0:
            v = v * v
        total += np.int64(v) * np.int64(w2[ob, HIDDEN + h])
    total += np.int64(b2[ob])
    return np.int64(total // np.int64(b2[NO]))
