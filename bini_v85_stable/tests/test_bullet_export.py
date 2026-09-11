"""Gate: bullet raw weights -> tools/bullet_export.py -> bini_nnue's integer forward equals a numpy reference
written from bullet's own conventions (bullet_export.bullet_forward) to within quantisation error.

    python tests/test_bullet_export.py [--hidden 512] [--act screlu] [--n 1000] [--factorise] [--out-scale 1.0]

A synthetic random raw.bin is written in bullet's derived layout (see bullet_export.py), exported, loaded by
bini_nnue (BINI_NNUE is set before the import) and compared on random legal positions from two sources:
random playouts with a capture bias (real-looking positions, both sides to move, endgames) and random piece
placements accepted by python-chess (kings on every file, 2..32 men).

Tolerance, computed per position from the exported integers. With n men on the board every accumulator entry
sums n + 1 rounded values (w1, b1 x 255), each rounding error uniform in [-0.5, 0.5]:
  worst case : |acc_int - 255 acc| <= d = (n+1)/2; crelu is 1-Lipschitz (|dact| <= d), screlu on [0, 255] gives
               |x^2 - y^2| <= 510 d; w2 is rounded to 1/(qb 400), b2 to 1/(255^k qb 400), the engine floors:
               bound_cp = (sum_h |w2q_h| dact + 0.5 sum_h (act_h + dact) + 0.5) / (255^k qb) + 1   (hundreds of cp,
               never approached because the errors are independent and add in quadrature)
  statistical: var(acc error) = (n+1)/12; crelu passes it through on active units (0 < acc < 255), screlu scales it
               by (2 x)^2; var(out) = sum_h w2q_h^2 var(dact_h) + sum_h act_h^2 / 12 + 1/12; the test asserts
               |int - ref| <= 6 sigma + 1 (floor) per position, and globally mean < 4 cp, max < 25 cp (x out_scale),
               the same limits tests/test_train_consistency.py applies to real nets.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import chess  # noqa: E402

import bullet_export as X  # noqa: E402


def write_synthetic_raw(path: Path, hidden: int, nb: int, no: int, factorise: bool, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """Random weights with realistic magnitudes, written exactly as bullet's save_unquantised does."""
    t = {
        "l0w": rng.normal(0.0, 0.08, (nb * 768, hidden)).clip(-1.9, 1.9).astype(np.float32),
        "l0b": rng.normal(0.0, 0.10, hidden).astype(np.float32),
        "l1w": rng.normal(0.0, 0.05, (no, 2 * hidden)).astype(np.float32),
        "l1b": rng.normal(0.0, 0.10, no).astype(np.float32),
    }
    if factorise:
        t["l0f"] = rng.normal(0.0, 0.03, (768, hidden)).astype(np.float32)
    with path.open("wb") as fh:
        fh.write(t["l0w"].astype("<f4").tobytes())                     # H x IN column-major == [IN][H]
        fh.write(t["l0b"].astype("<f4").tobytes())
        fh.write(np.ascontiguousarray(t["l1w"].T).astype("<f4").tobytes())  # NO x 2H column-major == [2H][NO]
        fh.write(t["l1b"].astype("<f4").tobytes())
        if factorise:
            fh.write(t["l0f"].astype("<f4").tobytes())
    return t


def playout_positions(rng: random.Random, count: int) -> list[chess.Board]:
    out: list[chess.Board] = []
    while len(out) < count:
        board = chess.Board()
        plies = rng.randint(0, 220)
        for _ in range(plies):
            moves = list(board.legal_moves)
            if not moves:
                break
            caps = [m for m in moves if board.is_capture(m)]
            board.push(rng.choice(caps) if caps and rng.random() < 0.5 else rng.choice(moves))
        out.append(board.copy())
    return out


