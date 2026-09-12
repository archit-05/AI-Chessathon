"""How well does our book cover the top-5 teams' actual openings?  For each of their games, walk the first 12 full moves;
at every position where WE would be to move against that team (they just moved), check whether the book has an entry.
Prints coverage by ply and the most frequent uncovered positions (as roots for a book extension).
usage: opp_book_cov.py book.json out_roots.epd team1.pgn [team2.pgn ...]"""
import sys, json, collections, chess, chess.pgn
book = json.load(open(sys.argv[1])); out = sys.argv[2]
def key(b): return f"{b.board_fen()} {'w' if b.turn else 'b'} {b.castling_xfen()}"
cov = collections.Counter(); tot = collections.Counter(); missed = collections.Counter(); missed_ex = {}
for path in sys.argv[3:]:
    team = path.rsplit('/', 1)[-1][:-4].replace('_', ' ')
    n = 0
    with open(path) as f:
        while True:
            g = chess.pgn.read_game(f)
            if g is None: break
            them_white = team.lower() in g.headers.get('White', '').lower()
            them_black = team.lower() in g.headers.get('Black', '').lower()
            if not (them_white or them_black): continue
            b = g.board(); n += 1
            for i, mv in enumerate(g.mainline_moves()):
                if b.fullmove_number > 12: break
                their_turn = (b.turn == chess.WHITE) == them_white
                b.push(mv)
                if their_turn and b.fullmove_number <= 12 and not b.is_game_over():
                    k = key(b); tot[b.fullmove_number] += 1
                    if k in book: cov[b.fullmove_number] += 1
                    else: missed[k] += 1; missed_ex.setdefault(k, (team, b.fen()))
    print(f"{team}: {n} games")
print("our-move positions vs their lines, coverage by fullmove:")
for fm in sorted(tot): print(f"  move {fm:2d}: {cov[fm]:4d}/{tot[fm]:4d} = {100*cov[fm]/tot[fm]:5.1f} %")
print(f"total {sum(cov.values())}/{sum(tot.values())} = {100*sum(cov.values())/max(1,sum(tot.values())):.1f} %")
roots = [(c, missed_ex[k][1], missed_ex[k][0]) for k, c in missed.most_common() if c >= 2]
with open(out, 'w') as f:
    for c, fen, team in roots: f.write(f"{fen}\n")
print(f"uncovered positions seen >= 2 times: {len(roots)} (written to {out}); top 12:")
for c, fen, team in roots[:12]: print(f"  x{c:2d} [{team}] {fen}")
