"""Convert a bullet checkpoint (tools/bullet_trainer) into Bini's nnue.safetensors.

    python tools/bullet_export.py --checkpoint ckpt/bini512-40 --hidden 512 --act screlu --out nnue.safetensors
    python tools/bullet_export.py --raw raw.bin --hidden 1024 --act crelu --out nnue.safetensors --out-scale 1.1
    python tools/bullet_export.py --weights ckpt/bini512-40/optimiser_state/weights.bin --act screlu --out ...

Input (derived from bullet rev 629ee50000b2afb7b3337595401c830d3b1e0f42, crates/bullet_lib/src/value/save.rs):
  raw.bin       f32 little-endian, no header/padding, untransformed weights in save-format order.
                bullet stores a weight of shape rows x cols column-major, i.e. memory index rows*col + row:
                    l0w  shape H x (8*768)  -> memory [8*768][H]   (per input feature, H contiguous)
                    l0b  shape H x 1        -> memory [H]
                    l1w  shape 8 x 2H       -> memory [2H][8]      (per hidden index, 8 buckets contiguous)
                    l1b  shape 8 x 1        -> memory [8]
                    l0f  shape H x 768      -> memory [768][H]     only with --factorise, NOT merged
  weights.bin   optimiser_state/weights.bin: named tensors, `id\\n` + u64 count + f32 LE values, sorted by id.

Bullet's feature index (game/inputs/chess768.rs + chess_buckets.rs), perspective P with king square k
(seen from P; P = the side not to move sees the board flipped, square ^ 56):
    bucket = KING_BUCKETS_32[(k // 8) * 4 + [0,1,2,3,3,2,1,0][k % 8]];   flip = 7 if k % 8 > 3 else 0
    feature = 768 * bucket + ((opp * 384 + type * 64 + sq) ^ flip)        type 0..5 = P N B R Q K, opp 1 = not P's piece
Bini's (bini_nnue._feature): 768 * bucket + (type * 2 + opp) * 64 + (sq ^ (7 if flip)) with the same bucket and
mirror rule, so the export is a fixed row permutation (bullet_to_bini_perm) plus Bini's quantisation.

Output: the safetensors that tools/train_nnue.py's export() writes (w1 int16 [8*768, H] in Bini feature order,
b1 int32 [H], w2 int16 [NO, 2H], b2 int32 [NO+1] with b2[NO] the divisor, metadata act/buckets/hidden/...).
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np

QA = 255
CP_SCALE = 400.0
BULLET_REV = "629ee50000b2afb7b3337595401c830d3b1e0f42"
NB_DEFAULT = 8
NO_DEFAULT = 8

# The 32-entry ChessBucketsMirrored array used by tools/bullet_trainer (rank-major, files a-d; e-h fold onto d-a).
KING_BUCKETS_32 = [
    0, 0, 1, 1,  # rank 1
    2, 2, 3, 3,  # rank 2
    4, 4, 5, 5,  # rank 3
    4, 4, 5, 5,  # rank 4
    6, 6, 7, 7,  # rank 5
    6, 6, 7, 7,  # rank 6
    6, 6, 7, 7,  # rank 7
    6, 6, 7, 7,  # rank 8
]


# ---------------------------------------------------------------------------------------------- tables
def expand_king_buckets(b32: list[int]) -> np.ndarray:
    """ChessBucketsMirrored::new: 64-entry bucket per king square (a1 = 0)."""
    fold = [0, 1, 2, 3, 3, 2, 1, 0]
    return np.array([b32[(sq // 8) * 4 + fold[sq % 8]] for sq in range(64)], dtype=np.int64)


def bullet_king_table(b32: list[int]) -> np.ndarray:
    """bucket * 2 + mirror per king square, the form of bini_nnue.KB_TABLE, from bullet's rules."""
    buckets = expand_king_buckets(b32)
    return np.array([int(buckets[sq]) * 2 + (1 if sq % 8 > 3 else 0) for sq in range(64)], dtype=np.int64)


def bini_king_table(nb: int = 8) -> np.ndarray:
    """Bini's _king_table(8), re-derived here so the exporter can self-check KING_BUCKETS_32."""
    t = np.zeros(64, dtype=np.int64)
    for sq in range(64):
        r, f = divmod(sq, 8)
        mirror = 1 if f >= 4 else 0
        ff = f ^ 7 if mirror else f
        if r == 0:
            bucket = 0 if ff < 2 else 1
        elif r == 1:
            bucket = 2 if ff < 2 else 3
        elif r <= 3:
            bucket = 4 if ff < 2 else 5
        else:
            bucket = 6 if ff < 2 else 7
        t[sq] = bucket * 2 + mirror
    return t


