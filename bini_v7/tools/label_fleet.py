"""label_fleet.py -- high-throughput Stockfish position labeller writing bulletformat shards.

Two kinds of worker share one output directory OUT:

  producers  decode games with python-chess into FEN shards  OUT/queue/shard_XXXXXX.fen
             (`fen<TAB>result`, result +1/0/-1 from White's view, 0 = draw or unknown; first line
             `#sources<TAB>a.pgn,b.pgn`; up to 200k positions per shard; written to a temp name and
             renamed atomically, so a shard in queue/ is always complete)
  consumers  each own ONE Stockfish (raw pipes, Threads 1, Hash 16), claim a shard by atomic rename
             into OUT/inflight/, `ucinewgame`, then per position `position fen` + `go depth D` (or
             `go nodes N`), take the LAST multipv-1 `info ... score cp|mate` before `bestmove`
             (mate = +-3000, clipped to +-3000, from the side to move), quiet = bestmove is neither a
             capture nor a promotion, and write OUT/shard_XXXXXX.bin (bulletformat, 32 bytes/row) +
             OUT/shard_XXXXXX.meta.json, then delete the inflight .fen.

Sources (producers run only when at least one is given):
  --pgn FILE...        .pgn files or .zip archives of .pgn files
  --json-dir DIR       the site's game JSON files (a dict with a "pgn" field, or a list of them)
  --epd FILE --walk K  from every EPD root, --walks-per-root random walks of 2..K legal plies; the
                       final position of each walk is recorded (result 0, no min-ply filter)
Filters: ply >= --min-ply (8), side to move not in check, not game over / insufficient material,
>= --min-pieces pieces, keep every --stride-th position (a random per-game offset keeps both colours
to move), skip games under 20 plies, per-shard dedup of board+stm for plies <= 16.

Resumable: shards in inflight/ go back to queue/ on start (or are dropped if their .bin exists);
done shards are never re-labelled; Ctrl-C / SIGTERM makes a consumer write the rows it has and put
the rest of its shard back in the queue as shard_XXXXXXr.fen.  Sources fully processed are recorded
in OUT/produced.json and skipped on a second run (delete the file to re-produce).  One fleet per OUT.

    # produce (cheap, python-chess) and label (2 Stockfish) in one go
    python tools/label_fleet.py --out ../data/bullet --pgn ../data/elite/*.pgn --producers 8 \
        --consumers 2 --depth 7
    # produce only / label only / status
    python tools/label_fleet.py --out OUT --pgn games.zip --max-games 200 --stride 2
    python tools/label_fleet.py --out OUT --consumers 30 --depth 7 --pin --cpu-start 2
    python tools/label_fleet.py --out OUT --status

Trainer side: tools/bulletformat.read(path) returns pieces/stm/cp/result/quiet in the .npz
convention (with a `.files` attribute), so load_chunk() only needs its np.load line changed.
Consumers never import python-chess's engine module.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from multiprocessing import Array, Process, Queue, Value
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bulletformat as bf  # noqa: E402

SHARD_LINES = 200_000
SHARD_RE = re.compile(r"^shard_(\d{6}r*)$")
HEADER_RE = re.compile(r'^\[[A-Za-z0-9_]+ "')
RESULTS = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}
GAME_BATCH = 32
CP_CLIP = 3000


# ----------------------------------------------------------------------------- shared helpers

def shard_id(path: Path) -> str | None:
    m = SHARD_RE.match(path.name.split(".")[0])
    return m.group(1) if m else None


def numeric_ids(out: Path) -> list[int]:
    ids = []
    for d in (out, out / "queue", out / "inflight"):
        for p in d.glob("shard_*"):
            s = shard_id(p)
            if s:
                ids.append(int(s.rstrip("r")))
    return ids


def write_fen_shard(path: Path, sources: set[str], lines: list[str]) -> None:
    tmp = path.with_name(f".{path.name}.part")
    with open(tmp, "w") as f:
        f.write(f"#sources\t{','.join(sorted(sources))}\n")
        f.writelines(lines)
    os.replace(tmp, path)


def read_fen_shard(path: Path) -> tuple[list[str], list[str]]:
    sources: list[str] = []
    lines: list[str] = []
    with open(path) as f:
        for ln in f:
            if ln.startswith("#"):
                if ln.startswith("#sources\t"):
                    sources = [s for s in ln.rstrip("\n").split("\t", 1)[1].split(",") if s]
                continue
            if ln.strip():
                lines.append(ln)
    return sources, lines


def count_positions(path: Path) -> int:
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            n += chunk.count(b"\n")
    return max(0, n - 1)  # minus the #sources line


def pin_cpu(cpu: int, who: str) -> None:
    if hasattr(os, "sched_setaffinity"):
        try:
            os.sched_setaffinity(0, {cpu})   # what `taskset -c cpu` does; inherited by the Stockfish child
            print(f"{who}: pinned to cpu {cpu}", flush=True)
        except OSError as e:  # noqa: PERF203
            print(f"{who}: pin to cpu {cpu} failed: {e}", flush=True)
    else:
        print(f"{who}: --pin is a no-op on {sys.platform}", flush=True)


def find_stockfish(explicit: str | None) -> str:
    for cand in ([explicit] if explicit else []) + [shutil.which("stockfish") or "", "/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish", "/usr/games/stockfish"]:
        if cand and os.path.exists(cand) and os.access(cand, os.X_OK):
            return cand
    raise SystemExit("stockfish not found: pass --stockfish PATH")


# ----------------------------------------------------------------------------- feeder (sources)

def split_pgn_games(fh):
    """Yield the text of each game of a PGN stream (a header block followed by movetext)."""
    buf: list[str] = []
    in_moves = False
    for line in fh:
        if in_moves and HEADER_RE.match(line):
            yield "".join(buf)
            buf = []
            in_moves = False
        buf.append(line)
        if not in_moves and line.strip() and not line.startswith("["):
            in_moves = True
    if buf and in_moves:
        yield "".join(buf)


def iter_sources(a):
    """Yield (kind, text, source_name): kind 'pgn' (one game's PGN text) or 'epd' (one EPD line)."""
    done = load_produced(Path(a.out))
    for f in a.pgn or []:
        p = Path(f)
        if p.suffix.lower() == ".zip":
            with zipfile.ZipFile(p) as z:
                for m in z.namelist():
                    if not m.lower().endswith(".pgn"):
                        continue
                    name = f"{p.name}:{m}"
                    if name in done:
                        print(f"feeder: {name} already produced, skipping", flush=True)
                        continue
                    with z.open(m) as raw:
                        fh = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                        for g in split_pgn_games(fh):
                            yield "pgn", g, name
                    yield "done", "", name
        else:
            if p.name in done:
                print(f"feeder: {p.name} already produced, skipping", flush=True)
                continue
            with open(p, encoding="utf-8", errors="replace") as fh:
                for g in split_pgn_games(fh):
                    yield "pgn", g, p.name
            yield "done", "", p.name
    if a.json_dir:
        d = Path(a.json_dir)
        name = f"json:{d.name}"
        if name in done:
            print(f"feeder: {name} already produced, skipping", flush=True)
        else:
            for f in sorted(d.glob("*.json")):
                try:
                    obj = json.load(open(f))
                except Exception:  # noqa: BLE001
                    continue
                for g in obj if isinstance(obj, list) else [obj]:
                    pgn = g.get("pgn") if isinstance(g, dict) else None
                    if pgn:
                        yield "pgn", pgn if pgn.endswith("\n") else pgn + "\n", name
            yield "done", "", name
    if a.epd:
        p = Path(a.epd)
        if p.name in done:
            print(f"feeder: {p.name} already produced, skipping", flush=True)
        else:
            for ln in p.read_text().splitlines():
                if ln.strip() and not ln.startswith("#"):
                    yield "epd", ln, p.name
            yield "done", "", p.name


def load_produced(out: Path) -> dict:
    p = out / "produced.json"
    try:
        return json.load(open(p)) if p.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def mark_produced(out: Path, name: str, games: int) -> None:
    p = out / "produced.json"
    d = load_produced(out)
    d[name] = {"games": games, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1))
    os.replace(tmp, p)


