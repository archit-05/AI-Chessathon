"""Candidate VEC: vectorisable NNUE output layer. Adds nnue_eval_v1 (1-D views, int32 chunked
reduction, branch-free clamp) and selects it at import via BINI_EVAL_VARIANT (default 1; 0 = the
shipped scalar loop, kept verbatim as nnue_eval_v0). Values are identical by construction:
same integer arithmetic, chunk sums bounded by 256 * 255^2 * |w2|max < 2^31."""
import sys
from pathlib import Path
d = Path(sys.argv[1]); p = d / 'bini_nnue.py'; s = p.read_text()
old_head = "@njit(cache=False, boundscheck=False)\ndef nnue_eval(bb, st, acc, w2, b2):\n"
assert s.count(old_head) == 1
s = s.replace(old_head, "@njit(cache=False, boundscheck=False)\ndef nnue_eval_v0(bb, st, acc, w2, b2):\n")
s += '''

# ---------------------------------------------------------------------------------------------
# Candidate VEC: the same output layer written so LLVM can vectorise it. One-dimensional views
# of the two accumulators and of the bucket's weight row, a branch-free clamp, int32 products
# summed in int32 over chunks of CHUNK units (bounded: 256 * 255^2 * |w2| < 2^31 for |w2| < 129;
# the exporter prints |w2|max, fc_b is 63), chunk sums widened to int64. Identical values to v0.
# ---------------------------------------------------------------------------------------------
EVAL_VARIANT = int(os.environ.get("BINI_EVAL_VARIANT", "1"))
CHUNK = 256 if HIDDEN % 256 == 0 else (128 if HIDDEN % 128 == 0 else HIDDEN)
_Z32 = np.int32(0)
_QA32 = np.int32(QA)
assert int(np.abs(W2).max()) < 129, "VEC chunk bound needs |w2| < 129"


@njit(cache=False, boundscheck=False)
def _sq_dot(a, w):
    total = np.int64(0)
    for c in range(0, HIDDEN, CHUNK):
        s = np.int32(0)
        for h in range(c, c + CHUNK):
            v = min(max(np.int32(a[h]), _Z32), _QA32)
            s += v * v * np.int32(w[h])
        total += np.int64(s)
    return total


@njit(cache=False, boundscheck=False)
def _dot(a, w):
    total = np.int64(0)
    for c in range(0, HIDDEN, CHUNK):
        s = np.int32(0)
        for h in range(c, c + CHUNK):
            s += min(max(np.int32(a[h]), _Z32), _QA32) * np.int32(w[h])
        total += np.int64(s)
    return total


@njit(cache=False, boundscheck=False)
def nnue_eval_v1(bb, st, acc, w2, b2):
    ply = st[S_PLY]
    stm = st[S_SIDE]
    ob = 0
    if NO > 1:
        ob = (popcount(bb[14]) - 1) * NO // 32
        if ob > NO - 1:
            ob = NO - 1
    if ACT_SQ != 0:
        total = _sq_dot(acc[ply, stm], w2[ob, :HIDDEN]) + _sq_dot(acc[ply, 1 - stm], w2[ob, HIDDEN:])
    else:
        total = _dot(acc[ply, stm], w2[ob, :HIDDEN]) + _dot(acc[ply, 1 - stm], w2[ob, HIDDEN:])
    total += np.int64(b2[ob])
    return np.int64(total // np.int64(b2[NO]))


nnue_eval = nnue_eval_v1 if EVAL_VARIANT == 1 else nnue_eval_v0
'''
p.write_text(s); print('patched', p)
