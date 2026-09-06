#!/usr/bin/env python
"""Render the dossiers (intel/<rank>_<Bot>.txt), intel/00_summary.txt and intel/history/ from raw/*.json."""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import pathlib
import re
import statistics as st
from collections import Counter, defaultdict

from common import HERE, HISTORY, LEADERBOARD, NOTES, OUR_TEAM, SF_NODES, TARGETS, TOP_N, load_json, team_files

W = 100
AHEAD = 150       # "ahead" at a repetition
CONVERT = 300     # "winning" threshold for conversion checks
BLUNDER = 200
PHASES = ((1, 15), (16, 40), (41, 10**6))
FAILURES = {"flag", "illegal", "crash", "init"}


# ----------------------------------------------------------------------------- helpers
def mean(xs, nd=1):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), nd) if xs else None


def median(xs, nd=1):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), nd) if xs else None


def pct(a, b, nd=0):
    return round(100.0 * a / b, nd) if b else None


def f(x, nd=1, unit=""):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{nd}f}{unit}"
    return f"{x}{unit}"


def wdl(games):
    w = sum(1 for g in games if g["score"] == 1.0)
    d = sum(1 for g in games if g["score"] == 0.5)
    l = sum(1 for g in games if g["score"] == 0.0)
    return w, d, l


def rec(games):
    w, d, l = wdl(games)
    n = w + d + l
    return f"{w}-{d}-{l} ({pct(w + 0.5 * d, n) if n else 0:.0f}%)" if n else "0-0-0"


TIERS = (("top 10", 1, 10), ("11-20", 11, 20), ("21-50", 21, 50), ("rest", 51, 10**6))


def tier_of(rank):
    if rank is None:
        return "rest"
    for name, lo, hi in TIERS:
        if lo <= rank <= hi:
            return name
    return "rest"


def phase_of(n):
    for i, (lo, hi) in enumerate(PHASES, 1):
        if lo <= n <= hi:
            return i
    return 3


def family(opening: str) -> str:
    head = opening.split(",")[0].strip()
    words = head.split()
    if not words:
        return opening
    if words[0] in ("Ruy", "Queen's", "King's", "Two", "Four", "Old", "Bishop's", "Giuoco", "Modern", "Neo-Grunfeld") and len(words) > 1:
        return " ".join(words[:2])
    return words[0]


def wrap(text: str, indent: int = 2, width: int = W) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w_ in words:
        if len(cur) + len(w_) + 1 > width - indent and cur:
            lines.append(" " * indent + cur)
            cur = w_
        else:
            cur = f"{cur} {w_}".strip()
    if cur:
        lines.append(" " * indent + cur)
    return lines


def rnd(g):
    return f"R{g['round']}"


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def result_word(g):
    return {1.0: "win", 0.5: "draw", 0.0: "loss"}.get(g["score"], "void")


# ----------------------------------------------------------------------------- per-team statistics
ANALYSIS_KEYS = ("moves", "final_cp", "max_adv", "min_adv", "eval_swing", "cpl_mean", "cpl_n", "blunders", "worst_move",
                 "opp_cpl_mean", "opp_blunders", "opp_worst_move", "opp_time_mean")


def load_team(t):
    """Fresh identity and per-game facts from the scrape file, merged with whatever analysis exists."""
    files = team_files(t["slug"])
    data = load_json(files["scrape"])
    if not data:
        return None
    analysed = load_json(files["json"]) or {}
    by_id = {g["game"]: g for g in analysed.get("games", []) if "moves" in g}
    n = 0
    for g in data["games"]:
        a = by_id.get(g["game"])
        if a:
            for k in ANALYSIS_KEYS:
                if k in a:
                    g[k] = a[k]
            n += 1
        g.setdefault("moves", [])
    data["n_analysed"] = n
    data["analysed"] = n > 0
    data["rated"] = [g for g in data["games"] if not g.get("void")]
    data["void_games"] = [g for g in data["games"] if g.get("void")]
    # the leaderboard row is the freshest source for rank/rating/record
    for k in ("rank", "rating", "provisional", "wdl", "university", "tag"):
        if k in t:
            data[k] = t[k]
    data["games_played"] = t.get("games", data.get("games_played"))
    return data


def own_moves(team, games=None):
    for g in games if games is not None else team["rated"]:
        for m in g["moves"]:
            yield g, m


def quality(team):
    q = {}
    counted = [(g, m) for g, m in own_moves(team) if m["counted"]]
    q["n"] = len(counted)
    losses = [m["loss"] for _, m in counted]
    q["mean"], q["median"] = mean(losses), median(losses, 0)
    q["blunders"] = sum(1 for x in losses if x >= BLUNDER)
    q["blunder_pct"] = pct(q["blunders"], len(losses), 1)
    q["reliable"] = len(losses) >= 200  # about four games; below that the mean is noise
    q["phase"] = {}
    for i in (1, 2, 3):
        ls = [m["loss"] for _, m in counted if phase_of(m["n"]) == i]
        q["phase"][i] = {"n": len(ls), "mean": mean(ls), "median": median(ls, 0), "bl": pct(sum(1 for x in ls if x >= BLUNDER), len(ls), 1)}
    q["colour"] = {}
    for c in ("white", "black"):
        ls = [m["loss"] for g, m in counted if g["colour"] == c]
        q["colour"][c] = {"n": len(ls), "mean": mean(ls), "median": median(ls, 0), "bl": pct(sum(1 for x in ls if x >= BLUNDER), len(ls), 1)}
    # site's own tags as a cross-check
    tags = Counter(m.get("verdict") for _, m in own_moves(team) if m.get("verdict"))
    q["site_tags"] = tags
    sa = [g["site_acpl"] for g in team["rated"] if g.get("site_acpl") is not None]
    q["site_acpl"] = mean(sa)
    q["site_acpl_n"] = len(sa)
    q["site_acc"] = mean([g["site_accuracy"] for g in team["rated"] if g.get("site_accuracy") is not None])
    q["site_src"] = next((g.get("site_review_source") for g in team["rated"] if g.get("site_review_source")), "").replace(" · ", ", ")
    # blunders while level or ahead (tactical oversights rather than desperation)
    q["blunders_not_losing"] = sum(1 for g, m in counted if m["loss"] >= BLUNDER and m["cp_before"] >= -100)
    worst = sorted(((m["loss"], g, m) for g, m in own_moves(team) if m["loss"] >= 100 and m["cp_before"] > -300 and (m["cp_before"] < 1000 or m["cp_after"] < 300)), key=lambda x: -x[0])[:3]
    q["worst"] = [(g, m) for _, g, m in worst]
    return q


def clock_moves(team):
    """Own moves with clock data: analysed moves where available, else pseudo-moves from the scrape clocks."""
    for g in team["rated"]:
        if g["moves"]:
            for m in g["moves"]:
                if m["time"] is not None:
                    yield g, m
        else:
            for i, (tm, ck) in enumerate(zip(g.get("time_per_move") or [], g.get("clock_after_move") or [])):
                yield g, {"n": i + 1, "time": tm, "clock": ck, "cp_before": None, "cp_after": None}


