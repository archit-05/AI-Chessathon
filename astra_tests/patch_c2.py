"""C2 - repetition indexing and history boundaries.

Two edits, both in the candidate tree named by argv[1]:
  bini_search.py  is_repetition() rewritten on an explicit distance model, taking `ui` so it
                  can stop at a synthetic null-move ancestor; its single call site updated.
  bini_board.py   make_null() no longer advances the halfmove clock: a pass is not a move, so
                  it must neither age the fifty-move counter nor extend the repetition window.
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
B = D / 'bini_board.py'

# ---------------------------------------------------------------- bini_search.py
src = S.read_text()

OLD = '''@njit(cache=False, boundscheck=False)
def is_repetition(bb, st, ub, hist, hist_n):
    """Has the current position occurred before, on the search path or in the game?"""
    key = bb[15]
    ply = st[S_PLY]
    half = st[S_HALF]
    # search path: positions at ply-2, ply-4, ... (same side to move), no further back than
    # the last irreversible move
    i = ply - 2
    steps = 2
    while i >= 0 and steps <= half:
        if ub[i] == key:
            return True
        i -= 2
        steps += 2
    # game history before the root (hist[hist_n-1] is the root position), continue the count
    j = hist_n - 1 - (ply & 1) - (2 if (ply & 1) == 0 else 1) + 1
    # simpler: walk backwards over history entries with the same parity as the current ply
    j = hist_n - 1
    # hist_n-1 is the root (ply 0); position at ply p has same parity as root when p is even
    if (ply & 1) == 1:
        j -= 1
    while j >= 0 and steps <= half:
        if hist[j] == key:
            return True
        j -= 2
        steps += 2
    return False
'''

NEW = '''@njit(cache=False, boundscheck=False)
def is_repetition(bb, st, ub, ui, hist, hist_n):
    """Has the current position occurred before, on the search path or in the game before it?

    Explicit distance model. An ancestor with the same side to move sits 2, 4, 6, ... plies
    back. Distance d is the position at search ply ply-d while that is still inside the tree,
    and hist[hist_n-1-(d-ply)] once it reaches past the root; hist[hist_n-1] IS the root, so
    the root is visited exactly once and the distance counter never advances twice for it.

    The walk stops at the last irreversible move (distance may not exceed the halfmove clock)
    and at a synthetic null-move ancestor: a pass is not a move a real game could play, so a
    position on the far side of one is not a repetition of this one.
    """
    key = bb[15]
    ply = st[S_PLY]
    limit = st[S_HALF]
    # nearest null-move ancestor inside the window, if any
    lo = ply - limit
    if lo < 0:
        lo = 0
    i = ply - 1
    while i >= lo:
        if ui[i, 4] == 0:
            limit = ply - i - 1
            break
        i -= 1
    d = 2
    while d <= limit:
        if d <= ply:
            if ub[ply - d] == key:
                return True
        else:
            j = hist_n - 1 - (d - ply)
            if j < 0:
                return False
            if hist[j] == key:
                return True
        d += 2
    return False
'''

assert src.count(OLD) == 1, 'is_repetition anchor not found exactly once'
src = src.replace(OLD, NEW)

CALL_OLD = 'if st[S_HALF] >= 100 or is_repetition(bb, st, ub, hist, info[I_HIST_N]):'
CALL_NEW = 'if st[S_HALF] >= 100 or is_repetition(bb, st, ub, ui, hist, info[I_HIST_N]):'
assert src.count(CALL_OLD) == 1, 'is_repetition call site anchor not found exactly once'
src = src.replace(CALL_OLD, CALL_NEW)
assert 'is_repetition(bb, st, ub, hist' not in src, 'an old-signature call survived'

S.write_text(src)
py_compile.compile(str(S), doraise=True)

# ---------------------------------------------------------------- bini_board.py
bsrc = B.read_text()
NOLD = '''    key ^= ZOB_SIDE
    st[S_SIDE] = 1 - st[S_SIDE]
    st[S_HALF] += 1
    st[S_PLY] = ply + 1
    bb[15] = key
'''
NNEW = '''    key ^= ZOB_SIDE
    st[S_SIDE] = 1 - st[S_SIDE]
    # the halfmove clock is deliberately NOT advanced: a pass is not a move, so it must not
    # age the fifty-move counter (which would manufacture draws inside null subtrees) nor
    # widen the repetition window past the pass.  unmake_null restores it either way.
    st[S_PLY] = ply + 1
    bb[15] = key
'''
assert bsrc.count(NOLD) == 1, 'make_null anchor not found exactly once'
bsrc = bsrc.replace(NOLD, NNEW)
B.write_text(bsrc)
py_compile.compile(str(B), doraise=True)

print('C2 applied to', D)
