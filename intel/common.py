"""Shared paths and helpers for the intel pipeline (scrape.py -> analyse.py -> report.py)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
CACHE_GAMES = RAW / "cache" / "games"
CACHE_TEAMS = RAW / "cache" / "teams"
HISTORY = HERE / "history"
NOTES = HERE / "notes"
EVALS = RAW / "evals.jsonl"
LEADERBOARD = RAW / "leaderboard.json"
TARGETS = RAW / "targets.json"

OUR_TEAM = "Opus Carlsen"
TOP_N = 10

# Stockfish settings: every team is measured the same way.
SF_PATH = "/opt/homebrew/bin/stockfish"
SF_NODES = 120_000
SF_NODES_DECIDED = 30_000  # positions already decided (|eval| >= DECIDED_CP) get a cheaper look
DECIDED_CP = 1000
SF_THREADS = 1
SF_HASH = 64
MATE_CP = 10_000  # mate-in-N is stored as +-(MATE_CP - N)

BASE_MS = 120_000
INC_MS = 500


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", html.unescape(name)).strip("_")
    return s or "team"


def clean(text: str) -> str:
    """Strip tags, comment markers and entities from a fragment of site HTML."""
    text = re.sub(r"<svg.*?</svg>", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    with open(path) as fh:
        return json.load(fh)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=False)
    tmp.replace(path)


def team_files(slug: str) -> dict[str, Path]:
    return {
        "pgn": RAW / f"{slug}.pgn",
        "scrape": RAW / f"{slug}.scrape.json",
        "json": RAW / f"{slug}.json",
    }
