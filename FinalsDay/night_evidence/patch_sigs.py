"""Compile-time patch (finals, 30 s init): explicit numba signatures on the ten helpers that numba was specialising per
constant argument (castling squares, promotion codes, capture flags, literal bases) — 60 of the 109 compiled
specialisations. With a declared signature the dispatcher cannot compile literal variants, so every call resolves to the
one overload (literal ints convert to int64). Logic unchanged; verified node-identical. usage: patch_sigs.py <build_dir>"""
import sys
from pathlib import Path
b = Path(sys.argv[1])
SIGS = {
    "bini_board.py": {
        "rook_att":   "uint64(int64, uint64)",
        "bishop_att": "uint64(int64, uint64)",
        "attacked":   "boolean(uint64[::1], int64, int64)",
        "_add":       "int64(int64[::1], int64, int64, int64, int64, int64)",
        "gen_moves":  "int64(uint64[::1], int64[::1], int64[::1], int64[::1], int64, boolean)",
    },
    "bini_nnue.py": {
        "king_id":            "int64(uint64[::1], int64)",
        "_feature":           "int64(int64, int64, int64, int64)",
        "nnue_refresh_persp": "void(uint64[::1], int64[::1], int16[:, :, ::1], int64, int64, int16[:, ::1], int32[::1])",
    },
    "bini_search.py": {
        "corr_index": "int64(uint64[::1], int64, int64)",
        "tt_store":   "void(uint64[::1], int64[::1], uint64, int64, int64, int64, int64, int64, int64)",
    },
}
n = 0
for fname, funcs in SIGS.items():
    p = b / fname; s = p.read_text()
    for fn, sig in funcs.items():
        old = f"@njit(cache=False, boundscheck=False)\ndef {fn}("
        assert s.count(old) == 1, (fname, fn, s.count(old))
        s = s.replace(old, f'@njit("{sig}", cache=False, boundscheck=False)\ndef {fn}('); n += 1
    p.write_text(s)
print(f"explicit signatures on {n} helpers in {b}")
