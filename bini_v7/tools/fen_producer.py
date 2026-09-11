"""FEN shard producer for the Stockfish labelling fleet (Project Prometheus, route C).

Writes `shard_XXXXXX.fen` files (200k lines of `fen<TAB>result`, result +1/0/-1 from White's view,
0 when unknown) into --out, which tools/peer_label.py labels at one fixed depth into npz chunks.
Shard ids start at --start-id so sources never collide (0-229 = the elite even plies, done).

Sources:
  --elite ZIP...      Lichess Elite zips; --parity 1 keeps odd plies (black to move; the even
                      plies were done at stride 2), ply >= --min-ply, side to move not in check
  --site-json DIR     the site's game JSON files ("pgn" field), every ply >= --min-ply
  --lichess-zst FILE  the Lichess evaluation database (jsonl.zst); every --stride-th line,
                      parsed by --workers processes; result 0
Positions with the side to move in check are skipped everywhere.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile
from multiprocessing import Pool
from pathlib import Path

import chess
import chess.pgn

SHARD = 200_000


class Writer:
    def __init__(self, out: Path, start_id: int) -> None:
        self.out, self.id, self.buf, self.total = out, start_id, [], 0
        out.mkdir(parents=True, exist_ok=True)

    def add(self, fen: str, result: int) -> None:
        self.buf.append(f"{fen}\t{result}")
        if len(self.buf) >= SHARD:
            self.flush()

    def flush(self) -> None:
        if not self.buf:
            return
        tmp = self.out / f"shard_{self.id:06d}.fen.tmp"
        tmp.write_text("\n".join(self.buf) + "\n")
        os.rename(tmp, self.out / f"shard_{self.id:06d}.fen")
        self.total += len(self.buf)
        self.id += 1
        self.buf = []


RESULTS = {"1-0": 1, "0-1": -1, "1/2-1/2": 0}


def games_from_pgn_text(text: str):
    f = io.StringIO(text)
    while True:
        g = chess.pgn.read_game(f)
        if g is None:
            return
        yield g


def emit_game(game, w: Writer, min_ply: int, parity: int | None) -> int:
    res = RESULTS.get(game.headers.get("Result", "*"), 0)
    board = game.board()
    n = 0
    for ply, mv in enumerate(game.mainline_moves(), start=1):
        board.push(mv)
        if ply < min_ply or (parity is not None and ply % 2 != parity) or board.is_check():
            continue
        w.add(board.fen(), res)
        n += 1
    return n


def do_elite(zips: list[str], w: Writer, min_ply: int, parity: int) -> None:
    for zp in zips:
        t0, games = time.time(), 0
        print(f"elite {zp}", flush=True)
        with zipfile.ZipFile(zp) as zf:
            for name in zf.namelist():
                if not name.endswith(".pgn"):
                    continue
                with zf.open(name) as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8", errors="ignore")
                    while True:
                        g = chess.pgn.read_game(text)
                        if g is None:
                            break
                        games += 1
                        emit_game(g, w, min_ply, parity)
                        if games % 20000 == 0:
                            print(f"  {games} games, {w.total + len(w.buf)} positions, {time.time() - t0:.0f}s", flush=True)
        w.flush()


def do_site(d: str, w: Writer, min_ply: int) -> None:
    n = 0
    for f in sorted(Path(d).glob("*.json")):
        try:
            pgn = json.load(open(f)).get("pgn")
        except Exception:  # noqa: BLE001
            continue
        if not pgn:
            continue
        for g in games_from_pgn_text(pgn):
            emit_game(g, w, min_ply, None)
            n += 1
    w.flush()
    print(f"site: {n} games, {w.total} positions", flush=True)


def _parse_lines(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        try:
            fen = json.loads(line)["fen"]
            b = chess.Board(fen)
        except Exception:  # noqa: BLE001
            continue
        if b.is_check() or not b.is_valid():
            continue
        out.append(b.fen())
    return out


def do_lichess(path: str, w: Writer, stride: int, workers: int, max_positions: int) -> None:
    import zstandard  # noqa: PLC0415

    t0 = time.time()
    with open(path, "rb") as fh, Pool(workers) as pool:
        reader = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8", errors="ignore")
        batch, batches, seen = [], [], 0

        def gen():
            nonlocal batch, seen
            for line in reader:
                seen += 1
                if seen % stride:
                    continue
                batch.append(line)
                if len(batch) >= 20000:
                    yield batch
                    batch = []
            if batch:
                yield batch

        for fens in pool.imap(_parse_lines, gen(), chunksize=1):
            for fen in fens:
                w.add(fen, 0)
            if w.total >= max_positions:
                break
            if (w.total // SHARD) % 10 == 0 and len(w.buf) < 100:
                print(f"  lichess: {seen} lines read, {w.total} positions, {time.time() - t0:.0f}s", flush=True)
    w.flush()
    print(f"lichess done: {seen} lines, {w.total} positions, {time.time() - t0:.0f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-id", type=int, required=True)
    ap.add_argument("--min-ply", type=int, default=8)
    ap.add_argument("--elite", nargs="*", default=[])
    ap.add_argument("--parity", type=int, default=1)
    ap.add_argument("--site-json")
    ap.add_argument("--lichess-zst")
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-positions", type=int, default=10**12)
    a = ap.parse_args()
    w = Writer(Path(a.out), a.start_id)
    if a.elite:
        do_elite(a.elite, w, a.min_ply, a.parity)
    if a.site_json:
        do_site(a.site_json, w, a.min_ply)
    if a.lichess_zst:
        do_lichess(a.lichess_zst, w, a.stride, a.workers, a.max_positions)
    print(f"total {w.total} positions, next id {w.id}", flush=True)


if __name__ == "__main__":
    main()
