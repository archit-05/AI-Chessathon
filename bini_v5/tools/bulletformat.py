"""bulletformat.py -- read/write the `bullet` trainer's `ChessBoard` format (32 bytes per position).

Layout, derived from bulletformat/src/chess.rs (`#[repr(C)] struct ChessBoard`, compile-time
asserted to be 32 bytes; `HEADER_SIZE = 0`, so a .bin file is a flat array of records, little-endian):

    off size field    meaning
    0   8    occ      u64 bitboard of occupied squares, bit i = square i (a1 = 0, h1 = 7, a8 = 56,
                      h8 = 63) in the SIDE-TO-MOVE frame (see flipping below)
    8   16   pcs      32 nibbles, one per set bit of occ in ascending square order (BoardIter walks
                      trailing_zeros); nibble k lives in pcs[k // 2] >> (4 * (k & 1)), i.e. the LOW
                      nibble comes first; nibble = (colour << 3) | piece, piece 0..5 = P N B R Q K,
                      colour 0 = side to move, 1 = opponent
    24  2    score    i16 centipawns from the SIDE TO MOVE's view
    26  1    result   0 = side to move lost, 1 = draw, 2 = side to move won
                      (Rust: `result: f32` in {0, 0.5, 1} times 2)
    27  1    ksq      square of the side to move's king, stm frame
    28  1    opp_ksq  square of the opponent's king in the stm frame XOR 56 (= its square as seen
                      from the opponent's own side)
    29  3    extra    ignored by bullet.  OURS: extra[0] = quiet (1 = bestmove neither capture nor
                      promotion), extra[1] = search depth (0 unknown), extra[2] = ABSOLUTE side to
                      move (0 White, 1 Black) -- the record itself does not store it, and `read`
                      needs it to hand back White-relative data.  A file written by other tools has
                      extra = 0, so it reads back as "White to move" everywhere, which is a legal
                      symmetry of the position for a perspective net.

Flipping (`from_raw` with stm == 1, identically `from_str`): when Black is to move every bitboard is
byte-swapped (square ^= 56, a vertical mirror), the White and Black bitboards are swapped (colour bit
of every nibble toggles), score is negated and result becomes 1 - result (byte 2 - b).  So a record
always reads as "the mover is White".  Castling rights, en passant and move counters are not stored.

Our convention (what `read` returns, matching tools/train_nnue.py `load_chunk` / the .npz chunks):
    pieces  uint8[N, 64]  codes 1..12 = white P N B R Q K, black p n b r q k, absolute colours
    stm     uint8[N]      0 White to move, 1 Black
    cp      int16[N]      centipawns from WHITE's view
    result  int8[N]       +1 White won, 0 draw/unknown, -1 Black won
    quiet   uint8[N]      from extra[0]
    depth   uint8[N]      from extra[1]

    python tools/bulletformat.py info  FILE.bin ...
    python tools/bulletformat.py dump  FILE.bin [-n 10]
    python tools/bulletformat.py convert CHUNK.npz OUT.bin
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

DTYPE = np.dtype(
    [
        ("occ", "<u8"),
        ("pcs", "u1", (16,)),
        ("score", "<i2"),
        ("result", "u1"),
        ("ksq", "u1"),
        ("opp_ksq", "u1"),
        ("extra", "u1", (3,)),
    ]
)
RECORD = DTYPE.itemsize
assert RECORD == 32, RECORD

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}
SYMBOLS = ".PNBRQKpnbrqk"
CP_CLIP = 3000

# our code (1..12, 1..6 = side to move after the colour swap) -> bullet nibble
_NIB = np.array([0, 0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13], dtype=np.uint8)
# bullet nibble -> our code (colour 0 of the nibble = "white" of the stm frame); 6, 7, 14, 15 unused
_CODE = np.zeros(16, dtype=np.uint8)
for _n in range(16):
    if (_n & 7) < 6:
        _CODE[_n] = (_n & 7) + 1 + 6 * (_n >> 3)
_SWAP = np.array([0, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6], dtype=np.uint8)  # colour swap of codes
_FLIP = np.arange(64) ^ 56                                                       # vertical mirror
_SQ64 = np.arange(64, dtype=np.uint64)
_BLOCK = 32768


class Chunk(dict):
    """dict of arrays with a `.files` attribute so it can stand in for an np.load() result."""

    @property
    def files(self) -> list[str]:
        return list(self.keys())


# ----------------------------------------------------------------------------- encode / decode

def _encode_block(pieces, stm, cp, result, quiet, depth):
    n = len(pieces)
    black = stm == 1
    rel = pieces.copy()
    if black.any():
        rel[black] = _SWAP[pieces[black][:, _FLIP]]      # mirror, then swap colours
    occupied = rel != 0
    occ = np.bitwise_or.reduce(occupied.astype(np.uint64) << _SQ64, axis=1)
    idx = np.cumsum(occupied, axis=1, dtype=np.int16) - 1
    rows, sqs = np.nonzero(occupied)
    k = idx[rows, sqs]
    if len(k) and k.max() >= 32:
        raise ValueError("a position has more than 32 pieces")
    nib32 = np.zeros((n, 32), dtype=np.uint8)
    nib32[rows, k] = _NIB[rel[rows, sqs]]
    pcs = nib32[:, 0::2] | (nib32[:, 1::2] << 4)
    kings = rel == 6
    opp_kings = rel == 12
    if not ((kings.sum(1) == 1) & (opp_kings.sum(1) == 1)).all():
        raise ValueError("every position needs exactly one king per colour")
    out = np.zeros(n, dtype=DTYPE)
    out["occ"] = occ
    out["pcs"] = pcs
    score = np.where(black, -cp.astype(np.int32), cp.astype(np.int32))
    out["score"] = np.clip(score, -32768, 32767).astype(np.int16)
    out["result"] = np.where(black, 1 - result.astype(np.int16), 1 + result.astype(np.int16)).astype(np.uint8)
    out["ksq"] = np.argmax(kings, axis=1).astype(np.uint8)
    out["opp_ksq"] = (np.argmax(opp_kings, axis=1) ^ 56).astype(np.uint8)
    out["extra"][:, 0] = quiet
    out["extra"][:, 1] = depth
    out["extra"][:, 2] = stm
    return out


def encode(pieces, stm, cp, result, quiet=None, depth=None) -> np.ndarray:
    """Our convention (see module doc) -> structured array of DTYPE, one record per position."""
    pieces = np.ascontiguousarray(pieces, dtype=np.uint8).reshape(-1, 64)
    n = len(pieces)
    stm = np.asarray(stm, dtype=np.uint8).reshape(n)
    cp = np.asarray(cp).reshape(n)
    result = np.asarray(result, dtype=np.int8).reshape(n)
    quiet = np.ones(n, dtype=np.uint8) if quiet is None else np.asarray(quiet, dtype=np.uint8).reshape(n)
    depth = np.zeros(n, dtype=np.uint8) if depth is None else np.asarray(np.clip(depth, 0, 255), dtype=np.uint8).reshape(n)
    if not np.isin(stm, (0, 1)).all():
        raise ValueError("stm must be 0 or 1")
    if not np.isin(result, (-1, 0, 1)).all():
        raise ValueError("result must be -1, 0 or +1 (White's view)")
    parts = [
        _encode_block(pieces[i : i + _BLOCK], stm[i : i + _BLOCK], cp[i : i + _BLOCK], result[i : i + _BLOCK], quiet[i : i + _BLOCK], depth[i : i + _BLOCK])
        for i in range(0, n, _BLOCK)
    ]
    return np.concatenate(parts) if parts else np.zeros(0, dtype=DTYPE)


def _decode_block(arr) -> tuple:
    n = len(arr)
    occupied = ((arr["occ"][:, None] >> _SQ64) & np.uint64(1)).astype(bool)
    pcs = arr["pcs"]
    nib32 = np.empty((n, 32), dtype=np.uint8)
    nib32[:, 0::2] = pcs & 15
    nib32[:, 1::2] = pcs >> 4
    idx = np.cumsum(occupied, axis=1, dtype=np.int16) - 1
    rows, sqs = np.nonzero(occupied)
    rel = np.zeros((n, 64), dtype=np.uint8)
    rel[rows, sqs] = _CODE[nib32[rows, idx[rows, sqs]]]
    stm = (arr["extra"][:, 2] & 1).astype(np.uint8)
    black = stm == 1
    pieces = rel
    if black.any():
        pieces = rel.copy()
        pieces[black] = _SWAP[rel[black][:, _FLIP]]
    score = arr["score"].astype(np.int32)
    cp = np.where(black, -score, score).astype(np.int16)
    res = arr["result"].astype(np.int16)
    result = np.where(black, 1 - res, res - 1).astype(np.int8)
    return pieces, stm, cp, result, arr["extra"][:, 0].copy(), arr["extra"][:, 1].copy()


def decode(arr) -> Chunk:
    """Structured array of DTYPE -> Chunk in our convention (absolute colours, White's view)."""
    arr = np.asarray(arr, dtype=DTYPE).reshape(-1)
    cols = [_decode_block(arr[i : i + _BLOCK]) for i in range(0, len(arr), _BLOCK)]
    names = ("pieces", "stm", "cp", "result", "quiet", "depth")
    if not cols:
        return Chunk(pieces=np.zeros((0, 64), np.uint8), stm=np.zeros(0, np.uint8), cp=np.zeros(0, np.int16), result=np.zeros(0, np.int8), quiet=np.zeros(0, np.uint8), depth=np.zeros(0, np.uint8))
    return Chunk({nm: np.concatenate([c[i] for c in cols]) for i, nm in enumerate(names)})


# ----------------------------------------------------------------------------- files

def write(path, rows) -> int:
    """Write records to `path` atomically (temp file + rename).  `rows` is a structured array of
    DTYPE, or a mapping in our convention (pieces/stm/cp/result[/quiet/depth]) which is encoded
    first.  Returns the number of records written."""
    if isinstance(rows, dict):
        arr = encode(rows["pieces"], rows["stm"], rows["cp"], rows["result"], rows.get("quiet"), rows.get("depth"))
    else:
        arr = np.ascontiguousarray(np.asarray(rows, dtype=DTYPE).reshape(-1))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.part")
    with open(tmp, "wb") as f:
        f.write(arr.tobytes())
    os.replace(tmp, path)
    return len(arr)


def read_raw(path) -> np.ndarray:
    """The records of a .bin as a structured array of DTYPE (no conversion)."""
    size = os.path.getsize(path)
    if size % RECORD:
        raise ValueError(f"{path}: size {size} is not a multiple of {RECORD}")
    return np.fromfile(path, dtype=DTYPE)


def read(path) -> Chunk:
    """A .bin in our convention: Chunk(pieces, stm, cp, result, quiet, depth); see module doc."""
    return decode(read_raw(path))


def count(path) -> int:
    return os.path.getsize(path) // RECORD


# ----------------------------------------------------------------------------- python-chess helpers

def board_to_row(board, row=None):
    """python-chess Board -> uint8[64] of our codes (placement only)."""
    if row is None:
        row = np.zeros(64, dtype=np.uint8)
    else:
        row[:] = 0
    for sq, pc in board.piece_map().items():
        row[sq] = CODES[pc.symbol()]
    return row


def row_to_board(row, stm: int):
    """uint8[64] of our codes + stm -> python-chess Board (no castling rights, no ep)."""
    import chess  # noqa: PLC0415

    b = chess.Board(None)
    for sq in np.nonzero(row)[0]:
        b.set_piece_at(int(sq), chess.Piece.from_symbol(SYMBOLS[int(row[sq])]))
    b.turn = chess.WHITE if stm == 0 else chess.BLACK
    return b


def row_to_fen(row, stm: int) -> str:
    """Placement + side to move as a FEN string, without python-chess."""
    ranks = []
    for r in range(7, -1, -1):
        s, empty = "", 0
        for f in range(8):
            c = int(row[8 * r + f])
            if c == 0:
                empty += 1
            else:
                if empty:
                    s += str(empty)
                    empty = 0
                s += SYMBOLS[c]
        if empty:
            s += str(empty)
        ranks.append(s)
    return "/".join(ranks) + (" w" if stm == 0 else " b") + " - - 0 1"


# ----------------------------------------------------------------------------- CLI

def _info(paths) -> None:
    tot = 0
    for p in paths:
        c = read(p)
        n = len(c["cp"])
        tot += n
        if n == 0:
            print(f"{p}: 0 rows")
            continue
        cp = c["cp"].astype(np.int32)
        res = c["result"]
        print(
            f"{p}: {n} rows, black-to-move {100 * c['stm'].mean():.1f}%, quiet {100 * c['quiet'].mean():.1f}%, "
            f"depth {int(c['depth'].min())}-{int(c['depth'].max())}, cp mean {cp.mean():+.0f} |cp| mean {np.abs(cp).mean():.0f} "
            f"|cp|>=1500 {100 * (np.abs(cp) >= 1500).mean():.1f}%, result +1/0/-1 {int((res == 1).sum())}/{int((res == 0).sum())}/{int((res == -1).sum())}"
        )
    if len(paths) > 1:
        print(f"total {tot} rows")


def _dump(path, n: int) -> None:
    c = read(path)
    for i in range(min(n, len(c["cp"]))):
        print(f"{row_to_fen(c['pieces'][i], int(c['stm'][i]))} | cp(white) {int(c['cp'][i]):+d} | result {int(c['result'][i]):+d} | quiet {int(c['quiet'][i])} | depth {int(c['depth'][i])}")


def _convert(src, dst) -> None:
    z = np.load(src)
    n = write(dst, {"pieces": z["pieces"], "stm": z["stm"], "cp": z["cp"], "result": z["result"] if "result" in z.files else np.zeros(len(z["cp"]), np.int8), "quiet": z["quiet"] if "quiet" in z.files else None, "depth": z["depth"] if "depth" in z.files else None})
    print(f"{n} rows -> {dst}")


def main(argv=None) -> None:
    import argparse  # noqa: PLC0415

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("info"); s.add_argument("files", nargs="+")
    s = sub.add_parser("dump"); s.add_argument("file"); s.add_argument("-n", type=int, default=10)
    s = sub.add_parser("convert"); s.add_argument("src"); s.add_argument("dst")
    a = ap.parse_args(argv)
    if a.cmd == "info":
        _info(a.files)
    elif a.cmd == "dump":
        _dump(a.file, a.n)
    else:
        _convert(a.src, a.dst)


if __name__ == "__main__":
    sys.exit(main())
