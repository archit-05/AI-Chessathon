"""Platform-faithful init probe: time `import agent` (that is when the runner prints its ready line), then show what
get_move does while the compile is still running (book position, then a non-book position), then when ready.
usage: (cd <package_dir> && BINI_JOIN_S=<s> python init_probe.py)"""
import time, sys, chess
t0 = time.perf_counter(); import agent; t_ready_line = time.perf_counter() - t0
print(f"READY LINE at {t_ready_line:.1f}s  (engine ready={agent._ready.is_set()})", flush=True)
for name, fen in [("book start", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
                  ("book after 1.e4", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"),
                  ("non-book middlegame", "r4rk1/1pqbbppp/p3pn2/8/PP1Q4/2N1P3/1B2BPPP/R2R2K1 b - - 2 14")]:
    t = time.perf_counter(); mv = agent.get_move(fen, 120000); dt = time.perf_counter() - t
    print(f"  {name:22s} -> {mv}  took {dt:5.1f}s  engine ready now={agent._ready.is_set()}  (t+{time.perf_counter()-t0:.1f}s since import)", flush=True)
agent._ready.wait(120); print(f"engine ready at t+{time.perf_counter()-t0:.1f}s since import start; compile {agent._compile_seconds:.1f}s", flush=True)
