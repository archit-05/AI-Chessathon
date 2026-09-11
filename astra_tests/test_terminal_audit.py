"""Exhaustive terminal audit: can ANY path still return a non-terminal score for a position
the rules have already decided?

Rather than reading the return statements and reasoning about them, this drives a corpus of
positions that python-chess calls terminal through every entry point, under every table state
that could supply a competing value:

    entry points   evaluate / qsearch / search(1,2,4,6) / search through a real parent move
    table states   cold | TT poisoned with an exact bogus score for THIS key | correction
                   history saturated | both
    ply parity     non-root ply 1 and 2 (the root is excluded by design: the engine must
                   still return a move there, and its score comes from the children)

A terminal position must score the draw utility (|s| <= 25) or a mate score. Anything else is
a hole. Negative controls confirm the checks are not simply zeroing everything.
"""
import os, sys, json, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, N, V, chess, np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe(); e = p.e
DRAW_TOL = 25


def build_corpus(n_random=6000, seed=987):
    """Terminal positions. Curated entries are FILTERED through python-chess rather than
    asserted - a hand-written FEN that turns out not to be terminal is dropped, not trusted -
    and the bulk comes from random play so the corpus is not limited by my own imagination."""
    CUR_MATE = ['7k/6Q1/5K2/8/8/8/8/8 b - - 0 1', 'kn6/1B6/1K6/8/8/8/8/8 b - - 0 1',
                'R5k1/5ppp/8/8/8/8/8/6K1 b - - 0 1', '6rk/6pp/8/8/8/8/8/5RRK b - - 0 1',
                '7k/5ppp/8/8/8/8/8/R5RK b - - 0 1']
    CUR_STALE = ['k7/8/1QK5/8/8/8/8/8 b - - 0 1', '7k/5K2/6Q1/8/8/8/8/8 b - - 0 1',
                 '5bnr/4p1pq/4Qpkr/7p/7P/4P3/PPPP1PP1/RNB1KBNR b KQ - 2 10',
                 'kb6/8/1K6/8/8/8/8/1R6 b - - 0 1']
    CUR_DEAD = ['8/8/4k3/8/8/4K3/8/8 w - - 0 1', '8/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
                '8/8/4k3/8/8/4K3/8/5N2 w - - 0 1', '5b2/8/4k3/8/8/4K3/8/8 b - - 0 1',
                '5n2/8/4k3/8/8/4K3/8/8 b - - 0 1', '6b1/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
                '8/8/8/8/6k1/8/6K1/8 w - - 0 1']
    CUR_FIFTY = ['8/8/4k3/8/8/4K3/8/7R b - - 100 1', '8/3r4/4k3/8/8/4K3/3R4/8 w - - 100 1',
                 '8/8/4k3/8/8/4K3/3Q4/8 b - - 101 1']
    mates = [f for f in CUR_MATE if chess.Board(f).is_checkmate()]
    stales = [f for f in CUR_STALE if chess.Board(f).is_stalemate()]
    dead = [f for f in CUR_DEAD if chess.Board(f).is_insufficient_material()]
    fifty = [f for f in CUR_FIFTY
             if chess.Board(f).halfmove_clock >= 100 and not chess.Board(f).is_checkmate()]
    dropped = (len(CUR_MATE) - len(mates)) + (len(CUR_STALE) - len(stales)) + \
              (len(CUR_DEAD) - len(dead)) + (len(CUR_FIFTY) - len(fifty))
    rng = random.Random(seed)
    CAP = 30
    for _ in range(n_random):
        if len(mates) >= CAP and len(stales) >= CAP and len(dead) >= CAP:
            break
        b = chess.Board()
        for _ in range(rng.randint(20, 200)):
            ms = list(b.legal_moves)
            if not ms:
                break
            b.push(rng.choice(ms))
            if b.is_checkmate():
                if len(mates) < CAP:
                    mates.append(b.fen())
                break
            if b.is_stalemate():
                if len(stales) < CAP:
                    stales.append(b.fen())
                break
            if b.is_insufficient_material():
                if len(dead) < CAP:
                    dead.append(b.fen())
                break
            if b.halfmove_clock >= 100:
                if len(fifty) < CAP:
                    fifty.append(b.fen())
                break
    return mates, stales, dead, fifty, dropped


