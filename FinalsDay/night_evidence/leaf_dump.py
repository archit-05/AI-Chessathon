"""Sample the positions the search evaluates, from real fixed-node searches.
usage: leaf_dump.py <diag_build> <roots.epd> <out.jsonl> --workers N --shard i/n [--nodes 2000000] [--per-search 1500] [--book book.json] [--extend 2]
For each root: a search from the root itself and, if --book is given, from positions --extend plies
along the book's stored line. Every search records ~per-search sampled evaluations (interior and
quiescence), decoded to FEN with the raw network score (side-to-move view), source and ply."""
import argparse, json, os, sys, time
from pathlib import Path
from multiprocessing import Pool
PIECES = ' PNBRQKpnbrqk'
def decode(words):
    pcs = [(int(words[i]) >> (4 * j)) & 15 for i in range(4) for j in range(16)]
    meta = int(words[4]); side = meta & 1; castle = (meta >> 1) & 15; ep = ((meta >> 5) & 127) - 1; half = (meta >> 12) & 255; ply = (meta >> 20) & 255; src = (meta >> 28) & 1
    rows = []
    for r in range(7, -1, -1):
        s = ''; e = 0
        for f in range(8):
            c = pcs[r * 8 + f]
            if c == 0: e += 1
            else:
                if e: s += str(e); e = 0
                s += PIECES[c]
        if e: s += str(e)
        rows.append(s)
    cr = ''.join(ch for bit, ch in ((1, 'K'), (2, 'Q'), (4, 'k'), (8, 'q')) if castle & bit) or '-'
    eps = '-' if ep < 0 else 'abcdefgh'[ep % 8] + str(ep // 8 + 1)
    return f"{'/'.join(rows)} {'b' if side else 'w'} {cr} {eps} {half} 1", int(words[5]), src, ply
def run(args):
    fens, a = args
    os.environ['BINI_DIR'] = a.build; os.environ['BINI_TT_BITS'] = '22'
    sys.path.insert(0, str(Path.home() / 'chess' / 'astra_tests')); sys.path.insert(0, '/Users/architbhardwaj/Desktop/AI Chessathon/astra_tests')
    from harness import Probe, S
    p = Probe(); out = []
    for fen, tag in fens:
        p.setup(fen, [], budget=3600); p.e.prev_score_valid = False
        info = p.e.info; info[S.I_DUMP_MAX] = 0
        # first a short probe to estimate evaluations per node, then set the stride for ~per-search samples
        p.e.think(1e9, 1e9, max_nodes=50_000, log=False)
        p.setup(fen, [], budget=3600); p.e.prev_score_valid = False
        info[S.I_DUMP_TICK] = 0; info[S.I_DUMP_COUNT] = 0; info[S.I_DUMP_STRIDE] = max(1, int(a.nodes * 1.6 / a.per_search)); info[S.I_DUMP_MAX] = min(S.DUMP_CAP, a.per_search * 2)
        mv, sc, d = p.e.think(1e9, 1e9, max_nodes=a.nodes, log=False)
        n = int(info[S.I_DUMP_COUNT]); sc_arr = p.e.scores
        seen = set()
        for i in range(n):
            w = sc_arr[S.DUMP_BASE + i * 6: S.DUMP_BASE + i * 6 + 6]
            f, ev, src, ply = decode(w)
            if f in seen: continue
            seen.add(f); out.append(dict(fen=f, ev=ev, src=src, ply=ply, root=tag, rootmove=mv, rootscore=int(sc), depth=int(d)))
        info[S.I_DUMP_MAX] = 0
    return out
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('build'); ap.add_argument('roots'); ap.add_argument('out'); ap.add_argument('--workers', type=int, default=4); ap.add_argument('--shard', default='0/1')
    ap.add_argument('--nodes', type=int, default=2_000_000); ap.add_argument('--per-search', type=int, default=1500); ap.add_argument('--book'); ap.add_argument('--extend', type=int, default=2); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(); a.build = str(Path(a.build).resolve()); i, n = map(int, a.shard.split('/'))
    import chess
    roots = [l.strip() for l in open(a.roots) if l.strip()][i::n]
    if a.limit: roots = roots[:a.limit]
    book = json.load(open(a.book)) if a.book else {}
    def key(b): return f"{b.board_fen()} {'w' if b.turn else 'b'} {b.castling_xfen()}"
    jobs = []
    for r in roots:
        starts = [(r, r)]
        b = chess.Board(r)
        for k in range(a.extend):
            e = book.get(key(b))
            if not e: break
            b.push_uci(e['move']); starts.append((b.fen(), r))
        jobs.append((starts, a))
    done_roots = set()
    if Path(a.out).exists():
        for l in open(a.out):
            try: done_roots.add(json.loads(l)['root'])
            except Exception: pass
    jobs = [j for j in jobs if j[0][0][1] not in done_roots]
    print(f"shard {a.shard}: {len(roots)} roots, {len(jobs)} to do, searches per root {1 + a.extend}, nodes {a.nodes}, per-search {a.per_search}", flush=True)
    t0 = time.perf_counter(); tot = 0; k = 0
    with Pool(a.workers) as pool, open(a.out, 'a') as f:
        for rows in pool.imap_unordered(run, jobs):
            for r in rows: f.write(json.dumps(r) + '\n')
            f.flush(); tot += len(rows); k += 1
            if k % 10 == 0 or k == len(jobs): el = time.perf_counter() - t0; print(f"  {k}/{len(jobs)} roots, {tot} positions, {el/60:.1f} min, ETA {el/k*(len(jobs)-k)/60:.0f} min", flush=True)
    print('done', flush=True)
