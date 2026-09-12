"""Two-game match odds from per-game W/D/L (or a pentanomial): P(win a must-win match: score >= 1.5) and
P(not losing a match where ties go to us: score >= 1.0). usage: match_odds.py W D L  |  match_odds.py --pent a b c d e"""
import sys
if sys.argv[1] == '--pent':
    p = [int(x) for x in sys.argv[2:7]]; n = sum(p)
    must_win = (p[4] + p[3]) / n; hold = (p[4] + p[3] + p[2]) / n
    print(f"pairs={n} pentanomial={p}: P(must-win match)={must_win:.3f}  P(hold as higher seed)={hold:.3f}")
else:
    W, D, L = map(float, sys.argv[1:4]); t = W + D + L; w, d, l = W / t, D / t, L / t
    print(f"per game W/D/L = {w:.3f}/{d:.3f}/{l:.3f}, expected score {w + d/2:.3f}")
    print(f"independent games: P(must-win match)={w*w + 2*w*d:.3f}   P(hold as higher seed)={1 - (l*l + 2*l*d):.3f}")