def timing(team):
    t = {}
    moves = [(g, m) for g, m in clock_moves(team)]
    times = [m["time"] for _, m in moves]
    if not times:
        return {"n": 0}
    t["n"] = len(times)
    t["mean"], t["median"], t["max"] = mean(times, 2), median(times, 2), round(max(times), 1)
    qs = st.quantiles(times, n=4) if len(times) >= 4 else [times[0], times[0], times[0]]
    t["q1"], t["q3"] = round(qs[0], 2), round(qs[2], 2)
    t["sd"] = round(st.pstdev(times), 2)
    t["instant_pct"] = pct(sum(1 for x in times if x < 0.05), len(times), 1)
    finals = [g["final_clock"] for g in team["rated"] if g.get("final_clock") is not None]
    t["final_mean"], t["final_min"] = mean(finals), round(min(finals), 1) if finals else None
    t["under5"] = [g for g in team["rated"] if any(c < 5 for c in g.get("clock_after_move", []))]
    t["under10"] = [g for g in team["rated"] if any(c < 10 for c in g.get("clock_after_move", []))]
    # spending vs complexity: eval moved by > 100 cp on the opponent's previous move (entering), or on the own move
    prev = {}
    entering, calm, own_swing, own_calm = [], [], [], []
    for g, m in moves:
        if m["cp_before"] is None:
            continue
        key = g["game"]
        last = prev.get(key)
        if last is not None:
            (entering if abs(m["cp_before"] - last["cp_after"]) > 100 else calm).append(m["time"])
        (own_swing if abs(m["cp_after"] - m["cp_before"]) > 100 else own_calm).append(m["time"])
        prev[key] = m
    t["swing_in"], t["calm_in"] = (mean(entering, 2), len(entering)), (mean(calm, 2), len(calm))
    t["swing_own"], t["calm_own"] = (mean(own_swing, 2), len(own_swing)), (mean(own_calm, 2), len(own_calm))
    # by clock band and by evaluation
    bands = {">60s": [], "30-60s": [], "10-30s": [], "<10s": []}
    for g, m in moves:
        c = m["clock"] + m["time"] - 0.5 if m["clock"] is not None else None  # clock before the move
        if c is None:
            continue
        band = ">60s" if c > 60 else "30-60s" if c > 30 else "10-30s" if c > 10 else "<10s"
        bands[band].append(m["time"])
    t["bands"] = {k: (mean(v, 2), len(v)) for k, v in bands.items()}
    ratios = []
    for g, m in moves:
        if m["clock"] is not None and m["time"] >= 0.05 and (m["cp_before"] is None or abs(m["cp_before"]) < 800):
            before = m["clock"] + m["time"] - 0.5
            if before > 1:
                ratios.append(100.0 * m["time"] / before)
    if len(ratios) >= 8:
        rq = st.quantiles(ratios, n=4)
        t["ratio"] = (round(st.median(ratios), 1), round(rq[0], 1), round(rq[2], 1))
    else:
        t["ratio"] = None
    ev = [(g, m) for g, m in moves if m["cp_before"] is not None]
    t["ahead"] = mean([m["time"] for _, m in ev if m["cp_before"] >= CONVERT], 2)
    t["behind"] = mean([m["time"] for _, m in ev if m["cp_before"] <= -CONVERT], 2)
    t["level"] = mean([m["time"] for _, m in ev if -CONVERT < m["cp_before"] < CONVERT], 2)
    t["by_phase"] = {i: mean([m["time"] for _, m in moves if phase_of(m["n"]) == i], 2) for i in (1, 2, 3)}
    t["opp_mean"] = mean([g.get("opp_time_mean") for g in team["rated"]], 2)
    return t


def draws(team):
    d = {}
    dr = [g for g in team["rated"] if g["score"] == 0.5]
    d["n"] = len(dr)
    d["by"] = Counter(g["termination"] for g in dr)
    d["rep_ahead"] = [g for g in dr if g["termination"] == "threefold_repetition" and g.get("final_cp") is not None and g["final_cp"] > AHEAD]
    d["rep_behind"] = [g for g in dr if g["termination"] == "threefold_repetition" and g.get("final_cp") is not None and g["final_cp"] < -AHEAD]
    d["rep_level"] = [g for g in dr if g["termination"] == "threefold_repetition" and g.get("final_cp") is not None and -AHEAD <= g["final_cp"] <= AHEAD]
    d["fifty_ahead"] = [g for g in dr if g["termination"] == "fifty_moves" and g.get("final_cp") is not None and g["final_cp"] > AHEAD]
    d["fifty_behind"] = [g for g in dr if g["termination"] == "fifty_moves" and g.get("final_cp") is not None and g["final_cp"] < -AHEAD]
    d["other_ahead"] = [g for g in dr if g["termination"] not in ("threefold_repetition", "fifty_moves") and g.get("final_cp") is not None and g["final_cp"] > AHEAD]
    # long shuffles: draws where the final 40 own moves were all inside +-50
    d["vs_top"] = [g for g in dr if g.get("opponent_rank_now") and g["opponent_rank_now"] <= 10]
    return d


def conversion(team):
    c = {"missed": [], "saved": [], "winning_games": 0, "losing_games": 0}
    for g in team["rated"]:
        if not g["moves"]:
            continue
        pre = [m["cp_before"] for m in g["moves"]] + [m["cp_after"] for m in g["moves"]]
        best = max(pre)
        worst = min(pre)
        if best >= CONVERT:
            c["winning_games"] += 1
            if g["score"] < 1.0:
                c["missed"].append((g, best, conversion_reason(g, best)))
        if worst <= -CONVERT:
            c["losing_games"] += 1
            if g["score"] > 0.0:
                c["saved"].append((g, worst, save_reason(g)))
    return c


def conversion_reason(g, best):
    ms = g["moves"]
    fin = g.get("final_cp")
    if g["score"] == 0.0:
        wm = g.get("worst_move")
        return f"lost it: worst move {wm['n']}.{wm['san']} cost {wm['loss']} cp" if wm else "lost"
    if g["termination"] == "fifty_moves" and fin is not None and fin > AHEAD:
        return f"fifty-move drift while still +{fin}"
    if g["termination"] == "threefold_repetition" and fin is not None and fin > AHEAD:
        return f"repeated while +{fin}"
    if g["termination"] == "insufficient_material":
        return "traded down into a dead draw"
    # find the move that gave it away
    peak_i = max(range(len(ms)), key=lambda i: ms[i]["cp_before"])
    after = [m for m in ms[peak_i:] if m["loss"] >= 150]
    if after:
        m = after[0]
        return f"threw it away: move {m['n']}.{m['san']} ({m['cp_before']:+d} -> {m['cp_after']:+d})"
    return f"drifted to {fin:+d} ({g['termination']})" if fin is not None else g["termination"]


def save_reason(g):
    ow = g.get("opp_worst_move")
    if g["score"] == 1.0:
        return f"opponent collapsed: {ow['san']} at ply {ow['ply']} lost {ow['loss']} cp" if ow else "opponent collapsed"
    if g["termination"] == "threefold_repetition":
        return "opponent allowed a repetition"
    if g["termination"] == "fifty_moves":
        return "opponent could not convert inside fifty moves"
    if g["termination"] == "insufficient_material":
        return "opponent traded into insufficient material"
    return g["termination"]


def openings(team):
    o = {}
    by_name = defaultdict(list)
    by_fam = defaultdict(list)
    for g in team["rated"]:
        by_name[g["opening"]].append(g)
        by_fam[family(g["opening"])].append(g)
    o["by_name"] = by_name
    o["by_fam"] = by_fam
    overall = mean([g["score"] for g in team["rated"]], 3) or 0
    o["under"] = [(fam, gs) for fam, gs in by_fam.items() if len(gs) >= 3 and mean([g["score"] for g in gs], 3) <= overall - 0.2]
    early = [m for _, m in own_moves(team) if m["n"] <= 6]
    later = [m for _, m in own_moves(team) if 7 <= m["n"] <= 20]
    o["early_best"] = pct(sum(1 for m in early if m["is_best"]), len(early))
    o["later_best"] = pct(sum(1 for m in later if m["is_best"]), len(later))
    o["early_cpl"] = mean([m["loss"] for m in early if m["counted"]])
    o["early_instant"] = pct(sum(1 for m in early if m["time"] is not None and m["time"] < 0.05), len(early))
    firsts = []
    for g in team["rated"]:
        for m in g["moves"]:
            if not m["is_best"] and m["loss"] >= 20:
                firsts.append(m["n"])
                break
    o["first_div"] = mean(firsts)
    return o