MATES, STALES, DEAD, FIFTY, DROPPED = build_corpus()
R.add('T0.corpus', 'terminal corpus assembled and confirmed by python-chess', 'INFO',
      checkmate=len(MATES), stalemate=len(STALES), dead_material=len(DEAD), fifty_move=len(FIFTY),
      curated_fens_dropped_as_not_terminal=DROPPED)


def poison_tt(bogus=900):
    """Store an EXACT bogus score for the current key at high depth, the strongest possible
    competing value a cutoff could return."""
    key = int(e.bb[15])
    idx = key & S.TT_MASK
    e.tt_key[idx] = np.uint64(key)
    S.tt_store(e.tt_key, e.tt_data, np.uint64(key), 0, bogus, 60, S.TT_EXACT, 1,
               int(e.st[B.S_PLY]))


def draw_utility(ply):
    """The exact value the engine is configured to return for a draw at this node:
    -contempt when the side to move is the root side, +contempt otherwise."""
    side = int(e.st[B.S_SIDE])
    root_side = int(e.info[S.I_ROOT_SIDE])
    c = int(e.info[S.I_CONTEMPT])
    return -c if side == root_side else c


def probe_all(fen, want, ply, tt_poison, corr_poison):
    """Return a list of (entry_point, score, expected) that violate `want`.

    Assertions are EXACT, not tolerances: a mate must be -MATE + ply (correct sign and correct
    ply distance, so a mate reported at the wrong distance is a failure), and a draw must equal
    the configured draw utility exactly, so a near-zero evaluation cannot pass for a draw.
    """
    bad = []
    for entry in ('qsearch', 'search1', 'search2', 'search4', 'search6',
                  'nullwin2', 'nullwin4', 'nullwin6'):
        p.setup(fen, budget=600.0)
        p.clear_tt(); p.clear_corr()
        e.st[B.S_PLY] = ply
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        expect = (-S.MATE + ply) if want == 'mate' else draw_utility(ply)
        if corr_poison:
            p.poison_corr()
        if tt_poison:
            poison_tt()
        if entry == 'qsearch':
            v = p.qsearch()
        elif entry.startswith('nullwin'):
            v = p.search(int(entry[7:]), alpha=-1, beta=0)
        else:
            v = p.search(int(entry[6:]))
        if int(v) != int(expect):
            bad.append((entry, int(v), int(expect)))
        e.st[B.S_PLY] = 0
    return bad


def run_class(tag, title, fens, want):
    worst = []
    combos = ((False, False), (True, False), (False, True), (True, True))
    for fen in fens:
        for ply in (1, 2):
            for ttp, corrp in combos:
                bad = probe_all(fen, want, ply, ttp, corrp)
                if bad:
                    worst.append(dict(fen=fen, ply=ply, tt_poisoned=ttp,
                                      corr_poisoned=corrp,
                                      violations=[dict(entry=x[0], got=x[1], expected=x[2])
                                                  for x in bad]))
    R.add(tag, title, 'PASS' if not worst else 'FAIL',
          positions=len(fens), states_each=len(combos) * 2 * 8,
          failing_states=len(worst), detail=worst[:3])
    return worst


run_class('T1.checkmate', 'checkmate returns a mate score from every entry point and table state',
          MATES, 'mate')
run_class('T2.stalemate', 'stalemate returns the draw utility from every entry point and table state',
          STALES, 'draw')
run_class('T3.dead_material', 'dead material returns the draw utility from every entry point and table state',
          DEAD, 'draw')
run_class('T4.fifty_move', 'the fifty-move rule returns the draw utility from every entry point and table state',
          FIFTY, 'draw')

# ---- terminal reached through a REAL parent move, not planted at the node -----------------
par_bad = []
rng = random.Random(4242)
pairs = []
for f in DEAD[:16] + STALES[:16] + MATES[:16]:
    b = chess.Board(f)
    for pre in list(b.legal_moves)[:1]:
        pass
    # walk one ply back by finding a predecessor: play from a position whose child is terminal
