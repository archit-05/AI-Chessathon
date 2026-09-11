"""Report 01 reproductions: the four cases named in the Astra directives, run against the
real search paths of whichever build BINI_DIR names."""
import os, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, N, V, E, chess, np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe()

# ---------------------------------------------------------------------------------------
# A. stalemate at the quiescence frontier
# ---------------------------------------------------------------------------------------
FEN_A = 'k7/8/1QK5/8/8/8/8/8 b - - 0 1'
assert chess.Board(FEN_A).is_stalemate()
p.setup(FEN_A); p.clear_tt(); p.clear_corr()
snap = p.snapshot()
sc = p.qsearch()
R.add('A.qsearch_stalemate', 'qsearch on a stalemate returns the draw utility',
      'PASS' if abs(sc) <= 25 else 'FAIL', score=sc, oracle='stalemate')
R.add('A.state_preserved', 'qsearch restores board state exactly',
      'PASS' if not p.diff_snapshot(snap) else 'FAIL', changed=p.diff_snapshot(snap))

# generalisation: several stalemates, all reached through qsearch, with a poisoned corr table
STALEMATES = [
    ('k7/8/1QK5/8/8/8/8/8 b - - 0 1', 'KQ box'),
    ('8/8/8/8/8/5k2/5p2/5K2 w - - 0 1', 'pawn block'),
    ('5bnr/4p1pq/4Qpkr/7p/7P/4P3/PPPP1PP1/RNB1KBNR b KQ - 2 10', 'classic'),
    ('7k/5K2/6Q1/8/8/8/8/8 b - - 0 1', 'corner queen'),
    ('kb6/8/1K6/8/8/8/8/1R6 b - - 0 1', 'rook cage'),
]
bad = []
for fen, name in STALEMATES:
    b = chess.Board(fen)
    if not b.is_stalemate():
        continue
    p.setup(fen); p.clear_tt(); p.clear_corr(); p.poison_corr()
    s = p.qsearch()
    if abs(s) > 25:
        bad.append((name, fen, s))
R.add('A.gen_stalemate_qsearch', 'stalemate set through qsearch with poisoned correction history',
      'PASS' if not bad else 'FAIL', failures=len(bad), detail=bad)

# A qsearch node that is NOT the first main-search-to-qsearch call: reached by playing a
# capture and calling qsearch at the resulting ply.  White is in check from Rb6; Qxb6 both
# resolves the check and stalemates Black.
FEN_A3 = 'k7/8/1rK5/8/8/8/1Q6/8 w - - 0 1'
_b = chess.Board(FEN_A3)
assert _b.is_valid() and _b.is_check(), 'A3 setup: expected White in check'
_b.push_uci('b2b6')
assert _b.is_stalemate(), 'A3 setup: Qxb6 must stalemate Black'
p.setup(FEN_A3); p.clear_tt(); p.clear_corr(); p.poison_corr()
p.push('b2b6')
snap3 = p.snapshot()
sa3 = p.qsearch()
chg3 = p.diff_snapshot(snap3)
p.pop()
R.add('A.recursive_frontier', 'qsearch at a node reached through a capture sees the stalemate',
      'PASS' if abs(sa3) <= 25 else 'FAIL', score=sa3,
      note='the parent takes a max, so this value only propagates when the stalemate is best')
R.add('A.probe_leaves_no_trace', 'the legality probe restores undo slots and move lists',
      'PASS' if not chg3 else 'FAIL', changed=chg3)

# ---------------------------------------------------------------------------------------
# B. checkmate at the fifty-move boundary
# ---------------------------------------------------------------------------------------
FEN_B = '7k/6Q1/5K2/8/8/8/8/8 b - - 100 1'
assert chess.Board(FEN_B).is_checkmate()
p.setup(FEN_B); p.clear_tt(); p.clear_corr()
p.e.st[B.S_PLY] = 1
N.nnue_refresh(p.e.bb, p.e.st, p.e.pcs, p.e.acc, p.e.w1, p.e.b1)
sc = p.search(1)
R.add('B.mate_at_half100_nonroot', 'non-root mate on the 100th halfmove returns a mate score',
      'PASS' if sc < -S.MATE_IN_MAX else 'FAIL', score=sc, expected=f'< -{S.MATE_IN_MAX}')

# the same thing through the real parent-move transition: White plays Qg7# at half 99
FEN_B2 = '7k/8/5K2/8/8/8/6Q1/8 w - - 99 1'
p.setup(FEN_B2); p.clear_tt(); p.clear_corr()
sc2 = p.search(3)
bo = chess.Board(FEN_B2)
R.add('B.parent_transition', 'parent search sees the mate rather than a fifty-move draw',
      'PASS' if sc2 > S.MATE_IN_MAX else 'FAIL', score=sc2, halfmove_after_mate=100)