def style(team):
    s = {}
    ms = [m for _, m in own_moves(team)]
    s["n"] = len(ms)
    s["capture_pct"] = pct(sum(1 for m in ms if m["capture"]), len(ms), 1)
    s["check_pct"] = pct(sum(1 for m in ms if m["check"]), len(ms), 1)
    s["plies"] = mean([g["plies"] for g in team["rated"]], 0)
    s["own_moves"] = mean([g["own_moves"] for g in team["rated"]], 0)
    wins = [g for g in team["rated"] if g["score"] == 1.0]
    losses = [g for g in team["rated"] if g["score"] == 0.0]
    s["wins_mate"] = sum(1 for g in wins if g["termination"] == "checkmate")
    s["wins_fail"] = [g for g in wins if g["termination"] in FAILURES]
    s["losses_mate"] = sum(1 for g in losses if g["termination"] == "checkmate")
    s["losses_fail"] = [g for g in losses if g["termination"] in FAILURES]
    s["longest"] = max(team["rated"], key=lambda g: g["plies"], default=None)
    # sacrifices: material given up (>= 2 pawns after the opponent's reply) without an eval loss, then recovered
    sacs = []
    for g in team["rated"]:
        mv = g["moves"]
        for i, m in enumerate(mv[:-1]):
            nxt = mv[i + 1]
            gave = nxt["mat_before"] - m["mat_before"]          # after the opponent's reply
            still = nxt["mat_after"] - m["mat_before"]          # after their own next move too
            if gave <= -2 and still <= -2 and m["loss"] <= 60 and m["counted"] and m["n"] > 1 and abs(m["cp_before"]) <= 300:
                horizon = mv[i + 2 : i + 10]
                recovered = any(h["mat_before"] >= m["mat_before"] - 1 for h in horizon) or (g["score"] == 1.0 and any(h["cp_before"] >= m["cp_before"] + 150 for h in horizon))
                if recovered:
                    sacs.append((g, m, gave))
    s["sacs"] = sacs
    # simplification when ahead: material leaving the board over own move + reply
    off_ahead, off_level = [], []
    cap_ahead, cap_level = [], []
    for g in team["rated"]:
        mv = g["moves"]
        for i, m in enumerate(mv[:-1]):
            off = m["tot_before"] - mv[i + 1]["tot_before"]
            if m["cp_before"] >= AHEAD:
                off_ahead.append(off)
                cap_ahead.append(m["capture"])
            elif -AHEAD < m["cp_before"] < AHEAD:
                off_level.append(off)
                cap_level.append(m["capture"])
    s["off_ahead"], s["off_level"] = mean(off_ahead, 2), mean(off_level, 2)
    s["cap_ahead"], s["cap_level"] = pct(sum(cap_ahead), len(cap_ahead), 1), pct(sum(cap_level), len(cap_level), 1)
    return s


def tiers(team):
    out = {}
    for name, _, _ in TIERS:
        gs = [g for g in team["rated"] if tier_of(g.get("opponent_rank_now")) == name]
        out[name] = gs
    return out


def spikes(team):
    """Rounds where the rating moved 100+ points; each is annotated with that round's game."""
    h = team.get("history", [])
    by_round = {g["round"]: g for g in team["games"]}
    out = []
    for i in range(1, len(h)):
        d = h[i][1] - h[i - 1][1]
        if abs(d) >= 100:
            g = by_round.get(h[i][0])
            what = f"{result_word(g)} vs {g.get('opponent_bot') or g['opponent']}" if g else "no game that round"
            out.append((h[i][0], d, h[i][1], what))
    return out


def recent_form(team, k=5):
    games = sorted(team["rated"], key=lambda g: g["round"])
    recent, earlier = games[-k:], games[:-k]
    out = {}
    for name, gs in (("recent", recent), ("earlier", earlier)):
        losses = [m["loss"] for g in gs for m in g["moves"] if m["counted"]]
        out[name] = {"n": len(gs), "rec": rec(gs), "cpl": mean(losses), "bl": pct(sum(1 for x in losses if x >= BLUNDER), len(losses), 1),
                     "rounds": f"R{gs[0]['round']}-R{gs[-1]['round']}" if gs else "-", "moves": len(losses)}
    return out


def compute(team):
    team["form"] = recent_form(team)
    team["q"] = quality(team)
    team["t"] = timing(team)
    team["d"] = draws(team)
    team["c"] = conversion(team)
    team["o"] = openings(team)
    team["s"] = style(team)
    team["tiers"] = tiers(team)
    team["spikes"] = spikes(team)
    return team


# ----------------------------------------------------------------------------- inference
def profile(team) -> list[str]:
    q, t, d, c, o, s = team["q"], team["t"], team["d"], team["c"], team["o"], team["s"]
    lines = []
    n = q["n"]
    conf = "high" if n >= 1500 else "medium" if n >= 600 else "low"
    if q["mean"] is None:
        return ["Not analysed yet (run analyse.py)."]
    if q["mean"] <= 10:
        lines.append(f"Move quality is engine-grade (mean loss {q['mean']} cp at {SF_NODES // 1000}k nodes): a real alpha-beta searcher with a strong, probably NNUE-class or well-tuned evaluation. Confidence {conf}.")
    elif q["mean"] <= 20:
        lines.append(f"Strong searcher (mean loss {q['mean']} cp): consistent with a bitboard alpha-beta engine at depth 8-12 with a decent evaluation. Confidence {conf}.")
    elif q["mean"] <= 35:
        lines.append(f"Mid-strength engine (mean loss {q['mean']} cp): plausible python alpha-beta at depth 4-7, hand-crafted evaluation. Confidence {conf}.")
    else:
        lines.append(f"Shallow or noisy engine (mean loss {q['mean']} cp, blunder rate {q['blunder_pct']}%). Confidence {conf}.")
    p = q["phase"]
    if p[3]["mean"] is not None and p[1]["mean"] is not None and p[3]["mean"] >= 1.5 * max(p[1]["mean"], 5):
        lines.append(f"Quality drops late (phase 41+ mean {p[3]['mean']} cp vs {p[1]['mean']} cp in the first 15 moves): endgame evaluation or horizon problems.")
    elif p[3]["mean"] is not None and p[1]["mean"] is not None and p[1]["mean"] >= 1.5 * max(p[3]["mean"], 5):
        lines.append(f"Weakest early (moves 1-15 mean {p[1]['mean']} cp vs {p[3]['mean']} cp later): no book and a thin opening evaluation.")
    if t.get("n"):
        fixed_share = bool(t.get("ratio")) and t["ratio"][2] <= 1.4 * t["ratio"][0] and t["ratio"][1] >= 0.6 * t["ratio"][0] and t["q3"] - t["q1"] > 0.5
        if fixed_share:
            lines.append(f"Time allocation is a fixed share of the remaining clock (~{t['ratio'][0]:.0f}% per move; median {t['median']} s, max {t['max']} s), so depth shrinks as the game goes on and no extra time goes to critical positions ({f(t['swing_in'][0])} s after a >100 cp swing vs {f(t['calm_in'][0])} s otherwise).")
        elif t["q3"] - t["q1"] <= 0.5 and t["max"] <= 3 * t["median"]:
            lines.append(f"Time use is nearly fixed ({t['median']} s median, interquartile {t['q1']}-{t['q3']} s, max {t['max']} s): a fixed per-move budget rather than adaptive allocation.")
        elif t["max"] >= 8:
            lines.append(f"Adaptive time use (median {t['median']} s, max {t['max']} s, spends {f(t['swing_in'][0])} s on moves after a >100 cp swing vs {f(t['calm_in'][0])} s otherwise).")
        if t["final_mean"] is not None and t["final_mean"] >= 40:
            lines.append(f"Leaves {t['final_mean']:.0f} s unused on average: the search is capped by something other than the clock (depth or node limit).")
        if len(t["under5"]) >= 3:
            lines.append(f"Poor clock awareness: {len(t['under5'])} of {len(team['rated'])} games went under 5 s.")
    if d["rep_ahead"]:
        lines.append(f"Repeats while clearly ahead ({len(d['rep_ahead'])} games): no contempt or repetition avoidance in the search.")
    if o["early_best"] is not None and o["early_instant"] is not None and o["early_instant"] >= 15:
        lines.append(f"Instant early moves ({o['early_instant']:.0f}% of the first six played in under 50 ms): an opening book covers part of the curated positions.")
    return lines


