"""Point 3: quiescence repetition and counter-check coverage.

qsearch has no repetition test. The question is whether it CAN revisit a position, and if so
whether that is bounded. This measures it rather than reasoning about it:

  * how deep does quiescence actually recurse on check-heavy positions (I_SELDEPTH)?
  * can a position repeat inside quiescence at all, given which move classes it generates?

Structure of the generator, which bounds the answer: at qdepth 0 quiescence generates captures,
promotions AND quiet checks; at every deeper node `quiet_checks` requires `qdepth == 0`, so only
captures are generated - or, when in check, evasions. Captures and promotions are irreversible,
so a cycle can only be sustained by quiet checks and quiet evasions, and quiet checks exist at
exactly one ply of the recursion.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, Results, S, B, N, chess
import numpy as np

R = Results(os.environ.get('BINI_DIR', 'bini_v8_ship'))
p = Probe(); e = p.e

CHECKY = [
    ('perpetual-ish', '6k1/5ppp/8/8/8/7Q/5PPP/6K1 w - - 0 1'),
    ('exposed king',  'r1bq1rk1/ppp2ppp/2n5/3Q4/2B5/8/PPP2PPP/RNB2RK1 w - - 0 1'),
    ('open king',     '8/8/8/3k4/8/8/3Q4/3K4 w - - 0 1'),
    ('kiwipete',      'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'),
    ('rook checks',   '4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1'),
    ('queen v king',  '8/8/4k3/8/8/8/3Q4/4K3 w - - 0 1'),
]
rows = []
worst = 0
for name, fen in CHECKY:
    for qs_checks in (0, 1):
        p.setup(fen, budget=300.0); p.clear_tt(); p.clear_corr()
        e.info[S.I_QS_CHECKS] = qs_checks
        e.info[S.I_SELDEPTH] = 0
        e.st[B.S_PLY] = 1
        N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
        v = p.qsearch()
        sd = int(e.info[S.I_SELDEPTH])
        e.st[B.S_PLY] = 0
        worst = max(worst, sd)
        rows.append(dict(position=name, qs_checks=qs_checks, seldepth=sd, score=int(v)))
R.add('Q1.quiescence_depth_bounded',
      'quiescence terminates well inside MAX_PLY on check-heavy positions',
      'PASS' if worst < B.MAX_PLY - 2 else 'FAIL',
      max_seldepth=worst, max_ply=int(B.MAX_PLY), samples=len(rows))

# Can a repetition actually occur inside quiescence? Walk the move classes it would generate.
def qs_reachable_cycle(fen, max_ply=6):
    """Search for a position repeat using only the move classes quiescence generates:
    qdepth 0 -> captures/promotions/quiet checks; deeper -> captures, or evasions when in check."""
    start = chess.Board(fen)
    seen_cycle = []
    def rec(b, qdepth, path, keys):
        if len(path) >= max_ply:
            return
        in_chk = b.is_check()
        if in_chk:
            moves = list(b.legal_moves)                       # evasions: all legal moves
        elif qdepth == 0:
            moves = [m for m in b.legal_moves
                     if b.is_capture(m) or m.promotion or b.gives_check(m)]
        else:
            moves = [m for m in b.legal_moves if b.is_capture(m) or m.promotion]
        for m in moves:
            b.push(m)
            k = b._transposition_key()
            if k in keys:
                seen_cycle.append(path + [m.uci()])
            else:
                rec(b, qdepth - 1, path + [m.uci()], keys | {k})
            b.pop()
            if seen_cycle:
                return
    rec(start, 0, [], {start._transposition_key()})
    return seen_cycle

cycles = []
for name, fen in CHECKY:
    c = qs_reachable_cycle(fen)
    if c:
        cycles.append((name, fen, c[0]))
R.add('Q2.cycle_reachability',
      'can a position repeat inside the move classes quiescence generates?',
      'INFO', positions=len(CHECKY), cycles_found=len(cycles), detail=cycles[:2],
      note='quiet checks exist only at qdepth 0; every deeper node generates captures or '
           'evasions, and captures are irreversible - so a cycle cannot be sustained')

R.add('Q3.status', 'quiescence repetition detection', 'INFO',
      implemented=False,
      resolution='EXPLICITLY UNRESOLVED - see Report 02. Quiescence does not test repetition. '
                 'It is bounded (Q1) and a sustained cycle is not reachable through its move '
                 'classes (Q2), so this is a known approximation, not a demonstrated defect. '
                 'No patch is proposed for it before the lock.')

out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"qsrep_{os.environ.get('LABEL','run')}.json"
R.dump(out, extra=dict(samples=rows))
print('written', out)
_f = R.summary()['failed']
sys.exit(1 if _f else 0)
