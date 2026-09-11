"""I2 (V8Plan): decisive-rate and loss-rate for a finished gate, from PREFIX.json.

The V8 thesis rules cannot be judged on Elo alone:
  half one (draws -> wins) needs the DECISIVE rate to rise while the WIN share rises, so a change
    that merely turns draws into losses fails;
  half two (losses -> draws) needs side A's LOSS rate to fall.
Usage: python tools/gate_rates.py <gate.json> [<baseline gate.json>]
"""
import json, sys

def rates(path):
    d = json.load(open(path))
    games = d["games"] if isinstance(d, dict) and "games" in d else d
    n = len(games)
    w = sum(1 for g in games if g["a_points"] == 1)
    l = sum(1 for g in games if g["a_points"] == 0)
    dr = n - w - l
    return dict(path=path, n=n, w=w, d=dr, l=l,
                win=100.0 * w / n, loss=100.0 * l / n, decisive=100.0 * (w + l) / n,
                score=100.0 * (w + 0.5 * dr) / n)

def show(r):
    print(f"{r['path'].split('/')[-1]:28s} n={r['n']:5d}  A: +{r['w']} ={r['d']} -{r['l']}   "
          f"score {r['score']:5.1f}%  win {r['win']:5.1f}%  loss {r['loss']:5.1f}%  decisive {r['decisive']:5.1f}%")

a = rates(sys.argv[1]); show(a)
if len(sys.argv) > 2:
    b = rates(sys.argv[2]); show(b)
    print(f"{'DELTA vs baseline':28s}        "
          f"win {a['win']-b['win']:+5.1f}pp  loss {a['loss']-b['loss']:+5.1f}pp  "
          f"decisive {a['decisive']-b['decisive']:+5.1f}pp")
    print(f"  half-one rule (decisive >= +4pp AND win share up): "
          f"{'PASS' if a['decisive']-b['decisive'] >= 4 and a['win'] > b['win'] else 'fail'}")
    print(f"  half-two rule (A loss rate falls):                 "
          f"{'PASS' if a['loss'] < b['loss'] else 'fail'}")
