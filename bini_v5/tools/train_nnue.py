"""Train the Bini NNUE and export int16 weights (see bini_nnue.py for the exact feature scheme).

    python tools/train_nnue.py --data ../data/lichessq ../data/lichessq2 --out nnue.safetensors \
        --buckets 8 --hidden 512 --act screlu --out-buckets 8 --factorise \
        --oversample ../data/site_labelled:10 --scale ../data/selfplay:1.3 --wdl 0.85 \
        --val ../data/site_labelled/chunk_0001.npz --val ../data/selfplay/chunk_w0_0000.npz

Two perspectives share the input layer; per perspective the own king square selects one of
--buckets king buckets plus a horizontal mirror (buckets=1 means the plain 768-feature net).
Activation: clipped ReLU, or squared clipped ReLU (--act screlu). Output: one linear layer per
output bucket (--out-buckets, by piece count), the side to move's accumulator first.
out_cp = CP_SCALE * (W2[b] . act(acc_stm), act(acc_nstm)] + b2[b]).
Loss: MSE between sigmoid(out/400) and a target that blends sigmoid(cp/400) with the game result
when a chunk carries one (--wdl lambda: 1.0 = labels only).
--factorise trains an extra un-bucketed 768-feature table whose rows are folded into every king
bucket at export (better generalisation per bucket; no inference change).
--scale DIR:k multiplies the labels of chunks under DIR by k (Stockfish 19 normalised
centipawns vs the Lichess database's classical scale; see tools/scale_fit.py).

Quantisation: W1, b1 x QA=255; W2 x QB*CP_SCALE with QB the largest power of two that keeps int16
unsaturated; b2 = [bias_b x QA^(1 or 2) x QB x CP_SCALE ..., QA^(1 or 2) x QB] so the integer
forward pass (sum + b2[b]) // b2[NO] is centipawns (QA^2 when the activation is squared).
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
    assert nb in (8, 16)
    for sq in range(64):
        r, f = divmod(sq, 8)
        mirror = 1 if f >= 4 else 0
        ff = f ^ 7 if mirror else f
        if nb == 8:
            if r == 0:
                bucket = 0 if ff < 2 else 1
            elif r == 1:
                bucket = 2 if ff < 2 else 3
            elif r <= 3:
                bucket = 4 if ff < 2 else 5
            else:
                bucket = 6 if ff < 2 else 7
        else:
            rr = r if r < 3 else 3
            bucket = rr * 4 + ff
        t[sq] = bucket * 2 + mirror
    return t


class Features:
    """Feature indices on the training device: (idx_stm, idx_nstm, idx_fact_stm, idx_fact_nstm, out_bucket)."""

    def __init__(self, nb: int, no: int, device: torch.device) -> None:
        self.nb, self.no, self.device = nb, no, device
        self.kb = torch.from_numpy(king_table(nb)).to(device)
        self.sq = torch.arange(64, dtype=torch.int64, device=device)[None, :]
        self.pad = nb * 768
        self.pad_f = 768

    def __call__(self, pieces: torch.Tensor, stm: torch.Tensor):
        code = pieces.to(torch.int64)
        present = code > 0
        colour = (code > 6).to(torch.int64)
        ptype = code - 1 - colour * 6
        kw = torch.argmax((code == 6).to(torch.int8), dim=1)
        kbk = torch.argmax((code == 12).to(torch.int8), dim=1) ^ 56
        views, facts = [], []
        for persp in (0, 1):
            own = (colour == persp).to(torch.int64)
            kind = ptype * 2 + (1 - own)
            ksq = kw if persp == 0 else kbk
            kid = self.kb[ksq]
            s = self.sq ^ 56 if persp == 1 else self.sq
            s = s ^ ((kid & 1) * 7)[:, None]
            local = kind * 64 + s
            idx = (kid >> 1)[:, None] * 768 + local
            views.append(torch.where(present, idx, self.pad))
            facts.append(torch.where(present, local, self.pad_f))
        stm_b = stm.to(torch.bool)[:, None]
        count = present.sum(dim=1)
        ob = torch.clamp((count - 1) * self.no // 32, max=self.no - 1) if self.no > 1 else torch.zeros_like(count)
        return (torch.where(stm_b, views[1], views[0]), torch.where(stm_b, views[0], views[1]),
                torch.where(stm_b, facts[1], facts[0]), torch.where(stm_b, facts[0], facts[1]), ob)


class NNUE(nn.Module):
    def __init__(self, nb: int, hidden: int, act: str = "crelu", no: int = 1, factorise: bool = False) -> None:
        super().__init__()
        self.nb, self.hidden, self.act, self.no, self.factorise = nb, hidden, act, no, factorise
        n_in = nb * 768
        self.ft = nn.EmbeddingBag(n_in + 1, hidden, mode="sum", padding_idx=n_in)
        self.b1 = nn.Parameter(torch.zeros(hidden))
        self.fact = nn.EmbeddingBag(768 + 1, hidden, mode="sum", padding_idx=768) if factorise else None
        self.w2 = nn.Parameter(torch.empty(no, 2 * hidden))
        self.b2 = nn.Parameter(torch.zeros(no))
        nn.init.normal_(self.ft.weight, std=0.02)
        nn.init.normal_(self.w2, std=0.02)
        with torch.no_grad():
            self.ft.weight[n_in].zero_()
            if self.fact is not None:
                self.fact.weight.zero_()

    def accum(self, idx: torch.Tensor, idx_f: torch.Tensor) -> torch.Tensor:
        a = self.ft(idx) + self.b1
        if self.fact is not None:
            a = a + self.fact(idx_f)
        a = torch.clamp(a, 0.0, 1.0)
        if self.act == "screlu":
            a = a * a
        return a

    def forward(self, idx_stm, idx_nstm, f_stm, f_nstm, ob) -> torch.Tensor:
        h = torch.cat([self.accum(idx_stm, f_stm), self.accum(idx_nstm, f_nstm)], dim=1)
        w = self.w2[ob]  # [B, 2H]
        return ((h * w).sum(dim=1) + self.b2[ob]) * CP_SCALE

    def folded_w1(self) -> np.ndarray:
        n_in = self.nb * 768
        w1 = self.ft.weight.detach().cpu().numpy()[:n_in].copy()
        if self.fact is not None:
            wf = self.fact.weight.detach().cpu().numpy()[:768]
            w1 = w1 + np.tile(wf, (self.nb, 1))
        return w1


def chunk_files(data_dir: Path, fmt: str = "npz") -> list[Path]:
    """--format npz: chunk_*.npz; --format bullet: *.bin (bulletformat ChessBoard records, tools/bulletformat.py)."""
    if fmt == "bullet":
        return sorted(data_dir.rglob("*.bin"))
    return sorted(data_dir.rglob("chunk_*.npz"))


def chunk_positions(path: Path) -> int:
    """Approximate position count of a chunk (used only to size the lr schedule)."""
    if path.suffix == ".bin":
        return path.stat().st_size // 32
    return 1_000_000


def load_chunk(path: Path, quiet_only: bool = False):
    if path.suffix == ".bin":  # bulletformat: bulletformat.read() hands back our npz convention (pieces/stm/cp/result/quiet)
        import bulletformat

        z = bulletformat.read(path)
    else:
        z = np.load(path)
    pieces, stm, cp = z["pieces"], z["stm"], z["cp"].astype(np.float32)
    res = z["result"].astype(np.float32) if "result" in z.files else None
    if quiet_only and "quiet" in z.files:
        keep = z["quiet"] == 1
        pieces, stm, cp = pieces[keep], stm[keep], cp[keep]
        res = res[keep] if res is not None else None
    return pieces, stm, cp, res


def targets(stm: np.ndarray, cp: np.ndarray, res, lam: float) -> tuple[np.ndarray, np.ndarray]:
    cp_stm = np.clip(np.where(stm == 1, -cp, cp), -1500, 1500)
    t = (1.0 / (1.0 + np.exp(-cp_stm / CP_SCALE))).astype(np.float32)
    if res is not None and lam < 1.0:
        wdl = (np.where(stm == 1, -res, res) + 1.0) / 2.0  # 1 win, 0.5 draw, 0 loss for the side to move
        t = (lam * t + (1.0 - lam) * wdl).astype(np.float32)
    return cp_stm, t


def export(model: NNUE, path: Path, out_scale: float = 1.0) -> None:
    """out_scale multiplies the network's centipawn output at export (weights and biases of the
    output layer), so a net whose scale differs from the one the search margins were tuned on
    (tools/net_diag.py reports the slope) can be brought back onto it without retraining."""
    w1 = model.folded_w1()                                              # [nb*768, H]
    b1 = model.b1.detach().cpu().numpy()
    w2 = model.w2.detach().cpu().numpy() * out_scale                    # [NO, 2H]
    b2 = model.b2.detach().cpu().numpy() * out_scale                    # [NO]
    q_w1 = np.clip(np.round(w1 * QA), -32767, 32767).astype(np.int16)
    q_b1 = np.round(b1 * QA).astype(np.int32)
    qb = 64
    while qb > 1 and np.abs(w2).max() * qb * CP_SCALE >= 32000:
        qb //= 2
    q_w2 = np.clip(np.round(w2 * qb * CP_SCALE), -32767, 32767).astype(np.int16)
    qa_act = QA * QA if model.act == "screlu" else QA
    q_b2 = np.concatenate([np.round(b2 * qa_act * qb * CP_SCALE), [qa_act * qb]]).astype(np.int32)
    tensors = {"w1": q_w1, "b1": q_b1, "w2": np.ascontiguousarray(q_w2), "b2": q_b2}
    dt = {np.dtype(np.int16): "I16", np.dtype(np.int32): "I32"}
    header = {}
    blobs = []
    off = 0
    for name, arr in tensors.items():
        raw = np.ascontiguousarray(arr).tobytes()
        header[name] = {"dtype": dt[arr.dtype], "shape": list(arr.shape), "data_offsets": [off, off + len(raw)]}
        blobs.append(raw)
        off += len(raw)
    header["__metadata__"] = {"arch": f"{model.nb}x768x{model.hidden}x2->{model.no}", "buckets": str(model.nb), "hidden": str(model.hidden), "act": model.act, "out_buckets": str(model.no), "qa": str(QA), "qb": str(qb), "cp_scale": str(CP_SCALE), "out_scale": str(out_scale)}
    hjson = json.dumps(header).encode("utf-8")
    hjson += b" " * ((8 - len(hjson) % 8) % 8)
    with path.open("wb") as fh:
        fh.write(struct.pack("<Q", len(hjson)))
        fh.write(hjson)
        for b in blobs:
            fh.write(b)
    print(f"exported {path} ({path.stat().st_size / 1e6:.2f} MB); qb {qb} |w1|max {np.abs(w1).max():.3f} |w2|max {np.abs(w2).max():.3f}", flush=True)


def scale_for(path: Path, scales: list[tuple[Path, float]]) -> float:
    for d, k in scales:
        if d in path.resolve().parents:
            return k
    return 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, nargs="+", help="one or more chunk directories")
    ap.add_argument("--out", default="nnue.safetensors")
    ap.add_argument("--chunks", type=int, default=100000, help="max training chunks")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch", type=int, default=16384)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--resume")
    ap.add_argument("--buckets", type=int, default=8)
    ap.add_argument("--hidden", type=int, default=512)
    ap.add_argument("--act", choices=["crelu", "screlu"], default="crelu")
    ap.add_argument("--out-buckets", type=int, default=1)
    ap.add_argument("--factorise", action="store_true")
    ap.add_argument("--quiet-only", action="store_true", help="train only on positions whose best move is quiet")
    ap.add_argument("--oversample", action="append", default=[], help="DIR:K — repeat the chunks of DIR K times per epoch")
    ap.add_argument("--scale", action="append", default=[], help="DIR:k — multiply the labels of chunks under DIR by k")
    ap.add_argument("--wdl", type=float, default=1.0, help="label weight lambda; 1-lambda goes to the game result where known")
    ap.add_argument("--wdl-dir", action="append", default=[], help="DIR:lambda — result blend for chunks under DIR only (others use --wdl)")
    ap.add_argument("--val", action="append", default=[], help="held-out chunk(s); default: the last chunk of --data")
    ap.add_argument("--val-n", type=int, default=200_000)
    ap.add_argument("--pc-weight", type=float, default=0.0, help="loss weight 1 + w*(24-pieces)/24 below 24 pieces (endgames count more)")
    ap.add_argument("--out-scale", type=float, default=1.0, help="multiply the exported output by this (scale matching, see net_diag slope)")
    ap.add_argument("--max-chunks", action="append", default=[], help="DIR:N — use at most N chunks from DIR (caps a large source)")
    ap.add_argument("--thin-flat", action="append", default=[], help="DIR:keep:thresh — keep only this fraction of DIR's positions with |cp| < thresh (self-play is 70% drawn, median 32 cp; unthinned it teaches 'everything is level')")
    ap.add_argument("--format", choices=["npz", "bullet"], default="npz", help="chunk format under --data/--oversample/--val: chunk_*.npz or bulletformat *.bin (tools/bulletformat.py)")
    a = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    print("device", device, flush=True)
    scales = []
    for s in a.scale:
        d, k = s.rsplit(":", 1)
        scales.append((Path(d).resolve(), float(k)))
    wdl_dirs = []
    for spec in a.wdl_dir:
        d, lam = spec.rsplit(":", 1)
        wdl_dirs.append((Path(d).resolve(), float(lam)))
    thins = []
    for s in a.thin_flat:
        d, keep, thr = s.split(":")
        thins.append((Path(d).resolve(), float(keep), float(thr)))
    caps = {}
    for spec in a.max_chunks:
        cd, n = spec.rsplit(":", 1)
        caps[Path(cd).resolve()] = int(n)
    files = []
    for d in a.data:
        fs = chunk_files(Path(d), a.format)
        if Path(d).resolve() in caps:
            fs = fs[: caps[Path(d).resolve()]]
        files.extend(fs)
    if a.val:
        val_files = [Path(v) for v in a.val]
        train_files = [f for f in files if f.resolve() not in {v.resolve() for v in val_files}][: a.chunks]
    else:
        val_files, train_files = [files[-1]], files[:-1][: a.chunks]
    for s in a.oversample:
        odir, k = s.rsplit(":", 1)
        extra = [f for f in chunk_files(Path(odir), a.format) if f.resolve() not in {v.resolve() for v in val_files}]
        already = 1 if Path(odir).resolve() in [Path(d).resolve() for d in a.data] else 0
        train_files = train_files + extra * (int(k) - already)
        print(f"oversampling {len(extra)} chunks from {odir} x{k}", flush=True)
    print(f"{len(train_files)} training chunks, validation {[v.name for v in val_files]}", flush=True)

    feats = Features(a.buckets, a.out_buckets, device)
    vals = []
    for vf in val_files:
        vp, vs, vc, vr = load_chunk(vf, a.quiet_only)
        vp, vs, vc = vp[: a.val_n], vs[: a.val_n], vc[: a.val_n] * scale_for(vf, scales)
        v_cp, v_t = targets(vs, vc, None, 1.0)
        with torch.no_grad():
            vf_t = feats(torch.from_numpy(vp).to(device), torch.from_numpy(vs).to(device))
        vals.append((vf.parent.name + "/" + vf.name, vf_t, torch.from_numpy(v_t).to(device), v_cp))

    model = NNUE(a.buckets, a.hidden, a.act, a.out_buckets, a.factorise).to(device)
    if a.resume:
        sd = torch.load(a.resume, map_location=device)
        if "out.weight" in sd:  # v2/v3 trainer checkpoint: one output, named out.*
            sd["w2"] = sd.pop("out.weight").reshape(1, -1)
            sd["b2"] = sd.pop("out.bias").reshape(1)
            if a.out_buckets > 1:  # start every bucket from the single old output
                sd["w2"] = sd["w2"].repeat(a.out_buckets, 1)
                sd["b2"] = sd["b2"].repeat(a.out_buckets)
        missing = model.load_state_dict(sd, strict=False)
        print("resumed", a.resume, "missing", missing.missing_keys, "unexpected", missing.unexpected_keys, flush=True)
    opt = torch.optim.Adam(model.parameters(), lr=a.lr)
    quiet_frac = 0.77 if a.quiet_only else 1.0
    total_steps = int(sum(chunk_positions(f) * quiet_frac // a.batch for f in train_files)) * a.epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=total_steps + 10, pct_start=0.03)
    rng = np.random.default_rng(0)

    def validate(tag: str) -> None:
        model.eval()
        with torch.no_grad():
            for name, vf_t, v_tt, v_cp in vals:
                out_cp = model(*vf_t)
                vloss = torch.mean((torch.sigmoid(out_cp / CP_SCALE) - v_tt) ** 2).item()
                mae = float(np.mean(np.abs(np.clip(out_cp.cpu().numpy(), -1500, 1500) - v_cp)))
                print(f"{tag} val {name}: loss {vloss:.5f} MAE {mae:.0f}cp", flush=True)
        model.train()

    validate("start")
    step = 0
    for epoch in range(a.epochs):
        model.train()
        order = rng.permutation(len(train_files))
        t0 = time.perf_counter()
        tot, cnt = 0.0, 0
        for ci, fi in enumerate(order):
            path = train_files[fi]
            pieces, stm, cp, res = load_chunk(path, a.quiet_only)
            for td, keep, thr in thins:
                if td in path.resolve().parents:
                    flat = np.abs(cp) < thr
                    drop = flat & (rng.random(len(cp)) > keep)
                    pieces, stm, cp = pieces[~drop], stm[~drop], cp[~drop]
                    res = res[~drop] if res is not None else None
            cp = cp * scale_for(path, scales)
            lam = a.wdl
            for wd, wl in wdl_dirs:
                if wd in path.resolve().parents:
                    lam = wl
            _, tgt = targets(stm, cp, res, lam)
            perm = rng.permutation(len(cp))
            nb = max(1, len(cp) // a.batch)
            for b in range(nb):
                idx = perm[b * a.batch : (b + 1) * a.batch]
                ft = feats(torch.from_numpy(pieces[idx]).to(device), torch.from_numpy(stm[idx]).to(device))
                tt = torch.from_numpy(tgt[idx]).to(device)
                pred = torch.sigmoid(model(*ft) / CP_SCALE)
                if a.pc_weight > 0.0:
                    npc = (ft[0] != feats.pad).sum(dim=1).to(torch.float32)
                    w = 1.0 + a.pc_weight * torch.clamp((24.0 - npc) / 24.0, min=0.0)
                    loss = torch.sum(w * (pred - tt) ** 2) / torch.sum(w)
                else:
                    loss = torch.mean((pred - tt) ** 2)
                opt.zero_grad(set_to_none=True)
                loss.backward()
                opt.step()
                if step < total_steps:
                    sched.step()
                step += 1
                tot += loss.item()
                cnt += 1
            if device.type == "mps":
                torch.mps.empty_cache()  # the caching allocator otherwise pins GBs of wired memory on an 8 GB Mac
            if ci % 10 == 0:
                print(f"epoch {epoch} chunk {ci + 1}/{len(train_files)} loss {tot / max(cnt, 1):.5f} {time.perf_counter() - t0:.0f}s", flush=True)
        print(f"epoch {epoch} done: train {tot / max(cnt, 1):.5f}  {time.perf_counter() - t0:.0f}s", flush=True)
        validate(f"epoch {epoch}")
        torch.save(model.state_dict(), Path(a.out).with_suffix(".pt"))
        export(model, Path(a.out), a.out_scale)


if __name__ == "__main__":
    main()
