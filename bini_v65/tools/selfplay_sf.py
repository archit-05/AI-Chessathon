"""Self-play data generation: Stockfish plays itself from the tournament's curated start positions
and every position it visits is labelled by its own fixed-depth search score. Output chunks match
tools/stream_lichess.py (pieces, stm, cp, depth, quiet) plus `result` (+1 white win, 0 draw,
-1 black win, from the game the position came from) for WDL blending in the trainer.

    python tools/selfplay_sf.py --epd tools/curated.epd --out ../data/selfplay --workers 4 \
        --depth 9 --positions 10000000 [--stockfish /path/to/stockfish]

Exploration keeps games distinct: in the first EXPLORE_PLIES plies a move is picked at random
among those within EXPLORE_CP of the best (MultiPV 3) with probability P_EXPLORE_EARLY, later
with P_EXPLORE_LATE; the label is always the best move's score, from White's point of view,
clipped to +-3000 (mates = +-3000). Positions with the side to move in check are skipped (the
trainer never sees them either). Games end by rule, at 400 plies, or when |score| >= ADJ_CP for
ADJ_PLIES consecutive plies (adjudicated to the side ahead).

Legal under the rules: nothing from Stockfish ships; these are training positions labelled by an
existing engine, which the organisers explicitly allow.
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
import time
from multiprocessing import Process
from pathlib import Path

import chess
import numpy as np

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}
EXPLORE_PLIES = 16
EXPLORE_CP = 80
P_EXPLORE_EARLY = 0.35
P_EXPLORE_LATE = 0.06
ADJ_CP = 1500
ADJ_PLIES = 6
MAX_PLIES = 400
CHUNK = 200_000
DEDUP_PLIES = 12      # a position inside the first 12 plies of a game is recorded at most...
DEDUP_MAX = 3         # ...this many times per worker (the 288 openings repeat otherwise)


class SF:
    def __init__(self, path: str, hash_mb: int = 64) -> None:
        self.p = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd("setoption name Threads value 1")
        self.cmd(f"setoption name Hash value {hash_mb}")
        self.cmd("setoption name MultiPV value 3")
        self.cmd("isready"); self.wait("readyok")

    def cmd(self, s: str) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(s + "\n"); self.p.stdin.flush()

    def wait(self, token: str) -> str:
        assert self.p.stdout is not None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith(token):
                return line.strip()

    def newgame(self) -> None:
        self.cmd("ucinewgame"); self.cmd("isready"); self.wait("readyok")

    def go(self, fen: str, depth: int, multipv: int = 1) -> list[tuple[str, int]]:
        """[(move, cp from the side to move's view)] for MultiPV lines 1..k at the final depth."""
        if multipv != getattr(self, "_mpv", 3):
            self.cmd(f"setoption name MultiPV value {multipv}")
            self._mpv = multipv
        self.cmd(f"position fen {fen}"); self.cmd(f"go depth {depth}")
        lines: dict[int, tuple[str, int, int]] = {}
        self.pv1: list[str] = []
        assert self.p.stdout is not None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("stockfish exited")
            if line.startswith("info") and " multipv " in line and " score " in line and " pv " in line:
                t = line.split()
                d = int(t[t.index("depth") + 1])
                k = int(t[t.index("multipv") + 1])
                si = t.index("score")
                if t[si + 1] == "cp":
                    cp = int(t[si + 2])
                else:
                    m = int(t[si + 2])
                    cp = 3000 if m > 0 else -3000
                pi = t.index("pv")
                mv = t[pi + 1]
                if k not in lines or d >= lines[k][2]:
                    lines[k] = (mv, cp, d)
                    if k == 1:
                        self.pv1 = t[pi + 1 :]
            elif line.startswith("bestmove"):
                best = line.split()[1]
                out = [(mv, cp) for k, (mv, cp, d) in sorted(lines.items())]
                if not out or out[0][0] != best:
                    # keep the engine's actual choice first if the info lines were out of step
                    out = [(best, out[0][1] if out else 0)] + [x for x in out if x[0] != best]
                return out

    def quit(self) -> None:
        try:
            self.cmd("quit"); self.p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.p.kill()


def encode(board: chess.Board, row: np.ndarray) -> None:
    row[:] = 0
    for sq, pc in board.piece_map().items():
        row[sq] = CODES[pc.symbol()]


def material_ok(b, spec: str) -> bool:
    """spec '' = any; 'RN' = only rooks and knights (plus pawns and kings) on the board."""
    if not spec:
        return True
    import chess as _c  # noqa: PLC0415

    allowed = {_c.PAWN, _c.KING} | {{"R": _c.ROOK, "N": _c.KNIGHT, "B": _c.BISHOP, "Q": _c.QUEEN}[ch] for ch in spec}
    return all(pc.piece_type in allowed for pc in b.piece_map().values()) and len(b.piece_map()) > 4


def game_starts(games_dir: str, ply_min: int, ply_max: int, rng: random.Random, limit: int = 4000, material: str = "") -> list[str]:
    """Start positions taken from the site's own games at a random ply in [ply_min, ply_max]."""
    import io  # noqa: PLC0415
    import json  # noqa: PLC0415

    import chess.pgn  # noqa: PLC0415

    files = sorted(Path(games_dir).glob("*.json"))
    rng.shuffle(files)
    out: list[str] = []
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:  # noqa: BLE001
            continue
        pgn = d.get("pgn")
        if not pgn:
            continue
        game = chess.pgn.read_game(io.StringIO(pgn))
        if game is None:
            continue
        b = game.board()
        moves = list(game.mainline_moves())
        if len(moves) < ply_min + 2:
            continue
        target = rng.randint(ply_min, min(ply_max, len(moves) - 1))
        for m in moves[:target]:
            b.push(m)
        if material:
            # walk on until the material matches (e.g. a rook-and-knight ending), if it ever does
            k = target
            while k < len(moves) and not material_ok(b, material):
                b.push(moves[k]); k += 1
            if not material_ok(b, material):
                continue
        if not b.is_game_over() and not b.is_check():
            out.append(b.fen())
        if len(out) >= limit:
            break
    return out


def worker(wid: int, a: argparse.Namespace, fens: list[str], weights: list[float]) -> None:
    rng = random.Random(a.seed * 1000 + wid)
    if a.from_games:
        fens = game_starts(a.from_games, a.ply_min, a.ply_max, rng, material=a.material)
        weights = [1.0] * len(fens)
        print(f"w{wid}: {len(fens)} start positions from the site's games, plies {a.ply_min}-{a.ply_max}, depth {a.depth}", flush=True)
    sf = SF(a.stockfish, a.hash)
    bini = None
    if a.bini_ms > 0:
        # our own engine plays one colour (alternating per game) so the stream contains the
        # positions Bini actually reaches; every position is still labelled by Stockfish
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import bini_engine as E  # noqa: PLC0415

        bini = E.Engine(use_nnue=True)
        E.warm_up(bini)
        print(f"w{wid}: Bini plays one side at {a.bini_ms} ms per move", flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    target = a.positions // a.workers
    buf_p = np.zeros((CHUNK, 64), dtype=np.uint8)
    buf_s = np.zeros(CHUNK, dtype=np.uint8)
    buf_c = np.zeros(CHUNK, dtype=np.int16)
    buf_d = np.full(CHUNK, a.depth, dtype=np.uint8)
    buf_q = np.zeros(CHUNK, dtype=np.uint8)
    buf_r = np.zeros(CHUNK, dtype=np.int8)
    n = 0
    total = 0
    chunk_id = 0
    games = 0
    t0 = time.perf_counter()
    log = open(out / f"worker_{wid}.log", "a")
    seen: dict[str, int] = {}
    skipped_dup = 0
    while total < target:
        fen = rng.choices(fens, weights)[0]
        board = chess.Board(fen)
        sf.newgame()
        bini_colour = (chess.WHITE if games % 2 == 0 else chess.BLACK) if bini is not None else None
        if bini is not None:
            bini.new_game()
        game_rows: list[int] = []  # indices into the buffers for this game (result filled at the end)
        adj = 0
        adj_sign = 0
        result = 0
        plies = 0
        # V4.5 data fix: with probability --random-open, a walk of 2-6 uniformly random legal plies
        # before anything is recorded, so a share of the games start from imbalanced positions that
        # Stockfish then plays out (decisive games instead of 70% draws from balanced openings)
        if a.random_open > 0 and rng.random() < a.random_open:
            for _ in range(rng.randint(2, 6)):
                if board.is_game_over(claim_draw=True):
                    break
                board.push(rng.choice(list(board.legal_moves)))
            if board.is_game_over(claim_draw=True):
                continue
        while not board.is_game_over(claim_draw=True) and plies < MAX_PLIES:
            in_check = board.is_check()
            p = P_EXPLORE_EARLY if plies < EXPLORE_PLIES else P_EXPLORE_LATE
            explore = rng.random() < p
            lines = sf.go(board.fen(), a.depth, 3 if explore else 1)
            best_mv, best_cp = lines[0]
            cp_white = best_cp if board.turn == chess.WHITE else -best_cp
            cp_white = max(-3000, min(3000, cp_white))
            record = not in_check
            if record and a.balance:
                # score-balanced sampling: thin the near-zero positions that dominate self-play so
                # the label distribution is not a spike at 0 (the middlegame flattening of s24.1)
                acp = abs(cp_white)
                keep = 0.3 if acp < 40 else (0.6 if acp < 120 else 1.0)
                record = rng.random() < keep
            if record and plies < DEDUP_PLIES:
                key = board.board_fen() + (" w" if board.turn else " b")
                c = seen.get(key, 0)
                if c >= DEDUP_MAX:
                    record = False
                    skipped_dup += 1
                else:
                    seen[key] = c + 1
            rec_board = board
            if record and a.resolve:
                # walk Stockfish's line while the move to play is a capture, promotion or check,
                # so the recorded position is the quiet one its score actually describes
                rb = board.copy()
                for pmv in sf.pv1[:8]:
                    try:
                        m = chess.Move.from_uci(pmv)
                    except Exception:  # noqa: BLE001
                        break
                    if m not in rb.legal_moves:
                        break
                    if rb.is_capture(m) or m.promotion is not None or rb.gives_check(m):
                        rb.push(m)
                        continue
                    break
                if rb.is_check() or rb.is_game_over():
                    record = False
                else:
                    rec_board = rb
            if record:
                if n >= CHUNK:
                    _flush(out, wid, chunk_id, n, buf_p, buf_s, buf_c, buf_d, buf_q, buf_r)
                    chunk_id += 1
                    # rows of the current game already flushed keep result 0 (unknown): acceptable
                    game_rows = []
                    n = 0
                encode(rec_board, buf_p[n])
                buf_s[n] = 0 if rec_board.turn == chess.WHITE else 1
                buf_c[n] = cp_white
                mv0 = chess.Move.from_uci(best_mv)
                buf_q[n] = 1 if (rec_board is not board) else (0 if (board.is_capture(mv0) or mv0.promotion is not None) else 1)
                buf_r[n] = 0
                game_rows.append(n)
                n += 1
                total += 1
            # adjudication
            if abs(cp_white) >= a.adj_cp:
                s = 1 if cp_white > 0 else -1
                adj = adj + 1 if s == adj_sign else 1
                adj_sign = s
                if adj >= ADJ_PLIES:
                    result = adj_sign
                    break
            else:
                adj = 0
            # move choice: exploration among near-best MultiPV lines
            choice = best_mv
            if bini is not None and board.turn == bini_colour:
                try:
                    bini.set_position(board.fen(), [])
                    choice = bini.think(a.bini_ms, 2 * a.bini_ms, log=False)[0]
                    if chess.Move.from_uci(choice) not in board.legal_moves:
                        choice = best_mv
                except Exception:  # noqa: BLE001
                    choice = best_mv
            elif explore and len(lines) > 1:
                cands = [mv for mv, cp in lines if best_cp - cp <= EXPLORE_CP]
                choice = rng.choice(cands)
            try:
                board.push(chess.Move.from_uci(choice))
            except Exception:  # noqa: BLE001
                break
            plies += 1
        if result == 0 and (board.is_game_over(claim_draw=True)):
            oc = board.outcome(claim_draw=True)
            if oc is not None and oc.winner is not None:
                result = 1 if oc.winner == chess.WHITE else -1
        for i in game_rows:
            buf_r[i] = result
        games += 1
        if games % 20 == 0:
            el = time.perf_counter() - t0
            print(f"w{wid} games {games} positions {total} ({total / el:.0f}/s) chunks {chunk_id} dup-skipped {skipped_dup}", file=log, flush=True)
    if n > 0:
        _flush(out, wid, chunk_id, n, buf_p, buf_s, buf_c, buf_d, buf_q, buf_r)
    print(f"w{wid} done: {games} games, {total} positions, {time.perf_counter() - t0:.0f}s", file=log, flush=True)
    sf.quit()


def _flush(out: Path, wid: int, cid: int, n: int, p, s, c, d, q, r) -> None:
    tmp = out / f"chunk_w{wid}_{cid:04d}.tmp.npz"
    np.savez(tmp, pieces=p[:n].copy(), stm=s[:n].copy(), cp=c[:n].copy(), depth=d[:n].copy(), quiet=q[:n].copy(), result=r[:n].copy())
    os.replace(tmp, out / f"chunk_w{wid}_{cid:04d}.npz")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epd", default=str(Path(__file__).with_name("curated.epd")))
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--depth", type=int, default=9)
    ap.add_argument("--positions", type=int, default=10_000_000)
    ap.add_argument("--stockfish", default="stockfish")
    ap.add_argument("--hash", type=int, default=64)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--min-weight", type=float, default=3.0, help="floor on a position's sampling weight")
    ap.add_argument("--from-games", default=None, help="start from random plies of the site's cached game pages (endgame-heavy set)")
    ap.add_argument("--ply-min", type=int, default=50)
    ap.add_argument("--ply-max", type=int, default=90)
    ap.add_argument("--worker-offset", type=int, default=0, help="first worker id (so two generators never share chunk names)")
    ap.add_argument("--bini-ms", type=int, default=0, help="if > 0, our engine plays one side at this budget (positions from our own distribution)")
    ap.add_argument("--resolve", action="store_true", help="record the quiet end of Stockfish's line instead of a tactical root position")
    ap.add_argument("--material", default="", help="with --from-games: only start from positions whose pieces are within this set, e.g. RN")
    ap.add_argument("--random-open", type=float, default=0.0, help="probability of a 2-6 ply uniformly random opening walk (imbalanced, decisive games)")
    ap.add_argument("--adj-cp", type=int, default=ADJ_CP, help="adjudicate when |score| stays at or above this for ADJ_PLIES plies")
    ap.add_argument("--balance", action="store_true", help="keep |cp|<40 positions with p=0.3, <120 with p=0.6, the rest always")
    a = ap.parse_args()
    fens, weights = [], []
    for ln in Path(a.epd).read_text().splitlines():
        if not ln.strip():
            continue
        parts = [x.strip() for x in ln.split(";")]
        fens.append(parts[0])
        w = float(parts[1]) if len(parts) > 1 and parts[1].replace(".", "").isdigit() else 1.0
        weights.append(max(a.min_weight, w))
    print(f"{len(fens)} start positions, {a.workers} workers, depth {a.depth}, target {a.positions:,}", flush=True)
    procs = [Process(target=worker, args=(a.worker_offset + i, a, fens, weights)) for i in range(a.workers)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