def random_placements(rng: random.Random, count: int) -> list[chess.Board]:
    out: list[chess.Board] = []
    while len(out) < count:
        board = chess.Board(None)
        squares = list(range(64))
        rng.shuffle(squares)
        wk, bk = squares[0], squares[1]
        if chess.square_distance(wk, bk) < 2:
            continue
        board.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
        board.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
        n_extra = rng.choice([0, 1, 2, 3, 4, 6, 8, 12, 16, 20, 24, 28, 30])
        for sq in squares[2 : 2 + n_extra]:
            pt = rng.choice([chess.PAWN, chess.PAWN, chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])
            if pt == chess.PAWN and chess.square_rank(sq) in (0, 7):
                pt = chess.KNIGHT
            board.set_piece_at(sq, chess.Piece(pt, rng.choice([chess.WHITE, chess.BLACK])))
        board.turn = rng.choice([chess.WHITE, chess.BLACK])
        if board.is_valid():
            out.append(board)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--act", choices=["crelu", "screlu"], default="screlu")
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--factorise", action="store_true")
    ap.add_argument("--out-scale", type=float, default=1.0)
    a = ap.parse_args()
    nb, no = 8, 8
    nrng = np.random.default_rng(a.seed)
    rng = random.Random(a.seed)

    tmp = Path(tempfile.mkdtemp(prefix="bini_bullet_"))
    raw_path = tmp / "raw.bin"
    truth = write_synthetic_raw(raw_path, a.hidden, nb, no, a.factorise, nrng)
    raw = X.read_raw(raw_path, a.hidden, nb, no)
    for k, v in truth.items():
        assert np.array_equal(raw[k], v), f"read_raw round trip failed for {k}"
    print(f"raw.bin {raw_path.stat().st_size} bytes read back: " + ", ".join(f"{k}{list(v.shape)}" for k, v in raw.items()))

    st_path = tmp / "nnue.safetensors"
    meta = X.export_bullet(raw, a.act, st_path, a.out_scale, nb, str(raw_path))
    qb = int(meta["qb"])

    os.environ["BINI_NNUE"] = str(st_path)
    import bini_board as B  # noqa: E402  (after BINI_NNUE)
    import bini_nnue as N  # noqa: E402

    assert N.LOADED and N.WEIGHTS_PATH == st_path
    assert (N.NB, N.HIDDEN, N.NO, N.ACT_SQ) == (nb, a.hidden, no, 1 if a.act == "screlu" else 0), (N.NB, N.HIDDEN, N.NO, N.ACT_SQ)
    assert np.array_equal(N.KB_TABLE, X.bullet_king_table(X.KING_BUCKETS_32)), "engine king table != bullet bucket array"
    assert int(N.B2[N.NO]) == (255 * 255 if a.act == "screlu" else 255) * qb
    # the exporter's permutation, checked directly against the engine's own feature function
    perm = X.bullet_to_bini_perm(nb)
    for b in range(nb):
        for t in range(6):
            for o in range(2):
                for s in (0, 7, 27, 63):
                    code = (t + 1) + (0 if o == 0 else 6)  # white piece from white's view: own when o == 0
                    assert int(N._feature.py_func(0, code, s, b * 2)) == b * 768 + (t * 2 + o) * 64 + s
                    assert perm[b * 768 + (t * 2 + o) * 64 + s] == b * 768 + o * 384 + t * 64 + s

    boards = playout_positions(rng, a.n // 2) + random_placements(rng, a.n - a.n // 2)
    bb, st, pcs = B.new_position()
    acc = N.new_accumulators()
    t0 = time.perf_counter()
    B.set_fen(bb, st, pcs, boards[0].fen())
    N.nnue_refresh(bb, st, pcs, acc, N.W1, N.B1)
    N.nnue_eval(bb, st, acc, N.W2, N.B2)
    print(f"numba compile {time.perf_counter() - t0:.0f}s", flush=True)

    qa_act = 255 * 255 if a.act == "screlu" else 255
    diffs, bounds, sigmas = [], [], []
    cover = {"black to move": 0, "white king e-h": 0, "white king a-d": 0, "black king e-h": 0, "black king a-d": 0, "<= 8 men": 0, ">= 28 men": 0}
    worst = None
    for board in boards:
        B.set_fen(bb, st, pcs, board.fen())
        N.nnue_refresh(bb, st, pcs, acc, N.W1, N.B1)
        q = int(N.nnue_eval(bb, st, acc, N.W2, N.B2))
        ref = X.bullet_forward(raw, board, a.act, nb) * a.out_scale
        d = abs(q - ref)
        n = len(board.piece_map())
        stm = 0 if board.turn else 1
        ob = X.out_bucket(n, no)
        delta = (n + 1) * 0.5
        dact = 510.0 * delta if a.act == "screlu" else delta
        w2q = np.abs(N.W2[ob].astype(np.float64))
        act_int = []
        for p in (stm, 1 - stm):
            v = np.clip(acc[0, p].astype(np.float64), 0, 255)
            act_int.append(v * v if a.act == "screlu" else v)
        act_int = np.concatenate(act_int)
        bound = (float((w2q * dact).sum()) + 0.5 * float((act_int + dact).sum()) + 0.5) / (qa_act * qb) + 1.0
        # statistical: variance of the accumulator rounding error per entry, propagated through the activation
        acc_raw = np.concatenate([acc[0, stm], acc[0, 1 - stm]]).astype(np.float64)
        var_acc = (n + 1) / 12.0
        if a.act == "screlu":
            var_act = 4.0 * np.clip(acc_raw, 0, 255) ** 2 * var_acc
        else:
            var_act = np.where((acc_raw > -delta) & (acc_raw < 255 + delta), var_acc, 0.0)
        var_out = float((w2q * w2q * var_act).sum()) + float((act_int * act_int).sum()) / 12.0 + 1.0 / 12.0
        sigma = np.sqrt(var_out) / (qa_act * qb)
        bound6 = 6.0 * sigma + 1.0
        diffs.append(d)
        bounds.append(bound6)
        sigmas.append(d / sigma)
        if worst is None or d > worst[0]:
            worst = (d, q, ref, bound6, board.fen())
        assert d <= bound, f"|int - ref| = {d:.2f} cp exceeds the worst-case rounding bound {bound:.2f}: {q} vs {ref:.2f} {board.fen()}"
        assert d <= bound6, f"|int - ref| = {d:.2f} cp exceeds 6 sigma + 1 = {bound6:.2f} (sigma {sigma:.2f}): {q} vs {ref:.2f} {board.fen()}"
        cover["black to move"] += stm
        cover["white king e-h" if chess.square_file(board.king(chess.WHITE)) >= 4 else "white king a-d"] += 1
        cover["black king e-h" if chess.square_file(board.king(chess.BLACK)) >= 4 else "black king a-d"] += 1
        cover["<= 8 men"] += n <= 8
        cover[">= 28 men"] += n >= 28
    diffs, bounds, sigmas = np.array(diffs), np.array(bounds), np.array(sigmas)
    print(f"{len(diffs)} positions, hidden {a.hidden} {a.act} qb {qb} factoriser {a.factorise} out_scale {a.out_scale}")
    print(f"|int - float| cp: mean {diffs.mean():.2f}, median {np.median(diffs):.2f}, max {diffs.max():.2f}; "
          f"6-sigma+1 tolerance: mean {bounds.mean():.1f}, min {bounds.min():.1f}; max |diff|/sigma {sigmas.max():.2f}")
    print(f"worst: int {worst[1]} ref {worst[2]:.2f} tolerance {worst[3]:.1f}  {worst[4]}")
    print("coverage: " + ", ".join(f"{k} {v}" for k, v in cover.items()))
    for k, v in cover.items():
        assert v >= 40, f"coverage too thin: {k} = {v}"
    scale = max(1.0, abs(a.out_scale))
    assert diffs.mean() < 4.0 * scale and diffs.max() < 25.0 * scale, "errors beyond what int16 quantisation explains"
    print("bullet export consistency ok")


if __name__ == "__main__":
    main()
