"""Stockfish opening book for the curated start positions (legal: the rules allow a shipped table
that answers the opening, move number <= 20, whatever produced it).

For every root and for EACH colour we might be, build a small tree: at plies where we are to
move only Stockfish's best move continues; at the opponent's plies the top-K replies within
`--window` cp of the best continue (K = --multipv). Every position on the tree stores Stockfish's
best move for its side to move. Positions with a legal en-passant capture are not stored (the
wrapper's key ignores en passant), nor positions beyond fullmove 20, nor lines already decided
(|score| > --decided). Output: JSONL, one entry per position, merged later by merge_book.py.

usage: sf_book.py <roots.epd> <out.jsonl> --stockfish PATH --workers N --shard i/n [--plies 6] [--nodes 1500000]
"""
import argparse, json, sys, time, os
from pathlib import Path
from multiprocessing import Pool
import chess, chess.engine

def key(board):
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"

def has_ep(board):
    return board.ep_square is not None and any(board.is_en_passant(m) for m in board.legal_moves)

def analyse(sf, board, multipv, nodes):
    infos = sf.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv)
    out = []
    for inf in infos:
        pv = inf.get('pv') or []
        if not pv: continue
        out.append((pv[0].uci(), inf['score'].pov(board.turn).score(mate_score=30000), inf.get('depth', 0)))
    return out

def build_root(args):
    root, a = args
    sf = chess.engine.SimpleEngine.popen_uci(a.stockfish); sf.configure({'Threads': 1, 'Hash': a.hash})
    entries = {}; n_an = 0; t0 = time.perf_counter()
    try:
        for us in (chess.WHITE, chess.BLACK):
            stack = [(chess.Board(root), 0)]
            while stack:
                board, ply = stack.pop()
                if board.is_game_over() or board.fullmove_number > 20: continue
                k = key(board)
                if k in entries:
                    best = entries[k]
                    tops = best['_tops']
                else:
                    want = a.multipv if board.turn != us else 1
                    tops = analyse(sf, board, want, a.nodes); n_an += 1
                    if not tops: continue
                    bm, sc, d = tops[0]
                    best = dict(move=bm, nodes=a.nodes, depth=int(d), score=int(sc), root=root, ply=ply, engine='SF19', _tops=tops, _ep=has_ep(board))
                    entries[k] = best
                if ply >= a.plies or abs(best['score']) > a.decided: continue
                if board.turn == us:
                    nxt = [best['move']]
                else:
                    if len(tops) < a.multipv:  # analysed as our node earlier: widen once
                        tops = analyse(sf, board, a.multipv, a.nodes); n_an += 1; best['_tops'] = tops
                    bsc = tops[0][1]; nxt = [m for m, sc, d in tops if sc >= bsc - a.window]
                for m in nxt:
                    b2 = board.copy(); b2.push_uci(m); stack.append((b2, ply + 1))
    finally:
        sf.quit()
    rows = [dict(key=k, **{kk: vv for kk, vv in v.items() if not kk.startswith('_')}) for k, v in entries.items() if not v['_ep']]
    return root, rows, n_an, time.perf_counter() - t0

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('roots'); ap.add_argument('out'); ap.add_argument('--stockfish', required=True); ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--shard', default='0/1'); ap.add_argument('--plies', type=int, default=6); ap.add_argument('--nodes', type=int, default=1500000); ap.add_argument('--multipv', type=int, default=3)
    ap.add_argument('--window', type=int, default=60); ap.add_argument('--decided', type=int, default=200); ap.add_argument('--hash', type=int, default=64)
    a = ap.parse_args(); ids, n = a.shard.split('/'); ids = {int(x) for x in ids.split(',')}; n = int(n)
    roots = [l.strip() for l in open(a.roots) if l.strip()]; roots = [r for i, r in enumerate(roots) if i % n in ids]
    done = set()
    out = Path(a.out)
    if out.exists():
        for l in open(out):
            try: done.add(json.loads(l)['root'])
            except Exception: pass
    todo = [r for r in roots if r not in done]
    print(f"shard {a.shard}: {len(roots)} roots, {len(todo)} to do, workers {a.workers}, plies {a.plies}, nodes {a.nodes}", flush=True)
    t0 = time.perf_counter(); n_pos = 0; n_roots = 0
    with Pool(a.workers) as pool, open(out, 'a') as f:
        for root, rows, n_an, dt in pool.imap_unordered(build_root, [(r, a) for r in todo]):
            for r in rows: f.write(json.dumps(r) + '\n')
            f.flush(); n_pos += n_an; n_roots += 1
            if n_roots % 10 == 0 or n_roots == len(todo):
                el = time.perf_counter() - t0; print(f"  {n_roots}/{len(todo)} roots, {n_pos} analyses, {el/60:.1f} min, ETA {el/n_roots*(len(todo)-n_roots)/60:.0f} min", flush=True)
    print('done', flush=True)
