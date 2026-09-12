"""Does the compression survive search? For real positions with 12-23 pieces and |SF16 d16| in [150, 900],
compare our engine's fixed-node search score (side-to-move -> White view) with the label, by piece band.
usage: search_resolution.py <build> <games_dir> <n_positions> <nodes> <out.json>"""
import os, sys, json, io, random, collections, statistics
from pathlib import Path
build, gdir, npos, nodes, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '20')
sys.path.insert(0, '/Users/architbhardwaj/Desktop/AI Chessathon/astra_tests')
from harness import Probe, B, N, S, chess
import chess.pgn
p = Probe(); files = sorted(gdir.glob('*.json')); random.Random(11).shuffle(files); cands = []
for f in files:
    if len(cands) >= npos * 3: break
    try: d = json.load(open(f))
    except Exception: continue
    ev = d.get('evals'); pgn = d.get('pgn')
    if not ev or not pgn or not ev.get('cp'): continue
    g = chess.pgn.read_game(io.StringIO(pgn))
    if g is None: continue
    b = g.board(); cps = ev['cp']
    for i, mv in enumerate(g.mainline_moves()):
        n = len(b.piece_map())
        if i < len(cps) and cps[i] is not None and 12 <= n <= 23 and 150 <= abs(int(cps[i])) <= 900 and not b.is_check(): cands.append((b.fen(), int(cps[i]), n))
        b.push(mv)
random.Random(12).shuffle(cands); cands = cands[:npos]; rows = []
for k, (fen, sf, n) in enumerate(cands):
    p.setup(fen, [], budget=600); p.e.prev_score_valid = False; b = chess.Board(fen)
    raw = int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2)); mv, sc, d = p.e.think(1e9, 1e9, max_nodes=nodes, log=False)
    net_w = raw if b.turn else -raw; sr_w = int(sc) if b.turn else -int(sc); rows.append((sf, net_w, sr_w, n, int(d)))
    if k % 100 == 0: print(f"  {k}/{len(cands)}", flush=True)
def summ(rs, idx):
    sf = [r[0] for r in rs]; x = [r[idx] for r in rs]
    return dict(n=len(rs), slope=round(sum(a * b for a, b in zip(sf, x)) / max(1, sum(a * a for a in sf)), 3), mae=round(statistics.mean(abs(a - b) for a, b in zip(sf, x)), 1), under_120_pct=round(100 * sum(abs(v) < 120 for v in x) / max(1, len(x)), 1))
res = dict(build=build.name, nodes=nodes, positions=len(rows), mean_depth=round(statistics.mean(r[4] for r in rows), 1), overall=dict(static=summ(rows, 1), search=summ(rows, 2)), by_pieces={})
for lo, hi in ((12, 14), (15, 17), (18, 20), (21, 23)):
    rs = [r for r in rows if lo <= r[3] <= hi]
    if rs: res['by_pieces'][f'{lo}-{hi}'] = dict(static=summ(rs, 1), search=summ(rs, 2))
json.dump(res, open(out, 'w'), indent=1); print(json.dumps(res, indent=1))
