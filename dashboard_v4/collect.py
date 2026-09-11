#!/usr/bin/env python3
"""Status collector for the V4 build dashboard. Reads the logs that already exist (training,
gates, self-play streams, platform game logs, the progress file, machine health, the VM over ssh)
and writes dashboard_v4/status.json atomically. Standard library only; one run takes about a
second and touches nothing outside this directory.

    python3 collect.py            # one pass
    bash run.sh                   # loop every 60 s + serve the page on 127.0.0.1:8765
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
PROGRESS = ROOT / "V4 Progress.md"
OUT = HERE / "status.json"

# build boundaries on the ladder (first rated round played by each upload)
BUILDS = [(24, "V1"), (29, "HCE"), (31, "V2"), (38, "V2.1"), (48, "V2.2"), (51, "V3")]
EPOCH_PLAN = {"v4a": 6, "v4b": 2, "v4c": 20, "v4d": 20, "v4e": 20}
STREAM_NAMES = {
    ".": "curated d9 (run 1)", "run2": "curated d9 (run 2)", "run3": "curated d9 (run 3)",
    "eg": "endgame d12 (from site games)", "eg2": "endgame d12 (resolved)", "rn": "rook+knight endings d14",
    "struct": "frequent structures d12", "bini": "Bini vs Stockfish",
}
CHAIN = [
    ("v4a training", r"v4a finished"),
    ("pull self-play chunks", r"pulling chunks"),
    ("v4b fine-tune", r"starting v4b"),
    ("v4b slope + scale-matched export", r"v4b slope"),
    ("gate v4b vs V3 (2 workers)", r"gate v4b vs V3"),
    ("whole-site refresh", r"refreshing the whole-site"),
    ("v4d: 20 epochs, tournament mix", r"starting v4d"),
    ("chain done", r"overnight chain done"),
]


def sh(cmd: list[str], timeout: float = 8.0) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:  # noqa: BLE001
        return ""


def tail(path: Path, n: int = 40) -> list[str]:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 200_000))
            return fh.read().decode("utf-8", "replace").splitlines()[-n:]
    except Exception:  # noqa: BLE001
        return []


def age_min(path: Path) -> float:
    try:
        return (time.time() - path.stat().st_mtime) / 60.0
    except Exception:  # noqa: BLE001
        return 1e9


# ----------------------------------------------------------------------------- platform
def build_for(round_no: int) -> str:
    name = "?"
    for start, b in BUILDS:
        if round_no >= start:
            name = b
    return name


def parse_round_log(path: Path) -> dict:
    """Clock profile from a platform log, either the raw stderr format or the MATCH LOG format."""
    out: dict = {}
    try:
        s = path.read_text(errors="replace")
    except Exception:  # noqa: BLE001
        return out
    rows = re.findall(r"bini-2\.0 m(\d+) d(\d+) \S+ (-?\d+)cp \d+n (\d+)ms left (\d+)ms", s)
    if rows:
        ms = [int(r[3]) for r in rows]
        left = [int(r[4]) for r in rows]
        depth = [int(r[1]) for r in rows]
        out["first_move_s"] = round(ms[0] / 1000, 1)
        out["clk20"] = round(left[19] / 1000, 1) if len(left) > 19 else None
        out["clk40"] = round(left[39] / 1000, 1) if len(left) > 39 else None
        out["depth"] = f"{min(depth)}-{max(depth)}"
        out["evals"] = [int(r[2]) for r in rows][:120]
    m = re.search(r"Ready in\s+([\d.]+) s", s) or re.search(r"import\+compile ([\d.]+)s", s)
    if m:
        out["init_s"] = float(m.group(1))
    m = re.search(r"^\s*(Won|Lost|Drawn) by (.+)$", s, flags=re.M)
    if m:
        out["result"] = {"Won": "Win", "Lost": "Loss", "Drawn": "Draw"}[m.group(1)]
        out["termination"] = m.group(2).strip().capitalize()
    m = re.search(r"^\s+Colour\s+(White|Black)", s, flags=re.M)
    if m:
        out["colour"] = m.group(1)
    m = re.search(r"^\s+Opponent\s+(.+)$", s, flags=re.M)
    if m:
        out["opponent"] = m.group(1).strip()
    m = re.search(r"^\s+Left at end\s+([\d.]+) s", s, flags=re.M)
    if m:
        out["clock_left_s"] = float(m.group(1))
    m = re.search(r"^\s+Moves\s+(\d+)", s, flags=re.M)
    if m:
        out["moves"] = int(m.group(1))
    m = re.search(r"^\s+Average\s+([\d.]+) s", s, flags=re.M)
    if m:
        out["avg_s"] = float(m.group(1))
    tbl = re.findall(r"^\s+(\d+)\s+\S+\s+([\d.]+) s\s+([\d.]+) s", s, flags=re.M)
    if tbl and "first_move_s" not in out:
        out["first_move_s"] = float(tbl[0][1])
        d = {int(a): float(c) for a, _, c in tbl}
        out["clk20"] = d.get(20)
        out["clk40"] = d.get(40)
    return out


def rows_left(path: Path) -> float | None:
    try:
        left = re.findall(r"left (\d+)ms", path.read_text(errors="replace"))
        return round(int(left[-1]) / 1000, 1) if left else None
    except Exception:  # noqa: BLE001
        return None


def platform() -> dict:
    games = []
    csvs = sorted(glob.glob(str(LOGS / "*.csv")) + glob.glob(str(ROOT / "*.csv")), key=os.path.getmtime)
    if csvs:
        with open(csvs[-1]) as fh:
            for r in csv.DictReader(fh):
                m = re.search(r"(\d+)", r.get("round", ""))
                if not m:
                    continue
                rn = int(m.group(1))
                games.append({
                    "round": rn, "colour": r.get("colour"), "opponent": r.get("opponent"), "result": r.get("result"),
                    "termination": r.get("termination"), "init_s": float(r.get("init_s") or 0),
                    "moves": int(float(r.get("moves") or 0)), "avg_s": float(r.get("average_s") or 0),
                    "slowest_s": float(r.get("slowest_s") or 0), "clock_left_s": float(r.get("clock_left_s") or 0),
                    "machine": r.get("machine"), "finished": r.get("finished_at", "")[:16].replace("T", " "),
                    "build": build_for(rn),
                })
    by_round = {g["round"]: g for g in games}
    for p in LOGS.glob("aichessathon-round-*.log"):
        m = re.search(r"round-(\d+)-(.+)\.log", p.name)
        if not m:
            continue
        rn = int(m.group(1))
        info = parse_round_log(p)
        g = by_round.get(rn)
        if g is None:
            g = {"round": rn, "opponent": m.group(2), "build": build_for(rn), "result": "?", "colour": "?",
                 "init_s": info.get("init_s", 0), "moves": 0, "avg_s": 0, "slowest_s": 0, "clock_left_s": 0,
                 "termination": "", "machine": "", "finished": ""}
            by_round[rn] = g
        for k, v in info.items():
            if k == "evals":
                continue
            if k in ("result", "colour", "opponent", "termination", "clock_left_s", "moves", "avg_s") and g.get(k) not in (None, "", "?", 0):
                continue  # the CSV row is authoritative when present
            g[k] = v
        if g.get("clock_left_s") in (None, 0) and rows_left(p):
            g["clock_left_s"] = rows_left(p)
        g["flags"] = []
        if g.get("clock_left_s") and g["clock_left_s"] < 5:
            g["flags"].append("ended under 5 s")
        if g.get("first_move_s") and g["first_move_s"] < 1.8 and rn >= 48:
            g["flags"].append("old-build first move")
        if g.get("clk40") and g["clk40"] < 20:
            g["flags"].append("under 20 s at move 40")
        if g.get("clk40") and g["clk40"] > 60:
            g["flags"].append("over 60 s unused at move 40")
        if info.get("init_s", 0) > 45:
            g["flags"].append("init over 45 s")
    games = sorted(by_round.values(), key=lambda g: -g["round"])
    rec: dict[str, dict] = {}
    for g in games:
        r = rec.setdefault(g["build"], {"W": 0, "D": 0, "L": 0})
        k = {"Win": "W", "Draw": "D", "Loss": "L"}.get(g.get("result", ""), None)
        if k:
            r[k] += 1
    return {"games": games[:40], "record_by_build": rec, "source": os.path.basename(csvs[-1]) if csvs else "round logs only"}


# ----------------------------------------------------------------------------- training
def training() -> list[dict]:
    runs = []
    for p in sorted(DATA.glob("train_v4*.log")):
        tag = re.search(r"train_(v4\w*)", p.name).group(1)
        lines = tail(p, 4000)
        head = "\n".join(lines[:6])
        m_ch = re.search(r"(\d+) training chunks", head)
        chunks = int(m_ch.group(1)) if m_ch else None
        prog = [re.match(r"epoch (\d+) chunk (\d+)/(\d+) loss ([\d.]+) (\d+)s", ln) for ln in lines]
        prog = [m for m in prog if m]
        done = [re.match(r"epoch (\d+) done: train ([\d.]+)(?: val ([\d.]+) val MAE (\d+)cp)?\s+(\d+)s", ln) for ln in lines]
        done = [m for m in done if m]
        epochs_done = [{"epoch": int(m.group(1)) + 1, "train": float(m.group(2)),
                        "val_mae": int(m.group(4)) if m.group(4) else None, "secs": int(m.group(5))} for m in done]
        plan = EPOCH_PLAN.get(tag, None)
        cur = None
        eta_min = None
        sec_per_chunk = None
        if prog:
            last = prog[-1]
            ep, ci, cn, loss, secs = int(last.group(1)) + 1, int(last.group(2)), int(last.group(3)), float(last.group(4)), int(last.group(5))
            sec_per_chunk = secs / max(1, ci)
            cur = {"epoch": ep, "chunk": ci, "chunks": cn, "loss": loss, "elapsed_min": round(secs / 60, 1),
                   "sec_per_chunk": round(sec_per_chunk, 1)}
            if plan:
                remaining = (cn - ci) + (plan - ep) * cn
                eta_min = round(remaining * sec_per_chunk / 60)
        finished = bool(re.search(r"exported .*safetensors", "\n".join(lines[-5:]))) and (plan is None or len(epochs_done) >= plan)
        active = age_min(p) < 10 and not finished
        runs.append({"tag": tag, "chunks_per_epoch": chunks, "epochs_planned": plan, "epochs_done": epochs_done,
                     "current": cur, "eta_min": eta_min, "active": active, "finished": finished,
                     "last_line": lines[-1] if lines else "", "age_min": round(age_min(p), 1)})
    return runs


def epoch_tables() -> list[dict]:
    """Markdown tables in the progress file whose header starts with '| v4'."""
    tables = []
    try:
        lines = PROGRESS.read_text().splitlines()
    except Exception:  # noqa: BLE001
        return tables
    i = 0
    while i < len(lines):
        if lines[i].startswith("| v4") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            header = [c.strip() for c in lines[i].strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip("|").split("|")])
                j += 1
            tables.append({"header": header, "rows": rows})
            i = j
        else:
            i += 1
    return tables


# ----------------------------------------------------------------------------- gates
def gates() -> list[dict]:
    out = []
    paths = list(DATA.glob("gate_*.log")) + list(ROOT.glob("bini*/tests/arena/*.log"))
    for p in paths:
        if age_min(p) > 60 * 24:
            continue
        lines = tail(p, 400)
        res = [re.match(r"\[(\d+)/(\d+)\] \+(\d+) =(\d+) -(\d+)\s+score ([\d.]+)%\s+elo ([+-]?\d+) ±(\d+)", ln) for ln in lines]
        res = [m for m in res if m]
        if not res:
            continue
        m = res[-1]
        n, total = int(m.group(1)), int(m.group(2))
        notes = sum(1 for ln in lines if ln.startswith("NOTE"))
        fails = sum(1 for ln in lines if "AGENT FAILURE" in ln)
        term = next((ln for ln in reversed(lines) if ln.startswith("terminations")), "")
        out.append({"name": p.stem, "path": str(p.relative_to(ROOT)), "n": n, "total": total,
                    "W": int(m.group(3)), "D": int(m.group(4)), "L": int(m.group(5)), "score": float(m.group(6)),
                    "elo": int(m.group(7)), "pm": int(m.group(8)), "fallback_games": notes, "failures": fails,
                    "running": age_min(p) < 15 and n < total, "age_min": round(age_min(p), 1), "terminations": term})
    out.sort(key=lambda g: g["age_min"])
    return out[:12]


# ----------------------------------------------------------------------------- data pipeline
def pipeline() -> dict:
    streams = []
    sp = DATA / "selfplay"
    dirs = [sp] + sorted(d for d in sp.iterdir() if d.is_dir()) if sp.exists() else []
    total_positions = 0
    for d in dirs:
        key = "." if d == sp else d.name
        chunks = list(d.glob("chunk_*.npz"))
        workers = []
        for w in sorted(d.glob("worker_*.log")):
            last = tail(w, 2)
            m = None
            for ln in reversed(last):
                m = re.search(r"w(\d+) games (\d+) positions (\d+) \((\d+)/s\)", ln)
                if m:
                    break
            if m:
                workers.append({"id": int(m.group(1)), "games": int(m.group(2)), "positions": int(m.group(3)),
                                "rate": int(m.group(4)), "active": age_min(w) < 20})
        pos = sum(w["positions"] for w in workers)
        total_positions += pos
        streams.append({"dir": key, "name": STREAM_NAMES.get(key, key), "chunks": len(chunks), "positions": pos,
                        "rate": sum(w["rate"] for w in workers if w["active"]), "workers": workers,
                        "active": any(w["active"] for w in workers)})
    sets = []
    for name in ("site_all", "site_labelled", "elite_labelled", "hard", "lichessq", "lichessq2", "lichessq3"):
        d = DATA / name
        if d.exists():
            sets.append({"name": name, "chunks": len(list(d.rglob("chunk_*.npz"))), "age_min": round(age_min(d), 0)})
    hard = DATA / "hard_fens.txt"
    hard_n = sum(1 for _ in open(hard)) if hard.exists() else 0
    book = DATA / "book.json"
    book_n = None
    if book.exists():
        try:
            book_n = len(json.load(open(book)))
        except Exception:  # noqa: BLE001
            book_n = None
    return {"streams": streams, "selfplay_positions": total_positions, "sets": sets, "hard_fens": hard_n, "book_entries": book_n,
            "book_log": tail(DATA / "book_build.log", 1)}


# ----------------------------------------------------------------------------- machines
def mac() -> dict:
    up = sh(["uptime"])
    m = re.search(r"load averages?:?\s*([\d.]+)[, ]+([\d.]+)[, ]+([\d.]+)", up)
    load = [float(x) for x in m.groups()] if m else [0, 0, 0]
    vm = sh(["vm_stat"])
    page = 16384
    m = re.search(r"page size of (\d+)", vm)
    if m:
        page = int(m.group(1))
    def pages(key: str) -> int:
        mm = re.search(rf"{key}:\s+(\d+)", vm)
        return int(mm.group(1)) if mm else 0
    free_mb = (pages("Pages free") + pages("Pages inactive")) * page / 1e6
    swap = sh(["sysctl", "-n", "vm.swapusage"])
    ms = re.search(r"used = ([\d.]+)M", swap)
    swap_mb = float(ms.group(1)) if ms else 0.0
    ps = sh(["ps", "-eo", "pcpu,rss,comm"]).splitlines()[1:]
    procs = []
    for ln in ps:
        parts = ln.split(None, 2)
        if len(parts) == 3:
            try:
                procs.append((float(parts[0]), int(parts[1]) / 1024, os.path.basename(parts[2])))
            except ValueError:
                pass
    procs.sort(reverse=True)
    top = [{"cpu": round(c, 0), "rss_mb": round(r), "name": n} for c, r, n in procs[:6] if c > 5]
    engines = sum(1 for c, r, n in procs if n.startswith("python") and c > 20)
    return {"load": load, "free_mb": round(free_mb), "swap_used_mb": round(swap_mb), "top": top,
            "busy_python": engines, "over_rule": load[0] > 10}


def vm() -> dict:
    out = sh(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", "priorcrypto-vm",
              "uptime; nproc; pgrep -c stockfish; free -m | sed -n 2p; ls ~/chess/data/selfplay/*/*.npz 2>/dev/null | wc -l"], timeout=12)
    if not out.strip():
        return {"reachable": False}
    lines = out.splitlines()
    m = re.search(r"load average: ([\d.]+), ([\d.]+), ([\d.]+)", lines[0]) if lines else None
    load = [float(x) for x in m.groups()] if m else [0, 0, 0]
    mem = lines[3].split() if len(lines) > 3 else []
    return {"reachable": True, "load": load, "cores": int(lines[1]) if len(lines) > 1 else None,
            "stockfish_procs": int(lines[2]) if len(lines) > 2 else None,
            "mem_used_mb": int(mem[2]) if len(mem) > 2 else None, "mem_total_mb": int(mem[1]) if len(mem) > 1 else None,
            "chunks_on_vm": int(lines[4]) if len(lines) > 4 else None}


# ----------------------------------------------------------------------------- chain, board, ship
def chain() -> list[dict]:
    log = "\n".join(tail(DATA / "overnight.log", 200))
    out = []
    for name, pat in CHAIN:
        m = re.search(r"^(\S+ \S+) .*" + pat, log, flags=re.M)
        out.append({"stage": name, "started": m.group(1)[11:16] if m else None})
    for i, st in enumerate(out):
        if st["started"]:
            st["state"] = "done" if i + 1 < len(out) and out[i + 1]["started"] else "running"
        else:
            st["state"] = "pending"
    return out


def board() -> dict:
    try:
        lines = PROGRESS.read_text().splitlines()
    except Exception:  # noqa: BLE001
        return {}
    rows = []
    in_board = False
    for ln in lines:
        if ln.startswith("## Board"):
            in_board = True
            continue
        if in_board and ln.startswith("## "):
            break
        if in_board and ln.startswith("|") and not ln.startswith("| Track") and not set(ln.replace("|", "").strip()) <= set("-: "):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) >= 3:
                rows.append({"track": cells[0], "state": cells[1], "next": cells[2]})
    log_lines = [ln for ln in lines if re.match(r"- \d\d:\d\d ", ln)]
    updated = next((ln for ln in lines if ln.startswith("## Board")), "")
    return {"rows": rows, "log": [ln[2:] for ln in log_lines[-8:]], "updated": updated.replace("## Board", "").strip(" ()")}


def ship() -> dict:
    zips = []
    for p in sorted(ROOT.glob("submission_*.zip"), key=os.path.getmtime, reverse=True)[:6]:
        zips.append({"name": p.name, "mb": round(p.stat().st_size / 1e6, 2),
                     "when": datetime.fromtimestamp(p.stat().st_mtime).strftime("%a %H:%M")})
    tags = sh(["git", "-C", str(ROOT), "for-each-ref", "--sort=-creatordate", "--format=%(refname:short) %(creatordate:format:%a %H:%M)", "refs/tags"]).splitlines()
    tags = [t for t in tags if "upload" in t][:5]
    return {"zips": zips, "tags": tags, "live": "V3 (submission_v3_0907_1258.zip, uploaded Mon 13:15 as dashboard v6)"}


def main() -> None:
    status = {"generated": datetime.now().strftime("%a %d %b %H:%M:%S"), "generated_utc": datetime.now(timezone.utc).isoformat()}
    for key, fn in (("platform", platform), ("training", training), ("epoch_tables", epoch_tables), ("gates", gates),
                    ("pipeline", pipeline), ("mac", mac), ("vm", vm), ("chain", chain), ("board", board), ("ship", ship)):
        try:
            status[key] = fn()
        except Exception as exc:  # noqa: BLE001
            status[key] = {"error": repr(exc)}
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(status, indent=1, default=str))
    os.replace(tmp, OUT)
    print(f"{status['generated']}: status.json written ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
