"""C2b - separate a real draw claim from the search-cycle heuristic.

The baseline, and C2 with it, treat ANY earlier occurrence as a draw - including a single
occurrence in the game before the root.  That is a SECOND occurrence: FIDE needs a third, and
so does the referee, which adjudicates with board.outcome(claim_draw=True) and first reports
THREEFOLD_REPETITION only once a third occurrence is available.  Scoring a second occurrence as
a draw is therefore a false draw, not a conservative one.

This patch replaces is_repetition with repetition_kind, which returns:
    0  no draw
    1  a cycle inside the search tree  - a NAMED heuristic: the side that wants the repetition
       can force it, so the standard engine convention scores it as drawn
    2  a genuine third occurrence reached through pre-root game history - a real claim

Both are scored as draws, but they are different claims, they are tested separately, and a bare
second occurrence in game history is no longer one of them.

Depends on: C2 (rewrites what C2 installed).
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
src = S.read_text()

OLD_START = '@njit(cache=False, boundscheck=False)\ndef is_repetition(bb, st, ub, ui, hist, hist_n):'
assert src.count(OLD_START) == 1, 'is_repetition anchor not found (apply C2 first)'
start = src.index(OLD_START)
end = src.index('@njit(cache=False, boundscheck=False)\ndef tt_probe(', start)
old_block = src[start:end]

NEW = '''@njit(cache=False, boundscheck=False)
def repetition_kind(bb, st, ub, ui, hist, hist_n):
    """How, if at all, does the current position repeat?

        0  not a draw
        1  a cycle inside the SEARCH TREE.  This is a heuristic, and it is named as one: the
           side that wants the repetition can force it, so every strong engine scores a second
           occurrence inside its own tree as drawn.  It is not a FIDE claim.
        2  a genuine THIRD occurrence, counting the game before the root.  This is a real claim
           and it matches what the referee adjudicates with outcome(claim_draw=True).

    A single earlier occurrence in game history is a SECOND occurrence and returns 0.  Treating
    it as a draw - which the baseline does - invents a claim that neither FIDE nor the referee
    would grant.

    Distances use the explicit model: an ancestor with the same side to move sits d = 2, 4, 6...
    plies back; d is ub[ply-d] inside the tree and hist[hist_n-1-(d-ply)] past the root, where
    hist[hist_n-1] is the root itself.  The walk stops at the last irreversible move and at a
    synthetic null-move ancestor, which is not a move a real game could have played.
    """
    key = bb[15]
    ply = st[S_PLY]
    limit = st[S_HALF]
    lo = ply - limit
    if lo < 0:
        lo = 0
    i = ply - 1
    while i >= lo:
        if ui[i, 4] == 0:
            limit = ply - i - 1
            break
        i -= 1
    hist_hits = 0
    d = 2
    while d <= limit:
        if d <= ply:
            if ub[ply - d] == key:
                return 1
        else:
            j = hist_n - 1 - (d - ply)
            if j < 0:
                return 0
            if hist[j] == key:
                hist_hits += 1
                if hist_hits >= 2:
                    return 2
        d += 2
    return 0


@njit(cache=False, boundscheck=False)
def is_repetition(bb, st, ub, ui, hist, hist_n):
    """Draw by repetition under either reading. Kept so callers and tests read naturally."""
    return repetition_kind(bb, st, ub, ui, hist, hist_n) != 0


'''
src = src[:start] + NEW + src[end:]
S.write_text(src)
py_compile.compile(str(S), doraise=True)
print('C2b applied to', D)
