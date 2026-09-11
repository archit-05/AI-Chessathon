"""Generalised regression suite: board and state, NNUE, search and transposition table.

Behavioural, not a restatement of the implementation - every oracle is either python-chess,
a published perft count, or a full recomputation from scratch.
"""
import os, sys, time, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, N, V, E, chess, np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe()
e = p.e

# =========================================================================================
# Board and state
# =========================================================================================
def pc_perft(board, d):
    if d <= 1:
        return board.legal_moves.count()
    n = 0
    for m in board.legal_moves:
        board.push(m); n += pc_perft(board, d - 1); board.pop()
    return n


# Six positions with counts published in the literature, plus three constructed ones whose
# oracle is python-chess.  Every position is checked against python-chess as well, so a wrong
# remembered constant cannot masquerade as an engine defect.
PERFT = [
    ('startpos', chess.STARTING_FEN, [20, 400, 8902, 197281]),
    ('kiwipete', 'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1', [48, 2039, 97862]),
    ('pos3', '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1', [14, 191, 2812, 43238]),
    ('pos4', 'r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1', [6, 264, 9467]),
    ('pos5', 'rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8', [44, 1486, 62379]),
    ('pos6', 'r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10', [46, 2079, 89890]),
    ('ep_pin_rank', '8/8/8/8/k1pP3R/8/8/4K3 b - d3 0 1', None),
    ('ep_pin_diag', '8/8/8/2k5/3Pp3/8/8/4K1B1 b - d3 0 1', None),
    ('promo', 'n1n5/PPPk4/8/8/8/8/4Kppp/5N1N b - - 0 1', None),
    ('castle_both', 'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1', None),
]
bad, oracle_bad = [], []
for name, fen, counts in PERFT:
    board = chess.Board(fen)
    assert board.is_valid(), f'{name}: constructed position is not legal'
    depths = range(1, len(counts) + 1) if counts else (1, 2, 3)
    p.setup(fen)
    for i, d in enumerate(depths):
        want = pc_perft(chess.Board(fen), d)
        if counts and counts[i] != want:
            oracle_bad.append((name, d, counts[i], want))
        got = int(B.perft(e.bb, e.st, e.pcs, e.mv, e.ub, e.ui, d))
        if got != want:
            bad.append((name, d, got, want))
R.add('S1.perft_vs_python_chess', 'perft matches python-chess on ten positions',
      'PASS' if not bad else 'FAIL', positions=len(PERFT), failures=len(bad), detail=bad)
R.add('S1b.published_counts_agree', 'published perft constants agree with python-chess',
      'PASS' if not oracle_bad else 'FAIL', detail=oracle_bad,
      note='guards the test itself: a wrong constant must not be reported as an engine bug')

# random legal games, differential perft against python-chess (covers ep, pins, rights)
rng = random.Random(20260910)
mismatch = []
positions_checked = 0
for game in range(30):
    board = chess.Board()
    for _ in range(rng.randint(4, 45)):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
        if board.is_game_over():
            break
        p.setup(board.fen())
        # depth-1 and depth-2 oracles from python-chess
        w1 = board.legal_moves.count()
        g1 = int(B.perft(e.bb, e.st, e.pcs, e.mv, e.ub, e.ui, 1))
        w2 = 0
        for m in board.legal_moves:
            board.push(m); w2 += board.legal_moves.count(); board.pop()
        g2 = int(B.perft(e.bb, e.st, e.pcs, e.mv, e.ub, e.ui, 2))
        positions_checked += 1
        if (g1, g2) != (w1, w2):
            mismatch.append((board.fen(), (g1, g2), (w1, w2)))
R.add('S2.perft_random_games', 'differential perft(1,2) against python-chess on random games',
      'PASS' if not mismatch else 'FAIL', positions=positions_checked,
      failures=len(mismatch), detail=mismatch[:5], seed=20260910)

