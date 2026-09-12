"""Net-vs-Stockfish calibration on real game positions: replay N site games (site evals = SF16 depth 16, White view),
compute our raw network score at every position, and report by |SF| band and by piece count: mean |net|, slope,
MAE, and the resolution-failure rate (|SF| >= 300 while |net| < 120).  usage: resolution_probe.py <build> <games_dir> <n_games> <out.json>"""
import os, sys, json, io, random, collections, statistics
from pathlib import Path
build, gdir, n_games, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
os.environ['BINI_DIR'] = str(build); os.environ.setdefault('BINI_TT_BITS', '16')
sys.path.insert(0, '/Users/architbhardwaj/Desktop/AI Chessathon/astra_tests')
from harness import Probe, B, N, S, chess
import chess.pgn
p = Probe(); files = sorted(gdir.glob('*.json')); random.Random(5).shuffle(files)
rows = []; used = 0
for f in files:
    if used >= n_games: break
    try: d = json.load(open(f))
    except Exception: continue
    ev = d.get('evals'); pgn = d.get('pgn')
    if not ev or not pgn or not ev.get('cp'): continue
    g = chess.pgn.read_game(io.StringIO(pgn))
    if g is None: continue
    b = g.board(); cps = ev['cp']; i = 0; used += 1
    for mv in g.mainline_moves():
        if i < len(cps) and cps[i] is not None and not b.is_check():
            p.setup(b.fen(), [], budget=1); raw = int(N.nnue_eval(p.e.bb, p.e.st, p.e.acc, p.e.w2, p.e.b2))
            net_w = raw if b.turn else -raw; sf = int(cps[i])
            if abs(sf) < 9000: rows.append((sf, net_w, len(b.piece_map()), b.fullmove_number))
        b.push(mv); i += 1
def band(x): a = abs(x); return '0-49' if a < 50 else '50-149' if a < 150 else '150-299' if a < 300 else '300-599' if a < 600 else '600-999' if a < 1000 else '1000+'
def summ(rs):
    if not rs: return None
    sf = [r[0] for r in rs]; nt = [r[1] for r in rs]
    mae = statistics.mean(abs(a - b) for a, b in zip(sf, nt)); slope = (sum(a * b for a, b in zip(sf, nt)) / max(1, sum(a * a for a in sf))) if any(sf) else 0
    return dict(n=len(rs), mean_abs_sf=round(statistics.mean(abs(x) for x in sf), 1), mean_abs_net=round(statistics.mean(abs(x) for x in nt), 1), slope_net_on_sf=round(slope, 3), mae=round(mae, 1), sign_disagree_pct=round(100 * sum((a > 0) != (b > 0) for a, b in zip(sf, nt) if abs(a) >= 100) / max(1, sum(abs(a) >= 100 for a in sf)), 1))
by_band = collections.defaultdict(list); by_pc = collections.defaultdict(list)
for r in rows: by_band[band(r[0])].append(r); by_pc[(r[2] // 6) * 6].append(r)
fail = [r for r in rows if abs(r[0]) >= 300 and abs(r[1]) < 120]; big = [r for r in rows if abs(r[0]) >= 300]
res = dict(build=build.name, games=used, positions=len(rows), overall=summ(rows), by_sf_band={k: summ(v) for k, v in sorted(by_band.items(), key=lambda kv: kv[1][0][0] if kv[1] else 0)}, by_piece_count={str(k): summ(v) for k, v in sorted(by_pc.items())},
           resolution_failures=dict(n=len(fail), of_positions_with_abs_sf_ge_300=len(big), rate_pct=round(100 * len(fail) / max(1, len(big)), 1), by_piece_count={str(k): sum(1 for r in fail if (r[2] // 6) * 6 == k) for k in sorted({(r[2] // 6) * 6 for r in fail})}))
json.dump(res, open(out, 'w'), indent=1); print(json.dumps(res, indent=1))