assert np.array_equal(bullet_king_table(KING_BUCKETS_32), bini_king_table(8)), "KING_BUCKETS_32 != Bini's king table"


def bullet_to_bini_perm(nb: int = NB_DEFAULT) -> np.ndarray:
    """perm[bini_row] = bullet_row, so w1_bini = w1_bullet[perm]."""
    perm = np.empty(nb * 768, dtype=np.int64)
    for b in range(nb):
        for t in range(6):
            for o in range(2):
                for s in range(64):
                    perm[b * 768 + (t * 2 + o) * 64 + s] = b * 768 + o * 384 + t * 64 + s
    assert len(np.unique(perm)) == nb * 768
    return perm


def out_bucket(pieces: int, no: int) -> int:
    """The trainer's BiniMaterial<NO> (= bini_nnue.out_bucket); pieces counts both kings."""
    if no == 1:
        return 0
    return min(no - 1, (pieces - 1) * no // 32)


# ---------------------------------------------------------------------------------------------- readers
def raw_sizes(hidden: int, nb: int, no: int) -> dict[str, int]:
    return {"l0w": nb * 768 * hidden, "l0b": hidden, "l1w": 2 * hidden * no, "l1b": no, "l0f": 768 * hidden}


def read_raw(path: Path, hidden: int, nb: int = NB_DEFAULT, no: int = NO_DEFAULT) -> dict[str, np.ndarray]:
    """raw.bin -> {'l0w': [nb*768, H] (bullet feature order), 'l0b': [H], 'l1w': [no, 2H], 'l1b': [no], ['l0f': [768, H]]}."""
    data = np.fromfile(path, dtype="<f4")
    sz = raw_sizes(hidden, nb, no)
    base = sz["l0w"] + sz["l0b"] + sz["l1w"] + sz["l1b"]
    if data.size == base:
        order = ["l0w", "l0b", "l1w", "l1b"]
    elif data.size == base + sz["l0f"]:
        order = ["l0w", "l0b", "l1w", "l1b", "l0f"]
    else:
        raise ValueError(f"{path}: {data.size} floats; expected {base} (no factoriser) or {base + sz['l0f']} "
                         f"(factoriser) for hidden={hidden} nb={nb} no={no}")
    out: dict[str, np.ndarray] = {}
    off = 0
    for name in order:
        chunk = data[off : off + sz[name]]
        off += sz[name]
        out[name] = _shape(name, chunk, hidden, nb, no)
    return out


def _shape(name: str, flat: np.ndarray, hidden: int, nb: int, no: int) -> np.ndarray:
    flat = np.asarray(flat, dtype=np.float32)
    if name == "l0w":
        return flat.reshape(nb * 768, hidden)          # column-major H x IN == row-major [IN][H]
    if name == "l0b":
        return flat.reshape(hidden)
    if name == "l1w":
        return np.ascontiguousarray(flat.reshape(2 * hidden, no).T)  # column-major NO x 2H -> [NO, 2H]
    if name == "l1b":
        return flat.reshape(no)
    if name == "l0f":
        return flat.reshape(768, hidden)
    raise KeyError(name)


def read_weights_bin(path: Path, nb: int = NB_DEFAULT) -> dict[str, np.ndarray]:
    """optimiser_state/weights.bin (ModelWeights::write_into): `id\\n`, u64 LE count, f32 LE values, per weight."""
    buf = path.read_bytes()
    flat: dict[str, np.ndarray] = {}
    off = 0
    while off < len(buf):
        end = buf.index(b"\n", off)
        name = buf[off:end].decode("ascii")
        off = end + 1
        (count,) = struct.unpack_from("<Q", buf, off)
        off += 8
        flat[name] = np.frombuffer(buf, dtype="<f4", count=count, offset=off).copy()
        off += 4 * count
    hidden = flat["l0b"].size
    assert flat["l0w"].size == nb * 768 * hidden, f"l0w has {flat['l0w'].size} floats, not {nb}*768*{hidden}"
    no = flat["l1b"].size
    assert flat["l1w"].size == 2 * hidden * no
    out = {name: _shape(name, flat[name], hidden, nb, no) for name in ("l0w", "l0b", "l1w", "l1b") if name in flat}
    if "l0f" in flat:
        out["l0f"] = _shape("l0f", flat["l0f"], hidden, nb, no)
    return out


def merge_factoriser(raw: dict[str, np.ndarray], nb: int = NB_DEFAULT) -> dict[str, np.ndarray]:
    """l0w + l0f tiled over the king buckets (bullet's save transform); a no-op without l0f."""
    if "l0f" not in raw:
        return raw
    merged = dict(raw)
    merged["l0w"] = raw["l0w"] + np.tile(raw["l0f"], (nb, 1))
    del merged["l0f"]
    return merged


# ---------------------------------------------------------------------------------------------- export
def quantise(w1: np.ndarray, b1: np.ndarray, w2: np.ndarray, b2: np.ndarray, act: str, out_scale: float = 1.0):
    """Exactly tools/train_nnue.py export(): w1, b1 x QA; w2 x qb x CP_SCALE; b2 = [bias x QA^k x qb x CP ..., QA^k x qb]."""
    w2 = w2 * out_scale
    b2 = b2 * out_scale
    q_w1 = np.clip(np.round(w1 * QA), -32767, 32767).astype(np.int16)
    q_b1 = np.round(b1 * QA).astype(np.int32)
    qb = 64
    while qb > 1 and np.abs(w2).max() * qb * CP_SCALE >= 32000:
        qb //= 2
    q_w2 = np.clip(np.round(w2 * qb * CP_SCALE), -32767, 32767).astype(np.int16)
    qa_act = QA * QA if act == "screlu" else QA
    q_b2 = np.concatenate([np.round(b2 * qa_act * qb * CP_SCALE), [qa_act * qb]]).astype(np.int32)
    return q_w1, q_b1, np.ascontiguousarray(q_w2), q_b2, qb


def write_safetensors(path: Path, tensors: dict[str, np.ndarray], metadata: dict[str, str]) -> None:
    dt = {np.dtype(np.int16): "I16", np.dtype(np.int32): "I32", np.dtype(np.float32): "F32"}
    header: dict = {}
    blobs = []
    off = 0
    for name, arr in tensors.items():
        raw = np.ascontiguousarray(arr).tobytes()
        header[name] = {"dtype": dt[arr.dtype], "shape": list(arr.shape), "data_offsets": [off, off + len(raw)]}
        blobs.append(raw)
        off += len(raw)
    header["__metadata__"] = metadata
    hjson = json.dumps(header).encode("utf-8")
    hjson += b" " * ((8 - len(hjson) % 8) % 8)
    with path.open("wb") as fh:
        fh.write(struct.pack("<Q", len(hjson)))
        fh.write(hjson)
        for b in blobs:
            fh.write(b)


def export_bullet(raw: dict[str, np.ndarray], act: str, out: Path, out_scale: float = 1.0, nb: int = NB_DEFAULT,
                  source: str = "") -> dict[str, str]:
    """bullet float weights (read_raw / read_weights_bin, factoriser merged here) -> Bini safetensors."""
    assert act in ("crelu", "screlu")
    raw = merge_factoriser(raw, nb)
    w1_bullet, b1, w2, b2 = raw["l0w"], raw["l0b"], raw["l1w"], raw["l1b"]
    hidden = w1_bullet.shape[1]
    no = w2.shape[0]
    assert w1_bullet.shape == (nb * 768, hidden) and b1.shape == (hidden,) and w2.shape == (no, 2 * hidden) and b2.shape == (no,)
    w1 = w1_bullet[bullet_to_bini_perm(nb)]
    q_w1, q_b1, q_w2, q_b2, qb = quantise(w1, b1, w2, b2, act, out_scale)
    meta = {"arch": f"{nb}x768x{hidden}x2->{no}", "buckets": str(nb), "hidden": str(hidden), "act": act,
            "out_buckets": str(no), "qa": str(QA), "qb": str(qb), "cp_scale": str(CP_SCALE), "out_scale": str(out_scale),
            "source": "bullet", "bullet_rev": BULLET_REV, "bullet_file": source}
    write_safetensors(out, {"w1": q_w1, "b1": q_b1, "w2": q_w2, "b2": q_b2}, meta)
    print(f"exported {out} ({out.stat().st_size / 1e6:.2f} MB): {meta['arch']} {act}; qb {qb} "
          f"|w1|max {np.abs(w1).max():.3f} |b1|max {np.abs(b1).max():.3f} |w2|max {np.abs(w2).max():.3f} |b2|max {np.abs(b2).max():.3f}",
          flush=True)
    if np.abs(w1).max() * QA > 32767:
        print("WARNING: |w1| x 255 saturates int16 (bullet's AdamW clips at 1.98, but the merged factoriser may exceed 2)")
    return meta


# ---------------------------------------------------------------------------------------------- reference forward
def bullet_features(board, b32: list[int] = KING_BUCKETS_32) -> tuple[list[int], list[int], int]:
    """(stm features, ntm features, pieces) for a python-chess board, following bulletformat::ChessBoard::from_raw
    (board flipped so the side to move is 'white'), Chess768::map_features and ChessBucketsMirrored::map_features."""
    import chess  # python-chess, only needed for the reference path

    buckets = expand_king_buckets(b32)
    stm_black = board.turn == chess.BLACK
    pieces = []  # (piece nibble = them << 3 | type, stm-relative square)
    for sq, pc in board.piece_map().items():
        them = 1 if pc.color != board.turn else 0
        s = sq ^ 56 if stm_black else sq
        pieces.append((them << 3 | (pc.piece_type - 1), s))
    ksq = next(s for p, s in pieces if p == 5)               # our king (type 5, them 0)
    opp_ksq = next(s for p, s in pieces if p == 13) ^ 56     # their king, from their side (ChessBoard.opp_ksq)

    def get(k):
        return (7 if k % 8 > 3 else 0, 768 * int(buckets[k]))

    stm_flip, stm_bucket = get(ksq)
    ntm_flip, ntm_bucket = get(opp_ksq)
    stm_feats, ntm_feats = [], []
    for piece, sq in pieces:
        c = 1 if piece & 8 else 0
        pc = 64 * (piece & 7)
        stm = [0, 384][c] + pc + sq
        ntm = [384, 0][c] + pc + (sq ^ 56)
        stm_feats.append(stm_bucket + (stm ^ stm_flip))
        ntm_feats.append(ntm_bucket + (ntm ^ ntm_flip))
    return stm_feats, ntm_feats, len(pieces)


def bullet_forward(raw: dict[str, np.ndarray], board, act: str, nb: int = NB_DEFAULT) -> float:
    """Float reference: centipawns for the side to move from bullet's raw weights, using only bullet's conventions
    (accumulator = l0b + sum of l0w columns; crelu/screlu; l1 row = BiniMaterial output bucket; x eval scale 400)."""
    raw = merge_factoriser(raw, nb)
    l0w, l0b, l1w, l1b = raw["l0w"].astype(np.float64), raw["l0b"].astype(np.float64), raw["l1w"].astype(np.float64), raw["l1b"].astype(np.float64)
    stm_feats, ntm_feats, pieces = bullet_features(board)
    acc_stm = l0b + l0w[stm_feats].sum(axis=0)
    acc_ntm = l0b + l0w[ntm_feats].sum(axis=0)
    h_stm = np.clip(acc_stm, 0.0, 1.0)
    h_ntm = np.clip(acc_ntm, 0.0, 1.0)
    if act == "screlu":
        h_stm, h_ntm = h_stm * h_stm, h_ntm * h_ntm
    ob = out_bucket(pieces, l1w.shape[0])
    hidden = l0b.size
    out = float(h_stm @ l1w[ob, :hidden] + h_ntm @ l1w[ob, hidden:] + l1b[ob])
    return CP_SCALE * out


# ---------------------------------------------------------------------------------------------- CLI
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--checkpoint", help="bullet checkpoint dir (uses raw.bin; falls back to optimiser_state/weights.bin)")
    src.add_argument("--raw", help="raw.bin")
    src.add_argument("--weights", help="optimiser_state/weights.bin (named tensors; --hidden inferred)")
    ap.add_argument("--hidden", type=int, help="accumulator size (required with raw.bin)")
    ap.add_argument("--act", choices=["crelu", "screlu"], required=True, help="activation the net was trained with")
    ap.add_argument("--king-buckets", type=int, default=NB_DEFAULT)
    ap.add_argument("--out-buckets", type=int, default=NO_DEFAULT)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-scale", type=float, default=1.0, help="multiply the centipawn output (see train_nnue.py)")
    ap.add_argument("--check", action="append", default=[], help="FEN: print the float reference eval (needs python-chess)")
    a = ap.parse_args()

    if a.checkpoint:
        ck = Path(a.checkpoint)
        raw_path, w_path = ck / "raw.bin", ck / "optimiser_state" / "weights.bin"
        if raw_path.exists() and a.hidden:
            raw, source = read_raw(raw_path, a.hidden, a.king_buckets, a.out_buckets), str(raw_path)
        elif w_path.exists():
            raw, source = read_weights_bin(w_path, a.king_buckets), str(w_path)
        else:
            ap.error(f"{ck}: need raw.bin (+ --hidden) or optimiser_state/weights.bin")
    elif a.raw:
        if not a.hidden:
            ap.error("--raw needs --hidden")
        raw, source = read_raw(Path(a.raw), a.hidden, a.king_buckets, a.out_buckets), a.raw
    else:
        raw, source = read_weights_bin(Path(a.weights), a.king_buckets), a.weights
    print(f"read {source}: " + ", ".join(f"{k}{list(v.shape)}" for k, v in raw.items()), flush=True)
    export_bullet(raw, a.act, Path(a.out), a.out_scale, a.king_buckets, source)
    if a.check:
        import chess

        for fen in a.check:
            print(f"{bullet_forward(raw, chess.Board(fen), a.act, a.king_buckets) * a.out_scale:8.1f} cp  {fen}")


if __name__ == "__main__":
    main()