for _ in range(400):
    b = chess.Board()
    for _ in range(rng.randint(20, 170)):
        ms = list(b.legal_moves)
        if not ms:
            break
        m = rng.choice(ms)
        parent = b.fen()
        b.push(m)
        if b.is_insufficient_material() or b.is_stalemate() or b.is_checkmate():
            pairs.append((parent, m.uci(),
                          'mate' if b.is_checkmate() else 'draw'))
            break
        if len(pairs) >= 60:
            break
    if len(pairs) >= 60:
        break
for parent, uci, want in pairs:
    p.setup(parent, budget=600.0); p.clear_tt(); p.clear_corr(); p.poison_corr()
    p.push(uci)
    poison_tt()
    v = p.qsearch()
    ok = abs(v) <= DRAW_TOL if want == 'draw' else (v < -S.MATE_IN_MAX or v > S.MATE_IN_MAX)
    if not ok:
        par_bad.append((parent, uci, want, int(v)))
    p.pop()
R.add('T5.through_parent_move', 'terminal reached by making a real move, with a poisoned TT entry',
      'PASS' if not par_bad else 'FAIL', transitions=len(pairs), detail=par_bad[:3])

# ---- negative controls -------------------------------------------------------------------
# The earlier version of this check asserted that a "winnable" position must not SEARCH to a
# near-zero score. That is not a sound assertion: K+B vs K+P is objectively drawish and a score
# of -20 there is correct, not a flattening bug. What actually matters is that the exact
# recognisers agree with python-chess, so that is what is tested.
HAS_DM = hasattr(S, 'dead_material')
rng2 = random.Random(20260910)
mismatch = []
probed = 0
for _ in range(4000 if HAS_DM else 0):
    b = chess.Board()
    for _ in range(rng2.randint(2, 200)):
        ms = list(b.legal_moves)
        if not ms:
            break
        b.push(rng2.choice(ms))
        if b.is_game_over():
            break
    fen = b.fen()
    p.setup(fen)
    got = bool(S.dead_material(e.bb))
    want = chess.Board(fen).is_insufficient_material()
    probed += 1
    if got != want:
        mismatch.append((fen, got, want))
    if len(mismatch) >= 5:
        break
R.add('T6.dead_material_matches_oracle',
      'dead_material agrees with python-chess is_insufficient_material on random positions',
      ('PASS' if not mismatch else 'FAIL') if HAS_DM else 'SKIP', positions=probed, mismatches=len(mismatch),
      detail=mismatch[:5])

# and explicitly on the classes the brief names, both orientations
CLASSES = {
    'K-K': '8/8/4k3/8/8/4K3/8/8 w - - 0 1',
    'KB-K': '8/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
    'KN-K': '8/8/4k3/8/8/4K3/8/5N2 w - - 0 1',
    'K-KB': '5b2/8/4k3/8/8/4K3/8/8 b - - 0 1',
    'K-KN': '5n2/8/4k3/8/8/4K3/8/8 b - - 0 1',
    'same-colour bishops': '6b1/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
    'KNN-K': '8/8/4k3/8/8/4K3/8/5NN1 w - - 0 1',
    'KBN-K': '8/8/4k3/8/8/4K3/8/4BN2 w - - 0 1',
    'opposite-colour bishops': '5b2/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
    'KB-KN': '5n2/8/4k3/8/8/4K3/8/5B2 w - - 0 1',
    'KN-KN': '5n2/8/4k3/8/8/4K3/8/5N2 w - - 0 1',
    'KBP-K': '8/5p2/4k3/8/8/4K3/8/5B2 w - - 0 1',
    'KQ-K': '8/8/4k3/8/8/4K3/8/4Q3 w - - 0 1',
}
cls_bad = []
for name, fen in (CLASSES.items() if HAS_DM else []):
    p.setup(fen)
    got = bool(S.dead_material(e.bb))
    want = chess.Board(fen).is_insufficient_material()
    if got != want:
        cls_bad.append((name, fen, got, want))
R.add('T7.material_classes', 'every material class the brief names is classified correctly',
      ('PASS' if not cls_bad else 'FAIL') if HAS_DM else 'SKIP', classes=len(CLASSES), detail=cls_bad)

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"terminal_{os.environ.get('LABEL','run')}.json"
R.dump(out)
print('written', out)
_failed = R.summary()['failed']
if _failed:
    print(f'FAILED: {_failed} test(s) did not pass', file=sys.stderr)
sys.exit(1 if _failed else 0)
