"""1,000 endgame-ish root positions (12-23 pieces, fullmove >= 25) from our own self-play PGNs, for leaf sampling.
usage: endgame_roots.py out.epd pgn1 [pgn2 ...]"""
import sys, io, random, chess, chess.pgn
out = sys.argv[1]; cands = []
for p in sys.argv[2:]:
    txt = open(p).read()
    for part in txt.split('\n\n[Event'):
        g = chess.pgn.read_game(io.StringIO(part if part.lstrip().startswith('[Event') else '[Event' + part))
        if g is None: continue
        b = g.board()
        for i, mv in enumerate(g.mainline_moves()):
            n = len(b.piece_map())
            if 12 <= n <= 23 and b.fullmove_number >= 25 and i % 6 == 0 and not b.is_game_over(): cands.append(b.fen())
            b.push(mv)
random.Random(9).shuffle(cands); seen = set(); keep = []
for f in cands:
    k = f.split(' ')[0]
    if k not in seen: seen.add(k); keep.append(f)
    if len(keep) >= 1000: break
open(out, 'w').write('\n'.join(keep) + '\n'); print(len(cands), 'candidates ->', len(keep), 'roots')
