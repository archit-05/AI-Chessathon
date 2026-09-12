"""Finals-day init patch (30 s init budget; rules forbid shipping compiled artefacts, so the compile stays in-process):
  1. agent.py: COMPILE_JOIN_S default 75 -> 21. The ready line is the import; the join is wall-clock, so it lands at
     ~22-23 s on any machine. Whatever compile remains runs during our first move (the process is suspended while the
     opponent thinks), so:
  2. agent.py: NUMBA_OPT set before numba is imported (a lower LLVM optimisation level compiles faster; the level is chosen
     from the measured compile-time / speed trade-off on the day).
usage: patch_init.py <build_dir> <numba_opt: 3|2|1>"""
import sys
from pathlib import Path
b = Path(sys.argv[1]); opt = sys.argv[2]; assert opt in ("3", "2", "1")
a = b / "agent.py"; s = a.read_text()
old_join = 'COMPILE_JOIN_S = float(os.environ.get("BINI_JOIN_S", "75"))'
assert s.count(old_join) == 1
s = s.replace(old_join, 'COMPILE_JOIN_S = float(os.environ.get("BINI_JOIN_S", "21"))  # finals: init budget 30 s (ready line = import); wall-clock join')
old_cache = 'os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp/numba_cache")\n'
assert s.count(old_cache) == 1
s = s.replace(old_cache, old_cache + f'os.environ.setdefault("NUMBA_OPT", "{opt}")  # finals: faster compile inside the 30 s init budget (measured trade-off, Cause Table §21)\n')
assert s.index('NUMBA_OPT') < s.index('import bini_board as B')
a.write_text(s); print(f"patched {a}: join 21 s, NUMBA_OPT={opt}")