def recommendations(team) -> list[str]:
    q, t, d, c, o, s = team["q"], team["t"], team["d"], team["c"], team["o"], team["s"]
    recs = []
    if q["mean"] is None:
        return ["Analysis pending."]
    n_games = len(team["rated"])
    if d["rep_ahead"]:
        rs = ", ".join(rnd(g) for g in d["rep_ahead"])
        recs.append(f"When we are worse, steer for repetitions: they accepted threefolds while ahead in {rs}. Keep our own contempt positive so we never return the favour.")
    if d["rep_behind"] and not d["rep_ahead"]:
        recs.append(f"They only repeat when worse ({len(d['rep_behind'])} games), so when ahead avoid any repetition and keep pieces on; do not expect gifts.")
    if len(c["missed"]) >= 2 and len(c["missed"]) >= 0.2 * c["winning_games"]:
        recs.append(f"Their conversion is leaky ({len(c['missed'])} of {c['winning_games']} won positions not won): when losing, keep material on and make them prove technique; the fifty-move and repetition rules are our friends.")
    elif c["winning_games"] >= 5 and len(c["missed"]) <= 1:
        recs.append(f"They convert ({c['winning_games'] - len(c['missed'])} of {c['winning_games']} won positions turned into wins): do not rely on swindles; the game is decided before -300.")
    p = q["phase"]
    if p[3]["mean"] is not None and p[1]["mean"] is not None and p[3]["mean"] >= 1.5 * max(p[1]["mean"], 5):
        recs.append(f"Head for long games: their loss per move rises from {p[1]['mean']} cp early to {p[3]['mean']} cp after move 40. Avoid early mass exchanges only if we are not better; otherwise simplify into a queenless middlegame and outplay them late.")
    if t.get("n"):
        if len(t["under5"]) >= 2:
            recs.append(f"Time pressure works: {len(t['under5'])} games dipped under 5 s ({', '.join(rnd(g) for g in t['under5'][:6])}). Keep games long and complicated; their play under 10 s averages {f(t['bands']['<10s'][0])} s a move.")
        if t["final_mean"] is not None and t["final_mean"] >= 30 and t["max"] <= 6:
            recs.append(f"They never use their clock (median {t['median']} s a move, {t['final_mean']:.0f} s left at the end). We can out-search them by spending our full budget in sharp positions; there is no way to out-clock them.")
        if t["swing_in"][0] is not None and t["calm_in"][0] is not None and t["swing_in"][0] <= 1.1 * t["calm_in"][0]:
            recs.append(f"No extra time goes to critical positions ({f(t['swing_in'][0])} s after a big swing vs {f(t['calm_in'][0])} s otherwise): our search can spend several times their budget on the few moves that decide a game, so prefer positions where one precise move matters over long manoeuvring.")
    if q["blunders_not_losing"] >= 3:
        recs.append(f"Tactics work: {q['blunders_not_losing']} blunders (>= {BLUNDER} cp) came from level or better positions, so they can be out-calculated. Keep the position sharp.")
    elif q["blunder_pct"] is not None and q["blunder_pct"] <= 0.5:
        recs.append(f"Do not count on gifts: only {plural(q['blunders'], 'blunder')} in {q['n']} measured moves. Keep our play sound; speculative sacrifices will be refuted.")
    if o["under"]:
        fams = ", ".join(f"{fam} ({rec(gs)})" for fam, gs in o["under"])
        recs.append(f"Opening families where they score badly: {fams}. Nothing to choose here (positions are assigned), but expect our best chances there.")
    if not recs:
        recs.append("No clear structural weakness in the sample; play our normal settings.")
    return recs[:5]


