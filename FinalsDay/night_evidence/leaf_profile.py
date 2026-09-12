"""Validate and profile a leaf dump: FEN legality, duplicates, source split, ply, piece count and |score|
histograms, and (optionally) the same profile of a bulletformat/npz training sample for comparison.
usage: leaf_profile.py dump.jsonl [--corpus-npz shard.npz]"""
import json, sys, collections, statistics, chess
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
bad = 0; fens = set(); pc = collections.Counter(); ab = collections.Counter(); src = collections.Counter(); ply = collections.Counter(); quiet = 0; incheck = 0
def bucket(x): return '<50' if x < 50 else '<150' if x < 150 else '<300' if x < 300 else '<600' if x < 600 else '<1000' if x < 1000 else '>=1000'
for r in rows:
    try: b = chess.Board(r['fen']); assert b.is_valid()
    except Exception: bad += 1; continue
    fens.add(r['fen']); n = len(b.piece_map()); pc[(n // 4) * 4] += 1; ab[bucket(abs(r['ev']))] += 1; src[r['src']] += 1; ply[min(r['ply'], 30)] += 1
    if b.is_check(): incheck += 1
    if not any(b.is_capture(m) for m in b.legal_moves): quiet += 1
n = len(rows)
print(json.dumps(dict(rows=n, invalid=bad, unique_fens=len(fens), source={'interior' if k == 0 else 'qsearch': v for k, v in src.items()}, in_check_pct=round(100 * incheck / n, 1), no_capture_available_pct=round(100 * quiet / n, 1),
    pieces_hist={str(k): v for k, v in sorted(pc.items())}, abs_score_hist=dict(ab), ply_hist={str(k): v for k, v in sorted(ply.items())}, median_abs_score=statistics.median(abs(r['ev']) for r in rows)), indent=1))
if len(sys.argv) > 3 and sys.argv[2] == '--corpus-npz':
    import numpy as np
    z = np.load(sys.argv[3]); pieces = z['pieces']; cp = z['cp']
    cnt = (pieces > 0).sum(axis=1); pch = collections.Counter(((cnt // 4) * 4).tolist()); abh = collections.Counter(bucket(abs(int(c))) for c in cp[:200000])
    print('corpus sample:', json.dumps(dict(rows=int(len(cp)), pieces_hist={str(k): int(v) for k, v in sorted(pch.items())}, abs_score_hist=dict(abh), median_abs_cp=float(np.median(np.abs(cp))))))