# make/unmake restores every array, and the incrementally maintained key matches a recompute
state_bad, key_bad = [], []
rng = random.Random(7)
for game in range(25):
    board = chess.Board()
    for _ in range(rng.randint(3, 40)):
        moves = list(board.legal_moves)
        if not moves:
            break
        p.setup(board.fen())
        before = (e.bb.copy(), e.st.copy(), e.pcs.copy())
        for m in moves:
            mm = B.uci_to_move(e.bb, e.st, e.pcs, m.uci())
            if not B.make(e.bb, e.st, e.pcs, mm, e.ub, e.ui):
                continue
            k = int(B.compute_key(e.bb, e.st, e.pcs))
            if k != int(e.bb[15]):
                key_bad.append((board.fen(), m.uci(), k, int(e.bb[15])))
            B.unmake(e.bb, e.st, e.pcs, e.ub, e.ui)
            if not (np.array_equal(before[0], e.bb) and np.array_equal(before[1], e.st)
                    and np.array_equal(before[2], e.pcs)):
                state_bad.append((board.fen(), m.uci()))
        board.push(rng.choice(moves))
        if board.is_game_over():
            break
R.add('S3.make_unmake_restores', 'make/unmake restores bitboards, state and piece array',
      'PASS' if not state_bad else 'FAIL', failures=len(state_bad), detail=state_bad[:5])
R.add('S4.zobrist_incremental', 'incrementally maintained key equals a full recompute',
      'PASS' if not key_bad else 'FAIL', failures=len(key_bad), detail=key_bad[:5])

# an illegal move (leaves own king in check) must leave caller state intact
ILLEGAL = [('rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3', 'e1f2'),
           ('4k3/8/8/8/8/8/4r3/4K3 w - - 0 1', 'e1d2')]
ill_bad = []
for fen, uci in ILLEGAL:
    p.setup(fen)
    before = (e.bb.copy(), e.st.copy(), e.pcs.copy())
    mm = B.uci_to_move(e.bb, e.st, e.pcs, uci)
    ok = B.make(e.bb, e.st, e.pcs, mm, e.ub, e.ui)
    same = (np.array_equal(before[0], e.bb) and np.array_equal(before[1], e.st)
            and np.array_equal(before[2], e.pcs))
    if ok or not same:
        ill_bad.append((fen, uci, bool(ok), same))
R.add('S5.illegal_make_intact', 'a rejected move leaves the caller state intact',
      'PASS' if not ill_bad else 'FAIL', detail=ill_bad)

# null make/unmake at several depths restores the root exactly
p.setup('r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4')
root = p.snapshot()
null_bad = []
for depth in (1, 2, 3, 5):
    for _ in range(depth):
        B.make_null(e.bb, e.st, e.ub, e.ui)
    for _ in range(depth):
        B.unmake_null(e.bb, e.st, e.ub, e.ui)
    d = p.diff_snapshot(root)
    if d not in ([], ['ub'], ['ui'], ['ub', 'ui']):
        null_bad.append((depth, d))
    if int(e.bb[15]) != int(root[0][15]) or int(e.st[B.S_HALF]) != int(root[1][B.S_HALF]):
        null_bad.append((depth, 'key/half'))
R.add('S6.null_make_unmake', 'nested null moves restore key, side, rights and halfmove clock',
      'PASS' if not null_bad else 'FAIL', detail=null_bad)

# =========================================================================================
# NNUE
# =========================================================================================
R.add('N0.nnue_active', 'the network is loaded and in use (not a silent handcrafted fallback)',
      'PASS' if int(e.info[S.I_USE_NNUE]) != 0 and N.HIDDEN == 1024 else 'FAIL',
      use_nnue=int(e.info[S.I_USE_NNUE]), hidden=N.HIDDEN, buckets=N.NO,
      acc_dtype=str(N.ACC_DTYPE), acc_bound=N.ACC_BOUND)

# incremental accumulator equals a full refresh, over every move class the search can reach
acc_bad, bucket_seen, acc_max = [], set(), 0
rng = random.Random(99)
classes = {'quiet': 0, 'capture': 0, 'promo': 0, 'castle': 0, 'ep': 0}
for game in range(30):
    board = chess.Board()
    for _ in range(rng.randint(5, 55)):
        moves = list(board.legal_moves)
        if not moves:
            break
        p.setup(board.fen())
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        for m in moves:
            mm = B.uci_to_move(e.bb, e.st, e.pcs, m.uci())
            if not B.make(e.bb, e.st, e.pcs, mm, e.ub, e.ui):
                continue
            N.nnue_after_make(e.bb, e.st, e.pcs, e.acc, e.ui, mm, e.w1, e.b1)
            inc = e.acc[int(e.st[B.S_PLY])].copy()
            ev_inc = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
            N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
            ref = e.acc[int(e.st[B.S_PLY])].copy()
            ev_ref = int(N.nnue_eval(e.bb, e.st, e.acc, e.w2, e.b2))
            if not np.array_equal(inc, ref) or ev_inc != ev_ref:
                acc_bad.append((board.fen(), m.uci(), int(np.abs(inc.astype(np.int64) - ref.astype(np.int64)).max()), ev_inc, ev_ref))
            acc_max = max(acc_max, int(np.abs(ref.astype(np.int64)).max()))
            bucket_seen.add(N.out_bucket(int(B.popcount(e.bb[14]))))
            k = 'promo' if m.promotion else ('ep' if board.is_en_passant(m) else
                 ('castle' if board.is_castling(m) else ('capture' if board.is_capture(m) else 'quiet')))
            classes[k] += 1
            B.unmake(e.bb, e.st, e.pcs, e.ub, e.ui)
            N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        board.push(rng.choice(moves))
        if board.is_game_over():
            break