# ----------------------------------------------------------------------------- rendering
def render_dossier(team, targets_by_uuid, ladder):
    q, t, d, c, o, s = team["q"], team["t"], team["d"], team["c"], team["o"], team["s"]
    L = []
    rated = team["rated"]
    add = L.append
    add(f"{team['bot']}  (team: {team['team']})  -  rank {team['rank']}, rating {team['rating']}")
    add("=" * min(W, len(L[0])))
    partial = f", {team['n_analysed']} of {len(team['games'])} analysed with Stockfish so far" if team["n_analysed"] < len(team["games"]) else ""
    add(f"Generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from {len(rated)} rated games (rounds {rated[0]['round']}-{rated[-1]['round']}{partial})"
        + (f", {len(team['void_games'])} void game(s) ignored: {', '.join(rnd(g) for g in team['void_games'])}" if team["void_games"] else "") + ".")
    add("")
    # Identity
    add("IDENTITY")
    tag = f" [{team['tag']} bot]" if team.get("tag") else ""
    stop = {"Tree", "Fish", "Bot", "Chess", "Team", "Sister", "Demon", "Ammo", "Liver", "Knights", "One", "Mistakes", "Disciple", "Preventer", "Shooter", "Research", "Game", "Club", "Dark", "Lightning", "Blank", "Fried", "Mate", "Loss"}
    words = team["team"].split()
    solo = ("team name reads like a personal name, probably solo" if len(words) == 2 and all(re.fullmatch(r"[A-Z][a-z]+", w) for w in words) and not (set(words) & stop) and team["team"] != team["bot"]
            else "members not shown on the site")
    add(f"  Bot {team['bot']}{tag}; team {team['team']}; university {team['university'] or 'n/a'}; {solo}.")
    prov = " (provisional: fewer than six games on the current build, i.e. a new upload in the last five rounds)" if team.get("provisional") else ""
    add(f"  Rank {team['rank']} of {len(ladder)}, rating {team['rating']}{prov}, record {team['record']} in {team['games_played']} rated games.")
    h = team.get("history", [])
    if h:
        peak = max(h, key=lambda x: x[1])
        add(f"  Rating trajectory: entered R{h[0][0]} at {h[0][1]}, peak {peak[1]} (R{peak[0]}), now {h[-1][1]} (R{h[-1][0]}).")
        sp = team["spikes"]
        if sp:
            add("  Jumps of 100+ between rounds (a jump that does not match the game result suggests a new upload;")
            add("  the first ten rounds swing a lot anyway):")
            for r, dd, v, what in sp:
                add(f"    R{r} {dd:+d} -> {v} ({what})")
        else:
            add("  No 100+ point jump between consecutive rounds.")
    fr = team["form"]
    if fr["earlier"]["n"] and fr["recent"]["moves"]:
        add(f"  Recent form (last {fr['recent']['n']} games, {fr['recent']['rounds']}): {fr['recent']['rec']}, loss {f(fr['recent']['cpl'])} cp/move, blunders {f(fr['recent']['bl'])}%"
            f" vs earlier ({fr['earlier']['rounds']}): {fr['earlier']['rec']}, {f(fr['earlier']['cpl'])} cp/move, {f(fr['earlier']['bl'])}%"
            + (" - the provisional flag says the last games are a new build" if team.get("provisional") else ""))
    add("")
    # Results by tier
    add("RESULTS BY OPPONENT TIER (tier = opponent's rank on the leaderboard now)")
    for name, gs in team["tiers"].items():
        add(f"  vs {name:<7}: {rec(gs)} over {len(gs)} games")
    top_games = sorted(team["tiers"]["top 10"] + team["tiers"]["11-20"], key=lambda g: g["round"])
    if top_games:
        add(f"  Games vs other top-{TOP_N} teams:")
        for g in top_games:
            opp = g.get("opponent_bot") or g["opponent"]
            add(f"    {rnd(g):<4} {g['colour']:<5} vs {opp:<18} (#{g['opponent_rank_now']:<2}) {result_word(g):<4} {g['termination']:<21} {g['opening']}")
    add("")
    # Move quality
    add(f"MOVE QUALITY (Stockfish 19, {SF_NODES // 1000}k nodes per position, loss clipped at 1000, positions inside +-800 only)")
    if q["mean"] is None:
        add("  not analysed yet")
    if q["mean"] is not None:
        add(f"  All own moves: n {q['n']}, mean loss {q['mean']} cp, median {q['median']:.0f} cp, blunders (>= {BLUNDER} cp) {q['blunders']} = {q['blunder_pct']}%"
            f" ({q['blunders_not_losing']} of them from level or better positions)")
        for i, (lo, hi) in enumerate(PHASES, 1):
            p = q["phase"][i]
            label = f"own moves {lo}-{hi}" if hi < 10**6 else f"own moves {lo}+"
            add(f"  {label:<18}: n {p['n']:>4}, mean {f(p['mean'])} cp, median {f(p['median'], 0)} cp, blunders {f(p['bl'])}%")
        for col in ("white", "black"):
            p = q["colour"][col]
            add(f"  as {col:<15}: n {p['n']:>4}, mean {f(p['mean'])} cp, median {f(p['median'], 0)} cp, blunders {f(p['bl'])}%")
        if q["worst"]:
            add("  Worst moves: " + "; ".join(f"{rnd(g)} {m['n']}.{m['san']} ({m['cp_before']:+d} -> {m['cp_after']:+d})" for g, m in q["worst"]))
        tags = q["site_tags"]
        if tags:
            add(f"  Site's own tags on their moves: blunder {tags.get('blunder', 0)}, mistake {tags.get('mistake', 0)}, miss {tags.get('miss', 0)}, inaccuracy {tags.get('inaccuracy', 0)} of {sum(tags.values())}")
    if q.get("site_acpl") is not None:
        add(f"  Site's own review ({q['site_src'] or 'site engine'}): mean ACPL {q['site_acpl']} over {q['site_acpl_n']} games, mean accuracy {f(q['site_acc'])}% (all games, not only analysed ones)")
    add("")
    # Time
    add("TIME MANAGEMENT (120 s + 0.5 s; seconds per own move from the PGN clocks)")
    if not t.get("n"):
        add("  no clock data")
    else:
        add(f"  Per move: mean {t['mean']} s, median {t['median']} s, quartiles {t['q1']}-{t['q3']} s, max {t['max']} s; instant (<50 ms) moves {t['instant_pct']}%")
        add(f"  Clock at the end: mean {f(t['final_mean'])} s, minimum {f(t['final_min'])} s; games under 10 s: {len(t['under10'])}, under 5 s: {len(t['under5'])}"
            + (f" ({', '.join(rnd(g) for g in t['under5'])})" if t["under5"] else ""))
        add(f"  By clock before the move: " + ", ".join(f"{k} {f(v[0])} s (n {v[1]})" for k, v in t["bands"].items()))
        add(f"  By own-move number: 1-15 {f(t['by_phase'][1])} s, 16-40 {f(t['by_phase'][2])} s, 41+ {f(t['by_phase'][3])} s; when +300 or better {f(t['ahead'])} s, level {f(t['level'])} s, -300 or worse {f(t['behind'])} s")
        if t["ratio"]:
            add(f"  Share of the remaining clock spent per move (positions inside +-800, moves >= 50 ms): median {t['ratio'][0]}%, quartiles {t['ratio'][1]}-{t['ratio'][2]}%")
        add(f"  After a >100 cp swing on the opponent's move: {f(t['swing_in'][0])} s (n {t['swing_in'][1]}) vs {f(t['calm_in'][0])} s otherwise;"
            f" on moves that themselves swing >100 cp: {f(t['swing_own'][0])} s (n {t['swing_own'][1]}) vs {f(t['calm_own'][0])} s")
        flags = []
        if t["q3"] - t["q1"] <= 0.5:
            flags.append("near-fixed time per move")
        if t["ratio"] and t["ratio"][2] <= 1.4 * t["ratio"][0] and t["ratio"][1] >= 0.6 * t["ratio"][0] and t["q3"] - t["q1"] > 0.5:
            flags.append(f"spends a fixed ~{t['ratio'][0]:.0f}% of the remaining clock per move, so its thinking time shrinks as the game goes on")
        if t["final_mean"] is not None and t["final_mean"] >= 40:
            flags.append(f"leaves ~{t['final_mean']:.0f} s unused")
        if len(t["under5"]) >= 2:
            flags.append("gets into time trouble")
        fixed_share = bool(t.get("ratio")) and t["ratio"][2] <= 1.4 * t["ratio"][0] and t["ratio"][1] >= 0.6 * t["ratio"][0] and t["q3"] - t["q1"] > 0.5
        if t["bands"]["<10s"][1] >= 10 and t["bands"]["<10s"][0] is not None and t["bands"]["<10s"][0] < 0.25 and not fixed_share:
            flags.append("panics under 10 s (sub-0.25 s moves)")
        if t["swing_in"][0] is not None and t["calm_in"][0] is not None and t["swing_in"][0] >= 1.5 * t["calm_in"][0]:
            flags.append("thinks longer when the position gets sharp")
        add("  Exploitable: " + ("; ".join(flags) if flags else "nothing obvious"))
    add("")
    # Draws
    add("DRAW BEHAVIOUR")
    add(f"  {d['n']} draws in {len(rated)} games ({pct(d['n'], len(rated))}%): " + (", ".join(f"{k} {v}" for k, v in d["by"].most_common()) if d["n"] else "none")
        + (f"; {len(d['vs_top'])} of them vs top-10 teams" if d["vs_top"] else ""))
    if team["analysed"]:
        add(f"  Repetition while ahead (> +{AHEAD} at the final position): {len(d['rep_ahead'])}"
            + (" -> " + ", ".join(f"{rnd(g)} vs {g.get('opponent_bot') or g['opponent']} at {g['final_cp']:+d}" for g in d["rep_ahead"]) if d["rep_ahead"] else ""))
        add(f"  Repetition while behind (< -{AHEAD}): {len(d['rep_behind'])}"
            + (" -> " + ", ".join(f"{rnd(g)} at {g['final_cp']:+d}" for g in d["rep_behind"]) if d["rep_behind"] else "")
            + f"; level repetitions: {len(d['rep_level'])}")
        if d["fifty_ahead"] or d["fifty_behind"] or d["other_ahead"]:
            add(f"  Fifty-move draws while ahead: {len(d['fifty_ahead'])}" + (" (" + ", ".join(f"{rnd(g)} at {g['final_cp']:+d}" for g in d["fifty_ahead"]) + ")" if d["fifty_ahead"] else "")
                + f"; while behind: {len(d['fifty_behind'])}; other draws while ahead: {len(d['other_ahead'])}")
    add("")
    # Conversion
    add(f"ENDGAME CONVERSION (+{CONVERT} = winning, -{CONVERT} = losing, own point of view)")
    if team["analysed"]:
        add(f"  Reached +{CONVERT} or better in {c['winning_games']} games, failed to win {len(c['missed'])}" + (":" if c["missed"] else "."))
        for g, best, why in c["missed"]:
            add(f"    {rnd(g):<4} vs {(g.get('opponent_bot') or g['opponent']):<18} peak {best:+5d}, {result_word(g)} by {g['termination']}: {why}")
        add(f"  Reached -{CONVERT} or worse in {c['losing_games']} games, escaped with a half point or more in {len(c['saved'])}" + (":" if c["saved"] else "."))
        for g, worst, why in c["saved"]:
            add(f"    {rnd(g):<4} vs {(g.get('opponent_bot') or g['opponent']):<18} low {worst:+5d}, {result_word(g)} by {g['termination']}: {why}")
    else:
        add("  not analysed yet")
    add("")
    # Openings
    add("OPENINGS (curated start positions assigned by the platform)")
    fams = sorted(o["by_fam"].items(), key=lambda kv: -len(kv[1]))
    add("  By family: " + "; ".join(f"{fam} {rec(gs)}" for fam, gs in fams))
    names = sorted(o["by_name"].items(), key=lambda kv: (-len(kv[1]), kv[0]))
    add("  Positions seen: " + "; ".join(f"{name} x{len(gs)} {rec(gs)}" if len(gs) > 1 else f"{name} {result_word(gs[0])}" for name, gs in names))
    if o["under"]:
        add("  Underperforms in: " + ", ".join(f"{fam} {rec(gs)}" for fam, gs in o["under"]))
    else:
        add("  No family with 3+ games scores 20+ points below their overall average.")
    if team["analysed"]:
        add(f"  First six own moves: {f(o['early_best'], 0)}% match Stockfish's first choice (moves 7-20: {f(o['later_best'], 0)}%), mean loss {f(o['early_cpl'])} cp,"
            f" {f(o['early_instant'], 0)}% played instantly; first clear divergence (loss >= 20 cp) at own move {f(o['first_div'])} on average.")
    add("")
    # Style
    add("STYLE")
    add(f"  Captures on {f(s['capture_pct'])}% of own moves, checks on {f(s['check_pct'])}%; average game {f(s['plies'], 0)} plies ({f(s['own_moves'], 0)} own moves)"
        + (f", longest {s['longest']['plies']} plies ({rnd(s['longest'])})" if s["longest"] else ""))
    wl = wdl(rated)
    add(f"  Wins: {wl[0]} ({s['wins_mate']} by checkmate, {len(s['wins_fail'])} by opponent failure); losses: {wl[2]} ({s['losses_mate']} by checkmate, {len(s['losses_fail'])} by own failure"
        + (": " + ", ".join(f"{rnd(g)} {g['termination']}" for g in s["losses_fail"]) if s["losses_fail"] else "") + ")")
    if team["analysed"]:
        add(f"  Sacrifices (gave >= 2 pawns of material without losing eval, then recovered): {len(s['sacs'])}"
            + (" -> " + ", ".join(f"{rnd(g)} {m['n']}.{m['san']}" for g, m, _ in s["sacs"][:6]) if s["sacs"] else ""))
        add(f"  When ahead (> +{AHEAD}) material leaves the board at {f(s['off_ahead'], 2)} pawns per own move (level: {f(s['off_level'], 2)}); capture rate {f(s['cap_ahead'])}% vs {f(s['cap_level'])}% level"
            + (" -> simplifies when ahead" if s["off_ahead"] is not None and s["off_level"] is not None and s["off_ahead"] >= 1.3 * s["off_level"] else " -> no deliberate simplification"))
    add("")
    add("LIKELY ENGINE PROFILE")
    for line in profile(team):
        L.extend(wrap(line))
    add("")
    add("HOW TO PLAY THEM")
    for i, r in enumerate(recommendations(team), 1):
        L.extend(wrap(f"{i}. {r}"))
    note = NOTES / f"{team['slug']}.txt"
    if note.exists():
        add("")
        stamp = dt.datetime.fromtimestamp(note.stat().st_mtime).strftime("%Y-%m-%d")
        add(f"ANALYST NOTES (hand-written {stamp}; numbers above are regenerated on every refresh, this text is not)")
        for line in note.read_text().rstrip().splitlines():
            add("  " + line if line.strip() else "")
    return finalize(L)


