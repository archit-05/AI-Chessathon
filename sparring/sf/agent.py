"""LOCAL SPARRING PARTNER ONLY — never shipped. Wraps the system Stockfish over UCI so the
harness can measure our engine against a fixed absolute strength.

Environment:
  SF_ELO    UCI_LimitStrength / UCI_Elo (1320..3190). Unset = full strength.
  SF_NODES  fixed node limit per move (overrides time). Unset = play on the clock.
  SF_MOVETIME_MS  fixed time per move in ms. Unset = use ~1/30 of the remaining clock.
"""

from __future__ import annotations

import os
import subprocess

_sf = subprocess.Popen(["stockfish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)


def _cmd(line: str) -> None:
    assert _sf.stdin is not None
    _sf.stdin.write(line + "\n")
    _sf.stdin.flush()


def _wait(token: str) -> str:
    assert _sf.stdout is not None
    while True:
        line = _sf.stdout.readline()
        if line.startswith(token):
            return line.strip()


_cmd("uci")
_wait("uciok")
_cmd("setoption name Threads value 1")
_cmd("setoption name Hash value 64")
if os.environ.get("SF_ELO"):
    _cmd("setoption name UCI_LimitStrength value true")
    _cmd(f"setoption name UCI_Elo value {int(os.environ['SF_ELO'])}")
_cmd("isready")
_wait("readyok")
_cmd("ucinewgame")


def get_move(fen: str, time_left_ms: int) -> str:
    _cmd(f"position fen {fen}")
    if os.environ.get("SF_NODES"):
        _cmd(f"go nodes {int(os.environ['SF_NODES'])}")
    elif os.environ.get("SF_MOVETIME_MS"):
        _cmd(f"go movetime {int(os.environ['SF_MOVETIME_MS'])}")
    else:
        _cmd(f"go movetime {max(20, int(time_left_ms / 30))}")
    line = _wait("bestmove")
    return line.split()[1]
