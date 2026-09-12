"""NNUE output-layer microbenchmark + bit-identity check for one build.
usage: microbench.py <build_dir> [positions=600] [reps=300]
Generates positions by random legal play (accumulators filled by the real incremental update),
checks nnue_eval (selected variant) == nnue_eval_v0 on every one, then times both in a jitted loop."""
import os, sys, time, random
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
if not ROOT.exists(): ROOT = Path.home() / 'chess'
build = Path(sys.argv[1]).resolve(); NPOS = int(sys.argv[2]) if len(sys.argv) > 2 else 600; REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 300
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '16')
sys.path.insert(0, str(ROOT / 'astra_tests'))
import numpy as np
from numba import njit
from harness import Probe, B, N, S, chess
nnue_eval_v0 = N.nnue_eval_v0; nnue_eval_sel = N.nnue_eval
print(f"build={build.name} variant={N.EVAL_VARIANT} HIDDEN={N.HIDDEN} NO={N.NO} ACT_SQ={N.ACT_SQ} ACC_DTYPE={N.ACC_DTYPE.__name__} |w2|max={int(np.abs(N.W2).max())}", flush=True)
p = Probe(); rng = random.Random(7)
STARTS = ["rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
          "6k1/4Qpp1/p3p2p/qrNb4/7P/1PR2PP1/4P1K1/8 w - - 9 39", "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"]
bbs, sts, accs = [], [], []
while len(bbs) < NPOS:
    fen = rng.choice(STARTS); board = p.setup(fen, [], budget=60); b = chess.Board(fen); depth = 0
    for k in range(rng.randint(0, 30)):
        moves = list(b.legal_moves)
        if not moves: break
        m = rng.choice(moves); p.push(m.uci()); b.push(m); depth += 1
        if k % 3 == 0:
            e = p.e; ply = int(e.st[B.S_PLY]); st = e.st.copy(); st[B.S_PLY] = 0
            bbs.append(e.bb.copy()); sts.append(st); accs.append(e.acc[ply:ply + 1].copy())
    for _ in range(depth): p.pop()
bbs = np.stack(bbs[:NPOS]); sts = np.stack(sts[:NPOS]); accs = np.stack(accs[:NPOS])
w2, b2 = N.W2, N.B2
@njit(cache=False)
def loop_v0(bbs, sts, accs, w2, b2, reps):
    t = np.int64(0)
    for r in range(reps):
        for i in range(bbs.shape[0]):
            t += nnue_eval_v0(bbs[i], sts[i], accs[i], w2, b2)
    return t
@njit(cache=False)
def loop_sel(bbs, sts, accs, w2, b2, reps):
    t = np.int64(0)
    for r in range(reps):
        for i in range(bbs.shape[0]):
            t += nnue_eval_sel(bbs[i], sts[i], accs[i], w2, b2)
    return t
mism = 0
for i in range(NPOS):
    a = int(nnue_eval_v0(bbs[i], sts[i], accs[i], w2, b2)); c = int(nnue_eval_sel(bbs[i], sts[i], accs[i], w2, b2))
    if a != c: mism += 1
print(f"identity check on {NPOS} positions: mismatches={mism}", flush=True)
loop_v0(bbs, sts, accs, w2, b2, 1); loop_sel(bbs, sts, accs, w2, b2, 1)
res = {}
for name, fn in (('v0', loop_v0), ('sel', loop_sel), ('v0', loop_v0), ('sel', loop_sel)):
    t0 = time.perf_counter(); s = fn(bbs, sts, accs, w2, b2, REPS); dt = time.perf_counter() - t0
    ns = dt / (REPS * NPOS) * 1e9; res.setdefault(name, []).append(ns)
    print(f"  {name:3s} {ns:7.1f} ns/eval  (checksum {int(s)})", flush=True)
v0 = min(res['v0']); sel = min(res['sel']); print(f"RESULT {build.name} variant={N.EVAL_VARIANT}: v0 {v0:.0f} ns, selected {sel:.0f} ns, speedup x{v0/sel:.2f}, mismatches={mism}", flush=True)
