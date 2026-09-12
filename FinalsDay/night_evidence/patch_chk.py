"""Candidate CHK: quiet moves that give DIRECT check are exempt from LMP, futility and history
pruning in the main search (SEE pruning and LMR untouched).  Switchable: BINI_CHK_EXEMPT (default 1)."""
import sys, re
from pathlib import Path
d = Path(sys.argv[1])
s = (d / 'bini_search.py').read_text()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:60], s.count(old))
    s = s.replace(old, new)
rep("I_MAX_NODES = 26  # fixed-node gates", "I_CHK_EXEMPT = 27  # candidate CHK: direct checks exempt from quiet-move pruning (0 = baseline)\nI_MAX_NODES = 26  # fixed-node gates")
rep("""    # move generation and ordering
    base = ply * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, False)
    side = st[S_SIDE]
""", """    # move generation and ordering
    base = ply * MOVES_PER_PLY
    n = gen_moves(bb, st, pcs, mv, base, False)
    side = st[S_SIDE]
    # candidate CHK: checking squares for the side to move, so a quiet move that gives direct
    # check (destination in the checking set of its piece; discovered checks not detected) is
    # exempt from the quiet-move prunes below.  Same masks as the quiescence quiet-check filter.
    chk_on = info[I_CHK_EXEMPT] != 0
    eksq = lsb(bb[5 + (1 - side) * 6])
    chk_n = KNIGHT_ATT[eksq]
    chk_b = bishop_att(eksq, bb[14])
    chk_r = rook_att(eksq, bb[14])
    chk_p = PAWN_ATT[1 - side, eksq]
""")
rep("""        quiet = (not is_cap) and promo == 0
        # late move pruning and futility pruning of quiet moves
        hsum = 0
""", """        quiet = (not is_cap) and promo == 0
        direct_check = False
        if quiet and chk_on:
            to_c = (m >> 6) & 63
            pt_c = pcs[m & 63]
            if pt_c > 6:
                pt_c -= 6
            tb_c = SQBB[to_c]
            if pt_c == PAWN:
                direct_check = (chk_p & tb_c) != ZERO
            elif pt_c == KNIGHT:
                direct_check = (chk_n & tb_c) != ZERO
            elif pt_c == BISHOP:
                direct_check = (chk_b & tb_c) != ZERO
            elif pt_c == ROOK:
                direct_check = (chk_r & tb_c) != ZERO
            elif pt_c == QUEEN:
                direct_check = ((chk_b | chk_r) & tb_c) != ZERO
        # late move pruning and futility pruning of quiet moves
        hsum = 0
""")
rep("""        if quiet and not pv_node and not in_chk and legal > 0 and best > -MATE_IN_MAX:
            if depth <= 5 and quiets_tried""", """        if quiet and not direct_check and not pv_node and not in_chk and legal > 0 and best > -MATE_IN_MAX:
            if depth <= 5 and quiets_tried""")
(d / 'bini_search.py').write_text(s)
e = (d / 'bini_engine.py').read_text()
old = "        self.info[S.I_CALIB] = int(os.environ.get(\"BINI_CALIB\", \"0\"))"
assert e.count(old) == 1
e = e.replace(old, old + "\n        self.info[S.I_CHK_EXEMPT] = int(os.environ.get(\"BINI_CHK_EXEMPT\", \"1\"))  # candidate CHK")
(d / 'bini_engine.py').write_text(e)
print('patched', d)
