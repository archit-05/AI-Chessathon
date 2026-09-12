"""Add --stats-out to arena_par.py: one JSON line per game with colour, start FEN, result, termination and our agent's stderr tail."""
import sys
from pathlib import Path
p = Path(sys.argv[1]); s = p.read_text()
def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
rep("    return agent_white, outcome.result, outcome.termination, pgn, ours.stderr_tail\n", "    return agent_white, outcome.result, outcome.termination, pgn, ours.stderr_tail, fen\n")
rep('    ap.add_argument("--seed", type=int, default=1)\n', '    ap.add_argument("--seed", type=int, default=1)\n    ap.add_argument("--stats-out", help="JSONL: one record per game with our stderr tail")\n')
rep("            agent_white, result, term, pgn, err = f.result()\n            done += 1\n", "            agent_white, result, term, pgn, err, fen = f.result()\n            done += 1\n            if a.stats_out:\n                with open(a.stats_out, 'a') as sf:\n                    sf.write(json.dumps(dict(i=done, agent_white=agent_white, fen=fen, result=result, term=term, stderr=err)) + '\\n')\n")
rep("import math\n", "import json\nimport math\n")
p.write_text(s); print('arena stats patch applied to', p)
