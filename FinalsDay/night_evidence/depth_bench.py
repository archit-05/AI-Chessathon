"""Fixed-depth in-situ check: node counts must be identical across builds (same eval values), time differs.
usage: depth_bench.py <build_dir> <depth>"""
import os, sys, time, json
from pathlib import Path
ROOT = Path('/Users/architbhardwaj/Desktop/AI Chessathon')
if not ROOT.exists(): ROOT = Path.home() / 'chess'
build, D = Path(sys.argv[1]).resolve(), int(sys.argv[2])
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '22')
sys.path.insert(0, str(ROOT / 'astra_tests'))
from harness import Probe, S
p = Probe()
FENS = ["r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
        "r2q1rk1/ppp2ppp/2n1bn2/2b1p3/3pP3/2P2N1P/PP1N1PP1/R2QR1K1 b - - 0 11", "6k1/4Qpp1/p3p2p/qrNb4/7P/1PR2PP1/4P1K1/8 w - - 9 39", "r1bq1rk1/pp3pbp/2nppnp1/2p5/4P2P/2NP2P1/PPP1NPB1/R1BQ1RK1 w - - 0 9"]
tn = 0; tt = 0.0; rows = []
for f in FENS:
    p.setup(f, [], budget=3600); p.e.prev_score_valid = False
    t0 = time.perf_counter(); mv, sc, d = p.e.think(1e9, 1e9, max_depth=D, log=False); dt = time.perf_counter() - t0
    n = int(p.e.info[S.I_NODES]); tn += n; tt += dt; rows.append(dict(fen=f[:18], move=mv, score=int(sc), depth=int(d), nodes=n, secs=round(dt, 2)))
    print(json.dumps(rows[-1]), flush=True)
print(f"RESULT {build.name} depth={D} total_nodes={tn} secs={tt:.2f} knps={tn/tt/1000:.1f}", flush=True)
