"""C3: position identity. Does the en-passant hashing ever give two DIFFERENT positions the
same key (dangerous), or only give two identical positions different keys (merely wasteful)?"""
import os, sys, sys, random, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, chess, np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe(); e = p.e

def key_of(fen):
    B.set_fen(e.bb, e.st, e.pcs, fen)
    return int(e.bb[15])

def legal_set(fen):
    return frozenset(m.uci() for m in chess.Board(fen).legal_moves)

# ---- 1. pinned en passant: EP square set, but the capture is illegal --------------------
PINNED = [
    '8/8/8/8/k1pP3R/8/8/4K3 b - d3 0 1',       # rank pin along the 4th
    '8/8/8/2k5/3Pp3/8/8/4K1B1 b - d3 0 1',     # diagonal pin
]
rows = []
for fen in PINNED:
    b = chess.Board(fen)
    assert b.is_valid()
    eps = [m.uci() for m in b.legal_moves if b.is_en_passant(m)]
    noep = fen.replace(' d3 ', ' - ').replace(' d6 ', ' - ')
    same_moves = legal_set(fen) == legal_set(noep)
    same_key = key_of(fen) == key_of(noep)
    rows.append(dict(fen=fen, ep_captures_legal=eps, identical_legal_moves=same_moves,
                     identical_key=same_key))
bad = [r for r in rows if not r['identical_legal_moves']]
R.add('C3.pinned_ep_no_legal_capture', 'a pinned en-passant capture is correctly illegal',
      'PASS' if not bad and all(r['ep_captures_legal'] == [] for r in rows) else 'FAIL', detail=rows)
over = [r for r in rows if r['identical_legal_moves'] and not r['identical_key']]
R.add('C3.ep_over_distinction', 'identical legal-move sets that hash differently (missed transposition)',
      'INFO', count=len(over), of=len(rows),
      note='wasteful, not wrong: it splits one position across two table entries')

# ---- 2. the dangerous direction: do different positions ever share a key? ---------------
rng = random.Random(4242)
seen = {}
collisions, ep_positions = [], 0
for game in range(120):
    board = chess.Board()
    for _ in range(rng.randint(6, 60)):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
        if board.is_game_over():
            break
        fen = board.fen()
        if board.ep_square is not None:
            ep_positions += 1
        k = key_of(fen)
        sig = (board.board_fen(), board.turn, board.castling_rights, legal_set(fen))
        if k in seen and seen[k] != sig:
            collisions.append((seen[k][0], sig[0], k))
        seen[k] = sig
R.add('C3.no_key_aliasing', 'no two positions with different legal moves share a Zobrist key',
      'PASS' if not collisions else 'FAIL', positions=len(seen), ep_positions=ep_positions,
      collisions=len(collisions), detail=collisions[:3])

# ---- 3. book keys: EP is omitted entirely ----------------------------------------------
def book_key(board):
    return f"{board.board_fen()} {'w' if board.turn else 'b'} {board.castling_xfen()}"

alias = []
for fen in PINNED + ['rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3']:
    b = chess.Board(fen)
    noep = chess.Board(fen.replace(f' {chess.SQUARE_NAMES[b.ep_square]} ', ' - ')) if b.ep_square else None
    if noep is None:
        continue
    if book_key(b) == book_key(noep) and legal_set(b.fen()) != legal_set(noep.fen()):
        alias.append((fen, sorted(legal_set(b.fen()) - legal_set(noep.fen()))))
R.add('C3.book_key_ep_aliasing', 'book key omits en passant, so two positions can share one entry',
      'XFAIL' if alias else 'PASS', aliased=len(alias), detail=alias,
      note='KNOWN AND ACCEPTED, unchanged from the frozen V8 baseline. agent.py legality-checks '
           'the book move it plays, so the worst case is a suboptimal move, never an illegal one. '
           'Fixing it means changing the book key format, which would strand all 1,226 existing '
           'entries, and the brief directs that a book migration stay separate from the search '
           'work. Recorded as a post-lock item, not a blocker. A NEW failure in this file still '
           'breaks the build: only this one line is declared.')

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"c3_{os.environ.get('LABEL','run')}.json"
R.dump(out)
print('written', out)
_failed = R.summary()['failed']
if _failed:
    print(f'FAILED: {_failed} unexpected failure(s)', file=sys.stderr)
sys.exit(1 if _failed else 0)
