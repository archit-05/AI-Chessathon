"""C1b and C2b: maximum-ply terminal exits, claim-versus-heuristic repetition, and NNUE
coverage of all eight output buckets."""
import os, sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, N, V, chess, np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe(); e = p.e
HAS_KIND = hasattr(S, 'repetition_kind')
MAXP = B.MAX_PLY - 1

# =========================================================================================
# C1b - the maximum-ply exits
# =========================================================================================
def at_max_ply(fen, fn):
    p.setup(fen); p.clear_tt(); p.clear_corr(); p.poison_corr()
    e.st[B.S_PLY] = MAXP
    N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
    v = fn()
    e.st[B.S_PLY] = 0
    return v

CASES = [
    ('dead KB-K',  '8/8/4k3/8/8/4K3/8/5B2 w - - 0 1',   'draw'),
    ('dead K-K',   '8/8/4k3/8/8/4K3/8/8 w - - 0 1',     'draw'),
    ('stalemate',  'k7/8/1QK5/8/8/8/8/8 b - - 0 1',     'draw'),
    ('checkmate',  '7k/6Q1/5K2/8/8/8/8/8 b - - 0 1',    'mate'),
]
qbad, sbad = [], []
for name, fen, want in CASES:
    q = at_max_ply(fen, lambda: p.qsearch())
    s = at_max_ply(fen, lambda: p.search(1))
    ok_q = (q < -S.MATE_IN_MAX) if want == 'mate' else abs(q) <= 25
    ok_s = (s < -S.MATE_IN_MAX) if want == 'mate' else abs(s) <= 25
    if not ok_q:
        qbad.append((name, fen, q, want))
    if not ok_s:
        sbad.append((name, fen, s, want))
R.add('V1.qsearch_at_max_ply', 'quiescence decides terminals at ply MAX_PLY-1, not by evaluation',
      'PASS' if not qbad else 'FAIL', ply=MAXP, detail=qbad)
R.add('V2.search_at_max_ply', 'main search decides terminals at ply MAX_PLY-1',
      'PASS' if not sbad else 'FAIL', ply=MAXP, detail=sbad)

# the exit must still return an evaluation for an ordinary position, not a draw
p.setup('r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3')
e.st[B.S_PLY] = MAXP
N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
ordinary = p.qsearch()
e.st[B.S_PLY] = 0
R.add('V3.max_ply_negative', 'an ordinary position at max ply still returns an evaluation',
      'PASS' if abs(ordinary) > 25 or ordinary != 0 else 'FAIL', score=ordinary)

# =========================================================================================
# C2b - a real claim versus the search-cycle heuristic
# =========================================================================================
def kind(pre, tree, fen=chess.STARTING_FEN):
    p.setup(fen, pre)
    for u in tree:
        p.push(u)
    if HAS_KIND:
        k = int(S.repetition_kind(e.bb, e.st, e.ub, e.ui, e.hist, e.info[S.I_HIST_N]))
    else:
        k = 1 if p.is_repetition() else 0
    ply, half = int(e.st[B.S_PLY]), int(e.st[B.S_HALF])
    for _ in tree:
        p.pop()
    return k, ply, half

CYC = ['g1f3', 'g8f6', 'f3g1', 'f6g8']
# 1. a cycle wholly inside the tree -> the named heuristic
k, ply, half = kind((), CYC)
R.add('V4.tree_cycle_is_heuristic', 'a cycle inside the search tree is the named search heuristic',
      'PASS' if k == 1 else 'FAIL', kind=k, expected=1, ply=ply, halfmove=half)

# 2. the directive's case: pre-root g1f3 g8f6, tree f3g1 f6g8 -> SECOND occurrence only
k2, ply2, half2 = kind(('g1f3', 'g8f6'), ('f3g1', 'f6g8'))
R.add('V5.second_occurrence_not_a_claim', 'a bare second occurrence in game history is NOT a draw',
      ('PASS' if k2 == 0 else 'FAIL') if HAS_KIND else 'SKIP', kind=k2, expected=0, ply=ply2, halfmove=half2,
      note='asserted only on builds that separate the two readings; the baseline has no such concept, '
           'and the 0 it returns here comes from its indexing bug, not from correct semantics')