def feeder(a, q: Queue, n_producers: int, fed: Value, capped: Value, stop: Value) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    out = Path(a.out)
    batch: list = []
    n = 0
    per_source: dict[str, int] = {}
    try:
        for kind, text, src in iter_sources(a):
            if stop.value:
                break
            if kind == "done":
                if batch:
                    q.put(batch)
                    batch = []
                mark_produced(out, src, per_source.get(src, 0))
                continue
            if a.max_games and n >= a.max_games:
                capped.value = 1
                break
            batch.append((kind, text, src))
            n += 1
            per_source[src] = per_source.get(src, 0) + 1
            if len(batch) >= GAME_BATCH:
                q.put(batch)
                batch = []
                fed.value = n
    finally:
        if batch:
            q.put(batch)
        fed.value = n
        for _ in range(n_producers):
            q.put(None)


# ----------------------------------------------------------------------------- producers

def positions_from_pgn(text: str, a, rng: random.Random, seen: set) -> list[str] | None:
    import chess  # noqa: PLC0415
    import chess.pgn  # noqa: PLC0415

    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or game.errors:
        return None
    if game.headers.get("Variant", "Standard") not in ("Standard", "From Position", "Chess960") and not a.any_variant:
        return None
    res = RESULTS.get(game.headers.get("Result", "*"))
    if res is None:
        if a.require_result:
            return None
        res = 0
    board = game.board()
    moves = list(game.mainline_moves())
    if len(moves) < 20:
        return None
    offset = rng.randrange(a.stride)
    rows: list[str] = []
    for i, mv in enumerate(moves):
        board.push(mv)
        ply = i + 1
        if ply < a.min_ply or (ply - a.min_ply) % a.stride != offset:
            continue
        if board.is_check():
            continue
        if a.min_pieces and bin(board.occupied).count("1") < a.min_pieces:
            continue
        if board.is_insufficient_material() or not any(board.generate_legal_moves()):
            continue
        if ply <= 16:
            key = board.board_fen() + ("w" if board.turn else "b")
            if key in seen:
                continue
            seen.add(key)
        rows.append(f"{board.fen()}\t{res}\n")
    return rows


