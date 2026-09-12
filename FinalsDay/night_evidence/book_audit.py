"""Audit a merged book.json: every key parses, every move is legal in it, no stored position has a legal
en-passant capture, provenance counts, per-ply counts, root coverage (Stockfish / old book / none).
usage: book_audit.py book.json roots.epd"""
import json, sys, collections, chess
book = json.load(open(sys.argv[1])); roots = [l.strip() for l in open(sys.argv[2]) if l.strip()]
def key(b): return f"{b.board_fen()} {'w' if b.turn else 'b'} {b.castling_xfen()}"
bad_key = illegal = ep = 0; prov = collections.Counter(); plies = collections.Counter()
for k, v in book.items():
    parts = k.split(' ')
    try: b = chess.Board(f"{parts[0]} {parts[1]} {parts[2]} - 0 1")
    except Exception: bad_key += 1; continue
    if chess.Move.from_uci(v['move']) not in b.legal_moves: illegal += 1
    prov[v.get('engine', 'own')] += 1; plies[(v.get('engine', 'own'), v.get('ply', -1))] += 1
cov = collections.Counter()
for r in roots:
    v = book.get(key(chess.Board(r)))
    cov['none' if v is None else v.get('engine', 'own')] += 1
print(json.dumps(dict(entries=len(book), bad_keys=bad_key, illegal_moves=illegal, provenance=dict(prov), root_coverage=dict(cov), sf_per_ply={str(p): n for (e, p), n in sorted(plies.items()) if e == 'SF19'})))
sys.exit(1 if (bad_key or illegal) else 0)
