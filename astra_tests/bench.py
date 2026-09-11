"""Runtime cost of the correctness patches.

Fixed-depth searches on a fixed position set: node counts show whether the tree changed,
wall time shows what the added terminal checks cost per node.  Deterministic - no clock in
the measurement path - so baseline and candidate are directly comparable.
"""
import os, sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, S, B, chess, np, environment, build_hashes

POSITIONS = [
    ('opening',   'r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3'),
    ('kiwipete',  'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1'),
    ('middlegame','r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10'),
    ('tactical',  '4rrk1/pp1n1ppp/2pb1q2/3p4/3P4/2NBPN2/PP3PPP/R2Q1RK1 w - - 0 1'),
    ('rook_endg', '8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1'),
    ('pawn_endg', '8/5ppp/8/8/8/8/5PPP/4K1k1 w - - 0 1'),
    ('minor_endg','8/8/4k3/3n4/8/4K3/5B2/8 w - - 0 1'),
    ('queenless', '2r3k1/pp3pp1/4p2p/8/2P5/1P3P2/P4KPP/2R5 w - - 0 1'),
    ('late_half', '8/8/4k3/8/8/4K3/5P2/6R1 w - - 80 60'),
]
DEPTH = int(os.environ.get('BENCH_DEPTH', '10'))
REPS = int(os.environ.get('BENCH_REPS', '3'))

p = Probe()
rows = []
for name, fen in POSITIONS:
    best_t, nodes = None, None
    for _ in range(REPS):
        p.setup(fen, budget=600.0)
        p.clear_tt(); p.clear_corr()
        p.e.info[S.I_NODES] = 0
        t0 = time.perf_counter()
        sc = p.search(DEPTH)
        dt = time.perf_counter() - t0
        n = int(p.e.info[S.I_NODES])
        if best_t is None or dt < best_t:
            best_t, nodes, score = dt, n, sc
    rows.append(dict(name=name, seconds=round(best_t, 4), nodes=nodes, score=score,
                     knps=round(nodes / best_t / 1000, 1)))
    print(f'{name:<12} {best_t*1000:8.1f} ms  {nodes:9d} n  {nodes/best_t/1000:7.1f} knps  score {score}', flush=True)

tot_t = sum(r['seconds'] for r in rows)
tot_n = sum(r['nodes'] for r in rows)
summary = dict(depth=DEPTH, reps=REPS, total_seconds=round(tot_t, 4), total_nodes=tot_n,
               knps=round(tot_n / tot_t / 1000, 1))
print(json.dumps(summary), flush=True)
out = Path(__file__).resolve().parents[1] / 'astra_reports' / f"bench_{os.environ.get('LABEL','run')}.json"
out.write_text(json.dumps(dict(summary=summary, rows=rows, environment=environment(),
                               build_hashes=build_hashes()), indent=2))
print('written', out)