def positions_from_epd(line: str, a, rng: random.Random, seen: set) -> list[str] | None:
    import chess  # noqa: PLC0415

    # first ';'-part, first 4..6 whitespace fields (EPD has no move counters; tools/curated.epd
    # appends '; weight ; name')
    fields = line.split(";")[0].split()
    if len(fields) < 4:
        return None
    fen = " ".join(fields[:6]) if len(fields) >= 6 else " ".join(fields[:4]) + " 0 1"
    try:
        root = chess.Board(fen)
    except Exception:  # noqa: BLE001
        return None
    if not root.is_valid():
        return None
    rows: list[str] = []
    for _ in range(a.walks_per_root):
        b = root.copy()
        for _ in range(rng.randint(2, max(2, a.walk))):
            moves = list(b.legal_moves)
            if not moves:
                break
            b.push(rng.choice(moves))
        if b.is_check() or b.is_insufficient_material() or not any(b.generate_legal_moves()):
            continue
        if a.min_pieces and bin(b.occupied).count("1") < a.min_pieces:
            continue
        key = b.board_fen() + ("w" if b.turn else "b")
        if key in seen:
            continue
        seen.add(key)
        rows.append(f"{b.fen()}\t0\n")
    return rows


def producer(pid: int, a, q: Queue, counter: Value, games: Array, rows: Array, active: Value) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # the feeder stops; we drain the queue and flush
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    rng = random.Random(a.seed * 1000 + pid)
    queue_dir = Path(a.out) / "queue"
    buf: list[str] = []
    seen: set = set()
    sources: set[str] = set()

    def flush(n_lines: int) -> None:
        nonlocal buf, seen, sources
        if not buf:
            return
        with counter.get_lock():
            sid = counter.value
            counter.value += 1
        write_fen_shard(queue_dir / f"shard_{sid:06d}.fen", sources, buf[:n_lines])
        buf = buf[n_lines:]
        seen = set()
        sources = set()

    try:
        while True:
            batch = q.get()
            if batch is None:
                break
            for kind, text, src in batch:
                try:
                    got = positions_from_pgn(text, a, rng, seen) if kind == "pgn" else positions_from_epd(text, a, rng, seen)
                except Exception as e:  # noqa: BLE001
                    print(f"p{pid}: skipped a game from {src}: {type(e).__name__}: {e}", flush=True)
                    got = None
                games[pid] += 1
                if not got:
                    continue
                buf.extend(got)
                rows[pid] += len(got)
                sources.add(src)
                while len(buf) >= SHARD_LINES:
                    flush(SHARD_LINES)
        flush(len(buf))
    finally:
        with active.get_lock():
            active.value -= 1


