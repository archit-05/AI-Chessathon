"""Find magic bitboard multipliers for rooks and bishops.

Run once; the output is pasted into bini_board.py as constants. Shipped so a judge can regenerate
the numbers. Uses a fixed-seed xorshift so the result is reproducible.
"""

from __future__ import annotations

import sys

import numpy as np
from numba import njit

U64 = np.uint64
MASK = (1 << 64) - 1


def rook_mask(sq: int) -> int:
    r, f = divmod(sq, 8)
    m = 0
    for rr in range(r + 1, 7):
        m |= 1 << (rr * 8 + f)
    for rr in range(r - 1, 0, -1):
        m |= 1 << (rr * 8 + f)
    for ff in range(f + 1, 7):
        m |= 1 << (r * 8 + ff)
    for ff in range(f - 1, 0, -1):
        m |= 1 << (r * 8 + ff)
    return m


def bishop_mask(sq: int) -> int:
    r, f = divmod(sq, 8)
    m = 0
    for dr, df in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        rr, ff = r + dr, f + df
        while 0 < rr < 7 and 0 < ff < 7:
            m |= 1 << (rr * 8 + ff)
            rr += dr
            ff += df
    return m


def slide(sq: int, occ: int, dirs: tuple[tuple[int, int], ...]) -> int:
    r, f = divmod(sq, 8)
    att = 0
    for dr, df in dirs:
        rr, ff = r + dr, f + df
        while 0 <= rr < 8 and 0 <= ff < 8:
            bit = 1 << (rr * 8 + ff)
            att |= bit
            if occ & bit:
                break
            rr += dr
            ff += df
    return att


ROOK_DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
BISHOP_DIRS = ((1, 1), (1, -1), (-1, 1), (-1, -1))


def subsets(mask: int) -> list[int]:
    out = []
    sub = 0
    while True:
        out.append(sub)
        sub = (sub - mask) & mask
        if sub == 0:
            break
    return out


@njit(cache=False)
def _search(occs, atts, bits, seed):
    n = occs.shape[0]
    table = np.zeros(1 << bits, dtype=np.uint64)
    used = np.zeros(1 << bits, dtype=np.uint8)
    s = seed
    tries = 0
    while True:
        tries += 1
        # xorshift64*
        s ^= s >> np.uint64(12)
        s ^= s << np.uint64(25)
        s ^= s >> np.uint64(27)
        a = s * np.uint64(2685821657736338717)
        s ^= s >> np.uint64(12)
        s ^= s << np.uint64(25)
        s ^= s >> np.uint64(27)
        b = s * np.uint64(2685821657736338717)
        s ^= s >> np.uint64(12)
        s ^= s << np.uint64(25)
        s ^= s >> np.uint64(27)
        c = s * np.uint64(2685821657736338717)
        magic = a & b & c
        if magic == np.uint64(0):
            continue
        ok = True
        for i in range(1 << bits):
            used[i] = 0
        for i in range(n):
            idx = (occs[i] * magic) >> np.uint64(64 - bits)
            if used[idx] == 0:
                used[idx] = 1
                table[idx] = atts[i]
            elif table[idx] != atts[i]:
                ok = False
                break
        if ok:
            return magic, tries


def find(sq: int, rook: bool, seed: int) -> tuple[int, int, int]:
    mask = rook_mask(sq) if rook else bishop_mask(sq)
    bits = bin(mask).count("1")
    occs = subsets(mask)
    dirs = ROOK_DIRS if rook else BISHOP_DIRS
    atts = [slide(sq, o, dirs) for o in occs]
    magic, tries = _search(
        np.array(occs, dtype=np.uint64), np.array(atts, dtype=np.uint64), bits, U64(seed)
    )
    return int(magic), bits, tries


def main() -> None:
    seed = 0x9E3779B97F4A7C15
    for name, rook in (("ROOK", True), ("BISHOP", False)):
        magics = []
        bits_list = []
        for sq in range(64):
            magic, bits, _ = find(sq, rook, seed + sq * 7919 + (0 if rook else 104729))
            magics.append(magic)
            bits_list.append(bits)
        print(f"{name}_MAGIC = [")
        for i in range(0, 64, 4):
            print("    " + ", ".join(f"0x{m:016X}" for m in magics[i : i + 4]) + ",")
        print("]")
        print(f"{name}_BITS = {bits_list}")
        print(f"# {name} table size = {sum(1 << b for b in bits_list)}", file=sys.stderr)


if __name__ == "__main__":
    main()
