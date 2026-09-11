"""One table per training run: trainer validation (quiet positions), diagnostic on the held-out
site chunk (all positions, quiet only, 5-16 pieces), scale slope, and the grader, per epoch.

    python tools/epoch_table.py ../data/train_v4a.log v4a   # reads ~/chess/nets/v4a_e*.{diag,grade}.txt on the VM
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def main() -> None:
    log, tag = Path(sys.argv[1]), sys.argv[2]
    text = log.read_text()
    val = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r"epoch (\d+) val site_labelled/chunk_0001.npz: loss [\d.]+ MAE (\d+)cp", text)}
    remote = subprocess.run(["ssh", "-o", "BatchMode=yes", "priorcrypto-vm", f"for f in ~/chess/nets/{tag}_e*.diag.txt; do echo FILE $f; grep -E 'positions:|^ +(5-8|9-12|13-16) |^ +1 +n' $f; done; for f in ~/chess/nets/{tag}_e*.grade.txt; do echo FILE $f; grep GRADE $f; done"], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout
    diag: dict[int, dict] = {}
    cur = None
    for ln in remote.splitlines():
        m = re.match(rf"FILE .*{tag}_e(\d+)\.(diag|grade)\.txt", ln)
        if m:
            cur = int(m.group(1)); diag.setdefault(cur, {}); continue
        if cur is None:
            continue
        d = diag[cur]
        m = re.search(r"MAE ([\d.]+) cp.*slope pred/label ([\d.]+)", ln)
        if m:
            d["all"], d["slope"] = float(m.group(1)), float(m.group(2)); continue
        m = re.match(r"\s+(5-8|9-12|13-16)\s+n\s+(\d+)\s+MAE\s+([\d.]+)", ln)
        if m:
            d.setdefault("mid", []).append((int(m.group(2)), float(m.group(3)))); continue
        m = re.match(r"\s+1\s+n\s+\d+\s+MAE\s+([\d.]+)", ln)
        if m and "quiet" not in d:
            d["quiet"] = float(m.group(1)); continue
        m = re.search(r"GRADE .* mean loss ([\d.]+) cp, median \d+, blunders \(>=200\) (\d+) = ([\d.]+)%", ln)
        if m:
            d["grade"], d["bl"], d["blp"] = float(m.group(1)), int(m.group(2)), float(m.group(3))
    print(f"| {tag} epoch | trainer val MAE (quiet) | diag all | diag quiet | diag 5-16 pieces | slope | grader cp | blunders |")
    print("|---|---|---|---|---|---|---|---|")
    print("| v3b (reference) | – | 144.8 | 131 | 165–215 | 1.305 | 14.2 | 1 (0.3%) |")
    for e in sorted(set(val) | set(diag)):
        d = diag.get(e, {})
        mid = ""
        if d.get("mid"):
            n = sum(x[0] for x in d["mid"]); mid = f"{sum(x[0] * x[1] for x in d['mid']) / n:.0f}"
        print(f"| {e + 1} | {val.get(e, '')} | {d.get('all', '')} | {d.get('quiet', '')} | {mid} | {d.get('slope', '')} | {d.get('grade', '')} | {d.get('bl', '')}{' (' + str(d['blp']) + '%)' if 'blp' in d else ''} |")


if __name__ == "__main__":
    main()
