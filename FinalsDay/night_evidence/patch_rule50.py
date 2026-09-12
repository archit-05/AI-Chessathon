"""Anti-shuffle patch (finals, from practice round 14): scale the static evaluation toward 0 as the fifty-move counter
grows — Stockfish's rule: v = v * (200 - rule50_plies) / 200. A pawn move or capture resets the counter and restores the
full evaluation, so when the engine believes it is better it is rewarded for making progress instead of shuffling into
a fifty-move draw; when it believes it is worse, shuffling toward the draw becomes relatively more attractive. Applied
after endgame_scale in bini_search.evaluate; symmetric in sign; switch BINI_RULE50 (default 1, 0 = old behaviour).
usage: patch_rule50.py <build_dir>"""
import sys
from pathlib import Path
p = Path(sys.argv[1]) / "bini_search.py"; s = p.read_text()
assert "RULE50" not in s
old = """def evaluate(bb, st, pcs, acc, info, w2, b2):
    if info[I_USE_NNUE] != 0:
        s = nnue_eval(bb, st, acc, w2, b2)
        if info[I_CALIB] != 0:
            s = calibrate(bb, st[S_SIDE], s)
        return endgame_scale(bb, s)
    return evaluate_hce(bb, st, pcs)"""
new = """def evaluate(bb, st, pcs, acc, info, w2, b2):
    if info[I_USE_NNUE] != 0:
        s = nnue_eval(bb, st, acc, w2, b2)
        if info[I_CALIB] != 0:
            s = calibrate(bb, st[S_SIDE], s)
        s = endgame_scale(bb, s)
        if RULE50 != 0:
            # fifty-move scaling (Stockfish): the longer nothing irreversible happens, the closer the position is to a
            # draw; a pawn move or capture resets st[S_HALF] and restores the full score, which rewards progress
            hm = st[S_HALF]
            if hm > 100:
                hm = 100
            if s >= 0:
                s = (s * (200 - hm)) // 200
            else:
                s = -(((-s) * (200 - hm)) // 200)
        return s
    return evaluate_hce(bb, st, pcs)"""
assert s.count(old) == 1, "evaluate() not found in the expected form"
s = s.replace(old, new)
i = s.index("from bini_eval import EG_DRAW"); j = s.index("\n", i)
s = s[:j] + "\nRULE50 = int(__import__('os').environ.get('BINI_RULE50', '1'))  # 1: fifty-move scaling of the static evaluation" + s[j:]
assert "S_HALF" in s
p.write_text(s); print(f"patched {p}: fifty-move scaling in evaluate() (switch BINI_RULE50)")
