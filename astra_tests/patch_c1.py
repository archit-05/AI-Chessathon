"""C1 - centralised exact terminal semantics.

All edits are in bini_search.py of the candidate tree named by argv[1]:
  * import `attacked` from bini_board and add the two square-colour masks;
  * add dead_material(), king_has_move() and has_legal_move();
  * search(): dead material before the TT probe; checkmate outranks the fifty-move rule;
  * qsearch(): dead material, rule draws and stalemate before the TT cutoff and stand pat.

bini_eval.endgame_scale is deliberately left alone: it is a heuristic scale, not a rule.
"""
import sys, py_compile
from pathlib import Path

D = Path(sys.argv[1]).resolve()
S = D / 'bini_search.py'
src = S.read_text()

# ---- 1. import attacked ------------------------------------------------------------------
IOLD = '    ZERO,\n    attackers_to,\n'
INEW = '    ZERO,\n    attacked,\n    attackers_to,\n'
assert src.count(IOLD) == 1, 'import anchor not found exactly once'
src = src.replace(IOLD, INEW)

# ---- 2. helpers, inserted immediately before is_repetition -------------------------------
ANCHOR = '@njit(cache=False, boundscheck=False)\ndef is_repetition('
assert src.count(ANCHOR) == 1, 'is_repetition anchor not found exactly once'

HELPERS = '''# Square-colour complexes (a1 is dark), for the bishops-only dead-material class.
DARK_SQ = U64(0xAA55AA55AA55AA55)
LIGHT_SQ = U64(0x55AA55AA55AA55AA)


@njit(cache=False, boundscheck=False)
def dead_material(bb):
    """Exactly python-chess's is_insufficient_material(): no sequence of legal moves from
    here can end in checkmate for either side.

    With no pawns, rooks or queens on the board the classes reduce to:
      * no knights  -> drawn when every bishop stands on one colour complex (including none);
      * knights     -> drawn only for a single knight in total, and no bishops.
    KNN-K, KBN-K, KB-KN, KN-KN and opposite-colour bishops are all excluded: they are not
    dead, whatever a material heuristic may think of their practical value.
    """
    if (bb[0] | bb[6] | bb[3] | bb[9] | bb[4] | bb[10]) != ZERO:
        return False  # a pawn, rook or queen: cheap reject for almost every node
    knights = popcount(bb[1]) + popcount(bb[7])
    bishops = bb[2] | bb[8]
    if knights == 0:
        return (bishops & DARK_SQ) == ZERO or (bishops & LIGHT_SQ) == ZERO
    return knights == 1 and bishops == ZERO


@njit(cache=False, boundscheck=False)
def king_has_move(bb, st):
    """Cheap and exact: can the king of the side to move step anywhere legal?

    True proves the position is not stalemate without generating a single move, which is the
    common case; only when it is False does a caller pay for a full legal-move probe.  The
    king is lifted off the occupancy first so a slider behind it is not treated as blocked.
    """
    side = st[S_SIDE]
    kbb = bb[side * 6 + 5]
    ksq = lsb(kbb)
    t = KING_ATT[ksq] & ~bb[12 + side]
    if t == ZERO:
        return False
    occ = bb[14]
    own = bb[12 + side]
    bb[14] = occ & ~kbb
    bb[12 + side] = own & ~kbb
    bb[side * 6 + 5] = ZERO
    res = False
    while t != ZERO:
        to = lsb(t)
        t &= t - U64(1)
        if not attacked(bb, to, 1 - side):
            res = True
            break
    bb[14] = occ
    bb[12 + side] = own
    bb[side * 6 + 5] = kbb
    return res


# Scratch move slots for legality probes: past every ply the search can ever reach, so a
# probe can never disturb a live move list.  new_move_stack() allocates MAX_PLY+8 plies.
PROBE_BASE = (MAX_PLY + 4) * MOVES_PER_PLY


@njit(cache=False, boundscheck=False)
def has_legal_move(bb, st, pcs, mv, ub, ui):
    """Does the side to move have any legal move at all?

    Generates into the scratch slice rather than this ply's slots, and saves and restores this
    ply's undo entry, which make()/unmake() use as working storage.  The probe therefore leaves
    the board, the move lists, the undo stack and the accumulator exactly as it found them.
    """
    ply = st[S_PLY]
    sub = ub[ply]
    s0 = ui[ply, 0]
    s1 = ui[ply, 1]
    s2 = ui[ply, 2]
    s3 = ui[ply, 3]
    s4 = ui[ply, 4]
    n = gen_moves(bb, st, pcs, mv, PROBE_BASE, False)
    found = False
    for i in range(n):
        if make(bb, st, pcs, mv[PROBE_BASE + i], ub, ui):
            unmake(bb, st, pcs, ub, ui)
            found = True
            break
    ub[ply] = sub
    ui[ply, 0] = s0
    ui[ply, 1] = s1
    ui[ply, 2] = s2
    ui[ply, 3] = s3
    ui[ply, 4] = s4
    return found


@njit(cache=False, boundscheck=False)
def is_stalemate(bb, st, pcs, mv, ub, ui):
    """Not in check and no legal move.  The caller has usually established `not in_check`
    already; the king probe keeps the expensive path off the hot line."""
    if king_has_move(bb, st):
        return False
    return not has_legal_move(bb, st, pcs, mv, ub, ui)


'''
src = src.replace(ANCHOR, HELPERS + ANCHOR)

