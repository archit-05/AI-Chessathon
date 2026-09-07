#!/usr/bin/env python
"""Cheap leaderboard + Bini snapshot (no Stockfish): top-12 table, rating jumps, our games since a round,
and the site's own move grades.  Prints plain text (< 40 lines).

    snapshot.py [--since-round 31] [--top 12] [--grades Bot1,Bot2,...] [--last 10]
"""

from __future__ import annotations

import argparse
import html
import io
from collections import Counter
from datetime import datetime

import chess
import chess.pgn

from common import HERE, LEADERBOARD, OUR_TEAM, RAW, dump_json, load_json
from ladder import archive_leaderboard, report as ladder_report

STATE = RAW / "snapshot_state.json"
from scrape import BASE, fetch, game_facts, get_game, get_team, now, parse_leaderboard

GRADES = ("best", "excellent", "good", "forced", "inaccuracy", "mistake", "miss", "blunder", "brilliant")
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def grade_split(gdata: dict, colour: str, start_turn: bool) -> tuple[Counter, Counter]:
    """Site verdict counts for (colour, opponent) from the game page's move list."""
    ours, theirs = Counter(), Counter()
    turn = start_turn  # True = white to move at the start position
    for san, v in gdata.get("site_verdicts", []):
        mover = "white" if turn else "black"
        (ours if mover == colour else theirs)[v] += 1
        turn = not turn
    return ours, theirs


def fmt_split(c: Counter) -> str:
    keys = ("best", "excellent", "good", "inaccuracy", "mistake", "miss", "blunder")
    return "/".join(str(c.get(k, 0)) for k in keys)


def material_balance(pgn: str, colour: str) -> int:
    game = chess.pgn.read_game(io.StringIO(pgn))
    board = game.end().board()
    tot = sum(v * (len(board.pieces(pt, chess.WHITE)) - len(board.pieces(pt, chess.BLACK))) for pt, v in VALUES.items())
    return tot if colour == "white" else -tot


