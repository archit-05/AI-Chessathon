"""Calibration probe: numba import cost, compile cost per non-trivial function, and raw speed
of bitboard-style integer work. Numbers feed the plan's compile-budget and nps estimates."""
import time
t0 = time.perf_counter()
import numpy as np
from numba import njit, uint64, int64
t_import = time.perf_counter() - t0

@njit(cache=False, boundscheck=False)
def popcount(b):
    b = b - ((b >> np.uint64(1)) & np.uint64(0x5555555555555555))
    b = (b & np.uint64(0x3333333333333333)) + ((b >> np.uint64(2)) & np.uint64(0x3333333333333333))
    b = (b + (b >> np.uint64(4))) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return int((b * np.uint64(0x0101010101010101)) >> np.uint64(56))

@njit(cache=False, boundscheck=False)
def lsb(b):
    # index of least significant set bit via de Bruijn-free loop (portable)
    n = 0
    while (b & np.uint64(1)) == np.uint64(0):
        b >>= np.uint64(1)
        n += 1
    return n

@njit(cache=False, boundscheck=False)
def rook_attacks_slow(sq, occ):
    att = np.uint64(0)
    r, f = sq // 8, sq % 8
    for dr, df in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, ff = r + dr, f + df
        while 0 <= rr < 8 and 0 <= ff < 8:
            bit = np.uint64(1) << np.uint64(rr * 8 + ff)
            att |= bit
            if occ & bit:
                break
            rr += dr; ff += df
    return att

@njit(cache=False, boundscheck=False)
def gen_and_eval(occ_arr, pst, iters):
    # pseudo "movegen + eval" loop: sliding attacks, popcounts, table lookups, a small stack
    total = 0
    stack = np.zeros(256, dtype=np.int64)
    for it in range(iters):
        occ = occ_arr[it % occ_arr.shape[0]]
        sp = 0
        bb = occ
        while bb:
            sq = lsb(bb)
            bb &= bb - np.uint64(1)
            att = rook_attacks_slow(sq, occ) & ~occ
            score = pst[sq] + popcount(att) * 3
            stack[sp] = score; sp += 1
        # mini alpha-beta-ish reduction over the stack
        best = -100000
        for i in range(sp):
            v = stack[i]
            if v > best: best = v
        total += best
    return total

rng = np.random.default_rng(1)
occ_arr = rng.integers(0, 2**63, size=1024, dtype=np.int64).astype(np.uint64) | rng.integers(0, 2**63, size=1024, dtype=np.int64).astype(np.uint64)
pst = rng.integers(-50, 50, size=64).astype(np.int64)

t1 = time.perf_counter()
gen_and_eval(occ_arr, pst, 10)
t_compile = time.perf_counter() - t1

t2 = time.perf_counter()
N = 200_000
gen_and_eval(occ_arr, pst, N)
dt = time.perf_counter() - t2
print(f"numba import      {t_import:6.2f} s")
print(f"compile (4 fns)   {t_compile:6.2f} s")
print(f"pseudo-positions  {N/dt/1000:8.0f} k/s   ({dt*1e6/N:.2f} us per position, ~30 sliding-attack+popcount+lookup each)")