def finalize(lines: list[str]) -> str:
    out = []
    for line in lines:
        if len(line) <= W:
            out.append(line)
            continue
        indent = len(line) - len(line.lstrip(" "))
        out.extend(wrap_hanging(line, indent))
    return "\n".join(out) + "\n"


def wrap_hanging(line: str, indent: int) -> list[str]:
    words = line.strip().split()
    first, rest = " " * indent, " " * (indent + 2)
    out, cur, pre = [], "", first
    for w_ in words:
        if len(pre) + len(cur) + len(w_) + 1 > W and cur:
            out.append(pre + cur)
            cur, pre = w_, rest
        else:
            cur = f"{cur} {w_}".strip()
    if cur:
        out.append(pre + cur)
    return out


# ----------------------------------------------------------------------------- summary
def league_row(team):
    q, t, d, c = team["q"], team["t"], team["d"], team["c"]
    n = len(team["rated"])
    return {
        "rank": team["rank"],
        "bot": team["bot"],
        "team": team["team"],
        "uuid": team["uuid"],
        "rating": team["rating"],
        "record": team["record"],
        "games": n,
        "cpl": q["mean"] if q.get("reliable") else None,
        "site_acpl": q.get("site_acpl"),
        "blunder_pct": q["blunder_pct"] if q.get("reliable") else None,
        "spm": t.get("mean"),
        "draw_pct": pct(d["n"], n),
        "rep_ahead": len(d["rep_ahead"]),
        "nonconv": len(c["missed"]),
        "provisional": team.get("provisional", False),
    }


def table(rows):
    hdr = f"{'#':>3} {'Bot':<18} {'Rating':>6} {'Record':>8} {'CPL':>5} {'sACPL':>5} {'Bl%':>5} {'s/mv':>5} {'Draw%':>5} {'RepA':>4} {'NonC':>4}"
    out = [hdr, "-" * len(hdr)]
    for r in rows:
        out.append(f"{r['rank']:>3} {r['bot'][:18]:<18} {r['rating']:>6} {r['record']:>8} {f(r['cpl']):>5} {f(r.get('site_acpl'), 0):>5} {f(r['blunder_pct']):>5} {f(r['spm'], 2):>5} {f(r['draw_pct'], 0):>5} {r['rep_ahead']:>4} {r['nonconv']:>4}"
                   + ("  *" if r["provisional"] else ""))
    return out