# negative: a real fifty-move draw must stay a draw
FEN_B3 = '8/8/4k3/8/8/4K3/8/7R b - - 100 1'
p.setup(FEN_B3); p.clear_tt(); p.clear_corr()
p.e.st[B.S_PLY] = 1
sc3 = p.search(2)
R.add('B.negative_real_fifty', 'genuine fifty-move position still returns the draw utility',
      'PASS' if abs(sc3) <= 40 else 'FAIL', score=sc3)

# negative: stalemate at halfmove 100 is still a draw (not a mate)
FEN_B4 = 'k7/8/1QK5/8/8/8/8/8 b - - 100 1'
p.setup(FEN_B4); p.clear_tt(); p.clear_corr()
p.e.st[B.S_PLY] = 1
sc4 = p.search(1)
R.add('B.negative_stalemate_at_100', 'stalemate on the 100th halfmove is a draw, not a mate',
      'PASS' if abs(sc4) <= 40 else 'FAIL', score=sc4)

# ---------------------------------------------------------------------------------------
# C. repetition at an even-ply history boundary
# ---------------------------------------------------------------------------------------
HAS_KIND = hasattr(S, 'repetition_kind')


def occurrence_truth(pre_ucis, in_tree_ucis, fen=chess.STARTING_FEN):
    """Independent oracle: replay the whole line with python-chess and classify the current
    position the way the rules do.  Returns (expected_kind, total_occurrences, where)."""
    b = chess.Board(fen)
    keys = []                       # (epd-with-rights key, index) for every position in order
    def k(board):
        return board._transposition_key()
    keys.append(k(b))
    for u in pre_ucis:
        b.push_uci(u)
        keys.append(k(b))
    root_index = len(keys) - 1
    for u in in_tree_ucis:
        b.push_uci(u)
        keys.append(k(b))
    cur = keys[-1]
    half = b.halfmove_clock
    cur_index = len(keys) - 1
    in_tree = False
    hist_hits = 0
    for d in range(2, half + 1, 2):
        j = cur_index - d
        if j < 0:
            break
        if keys[j] != cur:
            continue
        if j >= root_index:
            in_tree = True
            break
        hist_hits += 1
    if in_tree:
        return 1, hist_hits + 1, 'search tree'
    if hist_hits >= 2:
        return 2, hist_hits + 1, 'game history, third occurrence'
    return 0, hist_hits + 1, 'game history, %d occurrence(s) only' % (hist_hits + 1)


def rep_case(pre_ucis, in_tree_ucis, fen=chess.STARTING_FEN):
    """Return (engine_kind, ply, halfmove)."""
    p.setup(fen, pre_ucis)
    for u in in_tree_ucis:
        p.push(u)
    if HAS_KIND:
        got = int(S.repetition_kind(p.e.bb, p.e.st, p.e.ub, p.e.ui, p.e.hist, p.e.info[S.I_HIST_N]))
    else:
        got = 1 if p.is_repetition() else 0
    ply = int(p.e.st[B.S_PLY]); half = int(p.e.st[B.S_HALF])
    for _ in in_tree_ucis:
        p.pop()
    return got, ply, half


CFEN = 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1'
CASES = [
    ('C.even_ply_history_boundary', 'second occurrence straddling the root at even ply',
     ('g1f3', 'g8f6'), ('f3g1', 'f6g8'), chess.STARTING_FEN),
    ('C.odd_ply_history_boundary', 'occurrence at odd ply reaching back into game history',
     ('g1f3', 'g8f6', 'f3g1'), ('f6g8', 'g1f3', 'g8f6'), chess.STARTING_FEN),
    ('C.cycle_inside_tree', 'four-ply cycle entirely inside the search tree',
     (), ('g1f3', 'g8f6', 'f3g1', 'f6g8'), chess.STARTING_FEN),
    ('C.cycle_in_game_history', 'occurrence reached through pre-root game history',
     ('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3'), ('g8f6', 'f3g1', 'f6g8'), chess.STARTING_FEN),
    ('C.third_occurrence_claim', 'third occurrence through game history is a real claim',
     ('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6'), ('f3g1', 'f6g8'), chess.STARTING_FEN),
    ('C.negative_after_pawn_move', 'no repetition claimed across a pawn move',
     ('g1f3', 'g8f6', 'f3g1', 'f6g8'), ('e2e4',), chess.STARTING_FEN),
    ('C.negative_distinct_position', 'no repetition on a first occurrence',
     ('g1f3',), ('g8f6',), chess.STARTING_FEN),
    ('C.after_rights_spent', 'cycle straddling the root once castling rights are gone',
     ('e1e2', 'e8e7', 'e2e1', 'e7e8', 'a1b1'), ('a8b8', 'b1a1', 'b8a8'), CFEN),
    ('C.negative_rights_changed', 'same placement but spent castling rights is not a repetition',
     (), ('a1b1', 'a8b8', 'b1a1', 'b8a8'), CFEN),
    ('C.deep_cycle_empty_history', 'eight-ply double cycle with no pre-root history',
     (), ('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6', 'f3g1', 'f6g8'), chess.STARTING_FEN),
]
for tid, title, pre, tree, fen in CASES:
    want, total, where = occurrence_truth(pre, tree, fen)
    got, ply, half = rep_case(pre, tree, fen)
    if HAS_KIND:
        ok = got == want
    else:
        # a build without the distinction can only say draw / no draw; it is correct when it
        # agrees on WHETHER there is a draw at all, under its own (second-occurrence) reading
        ok = (got != 0) == (want != 0 or total >= 2)
    R.add(tid, title, 'PASS' if ok else 'FAIL', kind=got, expected=want,
          occurrences=total, matched_in=where, ply=ply, halfmove=half)

