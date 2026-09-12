"""Endgame honesty patch (finals night, Cause Table §18). Applies to a V8.5-derived build directory in place:
  1. bini_eval.endgame_scale: pawnless dead draws score 0 (identical piece sets, at most one minor each,
     two knights vs bare king); the existing 'less than a rook ahead -> score // 8' rule stays.
  2. bini_search.corrected / corr_update: no correction history in pawnless positions or with at most six pieces on
     the board (every pawnless position shares one pawn-structure slot and the two slots saturate at +-64 cp: the
     phantom '+60' of rounds 113/116/119; measured in the same games' rook+pawn endings: +72/+60/-38 with it,
     +22/+15/-7 without, Stockfish 0/0/0).
Switch: BINI_EG_DRAW (default 1); 0 reproduces the old behaviour exactly (verified node-identical).
usage: patch_endgame.py <build_dir>"""
import sys
from pathlib import Path
b = Path(sys.argv[1])
# ---- bini_eval.py
p = b / "bini_eval.py"; s = p.read_text()
assert "EG_DRAW" not in s, "already patched"
s = s.replace("MAT_MG = np.array(", "EG_DRAW = int(__import__('os').environ.get('BINI_EG_DRAW', '1'))  # 1: dead pawnless material draws score 0\nMAT_MG = np.array(", 1)
start = s.index("@njit(cache=False, boundscheck=False)\ndef endgame_scale(bb, score):")
end = s.index("    return score\n", s.index("if diff < MAT_MG[4]:", start)) + len("    return score\n")
new = '''@njit(cache=False, boundscheck=False)
def endgame_scale(bb, score):
    """Draw knowledge in front of the network (pawnless positions only; everything else is untouched).
    Dead draws score 0: identical piece sets (KRvKR, KQvKQ, KBvKB, KNvKN, KRRvKRR ...), at most one minor
    piece each (KBvKN, KBvK, KNvK), or two knights against a bare king. Otherwise, with no pawns a side
    needs at least a rook's worth of extra material to win (KRvKB, KRBvKR and the like), so such scores
    are divided by 8. Score is from the side to move's view; every rule is symmetric."""
    if bb[0] != ZERO or bb[6] != ZERO:
        return score
    n_w = popcount(bb[1]); b_w = popcount(bb[2]); r_w = popcount(bb[3]); q_w = popcount(bb[4])
    n_b = popcount(bb[7]); b_b = popcount(bb[8]); r_b = popcount(bb[9]); q_b = popcount(bb[10])
    npm_w = MAT_MG[2] * n_w + MAT_MG[3] * b_w + MAT_MG[4] * r_w + MAT_MG[5] * q_w
    npm_b = MAT_MG[2] * n_b + MAT_MG[3] * b_b + MAT_MG[4] * r_b + MAT_MG[5] * q_b
    if EG_DRAW != 0:
        if n_w == n_b and b_w == b_b and r_w == r_b and q_w == q_b:
            return 0
        if npm_w <= MAT_MG[3] and npm_b <= MAT_MG[3]:
            return 0
        if (n_w == 2 and npm_w == 2 * MAT_MG[2] and npm_b == 0) or (n_b == 2 and npm_b == 2 * MAT_MG[2] and npm_w == 0):
            return 0
    diff = npm_w - npm_b
    if diff < 0:
        diff = -diff
    if diff < MAT_MG[4]:
        return score // 8
    return score
'''
s = s[:start] + new + s[end:]; p.write_text(s)
# ---- bini_search.py
p = b / "bini_search.py"; s = p.read_text()
assert "EG_DRAW" not in s
i = s.index("from bini_eval import"); j = s.index("\n", i)
s = s[:j] + "\nfrom bini_eval import EG_DRAW  # pawnless positions: correction history off (one degenerate slot for all of them)" + s[j:]
old_c = "    if on == 0:\n        return static\n    c = scores[corr_index(bb, side, 0)] + scores[corr_index(bb, side, 1)]"
new_c = "    if on == 0:\n        return static\n    if EG_DRAW != 0 and ((bb[0] == ZERO and bb[6] == ZERO) or popcount(bb[14]) <= 6):\n        return static\n    c = scores[corr_index(bb, side, 0)] + scores[corr_index(bb, side, 1)]"
assert s.count(old_c) == 1; s = s.replace(old_c, new_c)
old_u = "def corr_update(scores, bb, side, raw_static, best, depth):\n    bonus = (best - raw_static) * depth // 4"
new_u = "def corr_update(scores, bb, side, raw_static, best, depth):\n    if EG_DRAW != 0 and ((bb[0] == ZERO and bb[6] == ZERO) or popcount(bb[14]) <= 6):\n        return\n    bonus = (best - raw_static) * depth // 4"
assert s.count(old_u) == 1; s = s.replace(old_u, new_u); p.write_text(s)
print(f"patched {b}: bini_eval.py + bini_search.py (switch BINI_EG_DRAW)")