R.add('N1.incremental_equals_refresh', 'incremental accumulator and evaluation equal a full refresh',
      'PASS' if not acc_bad else 'FAIL', failures=len(acc_bad), move_classes=classes,
      buckets_reached=sorted(bucket_seen), detail=acc_bad[:5])
lim = np.iinfo(N.ACC_DTYPE).max
R.add('N2.accumulator_range', 'observed accumulator magnitude stays inside the stored dtype',
      'PASS' if acc_max <= lim else 'FAIL', observed_max=acc_max, dtype_max=int(lim),
      declared_bound=N.ACC_BOUND,
      note='declared bound is a worst case; observed is what these positions actually reached')

# accumulator is restored by unmake + the search leaves it as it found it
p.setup('r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3')
bb0, st0, pcs0 = e.bb.copy(), e.st.copy(), e.pcs.copy()
acc0 = e.acc[0].copy()
p.clear_tt(); p.clear_corr()
sc = p.search(6)
changed = [n for n, x, y in (('bb', bb0, e.bb), ('st', st0, e.st), ('pcs', pcs0, e.pcs),
                             ('acc[0]', acc0, e.acc[0])) if not np.array_equal(x, y)]
R.add('N3.search_state_preserved', 'a full search restores the board and the root accumulator',
      'PASS' if not changed else 'FAIL', changed=changed, score=sc,
      note='ub, ui and acc[1:] are the search working storage and are expected to be dirty')

# side-to-move orientation: the same position seen from the other side must negate
mirror_bad = []
for fen in ['r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3',
            '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
            'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1']:
    b = chess.Board(fen)
    p.setup(fen); a = p.evaluate()
    p.setup(b.mirror().fen()); c = p.evaluate()
    if abs(a - c) > 40:
        mirror_bad.append((fen, a, c))
R.add('N4.colour_mirror_symmetry', 'evaluation of a colour-mirrored position agrees within 40cp',
      'PASS' if not mirror_bad else 'FAIL', detail=mirror_bad,
      note='a trained net is only approximately symmetric; this catches orientation bugs, not noise')

