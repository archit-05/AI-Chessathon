"""Gate 4b: the PyTorch model (trainer feature scheme, float) and the numba engine (quantised
weights, incremental accumulators) agree on random positions to within quantisation error.

    BINI_NNUE=<file>.safetensors python tests/test_train_consistency.py <file>.pt

Architecture (king buckets, hidden size, activation, output buckets, factoriser) is read from
the weights file's metadata and the state dict, so the same test covers every trainer variant.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import chess  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

import bini_engine as E  # noqa: E402
import bini_nnue as N  # noqa: E402
from train_nnue import NNUE, Features  # noqa: E402

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pt")
    a = ap.parse_args()
    assert N.LOADED
    sd = torch.load(a.pt, map_location="cpu")
    act = "screlu" if N.ACT_SQ else "crelu"
    model = NNUE(N.NB, N.HIDDEN, act, N.NO, factorise="fact.weight" in sd)
    model.load_state_dict(sd)
    model.eval()
    feats = Features(N.NB, N.NO, torch.device("cpu"))
    eng = E.Engine(use_nnue=True)
    E.warm_up(eng)
    rng = random.Random(21)
    diffs = []
    for _ in range(300):
        board = chess.Board()
        for _ in range(rng.randint(0, 80)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if board.is_game_over() or (not board.pieces(chess.PAWN, chess.WHITE) and not board.pieces(chess.PAWN, chess.BLACK)):
            continue  # pawnless positions are scaled by the engine on purpose
        pieces = np.zeros((1, 64), dtype=np.uint8)
        for sq, pc in board.piece_map().items():
            pieces[0, sq] = CODES[pc.symbol()]
        stm = np.array([0 if board.turn else 1], dtype=np.uint8)
        with torch.no_grad():
            f = float(model(*feats(torch.from_numpy(pieces), torch.from_numpy(stm)))[0])
        eng.set_position(board.fen(), [])
        q = eng.static_eval()
        diffs.append(abs(f - q))
    diffs = np.array(diffs)
    print(f"{len(diffs)} positions: mean |float - int| {diffs.mean():.2f}cp, max {diffs.max():.1f}cp")
    assert diffs.max() < 12 and diffs.mean() < 3, "trainer and engine disagree beyond quantisation error"
    print("trainer/engine consistency ok")


if __name__ == "__main__":
    main()
