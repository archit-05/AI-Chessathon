"""Label positions with Stockfish at a fixed depth, output the trainer's npz convention (pieces uint8[N,64]
codes 1..12 white PNBRQK black pnbrqk; stm; cp from WHITE's view; result 0; quiet; depth) in shards of
--shard-rows rows, plus a JSONL with the engine's own score for resolution analysis.
usage: label_leaf.py in.jsonl out_prefix --stockfish PATH --workers N --depth 12 [--limit N] [--stratify]
--stratify: cap the share of positions with >= 28 pieces at 40 % and of |engine score| < 50 at 40 % so the
labelled set is not dominated by dense, quiet positions."""
import argparse, json, sys, time, random
from pathlib import Path
from multiprocessing import Pool
import numpy as np, chess, chess.engine
CODE = {('P', True): 1, ('N', True): 2, ('B', True): 3, ('R', True): 4, ('Q', True): 5, ('K', True): 6, ('P', False): 7, ('N', False): 8, ('B', False): 9, ('R', False): 10, ('Q', False): 11, ('K', False): 12}
def label_batch(args):
    rows, a = args
    sf = chess.engine.SimpleEngine.popen_uci(a.stockfish); sf.configure({'Threads': 1, 'Hash': 64}); out = []
    try:
        for r in rows:
            b = chess.Board(r['fen'])
            if b.is_game_over(): continue
            inf = sf.analyse(b, chess.engine.Limit(depth=a.depth)); pv = inf.get('pv') or []
            cp_w = inf['score'].white().score(mate_score=30000)
            if cp_w is None: continue
            bm = pv[0] if pv else None; quiet = int(bm is not None and not b.is_capture(bm) and bm.promotion is None)
            out.append(dict(fen=r['fen'], cp_white=int(max(-32000, min(32000, cp_w))), best=bm.uci() if bm else None, quiet=quiet, depth=int(inf.get('depth', a.depth)), ev_stm=r.get('ev'), src=r.get('src'), ply=r.get('ply'), root=r.get('root')))
    finally: sf.quit()
    return out
def to_npz(rows, path):
    n = len(rows); pieces = np.zeros((n, 64), np.uint8); stm = np.zeros(n, np.uint8); cp = np.zeros(n, np.int16); res = np.zeros(n, np.int8); quiet = np.zeros(n, np.uint8); depth = np.zeros(n, np.uint8)
    for i, r in enumerate(rows):
        b = chess.Board(r['fen'])
        for sq, pc in b.piece_map().items(): pieces[i, sq] = CODE[(pc.symbol().upper(), pc.color)]
        stm[i] = 0 if b.turn else 1; cp[i] = r['cp_white']; quiet[i] = r['quiet']; depth[i] = r['depth']
    np.savez(path, pieces=pieces, stm=stm, cp=cp, result=res, quiet=quiet, depth=depth)
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('inp'); ap.add_argument('out'); ap.add_argument('--stockfish', required=True); ap.add_argument('--workers', type=int, default=4); ap.add_argument('--depth', type=int, default=12)
    ap.add_argument('--limit', type=int, default=0); ap.add_argument('--stratify', action='store_true'); ap.add_argument('--shard-rows', type=int, default=200000); ap.add_argument('--batch', type=int, default=200)
    a = ap.parse_args(); rows = [json.loads(l) for l in open(a.inp) if l.strip()]
    seen = set(); uniq = []
    for r in rows:
        if r['fen'] not in seen: seen.add(r['fen']); uniq.append(r)
    rng = random.Random(3); rng.shuffle(uniq)
    if a.stratify:
        for r in uniq: r['_pc'] = sum(ch.isalpha() for ch in r['fen'].split(' ')[0])
        dense = [r for r in uniq if r['_pc'] >= 28]; sparse = [r for r in uniq if r['_pc'] < 28]
        keep = sparse + dense[:max(len(sparse) * 2 // 3, 1)]; rng.shuffle(keep); uniq = keep
        quiet = [r for r in uniq if abs(r.get('ev', 0)) < 50]; loud = [r for r in uniq if abs(r.get('ev', 0)) >= 50]
        uniq = loud + quiet[:max(len(loud) * 2 // 3, 1)]; rng.shuffle(uniq)
    if a.limit: uniq = uniq[:a.limit]
    print(f"{len(rows)} rows -> {len(uniq)} to label at depth {a.depth} with {a.workers} workers", flush=True)
    batches = [(uniq[i:i + a.batch], a) for i in range(0, len(uniq), a.batch)]; done = []; t0 = time.perf_counter(); shard = 0
    with Pool(a.workers) as pool, open(a.out + '.labels.jsonl', 'a') as f:
        for k, out in enumerate(pool.imap_unordered(label_batch, batches), 1):
            for r in out: f.write(json.dumps(r) + '\n')
            done += out
            if len(done) >= a.shard_rows: to_npz(done[:a.shard_rows], f"{a.out}_{shard:03d}.npz"); done = done[a.shard_rows:]; shard += 1
            if k % 10 == 0 or k == len(batches): el = time.perf_counter() - t0; print(f"  {k}/{len(batches)} batches, {el/60:.1f} min, {len(out) * k / el:.0f} pos/s, ETA {el / k * (len(batches) - k) / 60:.0f} min", flush=True)
    if done: to_npz(done, f"{a.out}_{shard:03d}.npz")
    print('done', flush=True)
