"""Offline calibration of the shipped net's bias (V5, 20:40): on the site's Stockfish-16 depth-16
labelled positions, measure the mean residual of the net's static evaluation by (piece count,
material imbalance from the side to move) and emit a table that evaluate() subtracts at runtime.
The residual is measured in the net's own units (label x global slope), so the table only
removes systematic bias; it is a tuned evaluation term, baked into bini_eval.py as constants.

    python tools/calib_table.py ../data/site_all/chunk_0000.npz ../data/site_labelled/chunk_0000.npz --min 300 --out tools/calib_table.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bini_board as B  # noqa: E402
import bini_engine as E  # noqa: E402

import chess
PV = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
NB_IMB = 11  # imbalance bins: -5..+5 pawns (clipped), side-to-move view


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("chunks", nargs="+")
    ap.add_argument("--n", type=int, default=400_000)
    ap.add_argument("--min", type=int, default=300, help="minimum positions per bucket, else 0 correction")
    ap.add_argument("--out", default="tools/calib_table.json")
    a = ap.parse_args()
    eng = E.Engine(use_nnue=True); E.warm_up(eng)
    pieces, stm, cp = [], [], []
    for c in a.chunks:
        z = np.load(c)
        keep = z["quiet"] == 1 if "quiet" in z.files else np.ones(len(z["cp"]), bool)
        pieces.append(z["pieces"][keep]); stm.append(z["stm"][keep]); cp.append(z["cp"][keep])
    pieces, stm, cp = np.concatenate(pieces)[: a.n], np.concatenate(stm)[: a.n], np.concatenate(cp)[: a.n].astype(np.int64)
    # label from the side to move's view, in the net's units after the global slope fit below
    lab = np.where(stm == 1, -cp, cp).astype(np.float64)
    net = np.zeros(len(cp)); npc = np.zeros(len(cp), np.int64); imb = np.zeros(len(cp), np.int64)
    for i in range(len(cp)):
        if True:
            b = chess.Board(None)
            for sq in range(64):
                code = int(pieces[i][sq])
                if code:
                    b.set_piece_at(sq, chess.Piece((code - 1) % 6 + 1, code <= 6))
            b.turn = stm[i] == 0
            fen = b.fen()
        eng.set_position(fen, [])
        net[i] = eng.static_eval()
        npc[i] = int(np.count_nonzero(pieces[i]))
        m = sum(PV[pc.piece_type] * (1 if pc.color else -1) for pc in b.piece_map().values())
        imb[i] = max(-5, min(5, m if b.turn else -m))
    sel = np.abs(lab) <= 800
    k = float(np.dot(net[sel], lab[sel]) / np.dot(lab[sel], lab[sel]))
    resid = net - k * lab
    table = np.zeros((33, NB_IMB), np.int64); counts = np.zeros((33, NB_IMB), np.int64)
    for p in range(2, 33):
        for j in range(NB_IMB):
            m = (npc == p) & (imb == j - 5) & sel
            counts[p, j] = m.sum()
            if m.sum() >= a.min:
                table[p, j] = int(round(np.median(resid[m])))
    print(f"n {len(cp)}, slope {k:.3f}, residual mean {resid[sel].mean():.1f} sd {resid[sel].std():.1f}")
    for p in (4, 6, 8, 10, 14, 18, 22, 26, 30):
        print(f"  pieces {p:2d}: " + " ".join(f"{table[p, j]:5d}({counts[p, j]:5d})" for j in range(NB_IMB)))
    after = resid.copy()
    for i in range(len(cp)):
        after[i] -= table[npc[i], imb[i] + 5]
    print(f"MAE of residual before {np.abs(resid[sel]).mean():.1f} after {np.abs(after[sel]).mean():.1f}")
    json.dump({"slope": k, "table": table.tolist(), "counts": counts.tolist()}, open(a.out, "w"))
    print("->", a.out)


if __name__ == "__main__":
    main()