# ----------------------------------------------------------------------------- consumers

class Stockfish:
    """Raw-UCI Stockfish: one process, Threads 1, small hash; go() returns (bestmove, cp for the
    side to move) using the last multipv-1 score line before bestmove."""

    def __init__(self, path: str, hash_mb: int = 16) -> None:
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.name = ""
        self.cmd("uci")
        while True:
            line = self.readline()
            if line.startswith("id name"):
                self.name = line[8:].strip()
            if line.startswith("uciok"):
                break
        self.cmd("setoption name Threads value 1")
        self.cmd(f"setoption name Hash value {hash_mb}")
        self.cmd("setoption name MultiPV value 1")
        self.sync()

    def cmd(self, s: str) -> None:
        self.p.stdin.write(s + "\n")  # type: ignore[union-attr]
        self.p.stdin.flush()  # type: ignore[union-attr]

    def readline(self) -> str:
        line = self.p.stdout.readline()  # type: ignore[union-attr]
        if not line:
            raise RuntimeError("stockfish exited")
        return line

    def sync(self) -> None:
        self.cmd("isready")
        while not self.readline().startswith("readyok"):
            pass

    def newgame(self) -> None:
        self.cmd("ucinewgame")
        self.sync()

    def go(self, fen: str, depth: int, nodes: int) -> tuple[str, int | None]:
        self.cmd(f"position fen {fen}")
        self.cmd(f"go nodes {nodes}" if nodes else f"go depth {depth}")
        score = None
        while True:
            line = self.readline()
            if line.startswith("info"):
                if " score " not in line:
                    continue
                t = line.split()
                if "multipv" in t and t[t.index("multipv") + 1] != "1":
                    continue
                si = t.index("score")
                if t[si + 1] == "cp":
                    s = int(t[si + 2])
                elif t[si + 1] == "mate":
                    s = CP_CLIP if int(t[si + 2]) > 0 else -CP_CLIP
                else:
                    continue
                score = max(-CP_CLIP, min(CP_CLIP, s))
            elif line.startswith("bestmove"):
                return line.split()[1] if len(line.split()) > 1 else "(none)", score

    def quit(self) -> None:
        try:
            self.cmd("quit")
            self.p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.p.kill()


def claim_shard(queue_dir: Path, inflight_dir: Path) -> Path | None:
    for f in sorted(queue_dir.glob("shard_*.fen")):
        dst = inflight_dir / f.name
        try:
            os.rename(f, dst)
            return dst
        except FileNotFoundError:
            continue
    return None


