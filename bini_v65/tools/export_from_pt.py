"""Re-export a trainer checkpoint (.pt) to nnue.safetensors, optionally with an output scale.

    python tools/export_from_pt.py ../data/nnue_v4a.pt ../data/nnue_v4a_s.safetensors \
        --buckets 8 --hidden 512 --act screlu --out-buckets 8 --factorise --out-scale 1.28
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
    ap.add_argument("--act", default="screlu")
    ap.add_argument("--out-buckets", type=int, default=8)
    ap.add_argument("--factorise", action="store_true")
    ap.add_argument("--out-scale", type=float, default=1.0)
    a = ap.parse_args()
    sd = torch.load(a.pt, map_location="cpu")
    if "out.weight" in sd:  # v2/v3 trainer checkpoint: one output named out.*
        sd["w2"] = sd.pop("out.weight").reshape(1, -1)
        sd["b2"] = sd.pop("out.bias").reshape(1)
        if a.out_buckets > 1:
            sd["w2"] = sd["w2"].repeat(a.out_buckets, 1)
            sd["b2"] = sd["b2"].repeat(a.out_buckets)
    model = NNUE(a.buckets, a.hidden, a.act, a.out_buckets, factorise=("fact.weight" in sd) or a.factorise)
    model.load_state_dict(sd)
    export(model, Path(a.out), a.out_scale)


if __name__ == "__main__":
    main()
