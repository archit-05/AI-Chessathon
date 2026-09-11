"""C1d - a cached score must not stand in for STALEMATE either.

C1c guarded the transposition cutoff with `(not in_chk) or has_legal_move(...)`. That closes
checkmate but does nothing for stalemate, where by definition the king is NOT in check, so the
`not in_chk` arm short-circuits and the stored score is returned. Reproduced directly: with an
exact entry planted for the stalemate FEN `k7/8/1QK5/8/8/8/8/8 b - -`, a null-window search
returns 900 instead of the configured draw utility of -20.

The guard becomes unconditional at both cutoff sites: a transposition cutoff is only taken once
the side to move is known to have a legal move. Empty-table pruning paths (reverse futility,
null move, ProbCut) were measured separately and return the correct utility already, so they
are left alone rather than being guarded speculatively.

Depends on: C2, C1, C1b, C1c.
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
src = S.read_text()

QOLD = '''            # a stored score must never stand in for mate: at an in-check node, confirm the side
            # to move actually has a move before trusting it
            if (not in_chk) or has_legal_move(bb, st, pcs, mv, ub, ui):'''
QNEW = '''            # a stored score must never stand in for a terminal position.  The probe is
            # unconditional: checkmate needs it when in check, STALEMATE needs it when not,
            # and the cost falls only where a cutoff would actually be taken.
            if has_legal_move(bb, st, pcs, mv, ub, ui):'''
assert src.count(QOLD) == 1, 'qsearch C1c guard not found exactly once'
src = src.replace(QOLD, QNEW)

SOLD = '''            if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
                if (not in_chk) or has_legal_move(bb, st, pcs, mv, ub, ui):
                    return s'''
SNEW = '''            if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
                if has_legal_move(bb, st, pcs, mv, ub, ui):
                    return s'''
assert src.count(SOLD) == 1, 'search C1c guard not found exactly once'
src = src.replace(SOLD, SNEW)

S.write_text(src)
py_compile.compile(str(S), doraise=True)
print('C1d applied to', D)