# ---- 3. search(): terminal block ----------------------------------------------------------
SOLD = '''    if not root:
        # draws by rule, checked before anything else so frontier nodes see them too
        if st[S_HALF] >= 100 or is_repetition(bb, st, ub, ui, hist, info[I_HIST_N]):
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
'''
SNEW = '''    if not root:
        # Draws by rule, checked before anything else - before the transposition table, before
        # correction history, before any pruning - so that no stored or corrected number can
        # stand in for a terminal one, and so frontier nodes see them too.
        if dead_material(bb):
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
        if st[S_HALF] >= 100:
            # checkmate outranks the fifty-move rule: only fall through for the mated case,
            # which the legal==0 path below scores as -MATE+ply with the right normalisation
            if not (in_check(bb, st) and not has_legal_move(bb, st, pcs, mv, ub, ui)):
                c = info[I_CONTEMPT]
                return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
        elif is_repetition(bb, st, ub, ui, hist, info[I_HIST_N]):
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
'''
assert src.count(SOLD) == 1, 'search terminal anchor not found exactly once (apply C2 first)'
src = src.replace(SOLD, SNEW)

# ---- 4. qsearch(): terminal block before the TT cutoff and stand pat -----------------------
QOLD = '''    in_chk = in_check(bb, st)
    # transposition table: depth-0 entries from earlier quiescence searches cut immediately
    key = bb[15]
'''
QNEW = '''    # Terminal semantics first: a stored bound, a corrected static score or a stand-pat cutoff
    # must never be allowed to stand in for a position the rules have already decided.  This
    # is the recursive frontier, not only the first main-search-to-qsearch call.
    if dead_material(bb):
        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    in_chk = in_check(bb, st)
    if st[S_HALF] >= 100:
        if not (in_chk and not has_legal_move(bb, st, pcs, mv, ub, ui)):
            c = info[I_CONTEMPT]
            return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    elif not in_chk and is_stalemate(bb, st, pcs, mv, ub, ui):
        # "no legal captures" is not "no legal moves": without this the stand-pat below
        # returns a neural evaluation for a position that is over.
        c = info[I_CONTEMPT]
        return -c if st[S_SIDE] == info[I_ROOT_SIDE] else c
    # transposition table: depth-0 entries from earlier quiescence searches cut immediately
    key = bb[15]
'''
assert src.count(QOLD) == 1, 'qsearch anchor not found exactly once'
src = src.replace(QOLD, QNEW)

S.write_text(src)
py_compile.compile(str(S), doraise=True)
print('C1 applied to', D)