def h2h(teams):
    tops = [t for t in teams if t["rank"] <= TOP_N]
    tops.sort(key=lambda t: t["rank"])
    by_uuid = {t["uuid"]: t for t in tops}
    short, used = {}, set()
    for t in tops:
        base = re.sub(r"[^A-Za-z0-9]", "", t["bot"])[:3] or "T"
        code, k = base, 2
        while code in used:
            code, k = base[:2] + str(k), k + 1
        used.add(code)
        short[t["uuid"]] = code
    hdr = f"{'':<8}" + "".join(f"{short[t['uuid']]:>4}" for t in tops)
    out = ["  " + "; ".join(f"{short[t['uuid']]}={t['bot']}" for t in tops), hdr]
    games_list = []
    for a in tops:
        cells = []
        for b in tops:
            if a is b:
                cells.append(f"{'-':>4}")
                continue
            gs = sorted([g for g in a["rated"] if g.get("opponent_uuid") == b["uuid"]], key=lambda g: g["round"])
            cells.append(f"{''.join({1.0: 'W', 0.5: 'D', 0.0: 'L'}[g['score']] for g in gs) or '.':>4}")
            for g in gs:
                if a["rank"] < b["rank"]:
                    games_list.append((a, b, g))
        out.append(f"{short[a['uuid']]:<8}" + "".join(cells))
    out.append(f"  Row's result vs column, oldest game first (W/D/L). Games between top-{TOP_N} teams:")
    for a, b, g in sorted(games_list, key=lambda x: x[2]["round"]):
        res = {1.0: f"{a['bot']} won", 0.5: "draw", 0.0: f"{b['bot']} won"}[g["score"]]
        add_cpl = f" (loss/move {f(g.get('cpl_mean'))} vs {f(g.get('opp_cpl_mean'))})" if g.get("cpl_mean") is not None else ""
        out.append(f"  {rnd(g):<4} {a['bot']} ({g['colour']}) vs {b['bot']}: {res} by {g['termination']}, {g['opening']}, {g['plies']} plies{add_cpl}")
    return out


def losses_of(team):
    out = []
    for g in [g for g in team["rated"] if g["score"] == 0.0]:
        opp = g.get("opponent_bot") or g["opponent"]
        out.append(f"  {rnd(g)} as {g['colour']} vs {opp} (#{g.get('opponent_rank_now')}, rated {g.get('opponent_rating_then')} at the time): "
                   f"lost by {g['termination']} after {g['plies']} plies, {g['opening']}.")
        if g["moves"]:
            wm, ow = g.get("worst_move"), g.get("opp_worst_move")
            turn = next((m for m in g["moves"] if m["cp_before"] < -AHEAD), None)
            out.append(f"    Loss per move {f(g.get('cpl_mean'))} cp ({g.get('blunders')} blunders) vs opponent {f(g.get('opp_cpl_mean'))} cp ({g.get('opp_blunders')} blunders); "
                       f"best moment {g['max_adv']:+d}, first clearly worse at own move {turn['n'] if turn else 'n/a'}"
                       + (f" (clock {turn['clock']:.0f} s)" if turn and turn["clock"] is not None else "") + ".")
            if wm:
                out.append(f"    Decisive own error: {wm['n']}.{wm['san']} lost {wm['loss']} cp from {wm['cp_before']:+d}; final clock {f(g.get('final_clock'))} s"
                           + f"; game {g['url']}")
    return out


def findings(teams, ours):
    tops = [t for t in teams if t["rank"] <= TOP_N and t["q"]["mean"] is not None and t["q"].get("reliable")]
    cands = []
    if not tops:
        return ["analysis pending"]
    best = min(tops, key=lambda t: t["q"]["mean"])
    worst = max(tops, key=lambda t: t["q"]["mean"])
    cands.append((100, f"Move quality spread: {best['bot']} loses {best['q']['mean']} cp per move, {worst['bot']} {worst['q']['mean']} cp"
                  + (f"; our current build measures {ours['q']['mean']} cp" if ours and ours["q"]["mean"] is not None else "") + f". Blunder rates run {min(t['q']['blunder_pct'] for t in tops)}-{max(t['q']['blunder_pct'] for t in tops)}%."))
    rep = [t for t in tops if t["d"]["rep_ahead"]]
    if rep:
        cands.append((95, "Free half points: " + ", ".join(f"{t['bot']} ({len(t['d']['rep_ahead'])})" for t in rep) + f" accepted repetitions while more than +{AHEAD}. Against them, when worse, aim for repetition."))
    tt = [t for t in tops if len(t["t"].get("under5", [])) >= 2]
    if tt:
        cands.append((90, "Time trouble is real for " + ", ".join(f"{t['bot']} ({len(t['t']['under5'])} games under 5 s)" for t in tt) + ". Long, complicated games punish them."))
    unused = [t for t in tops if t["t"].get("final_mean") is not None and t["t"]["final_mean"] >= 30]
    if unused:
        cands.append((85, "Clock left unused by " + ", ".join(f"{t['bot']} ({t['t']['final_mean']:.0f} s)" for t in unused) + ": their depth is capped by a per-move budget, so our deeper search in critical moments is a real edge."))
    lk = [t for t in tops if len(t["c"]["missed"]) >= 2]
    if lk:
        cands.append((80, "Leaky conversion: " + ", ".join(f"{t['bot']} ({len(t['c']['missed'])} of {t['c']['winning_games']} winning positions not won)" for t in lk) + ". Keep lost positions alive."))
    late = [t for t in tops if t["q"]["phase"][3]["mean"] is not None and t["q"]["phase"][1]["mean"] is not None and t["q"]["phase"][3]["mean"] >= 1.5 * max(t["q"]["phase"][1]["mean"], 5)]
    if late:
        cands.append((75, "Endgame fade: " + ", ".join(f"{t['bot']} ({t['q']['phase'][1]['mean']} -> {t['q']['phase'][3]['mean']} cp)" for t in late) + " lose far more per move after own move 40."))
    prov = [t for t in tops if t.get("provisional")]
    if prov:
        cands.append((70, "New builds in the last five rounds (provisional ratings): " + ", ".join(t["bot"] for t in prov) + ". Their older games may not describe the bot we will face."))
    fixed = [t for t in tops if t["t"].get("n") and t["t"]["q3"] - t["t"]["q1"] <= 0.5]
    if fixed:
        cands.append((65, "Fixed per-move budgets: " + ", ".join(f"{t['bot']} ({t['t']['median']} s)" for t in fixed) + ". They cannot allocate extra time to critical positions."))
    dr = sorted(tops, key=lambda t: -pct(t["d"]["n"], len(t["rated"])))[:3]
    cands.append((60, "Drawishness: " + ", ".join(f"{t['bot']} {pct(t['d']['n'], len(t['rated']))}%" for t in dr) + " draw most often; threefold is the dominant draw type across the field."))
    cands.sort(key=lambda x: -x[0])
    return [c[1] for c in cands]


def changes(rows):
    prev_files = sorted(glob.glob(str(HISTORY / "summary_*.json")))
    if not prev_files:
        return ["First refresh: nothing to compare against."]
    prev = load_json(pathlib.Path(prev_files[-1]))
    stamp = os.path.basename(prev_files[-1])[8:-5]
    out = [f"Compared with history/summary_{stamp}.txt:"]
    pr = {r["uuid"]: r for r in prev["rows"]}
    cur = {r["uuid"]: r for r in rows}
    for u in cur:
        if u not in pr:
            out.append(f"  new in the table: {cur[u]['bot']} (rank {cur[u]['rank']})")
    for u in pr:
        if u not in cur:
            out.append(f"  dropped out: {pr[u]['bot']} (was rank {pr[u]['rank']})")
    for u, r in cur.items():
        p = pr.get(u)
        if not p:
            continue
        diffs = []
        if r["rank"] != p["rank"]:
            diffs.append(f"rank {p['rank']} -> {r['rank']}")
        if r["rating"] != p["rating"]:
            diffs.append(f"rating {p['rating']} -> {r['rating']}")
        if r["games"] != p["games"]:
            diffs.append(f"games {p['games']} -> {r['games']} ({r['record']})")
        if r["cpl"] is not None and p["cpl"] is not None and abs(r["cpl"] - p["cpl"]) >= 1:
            diffs.append(f"CPL {p['cpl']} -> {r['cpl']}")
        if r["rep_ahead"] != p["rep_ahead"]:
            diffs.append(f"repeats-ahead {p['rep_ahead']} -> {r['rep_ahead']}")
        if diffs:
            out.append(f"  {r['bot']}: " + ", ".join(diffs))
    if len(out) == 1:
        out.append("  no changes")
    return out


