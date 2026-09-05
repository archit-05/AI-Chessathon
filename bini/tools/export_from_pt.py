"""Re-export a saved PyTorch checkpoint to nnue.safetensors with the current quantisation.

    python tools/export_from_pt.py ../data/nnue_v1.pt ../data/nnue_v1.safetensors --buckets 1 --hidden 256
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_nnue import NNUE, export  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pt")
    ap.add_argument("out")
    ap.add_argument("--buckets", type=int, default=8)
    ap.add_argument("--hidden", type=int, default=512)
    a = ap.parse_args()
    model = NNUE(a.buckets, a.hidden)
    model.load_state_dict(torch.load(a.pt, map_location="cpu"))
    export(model, Path(a.out))


if __name__ == "__main__":
    main()
