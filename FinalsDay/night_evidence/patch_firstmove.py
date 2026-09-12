"""First-move fix (finals, from the V10 validation log): after waiting for the compile, the hard time cap subtracted the
wait a second time (overhead measured from the start of get_move), so the first engine move ran 8 ms / 4,096 nodes /
depth 6. Measure the overhead from the moment the wait ended instead. usage: patch_firstmove.py <build_dir>"""
import sys
from pathlib import Path
a = Path(sys.argv[1]) / "agent.py"; s = a.read_text()
old_wait = "            _ready.wait(timeout=max(0.0, min(0.35 * time_left_ms / 1000.0, 45.0)))\n            soft, hard = _budget(int(time_left_ms - (time.perf_counter() - t0) * 1000.0), _state.move_number)\n"
new_wait = "            _ready.wait(timeout=max(0.0, min(0.35 * time_left_ms / 1000.0, 45.0)))\n            soft, hard = _budget(int(time_left_ms - (time.perf_counter() - t0) * 1000.0), _state.move_number)\n            t_think = time.perf_counter()  # the wait is already out of the budget above; do not charge it again below\n"
assert s.count(old_wait) == 1, "wait block not found"
s = s.replace(old_wait, new_wait)
old_try = "    uci = None\n"
assert s.count(old_try) == 1
s = s.replace(old_try, "    uci = None\n    t_think = t0\n")
old_ov = "            overhead = (time.perf_counter() - t0) * 1000.0\n"
assert s.count(old_ov) == 1, "overhead line not found"
s = s.replace(old_ov, "            overhead = (time.perf_counter() - t_think) * 1000.0\n")
a.write_text(s); print(f"patched {a}: first-move overhead measured after the compile wait")
