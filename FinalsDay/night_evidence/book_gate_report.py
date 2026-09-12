"""Report for a real-wrapper book gate: results with pair-level (colour-paired) uncertainty, terminations,
fallbacks/timeouts, and book usage from the stats sidecar (hits, saved ms, exit fullmove) per colour.
usage: book_gate_report.py arena.log stats.jsonl"""
import json, sys, re, math, collections, statistics
log = open(sys.argv[1]).read(); stats = [json.loads(l) for l in open(sys.argv[2]) if l.strip()]
final = re.findall(r'^\[(\d+)/(\d+)\] \+(\d+) =(\d+) -(\d+)', log, re.M); n, N, w, d, l = map(int, final[-1]) if final else (0, 0, 0, 0, 0)
terms = re.findall(r'^terminations: (.*)$', log, re.M)
bad = dict(still_compiling=log.count('still compiling'), agent_failure=log.count('AGENT FAILURE'), engine_error=log.count('engine error'), illegal=log.count('ILLEGAL'))
# pair-level: games sharing a start FEN with opposite colours form a pair
score = {'white': 1.0, 'black': 0.0, 'draw': 0.5, 'void': 0.5}
by_fen = collections.defaultdict(list)
for g in stats:
    s = score.get(g['result'], 0.5); s = s if g['agent_white'] else 1 - s
    by_fen[g['fen']].append(s)
pairs = [sum(v) for v in by_fen.values() if len(v) == 2]
pent = collections.Counter(pairs)
mean = sum(pairs) / (2 * len(pairs)) if pairs else 0.5
if len(pairs) > 1:
    var = statistics.variance([p / 2 for p in pairs]); se = math.sqrt(var / len(pairs))
else: se = 0.25
def elo(p): p = min(max(p, 1e-6), 1 - 1e-6); return -400 * math.log10(1 / p - 1)
lo, hi = elo(mean - 1.96 * se), elo(mean + 1.96 * se)
hits = collections.defaultdict(list); saved = collections.defaultdict(list); exits = collections.defaultdict(list); nohit = 0
for g in stats:
    c = 'white' if g['agent_white'] else 'black'; err = g['stderr']
    h = len(re.findall(r' m\d+ book ', err)); hits[c].append(h)
    if h == 0: nohit += 1
    m = re.search(r'bookexit m\d+ hits=(\d+) saved=(\d+)ms fullmove=(\d+)', err)
    if m: saved[c].append(int(m.group(2)) / 1000); exits[c].append(int(m.group(3)))
    elif h: saved[c].append(sum(int(x) for x in re.findall(r'soft(\d+)ms', err)) / 1000)
def summ(v): return dict(n=len(v), mean=round(statistics.mean(v), 2) if v else None, median=statistics.median(v) if v else None, max=max(v) if v else None)
print(json.dumps(dict(games=n, of=N, W=w, D=d, L=l, score=round((w + d / 2) / n, 4) if n else None, terminations=terms[-1] if terms else None, failures=bad,
    pairs=len(pairs), pentanomial=[pent.get(k, 0) for k in (0, 0.5, 1, 1.5, 2)], pair_elo=round(elo(mean), 1), pair_elo_95=[round(lo, 1), round(hi, 1)],
    book=dict(games_without_hit=nohit, hits_white=summ(hits['white']), hits_black=summ(hits['black']), saved_s_white=summ(saved['white']), saved_s_black=summ(saved['black']), exit_fullmove_white=summ(exits['white']), exit_fullmove_black=summ(exits['black']))), indent=1))