def consumer(cid: int, a, rows_done: Array, producers_active: Value, stockfish: str, fleet_stop: Value) -> None:
    import chess  # noqa: PLC0415

    stop = {"flag": False}

    def _stop(signum, _frame):
        stop["flag"] = True

    def stopping() -> bool:
        if not stop["flag"] and fleet_stop.value:
            stop["flag"] = True
        return stop["flag"]

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    if a.pin:
        pin_cpu(a.cpu_start + cid, f"c{cid}")
    out = Path(a.out)
    queue_dir, inflight_dir = out / "queue", out / "inflight"
    sf = Stockfish(stockfish, a.hash)
    tag = f"c{cid}"
    t_start = time.perf_counter()
    last_t, last_rows, my_rows = t_start, 0, 0

    def limit_hit() -> bool:
        return bool(a.max_rows) and sum(rows_done[:]) >= a.max_rows

    try:
        while not stopping() and not limit_hit():
            shard = claim_shard(queue_dir, inflight_dir)
            if shard is None:
                if producers_active.value <= 0:
                    break
                time.sleep(1.0)
                continue
            sid = shard_id(shard)
            sources, lines = read_fen_shard(shard)
            n = len(lines)
            pieces = np.zeros((n, 64), dtype=np.uint8)
            stm = np.zeros(n, dtype=np.uint8)
            cp = np.zeros(n, dtype=np.int16)
            res = np.zeros(n, dtype=np.int8)
            quiet = np.zeros(n, dtype=np.uint8)
            k = 0
            done_lines = 0
            bad = 0
            t0 = time.perf_counter()
            sf.newgame()
            for i, ln in enumerate(lines):
                if (i & 15 == 0 and (stopping() or limit_hit())) or stop["flag"]:
                    break
                done_lines = i + 1
                try:
                    fen, r = ln.rstrip("\n").split("\t")
                    board = chess.Board(fen)
                except Exception:  # noqa: BLE001
                    bad += 1
                    continue
                if a.fresh:
                    sf.newgame()
                best, score = sf.go(fen, a.depth, a.nodes)
                if score is None or best in ("(none)", "0000"):
                    bad += 1
                    continue
                mv = chess.Move.from_uci(best)
                bf.board_to_row(board, pieces[k])
                stm[k] = 0 if board.turn else 1
                cp[k] = score if board.turn else -score
                res[k] = int(r)
                quiet[k] = 0 if (board.is_capture(mv) or mv.promotion is not None) else 1
                k += 1
                my_rows += 1
                rows_done[cid] = my_rows
                if (k & 255) == 0:
                    now = time.perf_counter()
                    if now - last_t >= a.report:
                        print(f"{tag} shard {sid}: {(my_rows - last_rows) / (now - last_t):.0f} pos/s (last {now - last_t:.0f}s), {my_rows} rows this run", flush=True)
                        last_t, last_rows = now, my_rows
            elapsed = time.perf_counter() - t0
            partial = done_lines < n
            if k > 0 or not partial:
                arr = bf.encode(pieces[:k], stm[:k], cp[:k], res[:k], quiet[:k], np.full(k, min(a.depth, 255), np.uint8))
                bf.write(out / f"shard_{sid}.bin", arr)
                meta = {
                    "shard": sid, "rows": int(k), "positions_in_shard": n, "skipped": bad, "depth": a.depth, "nodes": a.nodes, "fresh_hash": bool(a.fresh),
                    "elapsed_s": round(elapsed, 2), "positions_per_s": round(k / elapsed, 1) if elapsed > 0 else None,
                    "source": sources, "engine": sf.name, "consumer": cid, "partial": partial, "format": "bulletformat ChessBoard 32B; extra=[quiet,depth,stm]",
                    "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                tmp = out / f".shard_{sid}.meta.json.part"
                tmp.write_text(json.dumps(meta, indent=1))
                os.replace(tmp, out / f"shard_{sid}.meta.json")
            if partial:
                rest = lines[done_lines:]
                if rest:
                    write_fen_shard(queue_dir / f"shard_{sid}r.fen", set(sources), rest)
                if k == 0:
                    # nothing labelled: put the whole shard back under its own name
                    os.replace(shard, queue_dir / shard.name)
                    if rest:
                        os.remove(queue_dir / f"shard_{sid}r.fen")
                    continue
            os.remove(shard)
            print(f"{tag} shard {sid}: {k} rows in {elapsed:.0f}s = {k / elapsed if elapsed > 0 else 0:.0f} pos/s{' (partial, rest requeued)' if partial else ''}", flush=True)
    finally:
        sf.quit()
        el = time.perf_counter() - t_start
        print(f"{tag} done: {my_rows} rows in {el:.0f}s = {my_rows / el if el > 0 else 0:.0f} pos/s", flush=True)


# ----------------------------------------------------------------------------- orchestration

def recover(out: Path) -> None:
    queue_dir, inflight_dir = out / "queue", out / "inflight"
    for d in (queue_dir, inflight_dir):
        for part in d.glob(".*.part"):
            part.unlink()
    for part in out.glob(".*.part"):
        part.unlink()
    for f in sorted(inflight_dir.glob("shard_*.fen")):
        sid = shard_id(f)
        if sid and (out / f"shard_{sid}.bin").exists():
            print(f"recover: {f.name} already has a .bin, dropping the inflight copy", flush=True)
            f.unlink()
        else:
            print(f"recover: {f.name} -> queue", flush=True)
            os.replace(f, queue_dir / f.name)
    for f in sorted(queue_dir.glob("shard_*.fen")):
        sid = shard_id(f)
        if sid and (out / f"shard_{sid}.bin").exists():
            print(f"recover: {f.name} already labelled, dropping", flush=True)
            f.unlink()


def status(out: Path) -> None:
    queue = sorted((out / "queue").glob("shard_*.fen"))
    inflight = sorted((out / "inflight").glob("shard_*.fen"))
    done = sorted(out.glob("shard_*.bin"))
    rows = 0
    for b in done:
        m = b.with_name(b.name[:-4] + ".meta.json")
        try:
            rows += int(json.load(open(m))["rows"]) if m.exists() else bf.count(b)
        except Exception:  # noqa: BLE001
            rows += bf.count(b)
    qpos = sum(count_positions(f) for f in queue)
    ipos = sum(count_positions(f) for f in inflight)
    print(f"{out}: queue {len(queue)} shards ({qpos} positions), inflight {len(inflight)} ({ipos} positions), done {len(done)} shards, {rows} rows labelled")
    prod = load_produced(out)
    if prod:
        print("produced: " + ", ".join(f"{k} ({v['games']} games)" for k, v in prod.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description="producers + Stockfish consumers -> bulletformat shards", formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--status", action="store_true")
    src = ap.add_argument_group("sources (producers)")
    src.add_argument("--pgn", nargs="*", default=[], help=".pgn files or .zip archives of them")
    src.add_argument("--json-dir", default=None, help="site game JSON files with a 'pgn' field")
    src.add_argument("--epd", default=None)
    src.add_argument("--walk", type=int, default=8, help="with --epd: random walks of 2..K plies")
    src.add_argument("--walks-per-root", type=int, default=1)
    src.add_argument("--stride", type=int, default=1, help="keep every S-th position of a game")
    src.add_argument("--max-games", type=int, default=0)
    src.add_argument("--min-ply", type=int, default=8)
    src.add_argument("--min-pieces", type=int, default=0)
    src.add_argument("--require-result", action="store_true", help="skip games whose Result is '*'")
    src.add_argument("--any-variant", action="store_true", help="do not skip variant games")
    src.add_argument("--producers", type=int, default=8)
    src.add_argument("--seed", type=int, default=1)
    lab = ap.add_argument_group("labelling (consumers)")
    lab.add_argument("--consumers", type=int, default=0)
    lab.add_argument("--depth", type=int, default=7)
    lab.add_argument("--nodes", type=int, default=0, help="use `go nodes N` instead of depth")
    lab.add_argument("--stockfish", default=None)
    lab.add_argument("--hash", type=int, default=16)
    lab.add_argument("--max-rows", type=int, default=0, help="stop after this many rows in this run")
    lab.add_argument("--fresh", action="store_true", help="ucinewgame before every position (labels reproducible by a fresh engine; default: one per shard, warm hash)")
    lab.add_argument("--pin", action="store_true", help="pin consumer i to cpu --cpu-start + i (Linux sched_setaffinity, i.e. taskset)")
    lab.add_argument("--cpu-start", type=int, default=0)
    lab.add_argument("--report", type=float, default=60.0, help="seconds between rate reports")
    a = ap.parse_args()

    out = Path(a.out)
    if a.status:
        status(out)
        return
    have_sources = bool(a.pgn or a.json_dir or a.epd)
    if not have_sources and a.consumers <= 0:
        raise SystemExit("nothing to do: give sources (--pgn/--json-dir/--epd) and/or --consumers N")
    for d in (out, out / "queue", out / "inflight"):
        d.mkdir(parents=True, exist_ok=True)
    lock = out / "fleet.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text().split()[0])
            os.kill(pid, 0)
            raise SystemExit(f"another fleet (pid {pid}) is running on {out}; remove {lock} if it is stale")
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    lock.write_text(f"{os.getpid()} {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    try:
        recover(out)
        n_prod = a.producers if have_sources else 0
        counter = Value("q", (max(numeric_ids(out)) + 1) if numeric_ids(out) else 0)
        producers_active = Value("i", n_prod)
        games = Array("q", max(1, n_prod))
        prow = Array("q", max(1, n_prod))
        fed = Value("q", 0)
        capped = Value("i", 0)
        rows_done = Array("q", max(1, a.consumers))
        fleet_stop = Value("i", 0)
        procs: list[Process] = []
        if n_prod:
            q: Queue = Queue(maxsize=64)
            procs.append(Process(target=feeder, args=(a, q, n_prod, fed, capped, fleet_stop), name="feeder"))
            for i in range(n_prod):
                procs.append(Process(target=producer, args=(i, a, q, counter, games, prow, producers_active), name=f"p{i}"))
        stockfish = find_stockfish(a.stockfish) if a.consumers > 0 else ""
        for i in range(a.consumers):
            procs.append(Process(target=consumer, args=(i, a, rows_done, producers_active, stockfish, fleet_stop), name=f"c{i}"))
        for p in procs:
            p.start()
        print(f"fleet: {n_prod} producers, {a.consumers} consumers{' (' + stockfish + ', ' + ('nodes ' + str(a.nodes) if a.nodes else 'depth ' + str(a.depth)) + ')' if a.consumers else ''}, out {out}", flush=True)

        interrupted = {"n": 0}

        def _sigint(signum, _frame):
            interrupted["n"] += 1
            fleet_stop.value = 1   # consumers write what they have and requeue the rest; the feeder stops
            print("fleet: stopping (consumers finish their current position and requeue the rest)...", flush=True)
            if interrupted["n"] >= 3:
                for p in procs:
                    p.kill()

        signal.signal(signal.SIGINT, _sigint)
        signal.signal(signal.SIGTERM, _sigint)

        t0 = time.perf_counter()
        last_t, last_rows = t0, 0
        while any(p.is_alive() for p in procs):
            time.sleep(min(a.report, 1.0))
            now = time.perf_counter()
            if now - last_t >= a.report:
                total = sum(rows_done[:])
                nq = len(list((out / "queue").glob("shard_*.fen")))
                ni = len(list((out / "inflight").glob("shard_*.fen")))
                nd = len(list(out.glob("shard_*.bin")))
                msg = f"fleet {now - t0:.0f}s: rows {total} ({(total - last_rows) / (now - last_t):.0f}/s last {now - last_t:.0f}s, {total / (now - t0):.0f}/s avg), queue {nq} inflight {ni} done {nd}"
                if n_prod:
                    msg += f", produced {sum(prow[:])} positions from {sum(games[:])} games (fed {fed.value}), producers alive {producers_active.value}"
                print(msg, flush=True)
                last_t, last_rows = now, total
        for p in procs:
            p.join()
        el = time.perf_counter() - t0
        total = sum(rows_done[:])
        msg = f"fleet done in {el:.0f}s: {total} rows labelled ({total / el if el > 0 else 0:.0f}/s fleet, {total / el / a.consumers if el > 0 and a.consumers else 0:.0f}/s per consumer)"
        if n_prod:
            msg += f"; produced {sum(prow[:])} positions from {sum(games[:])} games" + (" (max-games reached)" if capped.value else "")
        print(msg, flush=True)
        status(out)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
