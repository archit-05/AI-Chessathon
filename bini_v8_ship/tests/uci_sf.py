"""Raw-pipe Stockfish driver used by the test battery (python-chess's asyncio wrapper stalls here)."""

from __future__ import annotations

import subprocess


class UCI:
    def __init__(self, hash_mb: int = 16, elo: int | None = None) -> None:
        self.p = subprocess.Popen(["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.cmd("uci"); self.wait("uciok")
        self.cmd("setoption name Threads value 1"); self.cmd(f"setoption name Hash value {hash_mb}")
        if elo is not None:
            self.cmd("setoption name UCI_LimitStrength value true"); self.cmd(f"setoption name UCI_Elo value {elo}")
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

    def bestmove(self, fen: str, nodes: int | None = None, movetime_ms: int | None = None) -> str:
        self.cmd(f"position fen {fen}")
        self.cmd(f"go nodes {nodes}" if nodes else f"go movetime {movetime_ms}")
        return self.wait("bestmove").split()[1]

    def quit(self) -> None:
        try:
            self.cmd("quit"); self.p.wait(timeout=5)
        except Exception:  # noqa: BLE001
            self.p.kill()