# ---------------------------------------------------------------------------------------
# D. the existing insufficient-material candidate is not an exact repair
# ---------------------------------------------------------------------------------------
FEN_D = 'kn6/1B6/1K6/8/8/8/8/8 b - - 0 1'
bd = chess.Board(FEN_D)
R.add('D.oracle_bn_mate', 'python-chess: KB vs KN is a legal checkmate here', 'INFO',
      valid=bd.is_valid(), checkmate=bd.is_checkmate(), insufficient=bd.is_insufficient_material())

p.setup(FEN_D); p.clear_tt(); p.clear_corr()
p.e.st[B.S_PLY] = 1
scd = p.search(1)
R.add('D.bn_mate_recognised', 'engine returns a mate score for the KB-vs-KN mate',
      'PASS' if scd < -S.MATE_IN_MAX else 'FAIL', score=scd)

# static zero is not a guarantee: correction history can move it
p.setup('7k/8/8/8/8/8/2B5/K7 w - - 0 1'); p.clear_corr(); p.poison_corr()
raw = p.evaluate()
corr = int(S.corrected(p.e.scores, p.e.bb, p.e.st[B.S_SIDE], 0, 1))
R.add('D.correction_moves_zero', 'saturated correction history shifts a static zero', 'INFO',
      static_zero_corrected_to=corr, raw_eval=raw)

# dead-material classes that MUST read as exactly drawn
DEAD = [
    ('8/8/4k3/8/8/4K3/8/8 w - - 0 1', 'K-K'),
    ('8/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'KB-K'),
    ('8/8/4k3/8/8/4K3/8/5N2 w - - 0 1', 'KN-K'),
    ('5b2/8/4k3/8/8/4K3/8/8 w - - 0 1', 'K-KB'),
    ('5n2/8/4k3/8/8/4K3/8/8 w - - 0 1', 'K-KN'),
    ('6b1/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'same-colour bishops'),
]
ALIVE = [
    ('8/8/4k3/8/8/4K3/8/5NN1 w - - 0 1', 'KNN-K'),
    ('8/8/4k3/8/8/4K3/8/4BN2 w - - 0 1', 'KBN-K'),
    ('5b2/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'opposite-colour bishops'),
    ('5n2/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'KB-KN'),
    ('5n2/8/4k3/8/8/4K3/8/5N2 w - - 0 1', 'KN-KN'),
    ('8/5p2/4k3/8/8/4K3/8/5B2 w - - 0 1', 'KBP-K'),
]
for fen, name in DEAD:
    assert chess.Board(fen).is_insufficient_material(), name
for fen, name in ALIVE:
    assert not chess.Board(fen).is_insufficient_material(), name

def probe_dead(fen):
    p.setup(fen); p.clear_tt(); p.clear_corr(); p.poison_corr()
    p.e.st[B.S_PLY] = 1
    return p.search(2), p.evaluate()

dead_bad = []
for fen, name in DEAD:
    s, ev = probe_dead(fen)
    if abs(s) > 25:
        dead_bad.append((name, fen, s, ev))
R.add('D.dead_material_scores_zero', 'python-chess dead-material classes score the draw utility',
      'PASS' if not dead_bad else 'FAIL', failures=len(dead_bad), detail=dead_bad)

alive_bad = []
for fen, name in ALIVE:
    s, ev = probe_dead(fen)
    if abs(s) <= 25 and name in ('KNN-K', 'KBN-K', 'KBP-K'):
        alive_bad.append((name, fen, s, ev))
R.add('D.winnable_material_not_zeroed', 'winnable pawnless/pawn material is not forced to zero',
      'PASS' if not alive_bad else 'FAIL', failures=len(alive_bad), detail=alive_bad,
      note='reported for information: heuristic scaling may still damp these')

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"repro_{os.environ.get('LABEL','run')}.json"
out.parent.mkdir(exist_ok=True)
R.dump(out)
print('written', out)
_failed = R.summary()['failed']
if _failed:
    print(f'FAILED: {_failed} test(s) did not pass', file=sys.stderr)
sys.exit(1 if _failed else 0)
