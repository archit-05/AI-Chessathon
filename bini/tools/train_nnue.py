"""Train the Bini NNUE (768 -> 2x256 -> 1) on Lichess-evaluated positions and export int16 weights.

    python tools/train_nnue.py --data ../data/lichess --out nnue.safetensors --epochs 6

Architecture (must match bini_nnue.py):
  two perspectives share W1 (768 x H) and b1; hidden = clipped_relu(acc) in [0, 1];
  out_cp = CP_SCALE * (W2_stm . hidden_stm + W2_nstm . hidden_nstm + b2), centipawns for the side
  to move; loss = MSE(sigmoid(out_cp/400), sigmoid(cp/400)).

Quantisation: W1, b1 scaled by QA=255 (clipped relu ceiling); W2 by QB*CP_SCALE; b2 by
QA*QB*CP_SCALE. The integer forward pass (sum + b2) // (QA*QB) is then centipawns.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

H = 256
QA = 255
QB = 32
CP_SCALE = 400.0


def features_from_pieces(pieces: np.ndarray, stm: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (idx_stm, idx_nstm) int64 [N, 32] padded with 768 (an all-zero embedding row)."""
    n = pieces.shape[0]
    sq = np.broadcast_to(np.arange(64, dtype=np.int64), (n, 64))
    code = pieces.astype(np.int64)
    present = code > 0
    colour = (code > 6).astype(np.int64)          # 0 white, 1 black
    ptype = code - 1 - colour * 6                   # 0..5
    out = []
    for persp in (0, 1):
        # perspective: 0 = white's view, 1 = black's view
        own = (colour == persp).astype(np.int64)
        kind = ptype * 2 + (1 - own)
        s = np.where(persp == 1, sq ^ 56, sq)
        idx = kind * 64 + s
        idx = np.where(present, idx, 768)
        # pack the present ones first (stable), pad with 768
        order = np.argsort(~present, axis=1, kind="stable")
        packed = np.take_along_axis(idx, order, axis=1)[:, :32]
        out.append(packed)
    white_view, black_view = out
    stm_b = stm.astype(bool)[:, None]
    idx_stm = np.where(stm_b, black_view, white_view)
    idx_nstm = np.where(stm_b, white_view, black_view)
    return idx_stm, idx_nstm


class NNUE(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.ft = nn.EmbeddingBag(769, H, mode="sum", padding_idx=768)
        self.b1 = nn.Parameter(torch.zeros(H))
        self.out = nn.Linear(2 * H, 1)
        nn.init.normal_(self.ft.weight, std=0.02)
        with torch.no_grad():
            self.ft.weight[768].zero_()

    def forward(self, idx_stm: torch.Tensor, idx_nstm: torch.Tensor) -> torch.Tensor:
        a = torch.clamp(self.ft(idx_stm) + self.b1, 0.0, 1.0)
        b = torch.clamp(self.ft(idx_nstm) + self.b1, 0.0, 1.0)
        # output in centipawns; the linear layer works in units of CP_SCALE so Adam converges fast
        return self.out(torch.cat([a, b], dim=1)).squeeze(1) * CP_SCALE


def chunk_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("chunk_*.npz"))


def load_chunk(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path)
    return z["pieces"], z["stm"], z["cp"].astype(np.float32)


