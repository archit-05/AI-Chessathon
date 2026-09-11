"""Main-search stalemate: does any path return a non-draw score?

C1c's legality probe is guarded by `in_chk`, so it does nothing at a stalemate, where the king
is NOT in check. This drives the original stalemate FEN through search() under exactly the
conditions the brief names: a poisoned transposition entry, and an EMPTY table with narrow
windows chosen to trigger reverse futility, null-move and ProbCut.
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import Probe, S, B, N, chess
import numpy as np

FEN = 'k7/8/1QK5/8/8/8/8/8 b - - 0 1'
assert chess.Board(FEN).is_stalemate()
p = Probe(); e = p.e
CONTEMPT = int(e.info[S.I_CONTEMPT])
print(f"build {os.environ['BINI_DIR']}   contempt={CONTEMPT}")
print(f"stalemate FEN {FEN}")

def util(ply):
    """The exact configured draw utility for the side to move at this node."""
    p.setup(FEN); e.st[B.S_PLY] = ply
    side = int(e.st[B.S_SIDE]); root_side = int(e.info[S.I_ROOT_SIDE])
    e.st[B.S_PLY] = 0
    return -CONTEMPT if side == root_side else CONTEMPT

def run(label, depth, alpha, beta, poison_tt, ply=1):
    p.setup(FEN, budget=600.0); p.clear_tt(); p.clear_corr()
    e.st[B.S_PLY] = ply
    N.nnue_refresh(e.bb, e.st, e.pcs, e.acc, e.w1, e.b1)
    if poison_tt:
        key = int(e.bb[15])
        e.tt_key[key & S.TT_MASK] = np.uint64(key)
        S.tt_store(e.tt_key, e.tt_data, np.uint64(key), 0, 900, 60, S.TT_EXACT, 1, ply)
    v = int(p.search(depth, alpha=alpha, beta=beta))
    e.st[B.S_PLY] = 0
    return v

want = util(1)
print(f"exact draw utility expected at ply 1: {want}\n")
rows = [
    ('poisoned TT, null window',      4, -1,   0,    True),
    ('poisoned TT, wide window',      4, None, None, True),
    ('empty TT, null window d2',      2, -1,   0,    False),
    ('empty TT, null window d4',      4, -1,   0,    False),
    ('empty TT, null window d6',      6, -1,   0,    False),
    ('empty TT, RFP window d3',       3, 400,  401,  False),
    ('empty TT, RFP window d5',       5, -600, -599, False),
    ('empty TT, NMP window d8',       8, -1,   0,    False),
    ('empty TT, ProbCut window d6',   6, -300, -299, False),
    ('empty TT, wide d6',             6, None, None, False),
]
bad = 0
print(f"  {'condition':<30} {'depth':>5} {'window':>14} {'got':>7}  verdict")
for label, d, a, b, poison in rows:
    v = run(label, d, a, b, poison)
    ok = v == want
    bad += 0 if ok else 1
    win = 'wide' if a is None else f'[{a},{b}]'
    print(f"  {label:<30} {d:>5} {win:>14} {v:>7}  {'ok' if ok else '*** NOT THE DRAW UTILITY ***'}")
print(f"\n  violations: {bad} of {len(rows)}")
sys.exit(1 if bad else 0)
