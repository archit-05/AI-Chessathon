"""NNUE-style evaluation for Bini: 768 piece-square features from both perspectives,
one hidden layer of H units per perspective (two accumulators), clipped ReLU, one output.

Weights are ours (trained by tools/train_nnue.py, quantised by tools/export_nnue.py) and ship
as nnue.safetensors, parsed here with numpy so torch is never imported at runtime.

Feature index for perspective P and a piece of colour C, type T (0..5) on square S:
    kind = T * 2 + (0 if C == P else 1)         # own pieces first
    sq   = S if P == white else S ^ 56          # mirror ranks for the black perspective
    idx  = kind * 64 + sq                       # 0 .. 767

Accumulators are int32, stacked per search ply so make/unmake is a copy-and-delta.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
from numba import njit

from bini_board import BLACK, MAX_PLY, S_PLY, S_SIDE, WHITE, lsb

HIDDEN = 256
QA = 255  # input layer scale / clipped ReLU ceiling
QB = 32   # output layer scale (|w2| must stay below 32767 / (QB * 400) = 2.56)
OUT_SCALE = QA * QB

# Placeholders replaced by load_weights(); shapes fixed so the jitted code compiles once.
W1 = np.zeros((768, HIDDEN), dtype=np.int16)
B1 = np.zeros(HIDDEN, dtype=np.int32)
W2 = np.zeros(2 * HIDDEN, dtype=np.int16)
B2 = np.zeros(1, dtype=np.int32)


def new_accumulators() -> np.ndarray:
    return np.zeros((MAX_PLY + 8, 2, HIDDEN), dtype=np.int32)


@njit(cache=False, boundscheck=False)
def _feature(persp, code, sq):
    colour = 0 if code <= 6 else 1
    t = code - 1 - colour * 6
    kind = t * 2 + (0 if colour == persp else 1)
    if persp == BLACK:
        sq ^= 56
    return kind * 64 + sq


@njit(cache=False, boundscheck=False)
def nnue_refresh(bb, st, pcs, acc, w1, b1):
    """Recompute both accumulators for the current ply from scratch."""
    ply = st[S_PLY]
    for p in range(2):
        for h in range(HIDDEN):
            acc[ply, p, h] = b1[h]
    for sq in range(64):
        code = pcs[sq]
        if code == 0:
            continue
        for p in range(2):
            f = _feature(p, code, sq)
            for h in range(HIDDEN):
                acc[ply, p, h] += w1[f, h]


@njit(cache=False, boundscheck=False)
def nnue_push(acc, ply, side, mv, moved, captured, promo_piece, capsq, w1):
    """Derive acc[ply+1] from acc[ply] after the move mv was played by `side`.

    moved: piece code that left `from`; captured: code removed at capsq (0 if none);
    promo_piece: code placed on `to` (0 if none, then `moved` lands on `to`).
    Castling rook moves are passed by the caller as a second push with captured = 0.
    """
    frm = mv & 63
    to = (mv >> 6) & 63
    for p in range(2):
        f_from = _feature(p, moved, frm)
        land = promo_piece if promo_piece != 0 else moved
        f_to = _feature(p, land, to)
        if captured != 0:
            f_cap = _feature(p, captured, capsq)
            for h in range(HIDDEN):
                acc[ply + 1, p, h] = acc[ply, p, h] - w1[f_from, h] + w1[f_to, h] - w1[f_cap, h]
        else:
            for h in range(HIDDEN):
                acc[ply + 1, p, h] = acc[ply, p, h] - w1[f_from, h] + w1[f_to, h]


@njit(cache=False, boundscheck=False)
def nnue_move_piece(acc, ply, code, frm, to, w1):
    """In-place adjustment of acc[ply] for a piece moving frm -> to (used for the castling rook)."""
    for p in range(2):
        f_from = _feature(p, code, frm)
        f_to = _feature(p, code, to)
        for h in range(HIDDEN):
            acc[ply, p, h] += w1[f_to, h] - w1[f_from, h]


@njit(cache=False, boundscheck=False)
def nnue_copy(acc, ply):
    for p in range(2):
        for h in range(HIDDEN):
            acc[ply + 1, p, h] = acc[ply, p, h]


@njit(cache=False, boundscheck=False)
def nnue_eval(bb, st, acc, w2, b2):
    ply = st[S_PLY]
    stm = st[S_SIDE]
    total = np.int64(0)
    for h in range(HIDDEN):
        v = acc[ply, stm, h]
        if v < 0:
            v = 0
        elif v > QA:
            v = QA
        total += np.int64(v) * np.int64(w2[h])
    for h in range(HIDDEN):
        v = acc[ply, 1 - stm, h]
        if v < 0:
            v = 0
        elif v > QA:
            v = QA
        total += np.int64(v) * np.int64(w2[HIDDEN + h])
    total += np.int64(b2[0])
    return np.int64(total // OUT_SCALE)


def read_safetensors(path: Path) -> dict[str, np.ndarray]:
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
    return out


def load_weights(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = read_safetensors(path)
    w1 = np.ascontiguousarray(t["w1"], dtype=np.int16)
    b1 = np.ascontiguousarray(t["b1"], dtype=np.int32)
    w2 = np.ascontiguousarray(t["w2"], dtype=np.int16)
    b2 = np.ascontiguousarray(t["b2"], dtype=np.int32)
    assert w1.shape == (768, HIDDEN) and b1.shape == (HIDDEN,) and w2.shape == (2 * HIDDEN,) and b2.shape == (1,)
    return w1, b1, w2, b2
