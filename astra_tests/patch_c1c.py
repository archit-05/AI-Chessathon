"""C1c - a cached score must not stand in for checkmate.

C1 put dead material, the fifty-move rule and stalemate ahead of the transposition cutoff, but
CHECKMATE is discovered only at the end of both routines, where `legal == 0`. A transposition
entry for a mated position therefore cuts before the search ever learns the side to move has no
move at all. The audit reproduces it: with an exact entry stored for a mated position's key,
qsearch returns the stored score (900) instead of a mate score, on 120 of 1,200 probed states.

The check is placed at the CUTOFF, not at the node, so the cost falls only where a cutoff would
actually be taken at an in-check node - not on every node, and not on every in-check node.

Depends on: C2, C1, C1b.
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
src = S.read_text()

QOLD = '''        if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
            info[I_QS_TTCUT] += 1
            return s'''
QNEW = '''        if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
            # a stored score must never stand in for mate: at an in-check node, confirm the side
            # to move actually has a move before trusting it
            if (not in_chk) or has_legal_move(bb, st, pcs, mv, ub, ui):
                info[I_QS_TTCUT] += 1
                return s'''
assert src.count(QOLD) == 1, 'qsearch tt cutoff anchor not found exactly once'
src = src.replace(QOLD, QNEW)

SOLD = '''        if not pv_node and excluded == 0 and tt_depth(data) >= depth:
            s = tt_score(data, ply)
            f = tt_flag(data)
            if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
                return s'''
SNEW = '''        if not pv_node and excluded == 0 and tt_depth(data) >= depth:
            s = tt_score(data, ply)
            f = tt_flag(data)
            if f == TT_EXACT or (f == TT_LOWER and s >= beta) or (f == TT_UPPER and s <= alpha):
                if (not in_chk) or has_legal_move(bb, st, pcs, mv, ub, ui):
                    return s'''
assert src.count(SOLD) == 1, 'search tt cutoff anchor not found exactly once'
src = src.replace(SOLD, SNEW)

S.write_text(src)
py_compile.compile(str(S), doraise=True)
print('C1c applied to', D)
