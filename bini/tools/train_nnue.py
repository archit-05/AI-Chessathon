"""Train the Bini NNUE and export int16 weights (see bini_nnue.py for the exact feature scheme).

    python tools/train_nnue.py --data ../data/lichess --out nnue.safetensors --buckets 8 --hidden 512

Two perspectives share the input layer; per perspective the own king square selects one of
--buckets king buckets plus a horizontal mirror (buckets=1 means the plain 768-feature net).
out_cp = CP_SCALE * (W2 . [relu1(acc_stm), relu1(acc_nstm)] + b2); loss = MSE(sigmoid(out/400),
sigmoid(cp/400)) on the side to move's view.

Quantisation: W1, b1 x QA=255 (clipped ReLU ceiling); W2 x QB*CP_SCALE with QB the largest power
of two that keeps int16 unsaturated; b2 = [bias x QA*QB*CP_SCALE, QA*QB] so the integer forward
pass (sum + b2[0]) // b2[1] is centipawns.
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

QA = 255
CP_SCALE = 400.0


def king_table(nb: int) -> np.ndarray:
    t = np.zeros(64, dtype=np.int64)
    if nb == 1:
        return t
    assert nb == 8
    for sq in range(64):
        r, f = divmod(sq, 8)
        mirror = 1 if f >= 4 else 0
        ff = f ^ 7 if mirror else f
        if r == 0:
            bucket = 0 if ff < 2 else 1
        elif r == 1:
            bucket = 2 if ff < 2 else 3
        elif r <= 3:
            bucket = 4 if ff < 2 else 5
        else:
            bucket = 6 if ff < 2 else 7
        t[sq] = bucket * 2 + mirror
    return t


def features_from_pieces(pieces: np.ndarray, stm: np.ndarray, kb: np.ndarray, nb: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (idx_stm, idx_nstm) int64 [N, 64]: one feature index per square, empty squares
    carry the padding index nb*768 (an all-zero embedding row), so no packing is needed."""
    n = pieces.shape[0]
    sq = np.broadcast_to(np.arange(64, dtype=np.int64), (n, 64))
    code = pieces.astype(np.int64)
    present = code > 0
    colour = (code > 6).astype(np.int64)
    ptype = code - 1 - colour * 6
    kw = np.argmax(code == 6, axis=1)
    kbk = np.argmax(code == 12, axis=1)
    pad = nb * 768
    views = []
    for persp in (0, 1):
        own = (colour == persp).astype(np.int64)
        kind = ptype * 2 + (1 - own)
        ksq = kw if persp == 0 else (kbk ^ 56)
        kid = kb[ksq]
        s = sq ^ 56 if persp == 1 else sq
        s = s ^ ((kid & 1) * 7)[:, None]
        idx = (kid >> 1)[:, None] * 768 + kind * 64 + s
        views.append(np.where(present, idx, pad))
    white_view, black_view = views
    stm_b = stm.astype(bool)[:, None]
    return np.where(stm_b, black_view, white_view), np.where(stm_b, white_view, black_view)


class NNUE(nn.Module):
    def __init__(self, nb: int, hidden: int) -> None:
        super().__init__()
        self.nb, self.hidden = nb, hidden
        n_in = nb * 768
        self.ft = nn.EmbeddingBag(n_in + 1, hidden, mode="sum", padding_idx=n_in)
        self.b1 = nn.Parameter(torch.zeros(hidden))
        self.out = nn.Linear(2 * hidden, 1)
        nn.init.normal_(self.ft.weight, std=0.02)
        with torch.no_grad():
            self.ft.weight[n_in].zero_()

    def forward(self, idx_stm: torch.Tensor, idx_nstm: torch.Tensor) -> torch.Tensor:
        a = torch.clamp(self.ft(idx_stm) + self.b1, 0.0, 1.0)
        b = torch.clamp(self.ft(idx_nstm) + self.b1, 0.0, 1.0)
        # output in centipawns; the linear layer works in units of CP_SCALE so Adam converges fast
        return self.out(torch.cat([a, b], dim=1)).squeeze(1) * CP_SCALE


def chunk_files(data_dir: Path) -> list[Path]:
    return sorted(data_dir.glob("chunk_*.npz"))


