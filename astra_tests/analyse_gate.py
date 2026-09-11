"""Read one or more arena_astra result files and report the gate exactly as §9 asks."""
import sys, json, math, statistics, collections
from pathlib import Path

def a_score(g):
    if g['result'] == 'draw':
        return 0.5
    return 1.0 if (g['result'] == 'white') == g['a_white'] else 0.0

def elo(s):
    s = min(max(s, 1e-9), 1 - 1e-9)
    return -400 * math.log10(1 / s - 1)

def pent(games):
    by = collections.defaultdict(list)
    for g in games:
        by[(g.get('_run', 0), g['pair_id'])].append(g)
    ps = [sum(a_score(x) for x in v) for v in by.values() if len(v) == 2]
    singles = [a_score(x) for v in by.values() if len(v) == 1 for x in v]
    n = len(ps)
    if n < 2:
        return None
    mu, var = statistics.fmean(ps), statistics.variance(ps)
    score, se = mu / 2, math.sqrt(var / n) / 2
    if singles:
        n1 = len(singles); v1 = statistics.pvariance(singles) if n1 > 1 else 0.25
        tot = n * 2 + n1
        score = (mu * n + sum(singles)) / tot
        se = math.sqrt((var * n + v1 * n1) / tot ** 2)
    lo, hi = max(1e-9, score - 1.96 * se), min(1 - 1e-9, score + 1.96 * se)
    return dict(score=score, se=se, elo=elo(score), lo=elo(lo), hi=elo(hi),
                pm=(elo(hi) - elo(lo)) / 2, pairs=n, unpaired=len(singles),
                counts={k: ps.count(k) for k in (0.0, 0.5, 1.0, 1.5, 2.0)})

runs, games = [], []
for i, path in enumerate(sys.argv[1:]):
    d = json.loads(Path(path).read_text())
    for g in d['games']:
        g['_run'] = i
    runs.append((path, d['summary']))
    games.extend(d['games'])

print('=' * 78)
for path, s in runs:
    c = s['config']
    print(f"run: {Path(path).name}")
    print(f"  a={Path(c['a']).name}  b={Path(c['b']).name}  {c['base_ms']}+{c['inc_ms']}ms  "
          f"workers {c['workers']}  host {c['host']} ({c['cpus']} cpus)")
    print(f"  openings {Path(c['openings']).name} offset {c['manifest_offset']} "
          f"unique {c['unique_openings']} manifest md5 {c['manifest_md5']}  seed {c['seed']}")
    print(f"  env {c['env']}   requested {s['requested']} completed {s['completed']} "
          f"valid {s['valid']} rejected {s['rejected']} {s['reject_reasons']}")
    print(f"  candidate: fallback {s['a_fallback']}  nnue_off {s['a_nnue_off']}   "
          f"baseline: fallback {s['b_fallback']}  nnue_off {s['b_nnue_off']}   flags {s['flags']}")
    print(f"  net md5 a={c['a_hashes'].get('nnue.safetensors','?')[:12]} b={c['b_hashes'].get('nnue.safetensors','?')[:12]}"
          f"  book a={c['a_hashes'].get('book.json','?')[:12]} b={c['b_hashes'].get('book.json','?')[:12]}")
print('=' * 78)

valid = [g for g in games if g['valid']]
w = sum(1 for g in valid if a_score(g) == 1)
d_ = sum(1 for g in valid if a_score(g) == 0.5)
l = sum(1 for g in valid if a_score(g) == 0)
st = pent(valid)
print(f"\nvalid games {len(valid)}   W {w}  D {d_}  L {l}   draw rate {d_/max(1,len(valid)):.1%}")
if st:
    print(f"score {st['score']:.2%}   Elo {st['elo']:+.1f}  95% [{st['lo']:+.1f}, {st['hi']:+.1f}]  (+-{st['pm']:.1f})")
    print(f"pairs {st['pairs']} unpaired {st['unpaired']}   pentanomial LL/LD/DD-WL/WD/WW = "
          + ' '.join(f"{k}:{v}" for k, v in st['counts'].items()))
    print(f"\nPREDECLARED: accept if the lower bound is above -20 Elo  ->  "
          f"lower bound {st['lo']:+.1f}  ==> {'PASS' if st['lo'] > -20 else 'FAIL'}")

print('\nterminations, candidate as White vs as Black:')
tw = collections.Counter(g['termination'] for g in valid if g['a_white'])
tb = collections.Counter(g['termination'] for g in valid if not g['a_white'])
for k in sorted(set(tw) | set(tb)):
    print(f"  {k:<26} white {tw[k]:>4}   black {tb[k]:>4}   total {tw[k]+tb[k]:>4}")

print('\ncolour split (candidate score):')
for name, sub in (('as White', [g for g in valid if g['a_white']]), ('as Black', [g for g in valid if not g['a_white']])):
    if sub:
        sc = statistics.fmean(a_score(g) for g in sub)
        print(f"  {name}: {sc:.1%} over {len(sub)} games")

print('\nengine telemetry (means over valid games):')
for arm, label in (('a', 'candidate'), ('b', 'baseline')):
    bm = statistics.fmean(g[arm]['book_moves'] for g in valid)
    sm = statistics.fmean(g[arm]['searched_moves'] for g in valid)
    print(f"  {label:<10} book moves {bm:.2f}   searched moves {sm:.1f}   "
          f"nnue on {sum(1 for g in valid if g[arm]['nnue_on'])}/{len(valid)}")
