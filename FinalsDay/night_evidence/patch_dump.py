"""Diagnostic build: record a sample of the positions the search hands to the network (interior static
evaluations and quiescence stand-pats) into the tail of the `scores` array, six int64 words per position
(64 piece nibbles, packed state, the raw network score). Search behaviour is unchanged; sampling is off
unless info[I_DUMP_MAX] > 0.  usage: patch_dump.py <build_dir>"""
import sys
from pathlib import Path
d = Path(sys.argv[1]); p = d / 'bini_search.py'; s = p.read_text()
def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old[:60], s.count(old))
    s = s.replace(old, new)
rep("I_MAX_NODES = 26  # fixed-node gates", "I_DUMP_MAX, I_DUMP_STRIDE, I_DUMP_TICK, I_DUMP_COUNT = 28, 29, 30, 31  # diagnostic leaf dump\nI_MAX_NODES = 26  # fixed-node gates")
rep("    scores = np.zeros(CORR_BASE + 2 * 2 * CORR_N, dtype=np.int64)  # move scores, then correction history\n",
    "    scores = np.zeros(CORR_BASE + 2 * 2 * CORR_N + 6 * DUMP_CAP, dtype=np.int64)  # move scores, correction history, then the diagnostic dump\n")
rep("def new_tt() -> tuple[np.ndarray, np.ndarray]:\n", '''DUMP_CAP = 250_000
DUMP_BASE = CORR_BASE + 2 * 2 * CORR_N


@njit(cache=False, boundscheck=False)
def _dump_leaf(scores, info, pcs, st, ev, src):
    mx = info[I_DUMP_MAX]
    if mx == 0:
        return
    info[I_DUMP_TICK] += 1
    if info[I_DUMP_TICK] % info[I_DUMP_STRIDE] != 0:
        return
    n = info[I_DUMP_COUNT]
    if n >= mx or n >= DUMP_CAP:
        return
    base = DUMP_BASE + n * 6
    for i in range(4):
        w = np.int64(0)
        for j in range(16):
            w |= np.int64(pcs[i * 16 + j] & 15) << np.int64(4 * j)
        scores[base + i] = w
    scores[base + 4] = np.int64(st[S_SIDE]) | (np.int64(st[S_CASTLE]) << np.int64(1)) | (np.int64(st[S_EP] + 1) << np.int64(5)) | (np.int64(st[S_HALF]) << np.int64(12)) | (np.int64(st[S_PLY]) << np.int64(20)) | (np.int64(src) << np.int64(28))
    scores[base + 5] = np.int64(ev)
    info[I_DUMP_COUNT] = n + 1


def new_tt() -> tuple[np.ndarray, np.ndarray]:
''')
rep("        stand = corrected(scores, bb, st[S_SIDE], evaluate(bb, st, pcs, acc, info, w2, b2), info[I_CORR])\n",
    "        _qraw = evaluate(bb, st, pcs, acc, info, w2, b2)\n        _dump_leaf(scores, info, pcs, st, _qraw, 1)\n        stand = corrected(scores, bb, st[S_SIDE], _qraw, info[I_CORR])\n")
rep("        raw_static = evaluate(bb, st, pcs, acc, info, w2, b2)\n        static = corrected(scores, bb, st[S_SIDE], raw_static, info[I_CORR])\n",
    "        raw_static = evaluate(bb, st, pcs, acc, info, w2, b2)\n        _dump_leaf(scores, info, pcs, st, raw_static, 0)\n        static = corrected(scores, bb, st[S_SIDE], raw_static, info[I_CORR])\n")
# S_CASTLE / S_EP are needed in the search module
rep("    S_HALF,\n    S_PLY,\n    S_SIDE,\n", "    S_CASTLE,\n    S_EP,\n    S_HALF,\n    S_PLY,\n    S_SIDE,\n")
p.write_text(s); print('dump hooks applied to', p)