def load_chunk(path: Path, quiet_only: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    z = np.load(path)
    pieces, stm, cp = z["pieces"], z["stm"], z["cp"].astype(np.float32)
    if quiet_only and "quiet" in z.files:
        keep = z["quiet"] == 1
        pieces, stm, cp = pieces[keep], stm[keep], cp[keep]
    return pieces, stm, cp


def targets(stm: np.ndarray, cp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cp_stm = np.where(stm == 1, -cp, cp)
    cp_stm = np.clip(cp_stm, -1500, 1500)
    return cp_stm, (1.0 / (1.0 + np.exp(-cp_stm / CP_SCALE))).astype(np.float32)


def export(model: NNUE, path: Path) -> None:
    n_in = model.nb * 768
    w1 = model.ft.weight.detach().cpu().numpy()[:n_in]             # [nb*768, H]
    b1 = model.b1.detach().cpu().numpy()
    w2 = model.out.weight.detach().cpu().numpy()[0]                  # [2H]
    b2 = model.out.bias.detach().cpu().numpy()[0]
    q_w1 = np.clip(np.round(w1 * QA), -32767, 32767).astype(np.int16)
    q_b1 = np.round(b1 * QA).astype(np.int32)
    qb = 64
    while qb > 1 and np.abs(w2).max() * qb * CP_SCALE >= 32000:
        qb //= 2
    q_w2 = np.clip(np.round(w2 * qb * CP_SCALE), -32767, 32767).astype(np.int16)
    q_b2 = np.array([np.round(b2 * QA * qb * CP_SCALE), QA * qb], dtype=np.int32)
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
    header["__metadata__"] = {"arch": f"{model.nb}x768x{model.hidden}x2->1", "buckets": str(model.nb), "hidden": str(model.hidden), "qa": str(QA), "qb": str(qb), "cp_scale": str(CP_SCALE)}
    hjson = json.dumps(header).encode("utf-8")
    hjson += b" " * ((8 - len(hjson) % 8) % 8)
    with path.open("wb") as fh:
        fh.write(struct.pack("<Q", len(hjson)))
        fh.write(hjson)
        for b in blobs:
            fh.write(b)
    print(f"exported {path} ({path.stat().st_size / 1e6:.2f} MB); qb {qb} |w1|max {np.abs(w1).max():.3f} |w2|max {np.abs(w2).max():.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+", help="one or more chunk directories")
    ap.add_argument("--out", default="nnue.safetensors")
    ap.add_argument("--chunks", type=int, default=1000, help="max training chunks (1M positions each)")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--resume")
    ap.add_argument("--buckets", type=int, default=8)
    ap.add_argument("--quiet-only", action="store_true", help="train only on positions whose best move is quiet")
    ap.add_argument("--hidden", type=int, default=512)
    a = ap.parse_args()

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print("device", device, flush=True)
    files = [f for d in a.data for f in chunk_files(Path(d))]
    if len(files) < 2:
        raise SystemExit("need at least two chunks (one is held out for validation)")
    val_file, train_files = files[-1], files[:-1][: a.chunks]
    print(f"{len(train_files)} training chunks, validation chunk {val_file.name}", flush=True)

    vp, vs, vc = load_chunk(val_file, a.quiet_only)
    vp, vs, vc = vp[:200_000], vs[:200_000], vc[:200_000]
    v_cp, v_t = targets(vs, vc)
    kb = king_table(a.buckets)
    fs, fn = features_from_pieces(vp, vs, kb, a.buckets)
    v_fs, v_fn, v_tt = torch.from_numpy(fs).to(device), torch.from_numpy(fn).to(device), torch.from_numpy(v_t).to(device)

    model = NNUE(a.buckets, a.hidden).to(device)
    if a.resume:
        model.load_state_dict(torch.load(a.resume, map_location=device))
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    per_chunk = int((770_000 if a.quiet_only else 1_000_000) // a.batch)
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
            pieces, stm, cp = load_chunk(train_files[fi], a.quiet_only)
            _, tgt = targets(stm, cp)
            perm = rng.permutation(len(cp))
            for b in range(len(cp) // a.batch):
                idx = perm[b * a.batch : (b + 1) * a.batch]
                fs, fn = features_from_pieces(pieces[idx], stm[idx], kb, a.buckets)
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
