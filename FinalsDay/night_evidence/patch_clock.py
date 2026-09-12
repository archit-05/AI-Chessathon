"""Finals-kit clock refactor for agent.py: the three absolute low-clock thresholds become
fractions of BASE_MS (identical at 120 s: 120000/30 = 4000, /4 = 30000, /12 = 10000).
usage: patch_clock.py <build_dir> [BASE_MS=120000] [INCREMENT_MS=500]"""
import sys
from pathlib import Path
d = Path(sys.argv[1]); base = int(sys.argv[2]) if len(sys.argv) > 2 else 120000; inc = int(sys.argv[3]) if len(sys.argv) > 3 else 500
p = d / 'agent.py'; s = p.read_text()
def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)
rep("INCREMENT_MS = 500\nRESERVE_MS = 1500          # never plan to dip below this\n",
    f"BASE_MS = {base}            # published base time; the low-clock thresholds below scale with it\nINCREMENT_MS = {inc}\nRESERVE_MS = 1500          # never plan to dip below this\nEMERGENCY_MS = BASE_MS // 30   # 4000 at 120 s\nLOW_CLOCK_MS = BASE_MS // 4    # 30000 at 120 s\nVERY_LOW_MS = BASE_MS // 12    # 10000 at 120 s\n")
rep("    if time_left_ms < 4000:\n", "    if time_left_ms < EMERGENCY_MS:\n")
rep("    if time_left_ms < 30000:\n", "    if time_left_ms < LOW_CLOCK_MS:\n")
rep("    if time_left_ms < 10000:\n", "    if time_left_ms < VERY_LOW_MS:\n")
p.write_text(s); print(f'patched {p} BASE_MS={base} INCREMENT_MS={inc}')
