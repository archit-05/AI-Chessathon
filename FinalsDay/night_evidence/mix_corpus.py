"""Concatenate + shuffle bulletformat corpora with a spice cap, profile, refuse if |cp|>800 > 4.5 %.
usage: mix_corpus.py out.bin --base base.bin [--spice file.bin:pct ...] [--seed 1]"""
import sys, argparse, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path.home() / 'chess' / 'bini_v7' / 'tools')); import bulletformat as bf
ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('--base', required=True); ap.add_argument('--spice', action='append', default=[]); ap.add_argument('--seed', type=int, default=1)
a = ap.parse_args(); rng = np.random.default_rng(a.seed)
base = np.fromfile(a.base, dtype=bf.DTYPE); parts = [base]; n_base = len(base); report = [f"base {a.base}: {n_base:,} rows"]
for s in a.spice:
    path, pct = s.rsplit(':', 1); pct = float(pct); arr = np.fromfile(path, dtype=bf.DTYPE)
    want = int(n_base * pct / (100 - pct)); take = min(want, len(arr))
    if take < len(arr): arr = arr[rng.permutation(len(arr))[:take]]
    reps = max(1, want // max(1, len(arr))) if want > len(arr) else 1
    for _ in range(reps): parts.append(arr)
    report.append(f"spice {path}: {len(arr):,} rows x{reps} (target {pct}% = {want:,})")
mix = np.concatenate(parts); mix = mix[rng.permutation(len(mix))]; hi = float(np.mean(np.abs(mix['score']) > 800))
print('\n'.join(report)); print(f"mix: {len(mix):,} rows, |cp|>800 {hi*100:.2f}%, mean|cp| {float(np.mean(np.abs(mix['score']))):.1f}")
if hi > 0.045: print('REFUSED: |cp|>800 above 4.5%'); sys.exit(1)
mix.tofile(a.out); print('wrote', a.out)
