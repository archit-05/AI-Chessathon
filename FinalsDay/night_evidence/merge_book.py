"""Deterministic merge of sf_book JSONL shards into book.json, Stockfish entries overriding a base book.
Rows are sorted by (key, ply, root, move, -depth) so the result does not depend on file order or the
order workers finished; per key the lowest ply wins, ties broken lexicographically. Reports conflicts
(same key and ply, different move across shards) and root coverage.
usage: merge_book.py out.json --roots roots.epd --base old_book.json shard1.jsonl [shard2.jsonl ...]"""
import json, sys, collections, hashlib
args = sys.argv[1:]; out = args.pop(0); base = roots_file = None
while args and args[0].startswith('--'):
    k = args.pop(0)
    if k == '--base': base = args.pop(0)
    elif k == '--roots': roots_file = args.pop(0)
rows = []
for p in args:
    for l in open(p):
        l = l.strip()
        if not l: continue
        try: r = json.loads(l)
        except Exception: continue
        rows.append(r)
rows.sort(key=lambda r: (r['key'], r['ply'], r['root'], r['move'], -r['depth']))
book = {}; first_at_ply = {}; conflicts = 0; roots = set(); plies = collections.Counter()
for r in rows:
    k = r['key']; roots.add(r['root'])
    if k not in book:
        book[k] = dict(move=r['move'], ms=0, nodes=r['nodes'], depth=r['depth'], score=r['score'], root=r['root'], ply=r['ply'], engine=r.get('engine', 'SF19'))
        first_at_ply[k] = (r['ply'], r['move']); plies[r['ply']] += 1
    elif first_at_ply[k][0] == r['ply'] and first_at_ply[k][1] != r['move']:
        conflicts += 1
n_sf = len(book); kept = 0
if base:
    old = json.load(open(base))
    for k, v in sorted(old.items()):
        if k not in book and v.get('root') not in roots:
            book[k] = v; kept += 1
json.dump(book, open(out, 'w'), separators=(',', ':'), sort_keys=True)
raw = open(out, 'rb').read()
cov = ''
if roots_file:
    all_roots = [l.strip() for l in open(roots_file) if l.strip()]
    cov = f"; roots covered by Stockfish {len(roots & set(all_roots))}/{len(all_roots)}"
print(f"{out}: {len(book)} entries = {n_sf} Stockfish (from {len(roots)} roots, per-ply {sorted(plies.items())}, same-ply move conflicts {conflicts}) + {kept} kept from the old book{cov}; bytes {len(raw):,}; sha256 {hashlib.sha256(raw).hexdigest()[:16]}")