def targets(stm: np.ndarray, cp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cp_stm = np.where(stm == 1, -cp, cp)
    cp_stm = np.clip(cp_stm, -1500, 1500)
    return cp_stm, (1.0 / (1.0 + np.exp(-cp_stm / CP_SCALE))).astype(np.float32)


def export(model: NNUE, path: Path) -> None:
    w1 = model.ft.weight.detach().cpu().numpy()[:768]              # [768, H]
    b1 = model.b1.detach().cpu().numpy()
    w2 = model.out.weight.detach().cpu().numpy()[0]                  # [2H]
    b2 = model.out.bias.detach().cpu().numpy()[0]
    q_w1 = np.clip(np.round(w1 * QA), -32767, 32767).astype(np.int16)
    q_b1 = np.round(b1 * QA).astype(np.int32)
    assert np.abs(w2).max() * QB * CP_SCALE < 32767, "output weights would saturate int16; lower QB"
    q_w2 = np.clip(np.round(w2 * QB * CP_SCALE), -32767, 32767).astype(np.int16)
    q_b2 = np.array([np.round(b2 * QA * QB * CP_SCALE)], dtype=np.int32)
    tensors = {"w1": q_w1, "b1": q_b1, "w2": q_w2, "b2": q_b2}
    dt = {np.dtype(np.int16): "I16", np.dtype(np.int32): "I32"}
    header = {}
    blobs = []
    off = 0
    for name, arr in tensors.items():
        raw = np.ascontiguousarray(arr).tobytes()
        header[name] = {"dtype": dt[arr.dtype], "shape": list(arr.shape), "data_offsets": [off, off + len(raw)]}
        blobs.append(raw)
        off += len(raw)
    header["__metadata__"] = {"arch": f"768x{H}x2->1", "qa": str(QA), "qb": str(QB), "cp_scale": str(CP_SCALE)}
    hjson = json.dumps(header).encode("utf-8")
    hjson += b" " * ((8 - len(hjson) % 8) % 8)
    with path.open("wb") as fh:
        fh.write(struct.pack("<Q", len(hjson)))
        fh.write(hjson)
        for b in blobs:
            fh.write(b)
    print(f"exported {path} ({path.stat().st_size / 1e6:.2f} MB); |w1|max {np.abs(w1).max():.3f} |w2|max {np.abs(w2).max():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="nnue.safetensors")
    ap.add_argument("--chunks", type=int, default=1000, help="max training chunks (1M positions each)")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--resume")
    a = ap.parse_args()

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("device", device, flush=True)
    files = chunk_files(Path(a.data))
    if len(files) < 2:
        raise SystemExit("need at least two chunks (one is held out for validation)")
    val_file, train_files = files[-1], files[:-1][: a.chunks]
    print(f"{len(train_files)} training chunks, validation chunk {val_file.name}", flush=True)

    vp, vs, vc = load_chunk(val_file)
    vp, vs, vc = vp[:200_000], vs[:200_000], vc[:200_000]
    v_cp, v_t = targets(vs, vc)
    fs, fn = features_from_pieces(vp, vs)
    v_fs, v_fn, v_tt = torch.from_numpy(fs).to(device), torch.from_numpy(fn).to(device), torch.from_numpy(v_t).to(device)

    model = NNUE().to(device)
    if a.resume:
        model.load_state_dict(torch.load(a.resume, map_location=device))
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    per_chunk = 1_000_000 // a.batch
    total_steps = per_chunk * len(train_files) * a.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=total_steps + 10, pct_start=0.03)
    rng = np.random.default_rng(0)

    step = 0
    for epoch in range(a.epochs):
        model.train()
        order = rng.permutation(len(train_files))
        t0 = time.perf_counter()
        tot, cnt = 0.0, 0
        for ci, fi in enumerate(order):
            pieces, stm, cp = load_chunk(train_files[fi])
            _, tgt = targets(stm, cp)
            perm = rng.permutation(len(cp))
            for b in range(len(cp) // a.batch):
                idx = perm[b * a.batch : (b + 1) * a.batch]
                fs, fn = features_from_pieces(pieces[idx], stm[idx])
                fs_t = torch.from_numpy(fs).to(device)
                fn_t = torch.from_numpy(fn).to(device)
                tt = torch.from_numpy(tgt[idx]).to(device)
                pred = torch.sigmoid(model(fs_t, fn_t) / CP_SCALE)
                loss = torch.mean((pred - tt) ** 2)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                opt.step()
                if step < total_steps:
                    sched.step()
                step += 1
                tot += loss.item()
                cnt += 1
            if ci % 5 == 0:
                print(f"epoch {epoch} chunk {ci + 1}/{len(train_files)} loss {tot / max(cnt, 1):.5f} {time.perf_counter() - t0:.0f}s", flush=True)
        model.eval()
        with torch.no_grad():
            out_cp = model(v_fs, v_fn)
            vloss = torch.mean((torch.sigmoid(out_cp / CP_SCALE) - v_tt) ** 2).item()
            mae = float(np.mean(np.abs(np.clip(out_cp.cpu().numpy(), -1500, 1500) - v_cp)))
        print(f"epoch {epoch} done: train {tot / max(cnt, 1):.5f} val {vloss:.5f} val MAE {mae:.0f}cp  {time.perf_counter() - t0:.0f}s", flush=True)
        torch.save(model.state_dict(), Path(a.out).with_suffix(".pt"))
        export(model, Path(a.out))


if __name__ == "__main__":
    main()