def why_not_won(g: dict, gdata: dict, ours: Counter, mat: int) -> str:
    bad = ours.get("blunder", 0) + ours.get("mistake", 0) + ours.get("miss", 0)
    low = min(g.get("clock_after_move") or [999])
    if g["termination"] in ("flag", "illegal", "crash", "init"):
        return f"our failure: {g['termination']}"
    if g["termination"] == "threefold_repetition":
        return f"repetition with material {mat:+d} ({'while ahead' if mat >= 2 else 'while behind' if mat <= -2 else 'level'})" + (f", {bad} site-tagged errors" if bad else "")
    if g["termination"] == "fifty_moves":
        return f"fifty-move drift with material {mat:+d}"
    if g["termination"] == "insufficient_material":
        return "traded into a dead draw"
    if low < 5:
        return f"time: clock fell to {low:.1f} s; {bad} site-tagged errors"
    if bad:
        return f"tactical: {ours.get('blunder', 0)} blunder / {ours.get('mistake', 0)} mistake / {ours.get('miss', 0)} miss by the site's grading"
    return g["termination"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-round", type=int, default=31)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--grades", default="", help="bots whose last games get a grade split")
    ap.add_argument("--last", type=int, default=10)
    ap.add_argument("--jump", type=int, default=80)
    ap.add_argument("--no-ladder", action="store_true", help="compact snapshot only (no whole-ladder movement section)")
    ap.add_argument("--leap-round", type=int, default=46, help="first round of the front-loaded-clock build; first-move and unused-clock flags apply from here")
    ap.add_argument("--max-games", type=int, default=8, help="show at most this many of our most recent games in the compact part")
    a = ap.parse_args()

    rows = parse_leaderboard(fetch(f"{BASE}/leaderboard"))
    dump_json(LEADERBOARD, {"fetched_at": now(), "rows": rows})
    ladder = {r["uuid"]: r for r in rows}
    out = []
    out.append(f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')} - top {a.top} (P = provisional: <6 games on the current build)")
    tops = [r for r in rows if r["rank"] <= a.top]
    jumps = []
    rounds_seen = set()
    for r in tops:
        team = get_team(r["uuid"], force=True)
        h = team["history"]
        rounds_seen.update(rr for rr, _ in h)
        for i in range(1, len(h)):
            d = h[i][1] - h[i - 1][1]
            if abs(d) >= a.jump:
                jumps.append((r["bot"], h[i][0], d, h[i][1]))
        last_round = h[-1][0] if h else "?"
        out.append(f"{r['rank']:>3} {r['bot'][:18]:<18} {r['rating']:>5}{'P' if r['provisional'] else ' '} {'-'.join(map(str, r['wdl'])):>8}  last R{last_round}")
    state = load_json(STATE, {}) or {}
    last_round, last_when = state.get("last_round", a.since_round - 1), state.get("when", "never")
    new_rounds = sorted(rr for rr in rounds_seen if rr > last_round)
    out.append(f"Rounds rated since the last snapshot ({last_when}): " + (", ".join(f"R{rr}" for rr in new_rounds) if new_rounds else "none")
               + f"; latest rated round R{max(rounds_seen) if rounds_seen else '?'}")
    recent = [j for j in jumps if j[1] >= a.since_round]
    out.append("Jumps >= %d in one round from R%d (likely new uploads): " % (a.jump, a.since_round) + ("; ".join(f"{b} R{r} {d:+d}->{v}" for b, r, d, v in sorted(recent, key=lambda x: -x[1])) if recent else "none"))

    ours = next((r for r in rows if r["team"] == OUR_TEAM), None)
    if ours:
        team = get_team(ours["uuid"], force=True)
        out.append(f"\n{ours['bot']} ({OUR_TEAM}): rank {ours['rank']}, rating {ours['rating']}{'P' if ours['provisional'] else ''}, {'-'.join(map(str, ours['wdl']))}; games since R{a.since_round}"
                   " (clk@20/40/60 = our clock in s after own moves 20/40/60; grades = site tags best/exc/good/inacc/mist/miss/blund on own moves):")
        games = sorted([g for g in team["games"] if g["round"] and g["round"] >= a.since_round], key=lambda g: g["round"])
        if len(games) > a.max_games:
            out.append(f"  ({len(games) - a.max_games} earlier games since R{a.since_round} omitted; all are in intel/raw/{team['bot'].replace(' ', '_')}.scrape.json)")
            games = games[-a.max_games:]
        if not games:
            out.append("  none yet")
        for row in games:
            gdata = get_game(row["game"])
            if not gdata:
                out.append(f"  R{row['round']} vs {row['opponent']}: page not final yet")
                continue
            opp_hist = get_team(row["opponent_uuid"], force=False)["history"] if row["opponent_uuid"] else []
            g = game_facts(team, row, gdata, opp_hist, ladder)
            start_white = chess.Board(g["start_fen"]).turn == chess.WHITE
            mine, theirs = grade_split(gdata, g["colour"], start_white)
            mat = material_balance(gdata["pgn"], g["colour"])
            tpm = g["time_per_move"]
            opp = ladder.get(row["opponent_uuid"], {})
            res = {1.0: "WIN ", 0.5: "DRAW", 0.0: "LOSS"}.get(g["score"], "VOID")
            clk = g.get("clock_after_move") or []
            curve = "/".join(f"{clk[i - 1]:.0f}" if len(clk) >= i else "-" for i in (20, 40, 60))
            out.append(f"  R{g['round']} {g['colour'][0].upper()} vs {opp.get('bot', row['opponent'])[:14]:<14} (#{opp.get('rank')},{opp.get('rating')}) {res} {g['termination'][:12]:<12} "
                       f"{g['own_moves']:>3}mv {sum(tpm) / len(tpm) if tpm else 0:.1f}s/mv clk@20/40/60 {curve} end {g['final_clock']:.0f}s  us {fmt_split(mine)} them {fmt_split(theirs)}  {g['opening']}")
            if g["score"] != 1.0:
                out.append(f"      {'lost' if g['score'] == 0.0 else 'drawn'}: {why_not_won(g, gdata, mine, mat)}")
            flags = []
            if g["final_clock"] is not None and g["final_clock"] < 5:
                flags.append(f"ended under 5 s ({g['final_clock']:.1f} s)")
            if tpm and tpm[0] < 2.5 and g["round"] >= a.leap_round:
                flags.append(f"first move took {tpm[0]:.1f} s: old-build clock profile?")
            if len(clk) >= 40 and clk[39] < 20:
                flags.append(f"only {clk[39]:.0f} s left at move 40")
            if len(clk) >= 40 and clk[39] > 60 and g["round"] >= a.leap_round:
                flags.append(f"{clk[39]:.0f} s still unused at move 40")
            if flags:
                out.append("      FLAG: " + "; ".join(flags))

    if a.grades:
        out.append(f"\nSite move grades over the last {a.last} games (best/exc/good/inacc/mist/miss/blund, own moves):")
        for bot in a.grades.split(","):
            r = next((x for x in rows if x["bot"] == bot.strip()), None)
            if not r:
                out.append(f"  {bot}: not on the leaderboard")
                continue
            team = get_team(r["uuid"], force=False)
            tot = Counter()
            games = sorted([g for g in team["games"] if g["round"]], key=lambda g: -g["round"])[: a.last]
            n = 0
            for row in games:
                gdata = get_game(row["game"])
                if not gdata or "Void" in gdata.get("state", ""):
                    continue
                gf = game_facts(team, row, gdata, [], ladder)
                mine, _ = grade_split(gdata, gf["colour"], chess.Board(gf["start_fen"]).turn == chess.WHITE)
                tot += mine
                n += 1
            moves = sum(tot.values())
            errs = tot.get("mistake", 0) + tot.get("miss", 0) + tot.get("blunder", 0)
            out.append(f"  {r['bot'][:18]:<18} {n:>2} games {moves:>4} moves  {fmt_split(tot):<22} errors/100 moves {100 * errs / moves if moves else 0:.1f}")
    if not a.no_ladder:
        archive_leaderboard(rows)
        out.append("")
        out.append("----- ladder movement (whole leaderboard) -----")
        out.extend(ladder_report(rows, top=8, detail=5, since=a.since_round - 1))
    text = "\n".join(out)
    print(text)
    if not a.no_ladder:
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        (HERE / "ladder").mkdir(exist_ok=True)
        (HERE / "ladder" / f"hourly_{stamp}.txt").write_text(text + "\n")
    if rounds_seen:
        dump_json(STATE, {"last_round": max(rounds_seen), "when": datetime.now().strftime("%Y-%m-%d %H:%M")})


if __name__ == "__main__":
    main()
