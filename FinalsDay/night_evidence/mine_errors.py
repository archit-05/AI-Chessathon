"""Mine decision errors from our own games: positions where the move played loses >= --loss cp against
Stockfish's best at a screening depth. Output JSONL: fen, played, best, cp_best, cp_played (side-to-move
view) for deep relabelling of both continuations.
usage: mine_errors.py out.jsonl --stockfish PATH --workers N --depth 14 --loss 100 --player NAME|both pgn1 [pgn2 ...]
--player both: every move of every game is ours (self-play gates)."""
import argparse, json, sys, time, io
from pathlib import Path
from multiprocessing import Pool
import chess, chess.pgn, chess.engine
def scan(args):
    pgn_text, a = args
    sf = chess.engine.SimpleEngine.popen_uci(a.stockfish); sf.configure({'Threads': 1, 'Hash': 64}); out = []
    try:
        g = chess.pgn.read_game(io.StringIO(pgn_text))
        if g is None: return out
        ours = {'both': (True, True)}.get(a.player, (g.headers.get('White') == a.player, g.headers.get('Black') == a.player))
        b = g.board()
        for mv in g.mainline_moves():
            if (b.turn and ours[0]) or ((not b.turn) and ours[1]):
                if b.fullmove_number >= 6 and not b.is_game_over() and len(b.piece_map()) >= 8:
                    best = sf.analyse(b, chess.engine.Limit(depth=a.depth)); bs = best['score'].pov(b.turn).score(mate_score=30000); bpv = best.get('pv') or []
                    if bpv and bpv[0] != mv and bs is not None and abs(bs) < 1500:
                        pl = sf.analyse(b, chess.engine.Limit(depth=a.depth), root_moves=[mv]); ps = pl['score'].pov(b.turn).score(mate_score=30000)
                        if ps is not None and bs - ps >= a.loss:
                            out.append(dict(fen=b.fen(), played=mv.uci(), best=bpv[0].uci(), cp_best=int(bs), cp_played=int(ps), loss=int(bs - ps), game=g.headers.get('Round', ''), white=g.headers.get('White'), black=g.headers.get('Black')))
            b.push(mv)
    finally: sf.quit()
    return out
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('pgns', nargs='+'); ap.add_argument('--stockfish', required=True); ap.add_argument('--workers', type=int, default=4); ap.add_argument('--depth', type=int, default=14); ap.add_argument('--loss', type=int, default=100); ap.add_argument('--player', default='both'); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(); games = []
    for p in a.pgns:
        txt = Path(p).read_text(); parts = [x for x in txt.split('\n\n[Event') if x.strip()]
        for i, x in enumerate(parts): games.append(x if x.lstrip().startswith('[Event') else '[Event' + x)
    if a.limit: games = games[:a.limit]
    print(f"{len(games)} games, depth {a.depth}, loss >= {a.loss}, player {a.player}", flush=True)
    t0 = time.perf_counter(); n = 0
    with Pool(a.workers) as pool, open(a.out, 'a') as f:
        for k, out in enumerate(pool.imap_unordered(scan, [(g, a) for g in games]), 1):
            for r in out: f.write(json.dumps(r) + '\n')
            f.flush(); n += len(out)
            if k % 20 == 0 or k == len(games): el = time.perf_counter() - t0; print(f"  {k}/{len(games)} games, {n} errors, {el/60:.1f} min, ETA {el/k*(len(games)-k)/60:.0f} min", flush=True)
    print('done', flush=True)
