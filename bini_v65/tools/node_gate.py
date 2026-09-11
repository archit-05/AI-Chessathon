"""Match runner with PERSISTENT engine processes (fixed nodes or a real clock).

    cd bini_v5 && ../aichessathon-starter/.venv/bin/python tools/node_gate.py \
        --a "BINI_NNUE=/abs/nnue_v3b.safetensors" --b "BINI_SEEP=0" \
        --openings tools/curated.epd --games 600 --nodes 30000 --workers 6 --pin --out /tmp/gate_x

Both sides run the SAME engine code (--engine DIR, default bini_v5) under different environments.
Each worker starts its two engines once (about 25 s of numba compile per engine, paid once instead
of once per game as tools/arena_par.py does) and then plays pair after pair on them: every opening
is played twice with colours swapped (game 2k: A white, game 2k+1: B white). The parent is the
referee: python-chess legality (an illegal move loses), checkmate, stalemate, insufficient
material, threefold, fifty-move and the ply cap (draw). No adjudication.

    --nodes N      fixed nodes per move (deterministic: a self-match mirrors exactly)
    --tc 5+0.05    base+increment seconds; budgets use the _budget formula of agent.py with
                   INCREMENT_MS = the increment given here; both clocks are tracked including the
                   increment after each move and a side that overruns its clock loses on time

Results are tallied per opening pair as a pentanomial from A's view (LL, LD, WL/DD, WD, WW);
score %, the pentanomial standard error and Elo +-1.96 SE go to PREFIX.log every 10 games and at
the end; PREFIX.pgn (SetUp/FEN tags), PREFIX.json (summary + every game) and PREFIX.err (engine
stderr) complete the output.

The same file is the engine driver (`python node_gate.py --driver`, cwd = engine dir): it imports
bini_engine from cwd, compiles once and then serves JSON lines on stdin.
"""

from __future__ import annotations

import argparse
import atexit
import json
import math
import os
import queue
import random
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# ----------------------------------------------------------------------------------------------
# clock policy: the _budget formula of agent.py, verbatim except that INCREMENT_MS comes from --tc
# and the four ABSOLUTE clock thresholds are scaled by CLOCK_SCALE = base / 120 s.
# Why: agent._budget's 4000/30000/10000/RESERVE_MS constants are tuned for the platform's 120 s
# base. Copied unscaled into a short gate they fire almost immediately -- at --tc 5+0.05 the engine
# drops into the emergency branch after one move and plays ~20 ms a move for the rest of the game,
# so every "5 s" and "10 s" verdict was a fixed-node verdict wearing a clock. At --tc 120+0.5
# CLOCK_SCALE is exactly 1.0 and this is byte-identical to agent.py.
INCREMENT_MS = 500
RESERVE_MS = 1500
CLOCK_SCALE = 1.0
MIN_THINK_MS = 8
MIDGAME_BOOST = float(os.environ.get("BINI_MIDGAME_BOOST", "1.0"))


def _budget(time_left_ms: int, move_number: int) -> tuple[float, float]:
    """Soft and hard limits in milliseconds for this move (copied from agent.py)."""
    if time_left_ms < 4000 * CLOCK_SCALE:
        soft = min(0.4 * INCREMENT_MS, 0.05 * time_left_ms)
        hard = min(0.8 * INCREMENT_MS, 0.15 * time_left_ms)
        return max(MIN_THINK_MS, soft), max(MIN_THINK_MS, hard)
    mtg = max(18.0, 34.0 - 0.4 * move_number)
    if 15 <= move_number < 35:
        mtg /= MIDGAME_BOOST
    soft = time_left_ms / mtg + 0.6 * INCREMENT_MS
    hard = min(2.2 * soft, 0.2 * time_left_ms, time_left_ms - RESERVE_MS * CLOCK_SCALE)
    if time_left_ms < 30000 * CLOCK_SCALE:
        hard = min(hard, time_left_ms / 15.0 + 0.6 * INCREMENT_MS)
    if time_left_ms < 10000 * CLOCK_SCALE:
        soft = min(soft, 0.06 * time_left_ms + 0.4 * INCREMENT_MS)
        hard = min(hard, 0.12 * time_left_ms + 0.6 * INCREMENT_MS)
    soft = min(soft, hard)
    return max(MIN_THINK_MS, soft), max(MIN_THINK_MS, hard)


