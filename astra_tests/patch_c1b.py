"""C1b - terminal semantics at the maximum-ply exits.

Both search() and qsearch() bail out with a raw evaluation once ply reaches MAX_PLY-1.  In
qsearch that bail-out sits BEFORE the terminal block, so the deepest nodes were still deciding
dead material and stalemate by neural evaluation.  In search the block runs first, but the
bail-out still returns an evaluation for a position that may be mate or stalemate.

Depends on: C2, then C1.
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
src = S.read_text()

# ---- qsearch: move the max-ply exit BELOW the terminal block ------------------------------
QOLD = '''    if ply >= MAX_PLY - 1:
        return evaluate(bb, st, pcs, acc, info, w2, b2)

    # Terminal semantics first: a stored bound, a corrected static score or a stand-pat cutoff
    # must never be allowed to stand in for a position the rules have already decided.  This
    # is the recursive frontier, not only the first main-search-to-qsearch call.
    if dead_material(bb):
        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    in_chk = in_check(bb, st)
'''
QNEW = '''    # Terminal semantics first: a stored bound, a corrected static score, a stand-pat cutoff or
    # the maximum-ply bail-out must never stand in for a position the rules have already
    # decided.  This is the recursive frontier, not only the first main-search-to-qsearch call,
    # and it is deliberately ABOVE the MAX_PLY exit so the deepest nodes are decided too.
    if dead_material(bb):
        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    in_chk = in_check(bb, st)
'''
assert src.count(QOLD) == 1, 'qsearch max-ply anchor not found exactly once'
src = src.replace(QOLD, QNEW)

# reinstate the exit after the terminal block, now with mate/stalemate handling
QOLD2 = '''        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    # transposition table: depth-0 entries from earlier quiescence searches cut immediately
    key = bb[15]
'''
QNEW2 = '''        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    if ply >= MAX_PLY - 1:
        # out of stack: still answer mate correctly rather than handing back an evaluation
        if in_chk and not has_legal_move(bb, st, pcs, mv, ub, ui):
            return -MATE + ply
        return evaluate(bb, st, pcs, acc, info, w2, b2)
    # transposition table: depth-0 entries from earlier quiescence searches cut immediately
    key = bb[15]
'''
assert src.count(QOLD2) == 1, 'qsearch tt anchor not found exactly once'
src = src.replace(QOLD2, QNEW2)

# ---- search: the max-ply exit must answer mate and stalemate too --------------------------
SOLD = '''    if ply >= MAX_PLY - 1:
        return evaluate(bb, st, pcs, acc, info, w2, b2)

    # transposition table
'''
SNEW = '''    if ply >= MAX_PLY - 1:
        # out of stack: the rule-draw block above has already run, but mate and stalemate are
        # decided by the legal==0 path further down, which this exit skips - so decide them here
        if not has_legal_move(bb, st, pcs, mv, ub, ui):
            if in_chk:
                return -MATE + ply
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
        return evaluate(bb, st, pcs, acc, info, w2, b2)

    # transposition table
'''
assert src.count(SOLD) == 1, 'search max-ply anchor not found exactly once'
src = src.replace(SOLD, SNEW)

S.write_text(src)
py_compile.compile(str(S), doraise=True)
print('C1b applied to', D)
