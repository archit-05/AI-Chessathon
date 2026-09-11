"""Tests for tools/bulletformat.py: byte-level expectations worked out by hand from the layout in
bulletformat/src/chess.rs, a literal Python port of the crate's `from_raw` as a reference encoder,
and round trips through encode/decode and write/read.

    aichessathon-starter/.venv/bin/python bini_v5/tools/test_bulletformat.py
"""

from __future__ import annotations

import os
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bulletformat as bf  # noqa: E402

import chess  # noqa: E402

REC = "<Q16BhBBB3B"  # occ, pcs[16], score, result, ksq, opp_ksq, extra[3]


# ------------------------------------------------------------------ reference: port of from_raw

def _swap_bytes(x: int) -> int:
    return int.from_bytes(x.to_bytes(8, "little"), "big")


def _tz(x: int) -> int:
    return (x & -x).bit_length() - 1 if x else 64


def rust_from_raw(bbs, stm, score, result_f):
    """Literal port of ChessBoard::from_raw (bitboards White, Black, P, N, B, R, Q, K; stm 0/1;
    score White-relative; result 1.0 White win / 0.5 / 0.0) -> the 32 record bytes (extra = 0)."""
    bbs = list(bbs)
    if stm == 1:
        bbs = [_swap_bytes(b) for b in bbs]
        bbs[0], bbs[1] = bbs[1], bbs[0]
        score = -score
        result_f = 1.0 - result_f
    occ = bbs[0] | bbs[1]
    pcs = [0] * 16
    idx = 0
    occ2 = occ
    while occ2:
        sq = _tz(occ2)
        bit = 1 << sq
        occ2 &= occ2 - 1
        colour = (1 if bit & bbs[1] else 0) << 3
        piece = next(i for i, bb in enumerate(bbs[2:]) if bit & bb)
        pcs[idx // 2] |= (colour | piece) << (4 * (idx & 1))
        idx += 1
    result = int(2.0 * result_f)
    ksq = _tz(bbs[0] & bbs[7])
    opp_ksq = _tz(bbs[1] & bbs[7]) ^ 56
    return struct.pack(REC, occ, *pcs, score, result, ksq, opp_ksq, 0, 0, 0)


def bitboards(board: chess.Board):
    return [board.occupied_co[chess.WHITE], board.occupied_co[chess.BLACK], board.pawns, board.knights, board.bishops, board.rooks, board.queens, board.kings]


def encode_board(board: chess.Board, cp_white: int, result_white: int, quiet: int = 1, depth: int = 0):
    row = bf.board_to_row(board)
    return bf.encode(row[None, :], [0 if board.turn else 1], [cp_white], [result_white], [quiet], [depth])[0]


def random_positions(n: int, seed: int) -> list[chess.Board]:
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        b = chess.Board()
        for _ in range(rng.randint(0, 120)):
            moves = list(b.legal_moves)
            if not moves:
                break
            b.push(rng.choice(moves))
            if rng.random() < 0.15 and not b.is_game_over():
                out.append(b.copy())
            if len(out) >= n:
                break
    return out


# ------------------------------------------------------------------ tests

class ByteLevel(unittest.TestCase):
    def test_startpos_white_to_move(self):
        rec = encode_board(chess.Board(), cp_white=25, result_white=1, quiet=1, depth=7)
        # occ: ranks 1, 2, 7, 8
        self.assertEqual(int(rec["occ"]), 0xFFFF00000000FFFF)
        # squares 0..7 R N B Q K B N R -> piece 3 1 2 4 5 2 1 3, low nibble first
        # squares 8..15 pawns -> 0; 48..55 black pawns -> 8|0 = 8; 56..63 r n b q k b n r -> 11 9 10 12 13 10 9 11
        pcs = [0x13, 0x42, 0x25, 0x31, 0x00, 0x00, 0x00, 0x00, 0x88, 0x88, 0x88, 0x88, 0x9B, 0xCA, 0xAD, 0xB9]
        self.assertEqual(list(rec["pcs"]), pcs)
        self.assertEqual(int(rec["score"]), 25)
        self.assertEqual(int(rec["result"]), 2)          # White (the mover) won
        self.assertEqual(int(rec["ksq"]), 4)             # e1
        self.assertEqual(int(rec["opp_ksq"]), 60 ^ 56)   # e8 -> 4
        self.assertEqual(list(rec["extra"]), [1, 7, 0])
        expect = struct.pack(REC, 0xFFFF00000000FFFF, *pcs, 25, 2, 4, 4, 1, 7, 0)
        self.assertEqual(rec.tobytes(), expect)

    def test_startpos_black_to_move(self):
        b = chess.Board()
        b.push_san("e4")
        b.pop()
        b.turn = chess.BLACK
        rec = encode_board(b, cp_white=25, result_white=1, quiet=0, depth=5)
        # the start position is mirror-symmetric: flip + colour swap gives the same board
        self.assertEqual(int(rec["occ"]), 0xFFFF00000000FFFF)
        self.assertEqual(list(rec["pcs"]), [0x13, 0x42, 0x25, 0x31, 0, 0, 0, 0, 0x88, 0x88, 0x88, 0x88, 0x9B, 0xCA, 0xAD, 0xB9])
        self.assertEqual(int(rec["score"]), -25)         # negated for the mover (Black)
        self.assertEqual(int(rec["result"]), 0)          # White won -> the mover lost
        self.assertEqual(int(rec["ksq"]), 4)             # e8 ^ 56
        self.assertEqual(int(rec["opp_ksq"]), 4)         # (e1 ^ 56) ^ 56
        self.assertEqual(list(rec["extra"]), [0, 5, 1])

    def test_asymmetric_black_to_move_kings_anywhere(self):
        # white K c3 (18), white P e2 (12); black k d6 (43); Black to move, White +150, White won
        b = chess.Board("8/8/3k4/8/8/2K5/4P3/8 b - - 0 1")
        rec = encode_board(b, cp_white=150, result_white=1, quiet=1, depth=9)
        # flip: K c3 -> c6 (42) becomes the opponent's king (8|5 = 13); P e2 -> e7 (52) opponent pawn (8);
        # k d6 -> d3 (19) is the mover's king (5).  Square order 19, 42, 52.
        occ = (1 << 19) | (1 << 42) | (1 << 52)
        pcs = [5 | (13 << 4), 8] + [0] * 14
        self.assertEqual(int(rec["occ"]), occ)
        self.assertEqual(list(rec["pcs"]), pcs)
        self.assertEqual(int(rec["score"]), -150)
        self.assertEqual(int(rec["result"]), 0)
        self.assertEqual(int(rec["ksq"]), 19)
        self.assertEqual(int(rec["opp_ksq"]), 42 ^ 56)   # 18 = c3, White's own square for its king
        self.assertEqual(rec.tobytes(), struct.pack(REC, occ, *pcs, -150, 0, 19, 18, 1, 9, 1))

    def test_asymmetric_white_to_move_corner_kings(self):
        # white K a1 (0), white R h1 (7); black k h8 (63), black q a8 (56); White to move, draw
        b = chess.Board("q6k/8/8/8/8/8/8/K6R w - - 0 1")
        rec = encode_board(b, cp_white=-40, result_white=0)
        occ = 1 | (1 << 7) | (1 << 56) | (1 << 63)
        pcs = [5 | (3 << 4), 12 | (13 << 4)] + [0] * 14   # K(5) R(3) | q(8|4=12) k(8|5=13)
        self.assertEqual(rec.tobytes(), struct.pack(REC, occ, *pcs, -40, 1, 0, 63 ^ 56, 1, 0, 0))

    def test_matches_rust_from_raw_on_random_positions(self):
        for b in random_positions(400, seed=7):
            cp = random.Random(b.fen()).randint(-3000, 3000)
            res = random.Random(b.fen() + "r").choice([-1, 0, 1])
            rec = encode_board(b, cp, res)
            ours = bytearray(rec.tobytes())
            ours[29:32] = b"\0\0\0"   # the reference leaves extra at zero
            ref = rust_from_raw(bitboards(b), 0 if b.turn else 1, cp, (res + 1) / 2)
            self.assertEqual(bytes(ours), ref, b.fen())


class RoundTrip(unittest.TestCase):
    def test_encode_decode_random(self):
        boards = random_positions(600, seed=11)
        n = len(boards)
        pieces = np.stack([bf.board_to_row(b) for b in boards])
        stm = np.array([0 if b.turn else 1 for b in boards], np.uint8)
        rng = np.random.default_rng(3)
        cp = rng.integers(-3000, 3001, n).astype(np.int16)
        result = rng.integers(-1, 2, n).astype(np.int8)
        quiet = rng.integers(0, 2, n).astype(np.uint8)
        depth = rng.integers(1, 30, n).astype(np.uint8)
        c = bf.decode(bf.encode(pieces, stm, cp, result, quiet, depth))
        self.assertTrue(stm.any() and not stm.all(), "both colours to move must be present")
        np.testing.assert_array_equal(c["pieces"], pieces)
        np.testing.assert_array_equal(c["stm"], stm)
        np.testing.assert_array_equal(c["cp"], cp)
        np.testing.assert_array_equal(c["result"], result)
        np.testing.assert_array_equal(c["quiet"], quiet)
        np.testing.assert_array_equal(c["depth"], depth)
        self.assertEqual(c["pieces"].dtype, np.uint8)
        self.assertEqual(c["stm"].dtype, np.uint8)
        self.assertEqual(c["cp"].dtype, np.int16)
        self.assertEqual(c["result"].dtype, np.int8)
        self.assertEqual(c["quiet"].dtype, np.uint8)
        self.assertEqual(set(c.files), {"pieces", "stm", "cp", "result", "quiet", "depth"})
        # the decoded rows rebuild the original placement
        for i in (0, n // 2, n - 1):
            self.assertEqual(bf.row_to_board(c["pieces"][i], c["stm"][i]).board_fen(), boards[i].board_fen())
            self.assertEqual(bf.row_to_fen(c["pieces"][i], c["stm"][i]).split()[0], boards[i].board_fen())

    def test_hand_positions_both_colours(self):
        fens = [
            "8/8/3k4/8/8/2K5/4P3/8 b - - 0 1",
            "8/8/3k4/8/8/2K5/4P3/8 w - - 0 1",
            "q6k/8/8/8/8/8/8/K6R w - - 0 1",
            "q6k/8/8/8/8/8/8/K6R b - - 0 1",
            "k7/8/8/8/8/8/8/7K w - - 0 1",
            "K7/8/8/8/8/8/8/7k b - - 0 1",
            "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
            "1k6/8/8/8/8/8/8/6K1 w - - 0 1",   # kings on b8 / g1
            "3K4/8/8/8/8/8/8/4k3 b - - 0 1",   # white king on the eighth rank, black king on the first
        ]
        for fen in fens:
            b = chess.Board(fen)
            for cp, res in ((0, 0), (700, 1), (-2999, -1), (3000, 1)):
                rec = encode_board(b, cp, res, quiet=0, depth=3)
                c = bf.decode(rec.reshape(1))
                self.assertEqual(bf.row_to_board(c["pieces"][0], c["stm"][0]).board_fen(), b.board_fen(), fen)
                self.assertEqual(int(c["stm"][0]), 0 if b.turn else 1)
                self.assertEqual(int(c["cp"][0]), cp)
                self.assertEqual(int(c["result"][0]), res)
                self.assertEqual(int(c["quiet"][0]), 0)
                self.assertEqual(int(c["depth"][0]), 3)
                # king squares: ksq is the mover's king in the mover's frame
                ksq = b.king(b.turn) if b.turn else b.king(b.turn) ^ 56
                oksq = (b.king(not b.turn) ^ 56) if b.turn else b.king(not b.turn)
                self.assertEqual(int(rec["ksq"]), ksq)
                self.assertEqual(int(rec["opp_ksq"]), oksq)

    def test_write_read_file(self):
        boards = random_positions(150, seed=5)
        pieces = np.stack([bf.board_to_row(b) for b in boards])
        stm = np.array([0 if b.turn else 1 for b in boards], np.uint8)
        cp = np.arange(len(boards), dtype=np.int16) * 7 - 500
        result = (np.arange(len(boards)) % 3 - 1).astype(np.int8)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.bin"
            n = bf.write(p, {"pieces": pieces, "stm": stm, "cp": cp, "result": result})
            self.assertEqual(n, len(boards))
            self.assertEqual(os.path.getsize(p), 32 * len(boards))
            self.assertEqual(bf.count(p), len(boards))
            self.assertFalse(list(Path(d).glob(".*.part")))
            c = bf.read(p)
            np.testing.assert_array_equal(c["pieces"], pieces)
            np.testing.assert_array_equal(c["stm"], stm)
            np.testing.assert_array_equal(c["cp"], cp)
            np.testing.assert_array_equal(c["result"], result)
            np.testing.assert_array_equal(c["quiet"], 1)
            raw = bf.read_raw(p)
            self.assertEqual(raw.dtype, bf.DTYPE)
            # structured-array input to write() and a second read agree byte for byte
            p2 = Path(d) / "y.bin"
            bf.write(p2, raw)
            self.assertEqual(p.read_bytes(), p2.read_bytes())
            # a foreign file (extra = 0) reads back as "White to move" with the stm-frame board
            raw2 = raw.copy()
            raw2["extra"] = 0
            c2 = bf.decode(raw2)
            self.assertTrue((c2["stm"] == 0).all())
            np.testing.assert_array_equal(c2["cp"], raw["score"])
            # a truncated file is rejected
            (Path(d) / "bad.bin").write_bytes(b"\0" * 33)
            with self.assertRaises(ValueError):
                bf.read(Path(d) / "bad.bin")

    def test_rejects_bad_input(self):
        row = bf.board_to_row(chess.Board())
        with self.assertRaises(ValueError):
            bf.encode(row, [2], [0], [0])
        with self.assertRaises(ValueError):
            bf.encode(row, [0], [0], [2])
        row2 = row.copy()
        row2[4] = 0  # no white king
        with self.assertRaises(ValueError):
            bf.encode(row2, [0], [0], [0])
        self.assertEqual(len(bf.encode(np.zeros((0, 64), np.uint8), [], [], [])), 0)
        self.assertEqual(len(bf.decode(np.zeros(0, bf.DTYPE))["cp"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