# ==============================================================================================
# driver: one persistent engine process
# ==============================================================================================
def driver_main() -> None:
    t_start = time.perf_counter()
    sys.path.insert(0, os.getcwd())
    # the protocol owns the real stdout; anything else that prints goes to stderr
    out = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    sys.stdout = sys.stderr
    tag = os.environ.get("NODE_GATE_TAG", "?")

    def send(obj: dict) -> None:
        out.write(json.dumps(obj) + "\n")
        out.flush()

    import chess  # noqa: PLC0415

    import bini_board as B  # noqa: PLC0415
    import bini_engine as E  # noqa: PLC0415

    eng = E.Engine(use_nnue=True)
    compile_s = E.warm_up(eng)
    scratch = B.new_position()

    def key_of(board: chess.Board) -> int:
        # keyed from the FEN exactly as agent.py does (GameState._key), so history and root agree
        bb, st, pcs = scratch
        B.set_fen(bb, st, pcs, board.fen())
        return int(bb[15])

    send({"ready": True, "startup_s": round(time.perf_counter() - t_start, 1), "compile_s": round(compile_s, 2), "nnue": bool(eng.use_nnue), "version": E.VERSION,
          "nnue_path": str(sys.modules["bini_nnue"].WEIGHTS_PATH), "pid": os.getpid(), "tag": tag})

    board: chess.Board | None = None
    keys: list[int] = []
    own_moves = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        cmd = req.get("cmd")
        if cmd == "quit":
            break
        if cmd == "newgame":
            board = chess.Board(req["fen"])
            eng.new_game()
            eng.set_position(board.fen(), [])
            keys = [key_of(board)]
            own_moves = 0
            send({"ok": True})
        elif cmd == "move":
            assert board is not None
            board.push(chess.Move.from_uci(req["uci"]))
            eng.play_uci(req["uci"])
            keys.append(key_of(board))
            send({"ok": True})
        elif cmd == "go":
            assert board is not None
            t0 = time.perf_counter()
            eng.set_position(board.fen(), keys[:-1])
            eng.move_number = own_moves
            if "nodes" in req:
                uci, score, depth = eng.think(1e9, 1e9, log=False, max_nodes=int(req["nodes"]))
            else:
                overhead = (time.perf_counter() - t0) * 1000.0
                uci, score, depth = eng.think(float(req["soft_ms"]), max(MIN_THINK_MS, float(req["hard_ms"]) - overhead), log=False)
            nodes = int(eng.info[sys.modules["bini_search"].I_NODES])
            ms = (time.perf_counter() - t0) * 1000.0
            mv = chess.Move.from_uci(uci) if uci != "0000" else None
            if mv is not None and mv in board.legal_moves:
                board.push(mv)
                eng.play_uci(uci)
                keys.append(key_of(board))
            own_moves += 1
            send({"move": uci, "score": int(score), "depth": int(depth), "nodes": nodes, "ms": round(ms, 1)})
        else:
            send({"error": f"unknown cmd {cmd!r}"})


# ==============================================================================================
# parent: engine handles, referee, tally
# ==============================================================================================
_CHILDREN: list[subprocess.Popen] = []
_CHILD_LOCK = threading.Lock()


def _kill_all() -> None:
    with _CHILD_LOCK:
        procs = list(_CHILDREN)
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:  # noqa: BLE001
            pass
    for p in procs:
        try:
            p.wait(timeout=2)
        except Exception:  # noqa: BLE001
            pass


atexit.register(_kill_all)


class EngineDied(RuntimeError):
    pass


