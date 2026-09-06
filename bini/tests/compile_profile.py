"""Time the first call (compile) of each jitted function in dependency order."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
T = time.perf_counter()
import bini_board as B
import bini_eval as EV
import bini_nnue as N
import bini_search as S
import bini_engine as E
print(f"imports {time.perf_counter()-T:.2f}s  (nnue loaded={N.LOADED}, NB={N.NB}, HIDDEN={N.HIDDEN})")
bb, st, pcs = B.new_position(); ub, ui = B.new_undo(); mv = B.new_move_stack()
B.set_fen(bb, st, pcs, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
eng = E.Engine(use_nnue=True)
acc = eng.acc
steps = [
 ("popcount/lsb", lambda: (B.popcount(bb[14]), B.lsb(bb[14]))),
 ("attacked", lambda: B.attacked(bb, 28, 1)),
 ("gen_moves", lambda: B.gen_moves(bb, st, pcs, mv, 0, False)),
 ("make/unmake", lambda: (B.make(bb, st, pcs, int(mv[0]), ub, ui), B.unmake(bb, st, pcs, ub, ui))),
 ("perft", lambda: B.perft(bb, st, pcs, mv, ub, ui, 1)),
 ("null/attackers/in_check", lambda: (B.make_null(bb, st, ub, ui), B.unmake_null(bb, st, ub, ui), B.attackers_to(bb, 28, bb[14]), B.in_check(bb, st))),
 ("evaluate_hce", lambda: EV.evaluate_hce(bb, st, pcs)),
 ("nnue_refresh", lambda: N.nnue_refresh(bb, st, pcs, acc, eng.w1, eng.b1)),
 ("nnue_eval", lambda: N.nnue_eval(bb, st, acc, eng.w2, eng.b2)),
 ("nnue_after_make", lambda: (B.make(bb, st, pcs, int(mv[0]), ub, ui), N.nnue_after_make(bb, st, pcs, acc, ui, int(mv[0]), eng.w1, eng.b1), B.unmake(bb, st, pcs, ub, ui))),
 ("see", lambda: S.see(bb, pcs, int(mv[0]))),
 ("is_repetition/tt/mvv/pick/check_time", lambda: (S.is_repetition(bb, st, ub, eng.hist, 1), S.tt_probe(eng.tt_key, eng.tt_data, bb[15]), S.tt_store(eng.tt_key, eng.tt_data, bb[15], 0, 0, 1, 1, 1, 0), S.mvv_lva(pcs, int(mv[0])), S.pick_next(mv, eng.scores, 0, 0, 2), S.check_time(eng.info, eng.tlim))),
 ("evaluate (wrapper)", lambda: S.evaluate(bb, st, pcs, acc, eng.info, eng.w2, eng.b2)),
 ("qsearch", lambda: S.qsearch(bb, st, pcs, mv, ub, ui, acc, eng.tt_key, eng.tt_data, eng.scores, eng.info, np.array([1e18]), eng.w1, eng.b1, eng.w2, eng.b2, -100, 100, 1)),
 ("count_legal", lambda: S.count_legal(bb, st, pcs, mv, ub, ui)),
 ("search", lambda: S.search(bb, st, pcs, mv, ub, ui, acc, eng.tt_key, eng.tt_data, eng.killers, eng.history, eng.counters, eng.scores, eng.info, np.array([1e18]), eng.hist, eng.w1, eng.b1, eng.w2, eng.b2, 2, -32000, 32000, 1)),
]
total = 0.0
for name, fn in steps:
    t0 = time.perf_counter(); fn(); st[B.S_PLY] = 0; dt = time.perf_counter() - t0; total += dt
    print(f"{name:40s} {dt:6.2f}s")
print(f"total first-call time {total:.2f}s")