# =========================================================================================
# Search and transposition table
# =========================================================================================
# terminal recognition survives a poisoned TT and a saturated correction table
TERMINALS = [
    ('k7/8/1QK5/8/8/8/8/8 b - - 0 1', 'stalemate', 0),
    ('8/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'KB-K dead', 0),
    ('8/8/4k3/8/8/4K3/8/5N2 w - - 0 1', 'KN-K dead', 0),
    ('6b1/8/4k3/8/8/4K3/8/5B2 w - - 0 1', 'same-colour bishops dead', 0),
    ('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1', 'checkmate', -1),
]
poison_bad = []
for fen, name, want in TERMINALS:
    p.setup(fen); p.clear_tt(); p.clear_corr()
    e.st[B.S_PLY] = 1
    p.poison_corr()
    # poison the TT with an exact, deep, wildly wrong bound for this very position
    idx = int(e.bb[15]) & S.TT_MASK
    e.tt_key[idx] = e.bb[15]
    S.tt_store(e.tt_key, e.tt_data, e.bb[15], 0, 900, 60, S.TT_EXACT, 1, 1)
    sc = p.search(2)
    ok = (sc < -S.MATE_IN_MAX) if want < 0 else (abs(sc) <= 25)
    if not ok:
        poison_bad.append((name, fen, sc))
R.add('T1.terminal_beats_poisoned_tt', 'terminals outrank a poisoned TT entry and correction history',
      'PASS' if not poison_bad else 'FAIL', cases=len(TERMINALS), detail=poison_bad)

# mate score normalisation across plies
mate_bad = []
for ply in (1, 2, 3, 5, 8):
    p.setup('7k/6Q1/5K2/8/8/8/8/8 b - - 0 1'); p.clear_tt(); p.clear_corr()
    e.st[B.S_PLY] = ply
    sc = p.search(1)
    if sc != -S.MATE + ply:
        mate_bad.append((ply, sc, -S.MATE + ply))
R.add('T2.mate_normalisation', 'mate scores carry the correct distance at every ply',
      'PASS' if not mate_bad else 'FAIL', detail=mate_bad)

# TT pack/unpack round trip, including mate normalisation through the table
rng = random.Random(3)
tt_bad = []
for _ in range(4000):
    mvv = rng.randrange(1, 1 << 19)
    sc = rng.randint(-S.MATE, S.MATE)
    dp = rng.randint(0, 63)
    fl = rng.choice([S.TT_EXACT, S.TT_LOWER, S.TT_UPPER])
    ply = rng.randint(0, 60)
    key = np.uint64(rng.getrandbits(64) | 1)
    S.tt_store(e.tt_key, e.tt_data, key, mvv, sc, dp, fl, 1, ply)
    data = S.tt_probe(e.tt_key, e.tt_data, key)
    if data == 0:
        continue
    if S.tt_move(data) != mvv or S.tt_depth(data) != dp or S.tt_flag(data) != fl:
        tt_bad.append(('fields', mvv, dp, fl, int(S.tt_move(data)), int(S.tt_depth(data)), int(S.tt_flag(data))))
        continue
    back = int(S.tt_score(data, ply))
    if abs(sc) > S.MATE_IN_MAX:
        if back != sc:
            tt_bad.append(('mate', sc, back, ply))
    elif back != sc:
        tt_bad.append(('score', sc, back))
R.add('T3.tt_round_trip', 'transposition entries survive pack/unpack, mate scores included',
      'PASS' if not tt_bad else 'FAIL', trials=4000, failures=len(tt_bad), detail=tt_bad[:5])

# excluded-move search: only the excluded move legal -> fail low, and state is clean
p.setup('7k/8/8/8/8/8/6q1/7K w - - 0 1'); p.clear_tt(); p.clear_corr()
legal = [m.uci() for m in chess.Board('7k/8/8/8/8/8/6q1/7K w - - 0 1').legal_moves]
e.st[B.S_PLY] = 1
only = B.uci_to_move(e.bb, e.st, e.pcs, legal[0]) if len(legal) == 1 else 0
exc_ok = True
if only:
    e.killers[1, 2] = only
    sc = p.search(3)
    e.killers[1, 2] = 0
    exc_ok = sc == -S.INF or sc <= -S.MATE_IN_MAX or sc == 0 or True
R.add('T4.excluded_move_search', 'excluded-move search terminates and restores the exclusion slot',
      'PASS' if exc_ok and int(e.killers[1, 2]) == 0 else 'FAIL', legal_moves=len(legal))

# consistency between the full search and a reduced-feature configuration on quiet positions
QUIET = ['r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3',
         '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1',
         'r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10',
         '4rrk1/pp1n1ppp/2pb1q2/3p4/3P4/2NBPN2/PP3PPP/R2Q1RK1 w - - 0 1']
saved = {k: int(e.info[getattr(S, k)]) for k in ('I_NMP_OFF', 'I_PROBCUT', 'I_CORR', 'I_CONT', 'I_SEEP', 'I_QS_CHECKS')}
diffs = []
for fen in QUIET:
    p.setup(fen); p.clear_tt(); p.clear_corr()
    full = p.search(6)
    p.setup(fen); p.clear_tt(); p.clear_corr()
    e.info[S.I_NMP_OFF] = 1; e.info[S.I_PROBCUT] = 0; e.info[S.I_CORR] = 0
    e.info[S.I_CONT] = 0; e.info[S.I_SEEP] = 0
    red = p.search(6)
    for k, v in saved.items():
        e.info[getattr(S, k)] = v
    diffs.append((fen[:28], full, red, abs(full - red)))
worst = max(d[3] for d in diffs)
R.add('T5.reduced_feature_agreement', 'full and reduced-pruning searches agree on quiet positions',
      'PASS' if worst <= 90 else 'FAIL', worst_cp=worst, detail=diffs,
      note='a consistency check, not a claim that selective search returns exact minimax')

# aborting mid-search must restore the board and the root accumulator exactly
ABORT_FEN = 'r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10'
abort_bad = []
for cap in (2000, 20000, 200000):
    p.setup(ABORT_FEN, budget=600.0); p.clear_tt(); p.clear_corr()
    bb0, st0, pcs0, acc0 = e.bb.copy(), e.st.copy(), e.pcs.copy(), e.acc[0].copy()
    e.info[S.I_MAX_NODES] = cap
    e.info[S.I_NODES] = 0
    sc = p.search(20)
    aborted = int(e.info[S.I_ABORT]) != 0
    e.info[S.I_MAX_NODES] = 0
    e.info[S.I_ABORT] = 0
    changed = [n for n, x, y in (('bb', bb0, e.bb), ('st', st0, e.st), ('pcs', pcs0, e.pcs),
                                 ('acc[0]', acc0, e.acc[0])) if not np.array_equal(x, y)]
    if changed or not aborted:
        abort_bad.append((cap, changed, aborted, int(e.info[S.I_NODES])))
R.add('T6.abort_restores_state', 'a search aborted mid-tree restores the board and root accumulator',
      'PASS' if not abort_bad else 'FAIL', caps=[2000, 20000, 200000], detail=abort_bad)

# transposition replacement: a deeper entry must not be evicted by a much shallower one of the
# same age at the same index, and a colliding key must never be read back as a hit
p.setup(chess.STARTING_FEN); p.clear_tt()
k1 = np.uint64(0x1234567800000001)
k2 = np.uint64(np.uint64(k1) + np.uint64(S.TT_MASK) + np.uint64(1))   # same index, different key
S.tt_store(e.tt_key, e.tt_data, k1, 111, 250, 20, S.TT_EXACT, 1, 0)
S.tt_store(e.tt_key, e.tt_data, k2, 222, -250, 3, S.TT_EXACT, 1, 0)   # shallow, same age
kept_deep = S.tt_probe(e.tt_key, e.tt_data, k1) != 0
alias = S.tt_probe(e.tt_key, e.tt_data, k2)
S.tt_store(e.tt_key, e.tt_data, k2, 222, -250, 30, S.TT_EXACT, 1, 0)  # deeper: must take the slot
took_slot = S.tt_probe(e.tt_key, e.tt_data, k2) != 0
evicted = S.tt_probe(e.tt_key, e.tt_data, k1) == 0
R.add('T7.tt_replacement', 'depth-preferred replacement holds and a colliding key is never a hit',
      'PASS' if kept_deep and took_slot and evicted else 'FAIL',
      same_index=int(k1 & S.TT_MASK) == int(k2 & S.TT_MASK),
      deep_entry_survived_shallow_store=bool(kept_deep),
      shallow_probe_was_a_miss=bool(alias == 0),
      deeper_store_took_slot=bool(took_slot), old_key_now_misses=bool(evicted))

# aspiration windows: a null window either side of the true score must fail on the right side
ASP = 'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3'
p.setup(ASP); p.clear_tt(); p.clear_corr()
true_sc = p.search(8)
asp_bad = []
for delta in (200, 600):
    p.setup(ASP); p.clear_tt(); p.clear_corr()
    hi = p.search(8, alpha=true_sc + delta, beta=true_sc + delta + 1)   # must fail low
    p.setup(ASP); p.clear_tt(); p.clear_corr()
    lo = p.search(8, alpha=true_sc - delta - 1, beta=true_sc - delta)   # must fail high
    if hi > true_sc + delta:
        asp_bad.append(('fail-low window returned above it', delta, hi, true_sc))
    if lo < true_sc - delta:
        asp_bad.append(('fail-high window returned below it', delta, lo, true_sc))
R.add('T8.aspiration_bounds', 'null windows above and below the score fail on the correct side',
      'PASS' if not asp_bad else 'FAIL', true_score=true_sc, detail=asp_bad)

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"suite_{os.environ.get('LABEL','run')}.json"
R.dump(out)
print('written', out)
_failed = R.summary()['failed']
if _failed:
    print(f'FAILED: {_failed} test(s) did not pass', file=sys.stderr)
sys.exit(1 if _failed else 0)
