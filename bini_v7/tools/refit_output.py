"""Last-layer refit (V5, 20:45): keep v3b's feature layer frozen and refit only the output layer
(w2, b2) on the tournament's own labelled positions (site_all train chunk) plus the elite
whole-game set, so the net is recalibrated to the distribution we play in without touching the
representation. Exports through the standard path (rescale to v3b's slope applied by the judge).

    python tools/refit_output.py --out ../data/nnue_v5r.safetensors --epochs 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_nnue import NNUE, Features, load_chunk, targets, export, CP_SCALE  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default="../data/nnue_v3b.pt")
    ap.add_argument("--data", nargs="+", default=["../data/site_all/chunk_0000.npz", "../data/elite_labelled/chunk_0000.npz", "../data/elite_labelled/chunk_0001.npz", "../data/elite_labelled/chunk_0002.npz"])
    ap.add_argument("--val", default="../data/site_labelled/chunk_0001.npz")
    ap.add_argument("--scale", type=float, default=1.0, help="label scale for the Stockfish-labelled sets (v3b used 1.0)")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--out", default="../data/nnue_v5r.safetensors")
    a = ap.parse_args()
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model = NNUE(8, 512, "crelu", 1, False).to(device)
    sd = torch.load(a.resume, map_location=device)
    if "out.weight" in sd:
        sd["w2"] = sd.pop("out.weight").reshape(1, -1); sd["b2"] = sd.pop("out.bias").reshape(1)
    model.load_state_dict(sd, strict=False)
    for p in model.ft.parameters(): p.requires_grad_(False)
    model.b1.requires_grad_(False)
    feats = Features(8, 1, device)
    opt = torch.optim.Adam([model.w2, model.b2], lr=a.lr)
    vp, vs, vc, _ = load_chunk(Path(a.val), True); vp, vs, vc = vp[:20000], vs[:20000], vc[:20000] * a.scale
    v_cp, v_t = targets(vs, vc, None, 1.0)
    with torch.no_grad(): vf = feats(torch.from_numpy(vp).to(device), torch.from_numpy(vs).to(device))
    def val(tag):
        model.eval()
        with torch.no_grad():
            out = model(*vf).cpu().numpy()
        print(f"{tag}: val MAE {np.mean(np.abs(np.clip(out, -1500, 1500) - v_cp)):.1f} cp", flush=True); model.train()
    val("start (v3b)")
    rng = np.random.default_rng(0)
    for ep in range(a.epochs):
        for path in a.data:
            pieces, stm, cp, _ = load_chunk(Path(path), True)
            cp = cp * a.scale
            _, tgt = targets(stm, cp, None, 1.0)
            perm = rng.permutation(len(cp))
            for b in range(len(cp) // 16384):
                idx = perm[b * 16384:(b + 1) * 16384]
                ft = feats(torch.from_numpy(pieces[idx]).to(device), torch.from_numpy(stm[idx]).to(device))
                pred = torch.sigmoid(model(*ft) / CP_SCALE)
                loss = torch.mean((pred - torch.from_numpy(tgt[idx]).to(device)) ** 2)
                opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
            if device.type == "mps": torch.mps.empty_cache()
        val(f"epoch {ep}")
    torch.save(model.state_dict(), Path(a.out).with_suffix(".pt"))
    export(model, Path(a.out), 1.0)


if __name__ == "__main__":
    main()
