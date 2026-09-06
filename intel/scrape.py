#!/usr/bin/env python
"""Scrape aichessathon.com for the current top-10 teams plus Opus Carlsen.

Writes (under intel/raw/):
  leaderboard.json            every ladder row (rank, uuid, bot, team, university, rating, record, tag)
  targets.json                the teams we build dossiers for
  cache/games/<uuid>.json     one file per game page (PGN, opening, termination, site verdicts); never refetched
  cache/teams/<uuid>.json     team pages (rating history, game list); refetched when they may have changed
  <Bot>.pgn                   all of the team's rated games, oldest round first
  <Bot>.scrape.json           team identity + per-game facts that do not need Stockfish

Idempotent: game pages are immutable once final and are fetched only once.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import chess
import chess.pgn

from common import (
    BASE_MS,
    CACHE_GAMES,
    CACHE_TEAMS,
    INC_MS,
    LEADERBOARD,
    OUR_TEAM,
    RAW,
    TARGETS,
    TOP_N,
    clean,
    dump_json,
    load_json,
    slugify,
    team_files,
)

BASE = "https://aichessathon.com"
PAUSE_S = 0.15


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, retries: int = 4) -> str:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (intel refresh)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                time.sleep(PAUSE_S)
                return r.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


# ----------------------------------------------------------------------------- leaderboard
def parse_leaderboard(page: str) -> list[dict]:
    rows = []
    for row in page.split("<tr")[1:]:
        m = re.search(r'data-href="/team/([0-9a-f-]{36})', row)
        if not m:
            continue
        rank = re.search(r'ladder-rank">(\d+)', row)
        name = re.search(r'ladder-bot-name">(.*?)</span>', row, flags=re.S)
        if not (rank and name):
            continue
        raw_name = name.group(1)
        small = re.search(r"<small>(.*?)</small>", raw_name)
        bot = clean(re.sub(r"<small>.*?</small>", "", raw_name))
        team = clean(small.group(1)) if small else bot
        tag = re.search(r'ladder-tag"[^>]*>(.*?)</span>', row)
        uni = re.search(r'ladder-uni">(.*?)</td>', row, flags=re.S)
        rating = re.search(r'ladder-rating">(\d+)', row)
        nums = re.findall(r'ladder-num">(\d+)</td>', row)
        wdl = re.search(r"(\d+)<!-- -->-<!-- -->(\d+)<!-- -->-<!-- -->(\d+)", row)
        rows.append(
            {
                "rank": int(rank.group(1)),
                "uuid": m.group(1),
                "bot": bot,
                "team": team,
                "university": clean(uni.group(1)) if uni else "",
                "tag": clean(tag.group(1)) if tag else "",
                "rating": int(rating.group(1)) if rating else None,
                "games": int(nums[0]) if nums else None,
                "wdl": [int(x) for x in wdl.groups()] if wdl else None,
                "provisional": "data-provisional" in row,
            }
        )
    return rows


# ----------------------------------------------------------------------------- team page
def parse_team(page: str, uuid: str) -> dict:
    h1 = re.search(r"<h1>(.*?)</h1>", page, flags=re.S)
    sub = re.search(r'team-subline"><span>(.*?)</span>', page, flags=re.S)
    facts = dict(re.findall(r"<dt>(Rating|Rank|Record)</dt><dd>(.*?)</dd>", page, flags=re.S))
    rounds = re.search(r"Across <!-- -->(\d+)<!-- --> rated rounds", page)
    history = [
        (int(r), int(v))
        for r, v in re.findall(r'R<!-- -->(\d+)<tspan class="rg-tip-value" dx="8">(\d+)</tspan>', page)
    ]
    games = []
    for gid, row in re.findall(r'<tr data-href="/game/([0-9a-f-]{36})[^"]*">(.*?)</tr>', page, flags=re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)
        if len(cells) < 5:
            continue
        label = clean(re.sub(r'<span class="sr-only">.*?</span>', "", cells[0]))
        kind, _, num = label.rpartition(" ")
        opp = re.search(r'href="/team/([0-9a-f-]{36})', cells[2])
        games.append(
            {
                "game": gid,
                "kind": kind or label,
                "round": int(num) if num.isdigit() else None,
                "colour": clean(cells[1]),
                "opponent": clean(cells[2]),
                "opponent_uuid": opp.group(1) if opp else None,
                "verdict": clean(cells[3]).lower(),
                "opening": clean(cells[4]),
            }
        )
    rec = clean(re.sub(r"<small>.*?</small>", "", facts.get("Record", "")))
    return {
        "uuid": uuid,
        "bot": clean(h1.group(1)) if h1 else "",
        "team": clean(sub.group(1)) if sub else (clean(h1.group(1)) if h1 else ""),
        "rating": int(clean(re.sub(r"<small>.*?</small>", "", facts.get("Rating", "0"))) or 0) or None,
        "rank": int(clean(re.sub(r"<small>.*?</small>", "", facts.get("Rank", "0"))) or 0) or None,
        "record": rec,
        "rated_rounds": int(rounds.group(1)) if rounds else len(history),
        "history": history,
        "games": games,
        "fetched_at": now(),
    }


def get_team(uuid: str, force: bool) -> dict:
    path = CACHE_TEAMS / f"{uuid}.json"
    cached = load_json(path)
    if cached and not force:
        return cached
    data = parse_team(fetch(f"{BASE}/team/{uuid}"), uuid)
    dump_json(path, data)
    return data


# ----------------------------------------------------------------------------- game page
def parse_game(page: str, gid: str) -> dict | None:
    m = re.search(r'href="(data:application/x-chess-pgn;charset=utf-8,[^"]+)"', page)
    if not m:
        return None
    pgn = urllib.parse.unquote(html.unescape(m.group(1)).split(",", 1)[1]).strip() + "\n"
    facts = dict(re.findall(r"<dt>(Time control|Termination|Opening)</dt><dd>(.*?)</dd>", page, flags=re.S))
    state = re.search(r'game-state">(.*?)</p>', page, flags=re.S)
    sides = re.findall(r'class="game-side" href="/team/([0-9a-f-]{36})', page)
    verdicts = re.findall(
        r'<button class="replay-move" data-verdict="([a-z]+)" title="[^"]*" type="button">([^<]+)<', page
    )
    return {
        "game": gid,
        "pgn": pgn,
        "opening": clean(facts.get("Opening", "")),
        "termination_text": clean(facts.get("Termination", "")),
        "time_control": clean(facts.get("Time control", "")),
        "state": clean(state.group(1)) if state else "",
        "white_uuid": sides[0] if len(sides) > 0 else None,
        "black_uuid": sides[1] if len(sides) > 1 else None,
        "site_verdicts": [[san, v] for v, san in verdicts],
        "fetched_at": now(),
    }


def get_game(gid: str) -> dict | None:
    path = CACHE_GAMES / f"{gid}.json"
    cached = load_json(path)
    if cached:
        return cached
    data = parse_game(fetch(f"{BASE}/game/{gid}"), gid)
    if data and ("Final" in data["state"] or "Void" in data["state"]):
        dump_json(path, data)  # anything else is still in progress: do not cache
    return data


# ----------------------------------------------------------------------------- per-game facts
def rating_before(history: list, rnd: int | None):
    """Rating shown for a team after the last rated round strictly before `rnd`."""
    if rnd is None:
        return None
    best = None
    for r, v in history:
        if r < rnd:
            best = v
    return best


def clock_facts(game: chess.pgn.Game, colour: chess.Color) -> dict:
    """Seconds spent per own move from the [%clk] comments (clock after the move, increment included)."""
    base = BASE_MS / 1000.0
    inc = INC_MS / 1000.0
    last = {chess.WHITE: base, chess.BLACK: base}
    spent = []
    clocks = []
    node = game
    while node.variations:
        node = node.variations[0]
        mover = not node.board().turn
        c = node.clock()
        if c is None:
            continue
        if mover == colour:
            spent.append(round(last[mover] - c + inc, 3))
            clocks.append(round(c, 3))
        last[mover] = c
    return {"time_per_move": spent, "clock_after_move": clocks, "final_clock": clocks[-1] if clocks else None}


def game_facts(team: dict, row: dict, gdata: dict, opp_hist: list | None, ladder: dict) -> dict | None:
    game = chess.pgn.read_game(__import__("io").StringIO(gdata["pgn"]))
    if game is None:
        return None
    hdr = game.headers
    white, black = html.unescape(hdr.get("White", "")), html.unescape(hdr.get("Black", ""))
    if white == team["team"]:
        colour = chess.WHITE
    elif black == team["team"]:
        colour = chess.BLACK
    else:
        colour = chess.WHITE if row["colour"].lower() == "white" else chess.BLACK
    res = hdr.get("Result", "*")
    score = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}.get(res)
    if score is not None and colour == chess.BLACK:
        score = 1.0 - score
    plies = sum(1 for _ in game.mainline_moves())
    own = (plies + (1 if (game.board().turn == colour) else 0)) // 2
    opp_row = ladder.get(row["opponent_uuid"]) if row["opponent_uuid"] else None
    facts = {
        "game": row["game"],
        "url": f"{BASE}/game/{row['game']}",
        "kind": row["kind"],
        "round": row["round"],
        "date": hdr.get("Date"),
        "colour": "white" if colour == chess.WHITE else "black",
        "opponent": row["opponent"],
        "opponent_uuid": row["opponent_uuid"],
        "opponent_bot": opp_row["bot"] if opp_row else None,
        "opponent_rank_now": opp_row["rank"] if opp_row else None,
        "opponent_rating_now": opp_row["rating"] if opp_row else None,
        "opponent_rating_then": rating_before(opp_hist or [], row["round"]),
        "own_rating_then": rating_before(team["history"], row["round"]),
        "own_rating_after": dict(team["history"]).get(row["round"]),
        "opening": gdata["opening"] or row["opening"],
        "start_fen": hdr.get("FEN", chess.STARTING_FEN),
        "result": res,
        "score": score,
        "termination": hdr.get("Termination", ""),
        "termination_text": gdata["termination_text"],
        "state": gdata["state"],
        "void": "Void" in gdata["state"] or res == "*",
        "plies": plies,
        "own_moves": own,
        "site_verdicts": gdata.get("site_verdicts", []),
    }
    facts.update(clock_facts(game, colour))
    return facts


# ----------------------------------------------------------------------------- main
def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])  # optional: restrict to these bot names (debugging)

    ladder_rows = parse_leaderboard(fetch(f"{BASE}/leaderboard"))
    if len(ladder_rows) < 50:
        raise SystemExit(f"leaderboard parse looks wrong: {len(ladder_rows)} rows")
    dump_json(LEADERBOARD, {"fetched_at": now(), "rows": ladder_rows})
    ladder = {r["uuid"]: r for r in ladder_rows}
    print(f"leaderboard: {len(ladder_rows)} rows")

    targets = [r for r in ladder_rows if r["rank"] <= TOP_N]
    ours = [r for r in ladder_rows if r["team"] == OUR_TEAM]
    if ours and ours[0] not in targets:
        targets.append(ours[0])
    if not ours:
        print(f"WARNING: team {OUR_TEAM!r} not found on the leaderboard")
    for t in targets:
        t["slug"] = slugify(t["bot"])
    dump_json(TARGETS, {"fetched_at": now(), "targets": targets})

    for t in targets:
        if only and t["bot"] not in only and t["slug"] not in only:
            continue
        team = get_team(t["uuid"], force=True)
        games = [g for g in team["games"] if g["round"] is not None]
        games.sort(key=lambda g: g["round"])
        facts, pgns, missing = [], [], 0
        for row in games:
            gdata = get_game(row["game"])
            if not gdata:
                missing += 1
                continue
            opp_hist = None
            if row["opponent_uuid"]:
                opp = get_team(row["opponent_uuid"], force=False)
                if not any(r < row["round"] for r, _ in opp["history"]) or max((r for r, _ in opp["history"]), default=0) < row["round"]:
                    opp = get_team(row["opponent_uuid"], force=True)
                opp_hist = opp["history"]
            f = game_facts(team, row, gdata, opp_hist, ladder)
            if f:
                facts.append(f)
                pgns.append(gdata["pgn"].strip())
        files = team_files(t["slug"])
        files["pgn"].write_text("\n\n".join(pgns) + "\n")
        out = {
            "fetched_at": now(),
            "slug": t["slug"],
            "bot": team["bot"] or t["bot"],
            "team": team["team"] or t["team"],
            "uuid": t["uuid"],
            "university": t["university"],
            "tag": t["tag"],
            "rank": t["rank"],
            "rating": t["rating"],
            "provisional": t["provisional"],
            "games_played": t["games"],
            "wdl": t["wdl"],
            "record": team["record"],
            "rated_rounds": team["rated_rounds"],
            "history": team["history"],
            "games": facts,
        }
        dump_json(files["scrape"], out)
        print(f"{t['rank']:>3} {t['bot']:<22} ({t['team']}) games {len(facts)} missing {missing} -> {files['pgn'].name}")


if __name__ == "__main__":
    main()