def main():
    lb = load_json(LEADERBOARD)["rows"]
    targets = load_json(TARGETS)["targets"]
    teams = []
    for t in targets:
        team = load_team(t)
        if team:
            teams.append(compute(team))
    by_uuid = {t["uuid"]: t for t in teams}
    ours = next((t for t in teams if t["team"] == OUR_TEAM), None)

    # remove stale dossiers, write new ones
    for old in glob.glob(str(HERE / "[0-9][0-9]*_*.txt")):
        os.remove(old)
    written = []
    for team in teams:
        name = f"{team['rank']:02d}_{team['slug']}.txt"
        (HERE / name).write_text(render_dossier(team, by_uuid, lb))
        written.append(name)

    rows = [league_row(t) for t in teams]
    tops = [r for r in rows if r["rank"] <= TOP_N]
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    L = []
    L.append(f"AI CHESSATHON TOP-{TOP_N} INTEL SUMMARY  ({dt.datetime.now().strftime('%Y-%m-%d %H:%M')}; leaderboard fetched {load_json(LEADERBOARD)['fetched_at']})")
    L.append("=" * 100)
    L.append(f"CPL = mean centipawn loss per own move (Stockfish 19, {SF_NODES // 1000}k nodes, positions inside +-800); sACPL = the site's own review ACPL")
    L.append(f"(Stockfish 16 depth 16, every game, mean per game); Bl% = moves losing >= {BLUNDER} cp; CPL and Bl% show n/a until 200 moves are analysed;")
    L.append(f"s/mv = mean seconds per own move; RepA = draws by repetition while more than +{AHEAD}; NonC = games at +{CONVERT} or better not won; * = provisional rating.")
    L.append("")
    L.append("LEAGUE TABLE")
    L.extend(table(tops))
    partial = [t for t in teams if t["n_analysed"] < len(t["games"])]
    if partial:
        L.append("  Stockfish analysis still incomplete for: " + ", ".join(f"{t['bot']} ({t['n_analysed']}/{len(t['games'])} games)" for t in partial) + ". Re-run ./refresh.sh --no-scrape to finish.")
    if ours:
        L.append("")
        L.append("OUR ROW")
        L.extend(table([league_row(ours)])[2:])
        opp = [g for g in ours["rated"] if g.get("opponent_rating_then") and g.get("own_rating_then")]
        if opp:
            diff = mean([g["opponent_rating_then"] - g["own_rating_then"] for g in opp], 0)
            L.append(f"  Pairing: our {len(opp)} rated opponents were rated {diff:+.0f} relative to us on average at the time (range "
                     f"{min(g['opponent_rating_then'] - g['own_rating_then'] for g in opp):+d} to {max(g['opponent_rating_then'] - g['own_rating_then'] for g in opp):+d}); "
                     f"current ranks {', '.join(str(g.get('opponent_rank_now')) for g in ours['rated'])}. Pairings track rating, so a fresh build climbs through weaker teams first.")
    L.append("")
    L.append("KEY FINDINGS")
    for i, line in enumerate(findings(teams, ours), 1):
        L.extend(wrap(f"{i}. {line}"))
        if i == 5:
            L.append("  (further observations)")
    snote = NOTES / "summary.txt"
    if snote.exists():
        L.append("")
        L.append(f"ANALYST NOTES (hand-written {dt.datetime.fromtimestamp(snote.stat().st_mtime).strftime('%Y-%m-%d')}; not regenerated)")
        for line in snote.read_text().rstrip().splitlines():
            L.append("  " + line if line.strip() else "")
    leader = min((t for t in teams if t["rank"] <= TOP_N), key=lambda t: t["rank"], default=None)
    if leader:
        L.append("")
        L.append(f"LOSSES OF THE LEADER ({leader['bot']}, {leader['record']})")
        lines = losses_of(leader)
        L.extend(lines if lines else ["  none"])
    L.append("")
    L.append(f"HEAD-TO-HEAD AMONG THE TOP {TOP_N}")
    L.extend(h2h(teams))
    L.append("")
    L.append(f"TIME MANAGEMENT (top {TOP_N})")
    hdr = f"{'Bot':<18} {'mean':>5} {'med':>5} {'max':>5} {'q1-q3':>11} {'end':>5} {'min':>5} {'<5s':>4} {'inst%':>5} {'swing':>6} {'calm':>6}"
    L.append(hdr)
    for t in sorted((t for t in teams if t["rank"] <= TOP_N), key=lambda t: t["rank"]):
        tt = t["t"]
        if tt.get("n"):
            L.append(f"{t['bot'][:18]:<18} {tt['mean']:>5} {tt['median']:>5} {tt['max']:>5} {f(tt['q1'], 2) + '-' + f(tt['q3'], 2):>11} {f(tt['final_mean'], 0):>5} {f(tt['final_min']):>5} {len(tt['under5']):>4} {f(tt['instant_pct']):>5} {f(tt['swing_in'][0], 2):>6} {f(tt['calm_in'][0], 2):>6}")
    L.append("  seconds per own move; end/min = clock left at the end (mean/min); swing/calm = s per move after a >100 cp swing vs otherwise")
    L.append("")
    L.append(f"DRAWS AND CONVERSION (top {TOP_N})")
    hdr = f"{'Bot':<18} {'draws':>5} {'3fold':>5} {'fifty':>5} {'insuf':>5} {'repA':>5} {'repB':>5} {'won+':>5} {'nonC':>5} {'lost-':>5} {'saved':>5}"
    L.append(hdr)
    for t in sorted((t for t in teams if t["rank"] <= TOP_N), key=lambda t: t["rank"]):
        d, c = t["d"], t["c"]
        L.append(f"{t['bot'][:18]:<18} {d['n']:>5} {d['by'].get('threefold_repetition', 0):>5} {d['by'].get('fifty_moves', 0):>5} {d['by'].get('insufficient_material', 0):>5} {len(d['rep_ahead']):>5} {len(d['rep_behind']):>5} {c['winning_games']:>5} {len(c['missed']):>5} {c['losing_games']:>5} {len(c['saved']):>5}")
    L.append(f"  repA/repB = repetition draws while ahead/behind by {AHEAD}+; won+ = games that reached +{CONVERT}; nonC = those not won; lost- = games at -{CONVERT}; saved = those not lost")
    L.append("")
    L.append("WHAT CHANGED SINCE LAST REFRESH")
    L.extend(changes(rows))
    L.append("")
    L.append("FILES: " + ", ".join(written))
    text = finalize(L)
    (HERE / "00_summary.txt").write_text(text)
    HISTORY.mkdir(exist_ok=True)
    (HISTORY / f"summary_{stamp}.txt").write_text(text)
    with open(HISTORY / f"summary_{stamp}.json", "w") as fh:
        json.dump({"stamp": stamp, "rows": rows}, fh, indent=1)
    # terminal output: league table and the five findings
    print("\n".join(table(tops)))
    if ours:
        print("\n".join(table([league_row(ours)])[2:]))
    print()
    for i, line in enumerate(findings(teams, ours)[:5], 1):
        print("\n".join(wrap(f"{i}. {line}")))


if __name__ == "__main__":
    main()
