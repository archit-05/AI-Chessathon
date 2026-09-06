#!/usr/bin/env python
"""Strategic report: reverse-engineer the top systems from their games and derive what Bini must do.

Writes intel/STRATEGY.txt from the same statistics as report.py plus notes/strategy.txt (hand-written).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
from collections import Counter

from common import CACHE_GAMES, HERE, LEADERBOARD, NOTES, OUR_TEAM, SF_NODES, TARGETS, TOP_N, load_json
from report import AHEAD, BLUNDER, CONVERT, compute, eval_label, f, finalize, h2h, league_row, load_team, mean, pct, rec, recommendations, table, wrap

FOCUS = 10  # teams that get a full reverse-engineering block
SERIES = HERE / "strategy"  # numbered archive: Strategy_1.txt, Strategy_2.txt, ...


def series_entries() -> list[tuple[int, str]]:
    out = []
    for path in glob.glob(str(SERIES / "Strategy_*.json")):
        m = re.search(r"Strategy_(\d+)\.json$", path)
        if m:
            out.append((int(m.group(1)), path))
    return sorted(out)


def series_rows(teams, ours):
    rows = {}
    for t in teams:
        rows[t["uuid"]] = {"bot": t["bot"], "rank": t["rank"], "rating": t["rating"], "record": t["record"], "games": len(t["rated"]),
                           "cpl": t["q"]["mean"] if t["q"].get("reliable") else None, "site_acpl": t["q"].get("site_acpl"),
                           "provisional": bool(t.get("provisional")), "analysed": t["n_analysed"], "rep_ahead": len(t["d"]["rep_ahead"]),
                           "under5": len(t["t"].get("under5", []))}
    return rows


def since_previous(rows, focus_uuids) -> list[str]:
    entries = series_entries()
    if not entries:
        return ["This is Strategy 1; nothing to compare against."]
    n, path = entries[-1]
    prev = load_json(__import__("pathlib").Path(path))
    pr = prev.get("rows", {})
    L = [f"Compared with Strategy {n} ({prev.get('when', '?')}):"]
    for u, r in rows.items():
        if u not in pr and r["rank"] <= FOCUS:
            L.append(f"  new in the top {FOCUS}: {r['bot']} (rank {r['rank']})")
    for u, p in pr.items():
        if u not in rows:
            L.append(f"  dropped out of the covered set: {p['bot']} (was rank {p['rank']})")
    for u, r in rows.items():
        p = pr.get(u)
        if not p or (r["rank"] > FOCUS and p["rank"] > FOCUS):
            continue
        d = []
        if r["rank"] != p["rank"]:
            d.append(f"rank {p['rank']} -> {r['rank']}")
        if r["rating"] != p["rating"]:
            d.append(f"rating {p['rating']} -> {r['rating']}")
        if r["games"] != p["games"]:
            d.append(f"{r['games'] - p['games']} new game(s), now {r['record']}")
        if r["provisional"] and not p["provisional"]:
            d.append("NEW UPLOAD (rating turned provisional)")
        if r["site_acpl"] is not None and p.get("site_acpl") is not None and abs(r["site_acpl"] - p["site_acpl"]) >= 2:
            d.append(f"site ACPL {p['site_acpl']:.0f} -> {r['site_acpl']:.0f}")
        if r["cpl"] is not None and p.get("cpl") is not None and abs(r["cpl"] - p["cpl"]) >= 1:
            d.append(f"CPL {p['cpl']} -> {r['cpl']}")
        elif r["cpl"] is not None and p.get("cpl") is None:
            d.append(f"CPL now measurable: {r['cpl']} cp")
        if r["rep_ahead"] != p.get("rep_ahead", 0):
            d.append(f"repeats-while-ahead {p.get('rep_ahead', 0)} -> {r['rep_ahead']}")
        if d:
            L.append(f"  {r['bot']}: " + ", ".join(d))
    tot_prev = sum(p.get("analysed", 0) for p in pr.values())
    tot_now = sum(r["analysed"] for r in rows.values())
    L.append(f"  Stockfish coverage: {tot_prev} -> {tot_now} games analysed.")
    if len(L) == 2:
        L.insert(1, "  no changes in the top-10 rows")
    return L


def strength_class(team) -> tuple[str, str]:
    q = team["q"]
    cpl, sa = (q["mean"] if q.get("reliable") else None), q.get("site_acpl")
    if (cpl is not None and cpl <= 8) or (cpl is None and sa is not None and sa <= 17):
        return "A", "engine-grade: deep search with a strong evaluation (NNUE-class or very well tuned)"
    if (cpl is not None and cpl <= 14) or (cpl is None and sa is not None and sa <= 22):
        return "B", "strong alpha-beta, roughly depth 8-12 with a tuned evaluation"
    if (cpl is not None and cpl <= 22) or (cpl is None and sa is not None and sa <= 28):
        return "C", "mid-strength alpha-beta, roughly depth 5-8, hand-crafted evaluation"
    return "D", "shallow or noisy search"


def eval_hint(team) -> str:
    p = team["q"]["phase"]
    a, b = p[1]["mean"], p[3]["mean"]
    if a is None or b is None:
        return "not enough analysed moves to judge the evaluation"
    if b >= 1.5 * max(a, 5):
        return f"quality fades late ({a} -> {b} cp): hand-crafted evaluation with weak endgame knowledge, or a horizon problem"
    if a >= 1.5 * max(b, 5):
        return f"weakest early ({a} cp in moves 1-15 vs {b} later): thin opening evaluation, no book"
    return f"quality holds across phases ({a}/{p[2]['mean']}/{b} cp): evaluation is consistent, NNUE-like or well-balanced terms"


def time_policy(team) -> str:
    t = team["t"]
    if not t.get("n"):
        return "no clock data"
    fixed_share = bool(t.get("ratio")) and t["ratio"][2] <= 1.4 * t["ratio"][0] and t["ratio"][1] >= 0.6 * t["ratio"][0] and t["q3"] - t["q1"] > 0.5
    if fixed_share:
        pol = f"fixed ~{t['ratio'][0]:.0f}% of the remaining clock per move (median {t['median']} s, max {t['max']} s)"
    elif t["q3"] - t["q1"] <= 0.5:
        pol = f"fixed per-move budget (median {t['median']} s, interquartile {t['q1']}-{t['q3']} s)"
    else:
        pol = f"adaptive (median {t['median']} s, max {t['max']} s)"
    return pol + f"; {f(t['final_mean'], 0)} s left at the end on average; {len(t['under5'])} games under 5 s"


def tactical(team) -> str:
    q = team["q"]
    if q["n"] == 0:
        return "n/a"
    per1000 = 1000.0 * q["blunders_not_losing"] / q["n"]
    return f"{per1000:.1f} blunders per 1000 moves from level or better positions ({q['blunders_not_losing']} in {q['n']})"


def reverse_block(team) -> list[str]:
    q, t, d, c, o, s = team["q"], team["t"], team["d"], team["c"], team["o"], team["s"]
    cls, cls_text = strength_class(team)
    L = []
    prov = " [fresh upload, provisional]" if team.get("provisional") else ""
    L.append(f"{team['rank']:>2}. {team['bot']} ({team['team']}, {team['university'] or 'n/a'}) - {team['rating']}, {team['record']}{prov}")
    cpl_txt = f"our CPL {f(q['mean'])} cp, blunders {f(q['blunder_pct'])}%" if q.get("reliable") else f"our CPL pending ({q['n']} moves measured so far)"
    L.append(f"    Class {cls}: {cls_text}. Site ACPL {f(q.get('site_acpl'), 0)}; {cpl_txt} ({team['n_analysed']}/{len(team['games'])} games analysed).")
    L.append(f"    Evaluation: {eval_hint(team)}.")
    L.append(f"    Tactics: {tactical(team)}.")
    book = "yes" if (o["early_instant"] or 0) >= 15 else "no"
    L.append(f"    Book: {book} ({f(o['early_instant'], 0)}% of the first six moves instant; {f(o['early_best'], 0)}% match Stockfish's first choice).")
    L.append(f"    Time: {time_policy(team)}.")
    reps = f"repeats while ahead {len(d['rep_ahead'])}, while behind {len(d['rep_behind'])}, level {len(d['rep_level'])}" if team["analysed"] else "not analysed"
    conv = f"converted {c['winning_games'] - len(c['missed'])}/{c['winning_games']} won positions, escaped {len(c['saved'])}/{c['losing_games']} lost ones" if team["analysed"] else "not analysed"
    L.append(f"    Draws: {d['n']} in {len(team['rated'])} games; {reps}. Conversion: {conv}.")
    top = team["tiers"]["top 10"]
    L.append(f"    Versus the top 10: {rec(top)} in {len(top)} games. Exploit: {recommendations(team)[0]}")
    return L


def leaks(focus) -> list[str]:
    """Where the top teams actually drop points: regenerated from the per-game data."""
    L = []
    for t in focus:
        d, c, tt = t["d"], t["c"], t["t"]
        items = []
        for g in d["rep_ahead"]:
            items.append(f"repeated while +{g['final_cp']} in R{g['round']} vs {(g.get('opponent_bot') or g['opponent'])[:14]}")
        for g, best, why in c["missed"]:
            if g["termination"] == "threefold_repetition" and g in d["rep_ahead"]:
                continue
            items.append(f"R{g['round']} vs {(g.get('opponent_bot') or g['opponent'])[:14]}: peak {best:+d}, {why}")
        # playing a found mate instantly is normal; it is a leak only when the game was then not won
        instant_mate = [(g, m) for g in t["rated"] if g["score"] < 1.0 for m in g["moves"] if m["cp_before"] >= 9000 and m["time"] is not None and m["time"] < 0.02]
        if instant_mate:
            rounds = sorted({g["round"] for g, _ in instant_mate})
            items.append(f"held a mate score, played {len(instant_mate)} moves in under 20 ms and still did not win (R{', R'.join(map(str, rounds))})")
        if tt.get("under5"):
            items.append(f"clock under 5 s in {len(tt['under5'])} of {len(t['rated'])} games")
        if not items:
            items.append("nothing found: converts, never repeats ahead, never short of time")
        L.append(f"{t['rank']:>2}. {t['bot']}: " + "; ".join(items))
    return L


def bar_to_clear(tops) -> list[str]:
    five = sorted(tops, key=lambda t: -t["rating"])[:5]
    L = []
    sa = [t["q"].get("site_acpl") for t in five if t["q"].get("site_acpl") is not None]
    rel = [t for t in five if t["q"].get("reliable")]
    cp = [t["q"]["mean"] for t in rel]
    L.append(f"Top five by rating: {', '.join(t['bot'] for t in five)}.")
    cp_txt = (f"our CPL {min(cp):.1f}-{max(cp):.1f} cp and blunder rate {min(t['q']['blunder_pct'] for t in rel)}-{max(t['q']['blunder_pct'] for t in rel)}% ({len(rel)} of 5 with enough analysed moves)" if rel else "CPL pending")
    L.append(f"Site ACPL {min(sa):.0f}-{max(sa):.0f} (mean {mean(sa):.1f}); {cp_txt}.")
    u5 = sum(len(t["t"].get("under5", [])) for t in five)
    left = [t["t"]["final_mean"] for t in five if t["t"].get("final_mean") is not None]
    L.append(f"Clock: {u5} games under 5 s in {sum(len(t['rated']) for t in five)}; {min(left):.0f}-{max(left):.0f} s left at the end; median move {min(t['t']['median'] for t in five)}-{max(t['t']['median'] for t in five)} s.")
    ra = sum(len(t["d"]["rep_ahead"]) for t in five)
    lv = sum(len(t["d"]["rep_level"]) for t in five)
    L.append(f"Draw discipline: {ra} repetitions accepted while ahead across the five; {lv} level repetitions (they do take a draw when nothing is left).")
    won = sum(t["c"]["winning_games"] for t in five)
    miss = sum(len(t["c"]["missed"]) for t in five)
    L.append(f"Conversion: {won - miss} of {won} positions at +{CONVERT} or better were won (analysed games only).")
    books = [t["bot"] for t in five if (t["o"]["early_instant"] or 0) >= 15]
    L.append("Opening book: " + (", ".join(books) if books else "none of the five") + " play part of the first six moves instantly.")
    return L


def openings_facts() -> list[str]:
    fens = Counter()
    names = {}
    games = 0
    for path in glob.glob(str(CACHE_GAMES / "*.json")):
        d = load_json(__import__("pathlib").Path(path))
        if not d or "Void" in d.get("state", ""):
            continue
        m = re.search(r'\[FEN "([^"]+)"\]', d["pgn"])
        if not m:
            continue
        games += 1
        fens[m.group(1)] += 1
        names[m.group(1)] = d["opening"]
    if not games:
        return ["no games cached"]
    fam = Counter()
    for fen, n in fens.items():
        fam[names[fen].split(",")[0].split()[0]] += n
    top40 = sum(v for _, v in fens.most_common(40))
    stm = Counter(fen.split()[1] for fen in fens)
    L = [f"{len(fens)} distinct curated start positions in {games} scraped games; the 40 most common cover {pct(top40, games):.0f}% of games;"
         f" {stm.get('b', 0)} positions have Black to move, {stm.get('w', 0)} White, mostly at move 6-8."]
    L.append("Families by games: " + ", ".join(f"{k} {v}" for k, v in fam.most_common(10)) + ".")
    L.append("Most repeated positions: " + "; ".join(f"{names[fen]} x{n}" for fen, n in fens.most_common(6)) + ".")
    return L


def implications(tops, ours) -> list[str]:
    five = sorted(tops, key=lambda t: -t["rating"])[:5]
    L = []
    sa = [t["q"].get("site_acpl") for t in five if t["q"].get("site_acpl") is not None]
    cp = [t["q"]["mean"] for t in five if t["q"].get("reliable")] or [None]
    our_sa = ours["q"].get("site_acpl") if ours else None
    v2 = [g for g in ours["rated"] if g["round"] >= 31] if ours else []
    v2s = ", ".join(f"R{g['round']} {f(g.get('site_acpl'), 0)}" for g in v2) if v2 else "none yet"
    cp_rng = f"{min(cp):.1f}-{max(cp):.1f} cp" if cp[0] is not None else "pending"
    cp_tgt = f"{min(cp):.0f} cp" if cp[0] is not None else "pending"
    L.append(f"1. Move quality is the whole game. The top five sit at site ACPL {min(sa):.0f}-{max(sa):.0f} and CPL {cp_rng} with blunder rates under 1%."
             f" Our ladder history shows site ACPL {f(our_sa, 0)} (mostly the v1 build); v2 games so far (site ACPL): {v2s}. Target for the final build: site ACPL <= {min(sa):.0f}, CPL <= {cp_tgt}.")
    med = [t["t"]["median"] for t in five]
    mx = [t["t"]["max"] for t in five]
    left = [t["t"]["final_mean"] for t in five if t["t"].get("final_mean") is not None]
    L.append(f"2. Time is the cheapest edge. The top five think {min(med)}-{max(med)} s per move (max {min(mx)}-{max(mx)} s) and leave {min(left):.0f}-{max(left):.0f} s unused,"
             f" mostly by spending a fixed 3-4% of the remaining clock. A budget that spends 2-3x that in the middlegame (about 3-5 s on moves 10-40, more after an evaluation swing) and keeps a 10 s reserve"
             " buys one to two extra plies on every critical move without any risk of flagging; the 0.5 s increment covers a long endgame on its own.")
    ra = sum(len(t["d"]["rep_ahead"]) for t in five)
    lv = sum(len(t["d"]["rep_level"]) for t in five)
    L.append(f"3. Draw policy: the top five gave away {ra} half points by repeating while ahead, but accepted {lv} level repetitions. So: positive contempt against everyone below the top ten"
             " (they hand out half points; see RepA in the summary), near-zero contempt against the top three when we are not better, and a repetition-seeking mode when we are worse against them: they will take it.")
    won = sum(t["c"]["winning_games"] for t in five)
    miss = sum(len(t["c"]["missed"]) for t in five)
    L.append(f"4. There are no swindles at the top: {won - miss} of {won} positions at +{CONVERT} were converted. A game against them is decided by the first -300, so the evaluation must be right in the"
             " middlegame structures the curated set produces (Sicilian Closed, English Symmetrical, Ruy Lopez Closed, Petroff, Caro-Kann) rather than by endgame technique.")
    weak = sorted([t for t in tops if t["q"].get("reliable")], key=lambda t: -(1000.0 * t["q"]["blunders_not_losing"] / t["q"]["n"]))[:3]
    L.append("5. Tactics only pay against the teams that blunder from level positions: " + (", ".join(f"{t['bot']} ({1000.0 * t['q']['blunders_not_losing'] / t['q']['n']:.1f}/1000)" for t in weak) or "pending") +
             ". Against class-A engines keep the position sound and let the time edge and the endgame do the work.")
    tt = [t for t in tops if len(t["t"].get("under5", [])) >= 3]
    L.append("6. Clock pressure works against " + (", ".join(f"{t['bot']} ({len(t['t']['under5'])} games under 5 s)" for t in tt) if tt else "nobody in the top ten") +
             ": keep those games long and complicated, never simplify early against them.")
    L.append("7. Openings: a shipped book is low value (231 curated positions, the top 40 cover a third of games, and every game leaves theory within a few moves). What matters is a"
             " cheap, correct first move out of the curated position (a 1-2 s search is fine) and an evaluation that understands closed Sicilian, symmetrical English and closed Ruy Lopez structures.")
    return L


def our_status(ours) -> list[str]:
    if not ours:
        return ["our team is not on the leaderboard"]
    L = [f"{ours['bot']} ({OUR_TEAM}): rank {ours['rank']}, rating {ours['rating']}, record {ours['record']}"]
    for g in ours["rated"]:
        L.append(f"  R{g['round']} {g['colour'][0].upper()} vs {(g.get('opponent_bot') or g['opponent'])[:16]:<16} (#{g.get('opponent_rank_now')}, {g.get('opponent_rating_then')}) "
                 f"{ {1.0: 'win ', 0.5: 'draw', 0.0: 'loss'}.get(g['score'], 'void')} {g['termination'][:14]:<14} site ACPL {f(g.get('site_acpl'), 0):>3} vs {f(g.get('opp_site_acpl'), 0):>3}"
                 f"  {f(mean(g.get('time_per_move') or []), 1)} s/mv, end {f(g.get('final_clock'), 0)} s, {g['opening']}")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", action="store_true", help="also write the next numbered strategy/Strategy_N.{txt,json}")
    a = ap.parse_args()
    lb = load_json(LEADERBOARD)["rows"]
    targets = load_json(TARGETS)["targets"]
    teams = [compute(t) for t in (load_team(x) for x in targets) if t]
    tops = sorted([t for t in teams if t["rank"] <= TOP_N and t["q"]["n"] or t["rank"] <= FOCUS], key=lambda t: t["rank"])
    focus = [t for t in teams if t["rank"] <= FOCUS]
    focus.sort(key=lambda t: t["rank"])
    ours = next((t for t in teams if t["team"] == OUR_TEAM), None)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    entries = series_entries()
    number = (entries[-1][0] + 1) if entries else 1
    rows = series_rows(teams, ours)
    L = []
    L.append(f"STRATEGY {number} - reverse-engineering the top of the AI Chessathon ladder  ({now})")
    L.append("=" * 100)
    src = Counter(t.get("eval_source", "sf") for t in teams).most_common(1)[0][0]
    L.extend(wrap(f"Sources: every public rated game of the top {TOP_N} (+ us), the site's own per-game review (accuracy, ACPL, move tags) and per-position evaluations ({eval_label({'eval_source': src})}), from which CPL, ahead/behind, conversion and time-vs-swing figures are computed. Regenerated by intel/refresh.sh; per-team detail in intel/<rank>_<Bot>.txt.", indent=0))
    L.append("")
    L.append("SINCE THE PREVIOUS STRATEGY")
    L.extend(since_previous(rows, {t["uuid"] for t in focus}))
    L.append("")
    L.append("A. THE FIELD")
    L.extend(table([league_row(t) for t in sorted(teams, key=lambda t: t["rank"]) if t["rank"] <= TOP_N]))
    if ours:
        L.extend(table([league_row(ours)])[2:])
    L.append("")
    L.append(f"B. REVERSE-ENGINEERED PROFILES (top {FOCUS})")
    for t in focus:
        L.extend(reverse_block(t))
        L.append("")
    L.append(f"C1. WHERE THE TOP {FOCUS} LEAK POINTS (from every rated game; details in the dossiers)")
    for line in leaks(focus):
        L.extend(wrap(line))
    L.append("")
    L.append("C. THE BAR TO CLEAR (top five by rating)")
    for line in bar_to_clear(focus):
        L.extend(wrap(line))
    L.append("")
    L.append("D. WHAT THIS MEANS FOR OUR BUILD")
    for line in implications(focus, ours):
        L.extend(wrap(line))
    L.append("")
    L.append("E. THE CURATED OPENINGS")
    for line in openings_facts():
        L.extend(wrap(line))
    L.append("")
    L.append("F. OUR OWN GAMES")
    L.extend(our_status(ours))
    L.append("")
    L.append(f"G. HEAD-TO-HEAD (top {TOP_N})")
    L.extend(h2h(teams)[:TOP_N + 3])
    note = NOTES / "strategy.txt"
    if note.exists():
        L.append("")
        L.append(f"H. ANALYST SYNTHESIS (hand-written {dt.datetime.fromtimestamp(note.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}; sections A-G are regenerated, this is not)")
        for line in note.read_text().rstrip().splitlines():
            L.append("  " + line if line.strip() else "")
    text = finalize(L)
    (HERE / "STRATEGY.txt").write_text(text)
    if a.archive:
        SERIES.mkdir(exist_ok=True)
        (SERIES / f"Strategy_{number}.txt").write_text(text)
        with open(SERIES / f"Strategy_{number}.json", "w") as fh:
            json.dump({"number": number, "when": now, "rows": rows}, fh, indent=1)
        print(f"archived as strategy/Strategy_{number}.txt")
    print(text[: text.find("B. REVERSE")])
    i = text.find("D. WHAT THIS MEANS")
    print(text[i: text.find("E. THE CURATED")])


if __name__ == "__main__":
    main()