class EngineProc:
    """A long-lived driver process for one side."""

    def __init__(self, engine_dir: Path, env: dict[str, str], tag: str, err_fh, cpu: int | None, ready_timeout: float) -> None:
        self.tag = tag
        cmd = [sys.executable, str(Path(__file__).resolve()), "--driver"]
        if cpu is not None and sys.platform.startswith("linux") and shutil.which("taskset"):
            cmd = ["taskset", "-c", str(cpu)] + cmd
        full_env = dict(os.environ)
        full_env.update(env)
        full_env["NODE_GATE_TAG"] = tag
        full_env.setdefault("PYTHONUNBUFFERED", "1")
        self.proc = subprocess.Popen(cmd, cwd=str(engine_dir), env=full_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_fh, start_new_session=True)
        with _CHILD_LOCK:
            _CHILDREN.append(self.proc)
        self.ready = self._read(ready_timeout)
        if not self.ready.get("ready"):
            raise EngineDied(f"{tag}: bad ready line {self.ready}")

    def _read(self, timeout: float) -> dict:
        fh = self.proc.stdout
        assert fh is not None
        deadline = time.monotonic() + timeout
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise EngineDied(f"{self.tag}: no reply within {timeout:.0f}s")
            r, _, _ = select.select([fh], [], [], min(left, 1.0))
            if r:
                break
            if self.proc.poll() is not None:
                raise EngineDied(f"{self.tag}: process exited with {self.proc.returncode}")
        line = fh.readline()
        if not line:
            raise EngineDied(f"{self.tag}: EOF (exit {self.proc.poll()})")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise EngineDied(f"{self.tag}: unparsable reply {line[:200]!r}") from exc

    def ask(self, obj: dict, timeout: float) -> dict:
        try:
            assert self.proc.stdin is not None
            self.proc.stdin.write((json.dumps(obj) + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise EngineDied(f"{self.tag}: write failed ({exc})") from exc
        return self._read(timeout)

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                assert self.proc.stdin is not None
                self.proc.stdin.write(b'{"cmd":"quit"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            pass
        try:
            if self.proc.poll() is None:
                self.proc.kill()
                self.proc.wait(timeout=2)
        except Exception:  # noqa: BLE001
            pass
        with _CHILD_LOCK:
            if self.proc in _CHILDREN:
                _CHILDREN.remove(self.proc)


def parse_env(spec: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for item in (spec or "").split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise SystemExit(f"bad env item {item!r} (want NAME=value)")
        k, v = item.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def load_openings(path: str) -> list[tuple[str, str]]:
    import chess  # noqa: PLC0415

    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(";")]
        fen = chess.Board(parts[0]).fen()  # normalised 6-field FEN
        name = parts[-1] if len(parts) > 1 else ""
        out.append((fen, name))
    if not out:
        raise SystemExit(f"no openings in {path}")
    return out


# ----------------------------------------------------------------------------------------------
class Referee:
    """Plays one game between two EngineProc handles on its own python-chess board."""

    def __init__(self, args: argparse.Namespace, log) -> None:
        self.args = args
        self.log = log
        self.stop = threading.Event()

    def play(self, white: EngineProc, black: EngineProc, fen: str, white_is_a: bool) -> dict:
        import chess  # noqa: PLC0415

        a = self.args
        board = chess.Board(fen)
        start_ply = board.ply()
        for e in (white, black):
            e.ask({"cmd": "newgame", "fen": fen}, 60.0)
        timed = a.tc is not None
        clocks = {white.tag: a.base_ms, black.tag: a.base_ms} if timed else {}
        own_moves = {white.tag: 0, black.tag: 0}
        moves: list[str] = []
        infos: list[dict] = []
        result, term = "1/2-1/2", "unknown"
        max_ms = 0.0
        while True:
            if self.stop.is_set():
                raise EngineDied("stopped")
            oc = board.outcome(claim_draw=True)
            if oc is not None:
                result = oc.result()
                term = oc.termination.name.lower()
                break
            if board.ply() - start_ply >= a.max_ply:
                result, term = "1/2-1/2", "ply_cap"
                break
            mover, other = (white, black) if board.turn == chess.WHITE else (black, white)
            if timed:
                left = clocks[mover.tag]
                soft, hard = _budget(int(left), own_moves[mover.tag])
                req = {"cmd": "go", "soft_ms": soft, "hard_ms": hard}
                timeout = hard / 1000.0 + 60.0
            else:
                req = {"cmd": "go", "nodes": a.nodes}
                timeout = a.move_timeout
            t0 = time.perf_counter()
            rep = mover.ask(req, timeout)
            spent = (time.perf_counter() - t0) * 1000.0
            max_ms = max(max_ms, spent)
            uci = rep.get("move", "0000")
            infos.append({"uci": uci, "score": rep.get("score"), "depth": rep.get("depth"), "nodes": rep.get("nodes"), "ms": round(spent, 1)})
            own_moves[mover.tag] += 1
            if timed:
                clocks[mover.tag] -= spent
                if clocks[mover.tag] < 0:
                    result = "0-1" if board.turn == chess.WHITE else "1-0"
                    term = "flag"
                    self.log(f"FLAG: {mover.tag} overran its clock by {-clocks[mover.tag]:.0f} ms (spent {spent:.0f} ms, budget soft {soft:.0f}/hard {hard:.0f}) in {board.fen()}")
                    break
                clocks[mover.tag] += a.inc_ms
            try:
                mv = chess.Move.from_uci(uci)
            except ValueError:
                mv = None
            if mv is None or mv not in board.legal_moves:
                result = "0-1" if board.turn == chess.WHITE else "1-0"
                term = "illegal"
                self.log(f"ILLEGAL MOVE: {mover.tag} played {uci!r} in {board.fen()} (after {' '.join(moves)})")
                break
            board.push(mv)
            moves.append(uci)
            other.ask({"cmd": "move", "uci": uci}, 60.0)
        a_pts = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}[result]
        if not white_is_a:
            a_pts = 1.0 - a_pts
        return {"fen": fen, "white": white.tag, "black": black.tag, "result": result, "termination": term, "plies": len(moves),
                "moves": moves, "infos": infos, "a_points": a_pts, "max_move_ms": round(max_ms, 1),
                "clocks_ms": {k: round(v) for k, v in clocks.items()} if timed else None}


# ----------------------------------------------------------------------------------------------
class Tally:
    S_VALS = (0.0, 0.25, 0.5, 0.75, 1.0)

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pent = [0, 0, 0, 0, 0]
        self.w = self.d = self.l = 0
        self.games_done = 0
        self.errors = 0
        self.terms: dict[str, int] = {}

    def add_pair(self, g1: dict, g2: dict) -> None:
        with self.lock:
            idx = int(round((g1["a_points"] + g2["a_points"]) * 2))
            self.pent[idx] += 1
            for g in (g1, g2):
                self.games_done += 1
                self.terms[g["termination"]] = self.terms.get(g["termination"], 0) + 1
                if g["a_points"] == 1.0:
                    self.w += 1
                elif g["a_points"] == 0.0:
                    self.l += 1
                else:
                    self.d += 1

    def stats(self) -> dict:
        n = sum(self.pent)
        if n == 0:
            return {"pairs": 0, "score": 0.5, "se": 0.0, "elo": 0.0, "elo_pm": 0.0}
        mean = sum(c * s for c, s in zip(self.pent, self.S_VALS)) / n
        var = sum(c * (s - mean) ** 2 for c, s in zip(self.pent, self.S_VALS)) / n
        se = math.sqrt(var / n)
        p = min(max(mean, 1e-6), 1 - 1e-6)
        elo = -400.0 * math.log10(1.0 / p - 1.0)
        pm = 1.96 * se * 400.0 / (math.log(10.0) * p * (1.0 - p))
        return {"pairs": n, "score": mean, "se": se, "elo": elo, "elo_pm": pm}

    def line(self, total_games: int) -> str:
        st = self.stats()
        return (f"[{self.games_done}/{total_games}] +{self.w} ={self.d} -{self.l} score {st['score']*100:.1f}% "
                f"elo {st['elo']:+.0f} ±{st['elo_pm']:.0f} (pentanomial {self.pent}" + (f", {self.errors} error pair(s)" if self.errors else "") + ")")


def game_pgn(g: dict, opening: str, round_tag: str, env_a: str, env_b: str) -> str:
    import chess  # noqa: PLC0415
    import chess.pgn  # noqa: PLC0415

    game = chess.pgn.Game()
    game.setup(chess.Board(g["fen"]))
    h = game.headers
    h["Event"] = "node_gate"
    h["Site"] = "local"
    h["Round"] = round_tag
    h["White"] = g["white"]
    h["Black"] = g["black"]
    h["Result"] = g["result"]
    h["Termination"] = g["termination"]
    h["PlyCount"] = str(g["plies"])
    if opening:
        h["Opening"] = opening
    h["EnvA"] = env_a or "-"
    h["EnvB"] = env_b or "-"
    node = game
    for uci, info in zip(g["moves"], g["infos"]):
        node = node.add_variation(chess.Move.from_uci(uci))
        if info.get("score") is not None:
            node.comment = f"{info['score']}cp d{info['depth']} {info['nodes']}n {info['ms']:.0f}ms"
    return str(game)


# ----------------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--driver", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--engine", default=str(Path(__file__).resolve().parents[1]), help="engine directory (default: the bini_v5 this file lives in)")
    ap.add_argument("--a", default="", help='environment for side A, e.g. "BINI_NNUE=/abs/x.safetensors,BINI_SEEP=0"')
    ap.add_argument("--b", default="", help="environment for side B")
    ap.add_argument("--openings", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--games", type=int, default=100, help="games (2 per opening pair; an odd count is rounded up)")
    ap.add_argument("--nodes", type=int, default=0, help="fixed nodes per move")
    ap.add_argument("--tc", default=None, help="base+increment in seconds, e.g. 5+0.05 (instead of --nodes)")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--pin", action="store_true", help="Linux: taskset each worker's two engines onto two CPU ids")
    ap.add_argument("--tt-bits", type=int, default=22, help="BINI_TT_BITS for both engines (22 = 64 MB each)")
    ap.add_argument("--out", default="node_gate", help="output prefix: PREFIX.pgn / .json / .log / .err")
    ap.add_argument("--seed", type=int, default=0, help="0 = openings in file order, otherwise shuffle the opening order with this seed")
    ap.add_argument("--max-ply", type=int, default=600, help="plies from the start position after which the game is a draw")
    ap.add_argument("--move-timeout", type=float, default=300.0, help="seconds to wait for a fixed-node move before declaring the engine dead")
    ap.add_argument("--ready-timeout", type=float, default=600.0, help="seconds to wait for an engine to compile")
    args = ap.parse_args()

    if args.driver:
        driver_main()
        return

    if (args.nodes > 0) == (args.tc is not None):
        raise SystemExit("give exactly one of --nodes N or --tc base+inc")
    args.base_ms = args.inc_ms = 0.0
    if args.tc is not None:
        global INCREMENT_MS, CLOCK_SCALE
        base, _, inc = args.tc.partition("+")
        args.base_ms = float(base) * 1000.0
        args.inc_ms = float(inc or 0) * 1000.0
        INCREMENT_MS = args.inc_ms
        CLOCK_SCALE = args.base_ms / 120000.0

    engine_dir = Path(args.engine).resolve()
    if not (engine_dir / "bini_engine.py").exists():
        raise SystemExit(f"{engine_dir} has no bini_engine.py")
    env_a, env_b = parse_env(args.a), parse_env(args.b)
    for env in (env_a, env_b):
        env.setdefault("BINI_TT_BITS", str(args.tt_bits))
        env.setdefault("BINI_BOOK", "0")
    openings = load_openings(args.openings)
    if args.seed:
        random.Random(args.seed).shuffle(openings)
    n_pairs = (args.games + 1) // 2
    total_games = 2 * n_pairs

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    log_fh = open(f"{out}.log", "a")
    pgn_fh = open(f"{out}.pgn", "a")
    err_fh = open(f"{out}.err", "a")
    io_lock = threading.Lock()

    def log(msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        with io_lock:
            print(line, flush=True)
            log_fh.write(line + "\n")
            log_fh.flush()

    mode = f"nodes {args.nodes}" if args.nodes else f"tc {args.tc} (base {args.base_ms:.0f} ms, inc {args.inc_ms:.0f} ms)"
    log(f"node_gate: engine {engine_dir}, {mode}, {n_pairs} pairs / {total_games} games, {len(openings)} openings, {args.workers} worker(s), tt-bits {args.tt_bits}, max-ply {args.max_ply}")
    log(f"  A env: {env_a}")
    log(f"  B env: {env_b}")

    tally = Tally()
    games: list[dict] = []
    pair_results: dict[int, dict] = {}
    referee = Referee(args, log)
    pairs_q: queue.Queue[int] = queue.Queue()
    for k in range(n_pairs):
        pairs_q.put(k)
    last_report = [0]
    ncpu = os.cpu_count() or 1

    def start_engines(w: int) -> tuple[EngineProc, EngineProc]:
        cpu_a = cpu_b = None
        if args.pin:
            cpu_a, cpu_b = (2 * w) % ncpu, (2 * w + 1) % ncpu
        ea = EngineProc(engine_dir, env_a, "A", err_fh, cpu_a, args.ready_timeout)
        eb = EngineProc(engine_dir, env_b, "B", err_fh, cpu_b, args.ready_timeout)
        log(f"worker {w}: engines ready: A pid {ea.ready['pid']} startup {ea.ready['startup_s']}s nnue={ea.ready['nnue']} ({ea.ready['nnue_path']}); "
            f"B pid {eb.ready['pid']} startup {eb.ready['startup_s']}s nnue={eb.ready['nnue']} ({eb.ready['nnue_path']})")
        return ea, eb

    def worker(w: int) -> None:
        ea = eb = None
        try:
            ea, eb = start_engines(w)
        except EngineDied as exc:
            log(f"worker {w}: could not start engines: {exc}")
            return
        while not referee.stop.is_set():
            try:
                k = pairs_q.get_nowait()
            except queue.Empty:
                break
            fen, name = openings[k % len(openings)]
            try:
                g1 = referee.play(ea, eb, fen, True)
                g2 = referee.play(eb, ea, fen, False)
            except EngineDied as exc:
                if referee.stop.is_set():
                    break
                log(f"worker {w}: pair {k} ERROR: {exc}; restarting this worker's engines")
                with tally.lock:
                    tally.errors += 1
                    pair_results[k] = {"error": str(exc), "opening": name}
                for e in (ea, eb):
                    if e is not None:
                        e.close()
                try:
                    ea, eb = start_engines(w)
                except EngineDied as exc2:
                    log(f"worker {w}: restart failed: {exc2}; worker stops")
                    return
                continue
            tally.add_pair(g1, g2)
            with io_lock:
                pgn_fh.write(game_pgn(g1, name, f"{k}.1", args.a, args.b) + "\n\n")
                pgn_fh.write(game_pgn(g2, name, f"{k}.2", args.a, args.b) + "\n\n")
                pgn_fh.flush()
            with tally.lock:
                for i, g in enumerate((g1, g2)):
                    g["pair"], g["game"], g["opening"] = k, 2 * k + i, name
                    games.append(g)
                pair_results[k] = {"opening": name, "a_points": g1["a_points"] + g2["a_points"], "results": [g1["result"], g2["result"]], "terminations": [g1["termination"], g2["termination"]]}
            for i, g in enumerate((g1, g2)):
                log(f"pair {k} game {2*k+i} [{name}] W={g['white']} B={g['black']} {g['result']} by {g['termination']} in {g['plies']} plies (max {g['max_move_ms']:.0f} ms/move): {' '.join(g['moves'])}")
            with tally.lock:
                due = tally.games_done // 10 > last_report[0]
                if due:
                    last_report[0] = tally.games_done // 10
            if due:
                log(tally.line(total_games))
        for e in (ea, eb):
            if e is not None:
                e.close()

    def on_signal(signum, frame):  # noqa: ARG001
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    t_start = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(w,), daemon=True, name=f"worker-{w}") for w in range(args.workers)]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.5)
    except KeyboardInterrupt:
        log("interrupted: stopping workers and killing engines")
        referee.stop.set()
        _kill_all()
        for t in threads:
            t.join(timeout=5)
    finally:
        _kill_all()

    elapsed = time.perf_counter() - t_start
    st = tally.stats()
    final = tally.line(total_games)
    log(final)
    log(f"terminations: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.terms.items())) + f"; {elapsed:.0f} s wall")
    summary = {
        "args": {k: v for k, v in vars(args).items() if k != "driver"},
        "env_a": env_a, "env_b": env_b,
        "games_total": total_games, "games_done": tally.games_done, "error_pairs": tally.errors,
        "wins": tally.w, "draws": tally.d, "losses": tally.l, "pentanomial": tally.pent,
        "score": st["score"], "se": st["se"], "elo": st["elo"], "elo_pm95": st["elo_pm"],
        "terminations": tally.terms, "wall_s": round(elapsed, 1), "final": final,
        "pairs": {str(k): v for k, v in sorted(pair_results.items())},
        "games": sorted(games, key=lambda g: g["game"]),
    }
    Path(f"{out}.json").write_text(json.dumps(summary, indent=1))
    log_fh.close()
    pgn_fh.close()
    err_fh.close()


if __name__ == "__main__":
    main()
