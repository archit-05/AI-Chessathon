#!/usr/bin/env python
"""Whole-leaderboard movement: who is climbing, over the last round, the last three rounds and since
yesterday's close, with details on the biggest climbers.

Data: hourly leaderboard archives (raw/ladder/leaderboard_<stamp>.json, every team, every rated round)
and per-team rating-by-round histories from the team pages (raw/cache/teams/<uuid>.json).

    ladder.py --seed          fetch every team page once (about 5 minutes, network only)
    ladder.py [--top 8] [--detail 5] [--since 30]   print the climbers report (used by snapshot.py and strategy.py)
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import html
import io
import pathlib
import time
from collections import Counter

import chess
import chess.pgn

from common import LEADERBOARD, OUR_TEAM, RAW, dump_json, load_json
from scrape import BASE, fetch, get_game, get_team, now, parse_leaderboard

ARCHIVE = RAW / "ladder"


def archive_leaderboard(rows: list[dict]) -> pathlib.Path:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    path = ARCHIVE / f"leaderboard_{dt.datetime.now().strftime('%Y%m%d_%H%M')}.json"
    dump_json(path, {"fetched_at": now(), "rows": rows})
    return path


def archives() -> list[tuple[str, dict]]:
    out = []
    for p in sorted(glob.glob(str(ARCHIVE / "leaderboard_*.json"))):
        d = load_json(pathlib.Path(p))
        if d:
            out.append((pathlib.Path(p).stem[12:], {r["uuid"]: r for r in d["rows"]}))
    return out


def histories() -> dict[str, dict[int, int]]:
    """uuid -> {round: rating} from the cached team pages."""
    out = {}
    for p in glob.glob(str(RAW / "cache" / "teams" / "*.json")):
        d = load_json(pathlib.Path(p))
        if d and d.get("history"):
            out[d["uuid"]] = {r: v for r, v in d["history"]}
    return out


def seed(rows: list[dict], pause: float = 0.1) -> int:
    n = 0
    for r in rows:
        get_team(r["uuid"], force=True)
        n += 1
        time.sleep(pause)
        if n % 50 == 0:
            print(f"  {n}/{len(rows)} team pages", flush=True)
    return n


def rating_at(hist: dict[int, int], rnd: int) -> int | None:
    """Rating after round `rnd` (or the last rated round before it)."""
    best = None
    for r in sorted(hist):
        if r <= rnd:
            best = hist[r]
    return best


def climbers(rows: list[dict], hist: dict[str, dict[int, int]], back: int, latest: int) -> list[dict]:
    out = []
    for r in rows:
        h = hist.get(r["uuid"])
        if not h or r["rating"] is None:
            continue
        then = rating_at(h, latest - back)
        if then is None or (latest - back) < min(h):
            continue
        out.append({**r, "then": then, "delta": r["rating"] - then, "played": sum(1 for x in h if latest - back < x <= latest)})
    return sorted(out, key=lambda x: -x["delta"])


def rank_delta(uuid: str, arcs: list[tuple[str, dict]], hours: int) -> str:
    if len(arcs) <= hours:
        return ""
    old = arcs[-1 - hours][1].get(uuid)
    new = arcs[-1][1].get(uuid)
    if old and new and old["rank"] != new["rank"]:
        return f", rank {old['rank']} -> {new['rank']}"
    return ""


def team_details(r: dict, ladder: dict[str, dict], n_games: int = 3) -> list[str]:
    team = get_team(r["uuid"], force=True)
    h = team["history"]
    tail = h[-6:]
    L = [f"  {r['bot']} (team {team['team']}, {r['university'] or 'n/a'}{', ' + r['tag'] + ' bot' if r.get('tag') else ''}): rank {r['rank']}, {r['rating']}{'P' if r.get('provisional') else ''}, "
         f"{'-'.join(map(str, r['wdl'])) if r.get('wdl') else team['record']}, entered R{h[0][0]} at {h[0][1]}" if h else f"  {r['bot']}: no rating history"]
    if tail:
        L.append("    rating by round: " + ", ".join(f"R{rr} {v}" for rr, v in tail))
    games = sorted([g for g in team["games"] if g["round"]], key=lambda g: -g["round"])[:n_games]
    for row in games:
        gd = get_game(row["game"])
        if not gd:
            L.append(f"    R{row['round']} {row['colour'][0]} vs {row['opponent'][:16]}: {row['verdict']} (page not final)")
            continue
        pgn = gd["pgn"]
        game = chess.pgn.read_game(io.StringIO(pgn))
        white = html.unescape(game.headers.get("White", ""))
        colour = "white" if white == team["team"] else "black"
        sides = (gd.get("review") or {}).get("sides") or []
        sides = sides if isinstance(sides, list) else []
        mine = sides[0] if colour == "white" else (sides[1] if len(sides) > 1 else {})
        theirs = sides[1] if colour == "white" else (sides[0] if sides else {})
        plies = sum(1 for _ in game.mainline_moves())
        # own time per move from the clocks
        clocks, last, spent = [], 120.0, []
        node = game
        while node.variations:
            node = node.variations[0]
            mover = "white" if not node.board().turn else "black"
            c = node.clock()
            if c is None:
                continue
            if mover == colour:
                spent.append(last - c + 0.5)
                last = c
        opp = ladder.get(row["opponent_uuid"], {})
        L.append(f"    R{row['round']} {colour[0].upper()} vs {(opp.get('bot') or row['opponent'])[:16]} (#{opp.get('rank', '?')}, {opp.get('rating', '?')}): {row['verdict']} by {game.headers.get('Termination', '?')[:12]}, "
                 f"{plies} plies, ACPL {mine.get('acpl', '?')} vs {theirs.get('acpl', '?')}, {sum(spent) / len(spent) if spent else 0:.1f} s/move, end {last:.0f} s, {row['opening']}")
    return L


CLIMB3 = 50    # "climbing a lot": rating gain over the last three rounds
CLIMB_DAY = 100  # or since yesterday's close
MAX_DETAIL = 10


def label(r: dict, width: int = 20) -> str:
    """Bot name, marked when it is our own team."""
    name = f"{r['bot']} (us)" if r.get("team") == OUR_TEAM else r["bot"]
    return name[:width]


def report(rows: list[dict], top: int = 8, detail: int = 5, since: int = 30) -> list[str]:
    hist = histories()
    latest = max((max(h) for h in hist.values() if h), default=0)
    arcs = archives()
    ladder = {r["uuid"]: r for r in rows}
    L = [f"LADDER MOVEMENT across all {len(rows)} teams (latest rated round R{latest}; rating-by-round from {len(hist)} team pages)"]
    windows = [(1, "over the last round"), (3, "over the last three rounds")]
    if latest - since > 0 and latest - since != 3:
        windows.append((latest - since, f"since R{since} (yesterday's close)"))
    for back, label_ in windows:
        cl = climbers(rows, hist, back, latest)
        if not cl:
            continue
        L.append(f"  Biggest gains {label_}:")
        for c in cl[:top]:
            L.append(f"    {c['delta']:+4d}  {label(c):<20} #{c['rank']:<3} {c['then']} -> {c['rating']}{'P' if c['provisional'] else ' '} {'-'.join(map(str, c['wdl'])) if c.get('wdl') else '':>9}"
                     f" {c['university'][:12]:<12}{rank_delta(c['uuid'], arcs, min(back, 6))}")
        if back == 1:
            L.append(f"  Biggest falls {label_}: " + "; ".join(f"{label(c, 16)} {c['delta']:+d} (#{c['rank']})" for c in cl[-4:][::-1]))
    fresh = sorted([r for r in rows if r.get("provisional") and r["rank"] <= 100], key=lambda r: r["rank"])
    if fresh:
        shown = fresh[:20]
        L.append(f"  Provisional (fresh upload, <6 games on the build): {len(fresh)} of the top 100, first 20 by rank: "
                 + ", ".join(f"{r['bot'][:16]} (#{r['rank']})" for r in shown) + (f", and {len(fresh) - 20} more" if len(fresh) > 20 else ""))
    if len(arcs) >= 2:
        prev = arcs[-2][1]
        new = [r for r in rows if r["uuid"] not in prev]
        if new:
            L.append("  New on the ladder since the previous snapshot: " + ", ".join(f"{label(r, 16)} (#{r['rank']}, {r['rating']})" for r in new[:10]))
    cl3 = climbers(rows, hist, 3, latest) or climbers(rows, hist, 1, latest)
    clday = climbers(rows, hist, latest - since, latest) if latest - since > 0 else []
    big = {c["uuid"]: c for c in cl3 if c["delta"] >= CLIMB3}
    for c in clday:
        if c["delta"] >= CLIMB_DAY and c["uuid"] not in big:
            big[c["uuid"]] = c
    if big:
        ordered = sorted(big.values(), key=lambda c: -c["delta"])
        L.append(f"  Climbing a lot ({CLIMB3}+ over the last three rounds or {CLIMB_DAY}+ since R{since}), {len(big)} teams: "
                 + ", ".join(f"{label(c, 16)} #{c['rank']} ({c['delta']:+d})" for c in ordered[:30]) + (f", and {len(ordered) - 30} more" if len(ordered) > 30 else ""))
    chosen, seen = [], set()
    for c in list(cl3[:detail]) + sorted(big.values(), key=lambda c: -c["delta"]):
        if c.get("team") == OUR_TEAM:
            continue  # our own games have their own section
        if c["uuid"] not in seen and len(chosen) < MAX_DETAIL:
            chosen.append(c)
            seen.add(c["uuid"])
    if chosen:
        L.append(f"  Details on the climbers ({len(chosen)} teams: the top {detail} of the last three rounds, then the biggest of those climbing a lot, at most {MAX_DETAIL}):")
        for c in chosen:
            L.extend(team_details(c, ladder))
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="fetch every team page once to seed the rating histories")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--detail", type=int, default=5)
    ap.add_argument("--since", type=int, default=30, help="round number of 'yesterday's close'")
    a = ap.parse_args()
    rows = parse_leaderboard(fetch(f"{BASE}/leaderboard"))
    dump_json(LEADERBOARD, {"fetched_at": now(), "rows": rows})
    if a.seed:
        print(f"seeding rating histories for {len(rows)} teams", flush=True)
        n = seed(rows)
        print(f"done: {n} team pages")
        return
    archive_leaderboard(rows)
    print("\n".join(report(rows, a.top, a.detail, a.since)))


if __name__ == "__main__":
    main()
