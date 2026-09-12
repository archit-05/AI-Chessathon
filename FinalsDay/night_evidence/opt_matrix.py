"""Compile time vs speed for a numba optimisation level. Run in the package dir with NUMBA_OPT set and BINI_JOIN_S=120.
Prints: compile seconds, then nodes/s and depth from a 4 s search on a middlegame position, and a fixed-node score."""
import os, time, sys; sys.path.insert(0, os.getcwd())
t = time.perf_counter(); import agent; agent._ready.wait(150); ti = time.perf_counter() - t
e, S = agent._engine, agent._S
fen = "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/2N2N2/PP2BPPP/R2QKB1R w KQ - 4 9"
e.new_game(); e.set_position(fen, []); t = time.perf_counter(); mv, sc, d = e.think(4000.0, 4000.0, log=False); dt = time.perf_counter() - t
nodes = int(e.info[S.I_NODES]); print(f"OPT={os.environ.get('NUMBA_OPT','3')} compile={agent._compile_seconds:.1f}s import={ti:.1f}s | 4s search: {nodes/dt/1000:.0f} knps depth {d} move {mv} score {sc}", flush=True)
e.new_game(); e.set_position(fen, []); mv2, sc2, d2 = e.think(60000.0, 60000.0, log=False, max_nodes=400000); print(f"   fixed 400k nodes: move {mv2} score {sc2} depth {d2} (identity check across OPT levels)", flush=True)
