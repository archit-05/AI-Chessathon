"""Prove the clock refactor changes nothing at 120+0.5: exec only the constants and _budget from two
agent.py files and compare outputs over a dense grid."""
import re, sys
from pathlib import Path
def load(path):
    src = Path(path).read_text()
    consts = "\n".join(l for l in src.splitlines() if re.match(r"^(BASE_MS|INCREMENT_MS|RESERVE_MS|MIN_THINK_MS|EMERGENCY_MS|LOW_CLOCK_MS|VERY_LOW_MS|MIDGAME_BOOST)\s*=", l))
    consts = consts.replace('float(os.environ.get("BINI_MIDGAME_BOOST", "1.0"))', '1.0')
    fn = src[src.index("def _budget("):]; fn = fn[:fn.index("\ndef get_move(")]
    ns = {}; exec(consts + "\n" + fn, ns); return ns["_budget"]
a, b = load(sys.argv[1]), load(sys.argv[2]); n = 0; bad = 0
for t in list(range(1, 200001, 37)) + [3999, 4000, 4001, 9999, 10000, 10001, 29999, 30000, 30001]:
    for m in range(0, 130):
        if a(t, m) != b(t, m): bad += 1
        n += 1
print(f"grid points={n} differences={bad}"); sys.exit(1 if bad else 0)
