#!/usr/bin/env python
"""Fetch every rated game page of every team on the ladder into the intel cache (game pages are
immutable once final and are never refetched), so the site's own per-position evaluations cover
the whole event and not only the top 20. Team pages are refetched only for teams whose cached
game list is older than their latest round.

    nice -n 15 ../aichessathon-starter/.venv/bin/python scrape_all.py [--max-teams N] [--pause 0.3]

Runs beside the intel pipeline without touching its dossiers: it only adds files under
raw/cache/games and raw/cache/teams.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scrape  # noqa: E402
from common import CACHE_GAMES, RAW  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-teams", type=int, default=10000)
    ap.add_argument("--pause", type=float, default=0.3)
    a = ap.parse_args()
    scrape.PAUSE_S = a.pause
    RAW.mkdir(parents=True, exist_ok=True)
    rows = scrape.parse_leaderboard(scrape.fetch(f"{scrape.BASE}/leaderboard"))
    print(f"leaderboard: {len(rows)} teams", flush=True)
    have = {p.stem for p in CACHE_GAMES.glob("*.json")}
    fetched = teams = 0
    t0 = time.perf_counter()
    for r in rows[: a.max_teams]:
        try:
            team = scrape.get_team(r["uuid"], force=True)
        except Exception as exc:  # noqa: BLE001
            print(f"team {r['bot']}: {exc!r}", flush=True)
            continue
        teams += 1
        for g in team["games"]:
            gid = g.get("game")
            if not gid or g.get("round") is None or gid in have:
                continue
            try:
                if scrape.get_game(gid):
                    have.add(gid)
                    fetched += 1
            except Exception as exc:  # noqa: BLE001
                print(f"game {gid}: {exc!r}", flush=True)
        if teams % 20 == 0:
            print(f"{teams} teams, {fetched} new game pages, {len(have)} cached, {time.perf_counter() - t0:.0f}s", flush=True)
    print(f"done: {teams} teams, {fetched} new game pages, {len(have)} cached in {time.perf_counter() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