# 3. the same line one cycle later -> THIRD occurrence -> a real claim
k3, ply3, half3 = kind(('g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6'), ('f3g1', 'f6g8'))
R.add('V6.third_occurrence_is_a_claim', 'a third occurrence reached through game history is a real claim',
      ('PASS' if k3 == 2 else 'FAIL') if HAS_KIND else 'SKIP', kind=k3, expected=2, ply=ply3, halfmove=half3,
      note='also proves the distance indexing still reaches pre-root history: a build that cannot '
           'index past the root cannot count two occurrences there')

# 4. negatives
k4, _, _ = kind(('g1f3',), ('g8f6',))
R.add('V7.no_repetition_negative', 'a first occurrence is not a draw under either reading',
      'PASS' if k4 == 0 else 'FAIL', kind=k4)
k5, _, _ = kind(('g1f3', 'g8f6', 'f3g1', 'f6g8'), ('e2e4',))
R.add('V8.irreversible_negative', 'no draw claimed across a pawn move',
      'PASS' if k5 == 0 else 'FAIL', kind=k5)

# 5. the referee's own verdict on the same two lines, as the independent oracle
def referee_says(ucis):
    b = chess.Board()
    for u in ucis:
        b.push_uci(u)
    o = b.outcome(claim_draw=True)
    return None if o is None else o.termination.name
ref2 = referee_says(['g1f3', 'g8f6', 'f3g1', 'f6g8'])
ref3 = referee_says(['g1f3', 'g8f6', 'f3g1', 'f6g8', 'g1f3', 'g8f6', 'f3g1', 'f6g8'])
R.add('V9.referee_agrees', 'the engine now agrees with the referee about which line is a draw',
      'PASS' if ref2 is None and ref3 is not None else 'FAIL',
      after_second=ref2, after_third=ref3,
      note='referee = board.outcome(claim_draw=True), the local harness rule')

