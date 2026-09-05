"""Stream the Lichess evaluation database (CC0) from stdin and write compact training chunks.

    curl -sL https://database.lichess.org/lichess_db_eval.jsonl.zst | zstd -dc \
        | python tools/stream_lichess.py 60000000 ../data/lichess

Each chunk: pieces uint8[N, 64] (0 empty, 1..6 white P N B R Q K, 7..12 black), stm uint8[N]
(0 white, 1 black), cp int16[N] (white's point of view, clipped to +-3000, mates = +-3000),
depth uint8[N]. Only the deepest evaluation of each position is kept, and only if depth >= 12.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

CODES = {"P": 1, "N": 2, "B": 3, "R": 4, "Q": 5, "K": 6, "p": 7, "n": 8, "b": 9, "r": 10, "q": 11, "k": 12}
MIN_DEPTH = 12
CHUNK = 1_000_000
BATCH = 20_000


def parse_batch(lines: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    pieces = np.zeros((len(lines), 64), dtype=np.uint8)
    stm = np.zeros(len(lines), dtype=np.uint8)
    cps = np.zeros(len(lines), dtype=np.int16)
    depths = np.zeros(len(lines), dtype=np.uint8)
    n = 0
    for line in lines:
        try:
            d = json.loads(line)
            best = None
            for ev in d["evals"]:
                if best is None or ev["depth"] > best["depth"]:
                    best = ev
            if best is None or best["depth"] < MIN_DEPTH:
                continue
            pv = best["pvs"][0]
            if "cp" in pv:
                cp = max(-3000, min(3000, int(pv["cp"])))
            elif "mate" in pv:
                cp = 3000 if int(pv["mate"]) > 0 else -3000
            else:
                continue
            fen = d["fen"].split()
            rank = 7
            f = 0
            row = pieces[n]
            for ch in fen[0]:
                if ch == "/":
                    rank -= 1
                    f = 0
                elif ch.isdigit():
                    f += int(ch)
                else:
                    row[rank * 8 + f] = CODES[ch]
                    f += 1
            stm[n] = 0 if fen[1] == "w" else 1
            cps[n] = cp
            depths[n] = min(255, best["depth"])
            n += 1
        except Exception:  # noqa: BLE001 - a malformed line is skipped, never fatal
            pieces[n] = 0
            continue
    return pieces[:n], stm[:n], cps[:n], depths[:n]


def main() -> None:
    limit = int(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    kept = 0
    seen = 0
    chunk_id = 0
    buf_p, buf_s, buf_c, buf_d = [], [], [], []
    buffered = 0

    def flush() -> None:
        nonlocal chunk_id, buf_p, buf_s, buf_c, buf_d, buffered
        if buffered == 0:
            return
        np.savez(out / f"chunk_{chunk_id:04d}.npz", pieces=np.concatenate(buf_p), stm=np.concatenate(buf_s), cp=np.concatenate(buf_c), depth=np.concatenate(buf_d))
        print(f"chunk {chunk_id} written ({buffered} positions, {kept} kept of {seen} seen)", file=sys.stderr, flush=True)
        chunk_id += 1
        buf_p, buf_s, buf_c, buf_d = [], [], [], []
        buffered = 0

    with Pool(6) as pool:
        pending = []
        batch: list[str] = []
        for line in sys.stdin:
            batch.append(line)
            seen += 1
            if len(batch) >= BATCH:
                pending.append(pool.apply_async(parse_batch, (batch,)))
                batch = []
                if len(pending) >= 12:
                    p, s, c, dd = pending.pop(0).get()
                    buf_p.append(p); buf_s.append(s); buf_c.append(c); buf_d.append(dd)
                    buffered += len(c)
                    kept += len(c)
                    if buffered >= CHUNK:
                        flush()
            if seen >= limit:
                break
        if batch:
            pending.append(pool.apply_async(parse_batch, (batch,)))
        for r in pending:
            p, s, c, dd = r.get()
            buf_p.append(p); buf_s.append(s); buf_c.append(c); buf_d.append(dd)
            buffered += len(c)
            kept += len(c)
        flush()
    print(f"done: {kept} positions kept of {seen} lines", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
