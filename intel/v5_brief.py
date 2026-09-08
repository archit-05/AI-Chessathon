#!/usr/bin/env python3
"""Render V5_INTEL_<stamp>.txt: a compact brief for the engine builder.

Reads only what refresh.sh has already produced (raw/*.json, raw/cache/games/*.json,
raw/ladder/*.json).  No network, no engine.  Usage:

    python v5_brief.py                 # new file, name stamped with the current time
    python v5_brief.py --out PATH      # overwrite PATH (what the hourly loop does)
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import LEADERBOARD, OUR_TEAM, RAW, CACHE_GAMES, load_json, slugify

W = 100
FAILURE_TERMS = {"init": "INIT", "crash": "CRSH", "illegal": "ILL", "flag": "CLK", "ply_cap": "PLYCAP"}


# --------------------------------------------------------------------------- helpers
def family(opening: str) -> str:
    head = (opening or "?").split(",")[0].strip()
    words = head.split()
    if not words:
        return opening or "?"
    if words[0] in ("Ruy", "Queen's", "King's", "Two", "Four", "Old", "Bishop's", "Giuoco", "Modern",
                    "Neo-Grunfeld") and len(words) > 1:
        return " ".join(words[:2])
    return words[0]


def wrap(tokens: list[str], indent: str, sep: str = "  ") -> list[str]:
    out, cur = [], indent
    cont = " " * len(indent)
    for t in tokens:
        if len(cur) + len(t) + len(sep) > W and cur.strip():
            out.append(cur.rstrip())
            cur = cont
        cur += t + sep
    if cur.strip():
        out.append(cur.rstrip())
    return out


def rating_then(g: dict) -> int | None:
    return g.get("opponent_rating_then") or g.get("opponent_rating_now")


def rated(team: dict) -> list[dict]:
    return [g for g in team["games"] if not g.get("void")]


def quality(games: list[dict]) -> tuple[float | None, float | None, int]:
    """(mean cp lost per own move, blunder %, moves counted) from the site evaluations."""
    tot = n = bl = 0
    for g in games:
        if g.get("cpl_mean") is not None and g.get("cpl_n"):
            tot += g["cpl_mean"] * g["cpl_n"]
            n += g["cpl_n"]
            bl += g.get("blunders") or 0
    if n < 100:
        return None, None, n
    return tot / n, 100.0 * bl / n, n


def sec_per_move(games: list[dict]) -> float | None:
    ts = [t for g in games for t in (g.get("time_per_move") or []) if t is not None]
    return sum(ts) / len(ts) if ts else None


def cause(g: dict) -> str:
    """Why this game was lost.

    INIT/CRSH/ILL   the bot never produced a legal move
    CLK             flagged
    BLU<n>/<drop>   one move at own move n turned a playable position (>= -150) into a lost one;
                    the last such move decides, and the mating sequence itself is ignored
    SLD             no single move did it: the evaluation slid
    +clk            the decisive move was played under 10 s, or the game ended under 5 s
    """
    term = g.get("termination") or ""
    if term in FAILURE_TERMS:
        return FAILURE_TERMS[term]
    decisive = None
    for m in g.get("moves") or []:
        cb, ca, loss = m.get("cp_before"), m.get("cp_after"), m.get("loss") or 0
        if cb is None or ca is None:
            continue
        if cb >= -150 and loss >= 250 and ca <= -150:
            decisive = m
    if decisive:
        tag = f"BLU{decisive['n']}/{decisive['loss']}"
        clk = decisive.get("clock")
    else:
        tag = "SLD"
        clk = None
    fc = g.get("final_clock")
    if (clk is not None and clk < 10) or (fc is not None and fc < 5):
        tag += "+clk"
    return tag


def score_str(games: list[dict]) -> str:
    if not games:
        return "-"
    pts = sum(g["score"] for g in games)
    return f"{pts:g}/{len(games)} {100 * pts / len(games):.0f}%"


def load_team(slug: str) -> dict | None:
    d = load_json(RAW / f"{slug}.json")
    return d if d and d.get("games") else load_json(RAW / f"{slug}.scrape.json")


def evals_cp(gid: str) -> list | None:
    d = load_json(CACHE_GAMES / f"{gid}.json")
    if not d:
        return None
    ev = d.get("evals") or {}
    return ev.get("cp")


# --------------------------------------------------------------------------- sections
def snapshot() -> None:
    """15 lines for logs/hourly.log: top 12, our last game, fresh uploads."""
    lb = load_json(LEADERBOARD) or {}
    rows = sorted(lb.get("rows", []), key=lambda r: r["rank"])
    us = load_team(slugify(OUR_TEAM)) or load_team("BINI_Alpha") or {}
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] leaderboard {lb.get('fetched_at', '?')} "
          f"| us #{us.get('rank')} {us.get('rating')} {us.get('record')}")
    prev = None
    snaps = sorted((RAW / "ladder").glob("leaderboard_*.json"))
    if len(snaps) >= 2:
        prev = {r["bot"]: r["rating"] for r in (load_json(snaps[-2]) or {}).get("rows", [])}
    for r in rows[:12]:
        d = ""
        if prev and r["bot"] in prev and prev[r["bot"]] is not None and r["rating"] is not None:
            d = f"{r['rating'] - prev[r['bot']]:+d}"
        w, dr, l = r["wdl"] or (0, 0, 0)
        print(f"  {r['rank']:>2} {r['bot'][:22]:<22} {r['rating']:>5} {d:>5}  {w}-{dr}-{l}"
              + ("  NEW" if r["provisional"] else ""))
    gs = [g for g in (us.get("games") or [])]
    if gs:
        g = gs[-1]
        t = g.get("site_tally") or {}
        res = {1.0: "win", 0.5: "draw", 0.0: "LOSS"}.get(g["score"], "void")
        print(f"  last R{g['round']} {g['colour']} vs {(g.get('opponent_bot') or g['opponent'])[:18]}"
              f"/{rating_then(g) or '?'} {res} {g.get('termination', '')}"
              f" | sACPL {g.get('site_acpl')}/{g.get('opp_site_acpl')}"
              f" | i/m/b {t.get('inaccuracy', 0)}/{t.get('mistake', 0)}/{t.get('blunder', 0)}"
              f" | clock left {g.get('final_clock')} s, {sec_per_move([g]) or 0:.2f} s/mv")
    fresh = [r["bot"] for r in rows[:20] if r["provisional"]]
    print(f"  fresh builds in the top 20 ({len(fresh)}): " + (", ".join(fresh) if fresh else "none"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--snapshot", action="store_true", help="print the 15-line hourly snapshot instead")
    args = ap.parse_args()

    if args.snapshot:
        snapshot()
        return

    lb = load_json(LEADERBOARD) or {}
    rows = sorted(lb.get("rows", []), key=lambda r: r["rank"])
    by_rank = {r["rank"]: r for r in rows}
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    L: list[str] = []
    add = L.append

    add(f"V5 INTEL BRIEF  {stamp}   (leaderboard fetched {lb.get('fetched_at', '?')})")
    add("=" * W)
    add("Site evaluations throughout (Stockfish 16 depth 16, identical for every team). CPL = mean cp lost")
    add("per own move (|eval| <= 800); Bl% = own moves losing >= 200 cp; sACPL = site review ACPL (all")
    add("positions); Draw% from the current record; New = provisional = build uploaded within 6 rounds.")
    add("Loss cause: BLU<n>/<cp> one move at own move n turned a playable position into a lost one, SLD")
    add("slide, CLK flag, INIT/CRSH/ILL no legal move; +clk = decisive move under 10 s or ended under 5 s.")
    add("")

    # ---------------------------------------------------------------- (a) top 15
    add("A. TOP 15")
    add("  #  Bot                 Rating  W- D- L   CPL sACPL  Bl%  s/mv Draw%  New")
    add("  " + "-" * 74)
    teams: dict[int, dict] = {}
    for r in rows[:15]:
        t = load_team(slugify(r["bot"])) or load_team(slugify(r["team"]))
        teams[r["rank"]] = t
        cpl = bl = spm = drawpc = sacpl = None
        if t:
            rd = rated(t)
            cpl, bl, _ = quality(t["games"])
            spm = sec_per_move(t["games"])
            if rd:
                drawpc = 100 * sum(1 for g in rd if g["score"] == 0.5) / len(rd)
            sac = [g["site_acpl"] for g in t["games"] if g.get("site_acpl") is not None]
            sacpl = sum(sac) / len(sac) if sac else None
        w, d, l = r["wdl"] or (0, 0, 0)
        add(f"  {r['rank']:<2} {r['bot'][:19]:<19} {r['rating']:>5}  {w:>2}-{d:>2}-{l:>2} "
            f"{cpl if cpl is None else round(cpl, 1):>5} {'' if sacpl is None else round(sacpl):>5} "
            f"{'' if bl is None else round(bl, 1):>4} {'' if spm is None else round(spm, 2):>5} "
            f"{'' if drawpc is None else round(drawpc):>5}  {'NEW' if r['provisional'] else ''}")
    add("")

    # ---------------------------------------------------------------- (b) top 10 detail
    add("B. TOP 10 IN DETAIL  (bands by the opponent's rating at the time)")
    bands = [("2500+", 2500, 9999), ("2300-2499", 2300, 2499), ("2100-2299", 2100, 2299), ("<2100", 0, 2099)]
    for r in rows[:10]:
        t = teams.get(r["rank"])
        if not t or not t.get("games"):
            add(f"  #{r['rank']} {r['bot']}: no game data scraped yet.")
            continue
        rd = rated(t)
        add(f"  #{r['rank']} {r['bot']} ({r['team']}) {r['rating']}"
            + (" [new build]" if r["provisional"] else ""))
        parts = []
        for name, lo, hi in bands:
            gs = [g for g in rd if rating_then(g) is not None and lo <= rating_then(g) <= hi]
            parts.append(f"{name} {score_str(gs)}")
        add("     band  " + " | ".join(parts))
        fams = defaultdict(list)
        for g in rd:
            fams[family(g.get("opening"))].append(g)
        top = sorted(fams.items(), key=lambda kv: -len(kv[1]))[:4]
        add("     open  " + " | ".join(f"{k} {score_str(v)}" for k, v in top))
        plies = [g["plies"] for g in rd if g.get("plies")]
        cpl, bl, _ = quality(t["games"])
        clocks = [g["final_clock"] for g in t["games"] if g.get("final_clock") is not None]
        losses = [g for g in rd if g["score"] == 0.0]
        tally = Counter(cause(g).split("+")[0].split("/")[0].rstrip("0123456789") for g in losses)
        add(f"     game  {sum(plies) / len(plies):.0f} ply, CPL {cpl:.1f}, Bl {bl:.1f}%, "
            f"{sec_per_move(t['games']):.2f} s/mv, {sum(clocks) / max(1, len(clocks)):.0f} s left; "
            f"lost {len(losses)} = " + ", ".join(f"{k} {v}" for k, v in tally.most_common()))
        toks = [f"R{g['round']}{g['colour'][0]} {(g.get('opponent_bot') or g['opponent'])[:11]}"
                f"/{rating_then(g) or '?'} {cause(g)}" for g in losses]
        for line in wrap(toks, "     lost  ", sep=" | "):
            add(line.rstrip(" |"))
    add("")

    # ---------------------------------------------------------------- (c) our games
    us = load_team(slugify(OUR_TEAM)) or load_team("BINI_Alpha")
    add(f"C. OUR GAMES SINCE ROUND 50  (BINI Alpha, rank {us.get('rank')}, {us.get('rating')}, "
        f"{us.get('record')})")
    add("  Rd  col  opponent            rat  res  sACPL us/opp  inacc/mist/blun  first < -100  term")
    add("  " + "-" * 92)
    ours = [g for g in us["games"] if g["round"] >= 50]
    for g in ours:
        cp = evals_cp(g["game"])
        first = "never"
        if cp:
            sign = 1 if g["colour"] == "white" else -1
            for i, v in enumerate(cp):
                if v is None:
                    continue
                if sign * v < -100:
                    first = f"ply {i}"
                    break
        t = g.get("site_tally") or {}
        res = {1.0: "win", 0.5: "draw", 0.0: "LOSS"}.get(g["score"], "void")
        sa = "?" if g.get("site_acpl") is None else str(g["site_acpl"])
        oa = "?" if g.get("opp_site_acpl") is None else str(g["opp_site_acpl"])
        add(f"  {g['round']:<3} {g['colour'][0]}    {(g.get('opponent_bot') or g['opponent'])[:18]:<18} "
            f"{rating_then(g) or '?':>4}  {res:<4} {sa:>4}/{oa:<4} "
            f"    {t.get('inaccuracy', 0)}/{t.get('mistake', 0)}/{t.get('blunder', 0):<3}"
            f"    {first:<12} {(g.get('termination') or '')[:14]}"
            + ("  VOID" if g.get("void") else ""))
    pts = sum(g["score"] for g in ours if not g.get("void"))
    n = sum(1 for g in ours if not g.get("void"))
    ac = [g["site_acpl"] for g in ours if g.get("site_acpl") is not None]
    oac = [g["opp_site_acpl"] for g in ours if g.get("opp_site_acpl") is not None]
    cpl, bl, _ = quality(ours)
    add(f"  Since R50: {pts:g}/{n}, mean sACPL {sum(ac) / len(ac):.0f} vs {sum(oac) / len(oac):.0f}, "
        f"CPL {cpl:.1f}, Bl% {bl:.1f}, s/mv {sec_per_move(ours):.2f}, "
        f"clock left {sum(g['final_clock'] for g in ours if g.get('final_clock') is not None) / len(ours):.0f} s")
    losses = [g for g in ours if g["score"] == 0.0 and not g.get("void")]
    toks = []
    for g in losses:
        worst = None
        for m in g.get("moves") or []:
            if m.get("cp_before") is None or m["cp_before"] < -400:
                continue
            if worst is None or (m.get("loss") or 0) > (worst.get("loss") or 0):
                worst = m
        detail = ""
        if worst:
            detail = (f", worst {worst['n']}.{worst['san']} -{worst['loss']} "
                      f"({worst['cp_before']:+d}->{worst['cp_after']:+d}, {worst['time']:.1f}s)")
        toks.append(f"R{g['round']} {(g.get('opponent_bot') or g['opponent'])[:12]}"
                    f"/{rating_then(g) or '?'} {cause(g)}{detail}")
    for line in wrap(toks, "  Losses: ", sep=" | "):
        add(line.rstrip(" |"))
    add("")

    # ---------------------------------------------------------------- (d) what is new
    add("D. NEW SINCE THE LAST BRIEF")
    fails = []
    for f in CACHE_GAMES.glob("*.json"):
        txt = f.read_text()
        m = re.search(r'"termination_text": "(Init|Crash|Illegal|Flag|Ply cap)"', txt)
        if not m:
            continue
        d = json.loads(txt)
        pgn = d.get("pgn", "")
        wm = re.search(r'\[White "(.*?)"\]', pgn)
        bm = re.search(r'\[Black "(.*?)"\]', pgn)
        rm = re.search(r'\[Result "(.*?)"\]', pgn)
        rd = re.search(r'\[Round "(\d+)"\]', pgn)
        loser = None
        if rm:
            loser = (bm.group(1) if rm.group(1) == "1-0" else wm.group(1) if rm.group(1) == "0-1" else None)
        fails.append((m.group(1), loser or "?", rd.group(1) if rd else "?"))
    add(f"  Bot failures in the whole cache ({len(fails)} games): "
        + (", ".join(f"{k} {v}" for k, v in Counter(f[0] for f in fails).most_common()) or "none"))
    bits = []
    for kind in ("Init", "Crash", "Illegal", "Ply cap", "Flag"):
        who = [f for f in fails if f[0] == kind and f[1] != "?"]
        if who:
            c = Counter(w[1][:20] for w in who)
            bits.append(f"{kind} " + ", ".join(f"{k} x{v}" if v > 1 else k for k, v in c.most_common(5))
                        + (f" +{len(c) - 5}" if len(c) > 5 else ""))
    if bits:
        add("    who: " + "; ".join(bits))
    snaps = sorted((RAW / "ladder").glob("leaderboard_*.json"))
    day = datetime.now().strftime("%Y%m%d")
    older = [s for s in snaps if s.name.split("_")[1] < day] or snaps
    if snaps:
        prev = load_json(older[-1])
        old20 = {r["bot"] for r in sorted(prev.get("rows", []), key=lambda r: r["rank"])[:20]}
        new20 = [r["bot"] for r in rows[:20] if r["bot"] not in old20]
        add(f"  New in top 20 since {older[-1].name.split('_', 1)[1][:-5]}: "
            + (", ".join(new20[:6]) + (f" +{len(new20) - 6}" if len(new20) > 6 else "")
               if new20 else "none"))
        moves = []
        prev_rank = {r["bot"]: r["rank"] for r in prev.get("rows", [])}
        for r in rows[:20]:
            if r["bot"] in prev_rank and prev_rank[r["bot"]] - r["rank"] >= 8:
                moves.append(f"{r['bot']} {prev_rank[r['bot']]}->{r['rank']}")
        if moves:
            add("  Biggest climbs inside the top 20: " + ", ".join(moves[:5]))
    if len(rows) >= 10:
        add(f"  Bar now: top 3 {by_rank[3]['rating'] + 1}, top 5 {by_rank[5]['rating'] + 1}, "
            f"top 10 {by_rank[10]['rating'] + 1}; leader {by_rank[1]['bot']} {by_rank[1]['rating']}; "
            f"us {us.get('rating')} (#{us.get('rank')}).")
    voided = [g for t in [teams.get(r["rank"]) for r in rows[:15]] if t for g in (t.get("games") or [])
              if g.get("void")]
    vt = Counter(g.get("termination") for g in voided)
    add(f"  Site rules: {len(voided)} top-15 games were played out and then voided "
        f"({', '.join(f'{k[:14]} {v}' for k, v in vt.most_common())}); unrated, one-off on 6 Sept.")
    add("  Site layout (8 Sept): ranks 1-3 are now podium rows (medal SVG, some cells streamed in late by")
    add("    React); scrape.py patched to read them - unpatched, the whole top 3 vanishes from the tables.")

    out_lines: list[str] = []
    for line in L:
        while len(line) > W:
            cut = line.rfind(" ", 0, W)
            if cut < 20:
                break
            out_lines.append(line[:cut])
            line = "    " + line[cut + 1:]
        out_lines.append(line)
    L = out_lines
    text = "\n".join(L) + "\n"
    out = Path(args.out) if args.out else (Path(__file__).resolve().parent /
                                           f"V5_INTEL_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
    out.write_text(text)
    print(f"{out} ({len(L)} lines)")


if __name__ == "__main__":
    main()