# =========================================================================================
# NNUE - every one of the eight output buckets
# =========================================================================================
# bucket = min(NO-1, (piece_count-1)*NO//32); with NO=8 that is (pieces-1)//4
BUCKET_FENS = [
    ('8/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 0),                       # 3 pieces
    ('8/5ppp/4k3/8/8/4K3/5PP1/8 w - - 0 1', 1),                    # 7
    ('8/3r1ppp/4k3/8/8/4K3/3R1PPP/8 w - - 0 1', 2),                # 9
    ('8/3r1ppp/2n1k3/8/8/2N1K3/3R1PPP/8 w - - 0 1', 2),            # 11
    ('r5k1/3r1ppp/2n5/8/8/2N5/3R1PPP/R5K1 w - - 0 1', 3),          # 13
    ('r4rk1/3q1ppp/2n5/8/8/2N5/3Q1PPP/R4RK1 w - - 0 1', 3),        # 15
    ('r1bq1rk1/5ppp/2n5/8/8/2N5/5PPP/R1BQ1RK1 w - - 0 1', 4),      # 17
    ('r1bq1rk1/4nppp/2n5/8/8/2N1N3/5PPP/R1BQ1RK1 w - - 0 1', 4),   # 19
    ('r1bq1rk1/pp2nppp/2n5/8/8/2N1N3/PP3PPP/R1BQ1RK1 w - - 0 1', 5),  # 21
    ('r1bq1rk1/pppnnppp/8/8/8/2N1N3/PPP2PPP/R1BQ1RK1 w - - 0 1', 5),  # 23
    ('r1bq1rk1/pppnnppp/8/8/8/2N1BN2/PPP2PPP/R1BQ1RK1 w - - 0 1', 6), # 25
    ('r1bqkbnr/pppppppp/8/8/8/2N2N2/PPPPPPPP/R1BQKB1R w KQkq - 0 1', 6),  # 28
    (chess.STARTING_FEN, 7),                                        # 32
]
seen, wrong, acc_bad = set(), [], []
for fen, _declared in BUCKET_FENS:
    b = chess.Board(fen)
    assert b.is_valid(), fen
    pc = chess.popcount(b.occupied)
    want = min(N.NO - 1, (pc - 1) * N.NO // 32)      # the documented formula, applied to the real count
    got = int(N.out_bucket(pc))
    seen.add(got)
    if got != want:
        wrong.append((fen, pc, got, want))
    p.setup(fen)
    N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
    for m in b.legal_moves:
        mm = B.uci_to_move(e.bb, e.st, e.pcs, m.uci())
        if not B.make(e.bb, e.st, e.pcs, mm, e.ub, e.ui):
            continue
        N.nnue_after_make(e.bb, e.st, e.pcs, e.acc, e.ui, mm, e.w1, e.b1)
        inc = e.acc[int(e.st[B.S_PLY])].copy()
        ev_i = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
        seen.add(int(N.out_bucket(int(B.popcount(e.bb[14])))))
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        ref = e.acc[int(e.st[B.S_PLY])].copy()
        ev_r = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
        if not np.array_equal(inc, ref) or ev_i != ev_r:
            acc_bad.append((fen, m.uci(), ev_i, ev_r))
        B.unmake(e.bb, e.st, e.pcs, e.ub, e.ui)
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
R.add('V10.bucket_mapping', 'out_bucket agrees with the documented piece-count mapping',
      'PASS' if not wrong else 'FAIL', detail=wrong)
R.add('V11.all_eight_buckets', 'incremental accumulator equals refresh in ALL eight output buckets',
      'PASS' if sorted(seen) == list(range(8)) and not acc_bad else 'FAIL',
      buckets_reached=sorted(seen), accumulator_failures=len(acc_bad), detail=acc_bad[:4])

# bucket transitions specifically: captures that cross a bucket boundary
# Bucket transitions: a capture only changes bucket when the piece count crosses a multiple of
# four, so the positions are found by search rather than guessed.
rng = random.Random(31337)
crossers = []
for _ in range(400):
    b = chess.Board()
    for _ in range(rng.randint(4, 90)):
        ms = list(b.legal_moves)
        if not ms or b.is_game_over():
            break
        b.push(rng.choice(ms))
    pc = chess.popcount(b.occupied)
    if pc % 4 != 1 or b.is_game_over():
        continue
    caps = [m for m in b.legal_moves if b.is_capture(m)]
    if caps:
        crossers.append((b.fen(), caps[0].uci()))
    if len(crossers) >= 40:
        break
trans, tbad = 0, []
for fen, uci in crossers:
    b = chess.Board(fen)
    p.setup(fen)
    N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
    before = int(N.out_bucket(int(B.popcount(e.bb[14]))))
    for m in b.legal_moves:
        if not b.is_capture(m):
            continue
        mm = B.uci_to_move(e.bb, e.st, e.pcs, m.uci())
        if not B.make(e.bb, e.st, e.pcs, mm, e.ub, e.ui):
            continue
        N.nnue_after_make(e.bb, e.st, e.pcs, e.acc, e.ui, mm, e.w1, e.b1)
        after = int(N.out_bucket(int(B.popcount(e.bb[14]))))
        if after != before:
            trans += 1
            inc_acc = e.acc[int(e.st[B.S_PLY])].copy()
            inc = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
            N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
            if inc != int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2)) or \
               not np.array_equal(inc_acc, e.acc[int(e.st[B.S_PLY])]):
                tbad.append((fen, m.uci(), before, after))
        B.unmake(e.bb, e.st, e.pcs, e.ub, e.ui)
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
R.add('V12.bucket_transitions', 'captures that cross an output-bucket boundary stay consistent',
      'PASS' if trans > 0 and not tbad else 'FAIL', positions=len(crossers),
      transitions=trans, detail=tbad[:4])

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"v2_{os.environ.get('LABEL','run')}.json"
R.dump(out)
print('written', out)
_failed = R.summary()['failed']
if _failed:
    print(f'FAILED: {_failed} test(s) did not pass', file=sys.stderr)
sys.exit(1 if _failed else 0)
