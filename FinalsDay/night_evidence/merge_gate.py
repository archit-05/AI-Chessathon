"""Combine real-clock gate results from several boxes (stats sidecars) into one pair-level report.
Each stats.jsonl row: i, agent_white (bool), fen, result ('white'|'black'|'draw'|'void'), term, stderr.
usage: merge_gate.py <stats.jsonl> [<stats.jsonl> ...]"""
import sys, json, math, collections
rows = []
for p in sys.argv[1:]:
    for l in open(p):
        if l.strip(): r = json.loads(l); r["_src"] = p; rows.append(r)
score = {"white": 1.0, "black": 0.0, "draw": 0.5, "void": 0.5}
W = D = L = 0; fails = collections.Counter(); terms = collections.Counter()
by_fen = collections.defaultdict(list)
for r in rows:
    s = score.get(r["result"], 0.5); s = s if r["agent_white"] else 1.0 - s
    W += s == 1.0; D += s == 0.5; L += s == 0.0; terms[r.get("term", "?")] += 1
    err = (r.get("stderr") or "")
    for k in ("AGENT FAILURE", "engine error", "ILLEGAL", "Traceback", "BUILD FAILED"):
        if k in err: fails[k] += 1
    if r.get("term") in ("init", "crash", "illegal", "flag"): fails["term:" + r["term"]] += 1
    by_fen[r["fen"]].append(s)
pairs = [v for v in by_fen.values() if len(v) >= 2]
ps = [(v[0] + v[1]) / 2 for v in pairs]
n = len(rows); mean = (W + 0.5 * D) / max(1, n)
def elo(p): return -400 * math.log10(1 / p - 1) if 0 < p < 1 else float("nan")
if ps:
    m = sum(ps) / len(ps); var = sum((x - m) ** 2 for x in ps) / max(1, len(ps) - 1); se = math.sqrt(var / len(ps))
    lo, hi = max(1e-6, m - 1.96 * se), min(1 - 1e-6, m + 1.96 * se)
    pent = [0] * 5
    for v in pairs: pent[int(round((v[0] + v[1]) * 2))] += 1
    print(f"games {n}  W/D/L {W}/{D}/{L}  score {mean:.3f}  pairs {len(pairs)}  pair Elo {elo(m):+.1f} [{elo(lo):+.1f}, {elo(hi):+.1f}]  pentanomial {pent}")
else:
    print(f"games {n}  W/D/L {W}/{D}/{L}  score {mean:.3f}  (no complete colour pairs yet)")
print("terminations:", dict(terms)); print("failures:", dict(fails) or "none"); print("per source:", collections.Counter(r["_src"].rsplit("/", 1)[-1] for r in rows))
