"""Where is the net wrong? Static evaluation of a labelled chunk, error binned by piece count,
king bucket, material balance, quiet/tactical and label magnitude.

    python tools/net_diag.py ../data/site_labelled/chunk_0001.npz [--scale 1.0]

Uses the engine's own integer forward pass (the same code that plays), so what is measured is
what ships. Labels are White's view; the engine returns the side to move's view.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bini_board as B  # noqa: E402
import bini_engine as E  # noqa: E402
import bini_nnue as N  # noqa: E402

CHARS = ".PNBRQKpnbrqk"
VAL = {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}


def to_fen(row: np.ndarray, stm: int) -> str:
    ranks = []
    for r in range(7, -1, -1):
        s, empty = "", 0
        for f in range(8):
            c = int(row[r * 8 + f])
            if c == 0:
                empty += 1
            else:
                if empty:
                    s += str(empty); empty = 0
                s += CHARS[c]
        if empty:
            s += str(empty)
        ranks.append(s)
    return "/".join(ranks) + (" w" if stm == 0 else " b") + " - - 0 1"


def report(name: str, keys: np.ndarray, err: np.ndarray, signed: np.ndarray, labels=None) -> None:
    print(f"\n{name}")
    for k in sorted(set(keys.tolist())):
        m = keys == k
        lab = labels[k] if labels else k
        print(f"  {str(lab):>14}  n {m.sum():6d}  MAE {err[m].mean():6.1f}  bias {signed[m].mean():+6.1f}  |err|>200 {100 * (err[m] > 200).mean():4.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("chunk")
    ap.add_argument("--scale", type=float, default=1.0, help="multiply labels by this before comparing")
    ap.add_argument("--n", type=int, default=30000)
    a = ap.parse_args()
    z = np.load(a.chunk)
    n = min(a.n, len(z["cp"]))
    eng = E.Engine(use_nnue=True)
    assert eng.use_nnue
    E.warm_up(eng)
    pred = np.zeros(n, dtype=np.int64)
    for i in range(n):
        eng.set_position(to_fen(z["pieces"][i], int(z["stm"][i])), [])
        v = eng.static_eval()
        pred[i] = v if z["stm"][i] == 0 else -v  # to White's view
    lab = np.clip(z["cp"][:n].astype(np.float64) * a.scale, -1500, 1500)
    p = np.clip(pred.astype(np.float64), -1500, 1500)
    signed = p - lab
    err = np.abs(signed)
    m = np.abs(lab) <= 800
    slope = float(np.dot(p[m], lab[m]) / max(1.0, np.dot(lab[m], lab[m])))
    print(f"{n} positions: MAE {err.mean():.1f} cp, bias {signed.mean():+.1f}, corr {np.corrcoef(p, lab)[0, 1]:.3f}, |err|>200: {100 * (err > 200).mean():.1f}%, scale slope pred/label {slope:.3f} (search margins assume 1.0)")
    pieces = z["pieces"][:n]
    count = (pieces > 0).sum(axis=1)
    report("by piece count", np.minimum(7, (count - 1) * 8 // 32), err, signed, labels=[f"{4 * k + 1}-{4 * k + 4}" for k in range(8)])
    mat = np.zeros(n)
    for code, v in VAL.items():
        mat += v * ((pieces == code).sum(axis=1) - (pieces == code + 6).sum(axis=1))
    report("by material balance (White)", np.clip(np.round(mat / 2) * 2, -6, 6).astype(int), err, signed)
    report("by |label|", np.minimum(4, (np.abs(lab) // 150).astype(int)), err, signed, labels=["0-149", "150-299", "300-449", "450-599", "600+"])
    report("quiet (1) vs tactical (0)", z["quiet"][:n].astype(int), err, signed)
    # king bucket of the side to move
    kb = np.zeros(n, dtype=int)
    for i in range(n):
        code = 6 if z["stm"][i] == 0 else 12
        ksq = int(np.argmax(pieces[i] == code))
        if z["stm"][i] == 1:
            ksq ^= 56
        kb[i] = int(N.KB_TABLE[ksq]) >> 1
    report("by side-to-move king bucket", kb, err, signed)
    queens = ((pieces == 5).sum(axis=1) + (pieces == 11).sum(axis=1)) > 0
    report("queens on (1) / off (0)", queens.astype(int), err, signed)


if __name__ == "__main__":
    main()
