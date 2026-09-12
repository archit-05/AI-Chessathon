"""Endgame spice corpus from the site's Stockfish-16 depth-16 evaluations of archived games:
positions with --pmin..--pmax pieces and |cp| in [--lo, --hi] (White view), not in check, deduplicated by FEN,
written as trainer-convention npz shards (pieces uint8[N,64] codes 1..12, stm, cp WHITE view, result 0, quiet, depth)
plus a JSONL. usage: site_spice.py <games_dir> <out_prefix> [--pmin 12 --pmax 23 --lo 150 --hi 600 --max 300000]"""
import sys, json, io, argparse, random, collections
from pathlib import Path
import numpy as np, chess, chess.pgn
ap = argparse.ArgumentParser(); ap.add_argument('gdir'); ap.add_argument('out'); ap.add_argument('--pmin', type=int, default=12); ap.add_argument('--pmax', type=int, default=23); ap.add_argument('--lo', type=int, default=150); ap.add_argument('--hi', type=int, default=600); ap.add_argument('--max', type=int, default=300000)
a = ap.parse_args(); CODE = {('P', True): 1, ('N', True): 2, ('B', True): 3, ('R', True): 4, ('Q', True): 5, ('K', True): 6, ('P', False): 7, ('N', False): 8, ('B', False): 9, ('R', False): 10, ('Q', False): 11, ('K', False): 12}
seen = set(); rows = []; games = 0; depth_c = collections.Counter()
for f in sorted(Path(a.gdir).glob('*.json')):
    try: d = json.load(open(f))
    except Exception: continue
    ev = d.get('evals'); pgn = d.get('pgn')
    if not ev or not pgn or not ev.get('cp'): continue
    g = chess.pgn.read_game(io.StringIO(pgn))
    if g is None: continue
    games += 1; b = g.board(); cps = ev['cp']; best = ev.get('best') or []; dep = int(ev.get('depth') or 0); depth_c[dep] += 1
    for i, mv in enumerate(g.mainline_moves()):
        n = len(b.piece_map())
        if i < len(cps) and cps[i] is not None and a.pmin <= n <= a.pmax and a.lo <= abs(int(cps[i])) <= a.hi and not b.is_check():
            key = b.board_fen() + (' w' if b.turn else ' b')
            if key not in seen:
                seen.add(key); bm = None
                try: bm = chess.Move.from_uci(best[i]) if i < len(best) and best[i] else None
                except Exception: bm = None
                quiet = int(bm is not None and bm in b.legal_moves and not b.is_capture(bm) and bm.promotion is None)
                rows.append(dict(fen=b.fen(), cp_white=int(cps[i]), quiet=quiet, depth=dep, pieces=n))
        b.push(mv)
random.Random(21).shuffle(rows); rows = rows[:a.max]
n = len(rows); pieces = np.zeros((n, 64), np.uint8); stm = np.zeros(n, np.uint8); cp = np.zeros(n, np.int16); res = np.zeros(n, np.int8); quiet = np.zeros(n, np.uint8); depth = np.zeros(n, np.uint8)
with open(a.out + '.jsonl', 'w') as fo:
    for i, r in enumerate(rows):
        b = chess.Board(r['fen'])
        for sq, pc in b.piece_map().items(): pieces[i, sq] = CODE[(pc.symbol().upper(), pc.color)]
        stm[i] = 0 if b.turn else 1; cp[i] = max(-32000, min(32000, r['cp_white'])); quiet[i] = r['quiet']; depth[i] = r['depth']; fo.write(json.dumps(r) + '\n')
np.savez(a.out + '.npz', pieces=pieces, stm=stm, cp=cp, result=res, quiet=quiet, depth=depth)
pc_h = collections.Counter((r['pieces'] // 4) * 4 for r in rows); ab = collections.Counter(min(abs(r['cp_white']) // 100 * 100, 600) for r in rows)
print(json.dumps(dict(games=games, positions=n, label_depths=dict(depth_c), pieces_hist={str(k): v for k, v in sorted(pc_h.items())}, abs_cp_hist={str(k): v for k, v in sorted(ab.items())}, quiet_pct=round(100 * float(quiet.mean()), 1), out=a.out + '.npz')))
