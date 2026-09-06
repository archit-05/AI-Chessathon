#!/usr/bin/env python
"""Evaluate every scraped game with Stockfish and write per-game facts to raw/<Bot>.json.

Every position is analysed once at SF_NODES nodes (Threads 1, Hash 64) and cached by FEN in
raw/evals.jsonl, so a refresh only analyses new games.  Positions that are already decided
(the previous full evaluation was at or beyond +-DECIDED_CP, or a mate score) get SF_NODES_DECIDED
nodes instead; if such a cheap look comes back inside the band it is redone at full nodes.  All
centipawn-loss statistics only use positions inside +-800, i.e. full-node evaluations.

Usage: analyse.py [--dry] [--teams Bot1,Bot2]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time

import chess
import chess.engine
import chess.pgn

from common import (
    BASE_MS,
    CACHE_GAMES,
    DECIDED_CP,
    EVALS,
    INC_MS,
    MATE_CP,
    SF_HASH,
    SF_NODES,
    SF_NODES_DECIDED,
    SF_PATH,
    SF_THREADS,
    TARGETS,
    dump_json,
    load_json,
    team_files,
)

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def material(board: chess.Board) -> int:
    """White material minus black material in pawns."""
    tot = 0
    for pt, v in VALUES.items():
        tot += v * (len(board.pieces(pt, chess.WHITE)) - len(board.pieces(pt, chess.BLACK)))
    return tot


def total_material(board: chess.Board) -> int:
    """Material of both sides together, in pawns (78 at the start)."""
    return sum(v * len(board.pieces(pt, c)) for pt, v in VALUES.items() for c in (chess.WHITE, chess.BLACK))


class Evaluator:
    def __init__(self, dry: bool = False):
        self.cache: dict[str, dict] = {}
        if EVALS.exists():
            with open(EVALS) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rec = json.loads(line)
                        old = self.cache.get(rec["fen"])
                        if old is None or rec["nodes"] >= old["nodes"]:
                            self.cache[rec["fen"]] = rec
        self.dry = dry
        self.engine = None
        self.new = 0
        self.pending: list[dict] = []
        self.t0 = time.time()

    def start(self):
        if self.engine is None:
            self.engine = chess.engine.SimpleEngine.popen_uci(SF_PATH)
            self.engine.configure({"Threads": SF_THREADS, "Hash": SF_HASH})

    def flush(self):
        if self.pending:
            with open(EVALS, "a") as fh:
                for rec in self.pending:
                    fh.write(json.dumps(rec) + "\n")
            self.pending = []

    def terminal(self, board: chess.Board) -> dict | None:
        if board.is_checkmate():
            cp = -MATE_CP if board.turn == chess.WHITE else MATE_CP
            return {"cp": cp, "mate": 0, "best": None, "depth": 0, "nodes": 0}
        if board.is_stalemate() or board.is_insufficient_material() or board.is_seventyfive_moves() or board.is_fivefold_repetition():
            return {"cp": 0, "mate": None, "best": None, "depth": 0, "nodes": 0}
        return None

    def evaluate(self, board: chess.Board, nodes: int, game_key: str) -> dict:
        fen = board.fen()
        rec = self.cache.get(fen)
        if rec is not None and (rec["nodes"] >= nodes or rec["nodes"] == 0):
            return rec
        term = self.terminal(board)
        if term is not None:
            rec = {"fen": fen, **term}
        else:
            if self.dry:
                rec = {"fen": fen, "cp": 0, "mate": None, "best": None, "depth": 0, "nodes": nodes}
                self.cache[fen] = rec
                self.new += 1
                return rec
            self.start()
            for attempt in range(3):
                try:
                    info = self.engine.analyse(board, chess.engine.Limit(nodes=nodes), game=game_key)
                    break
                except chess.engine.EngineError:
                    self.engine.close()
                    self.engine = None
                    self.start()
            score = info["score"].white()
            pv = info.get("pv") or []
            rec = {
                "fen": fen,
                "cp": score.score(mate_score=MATE_CP),
                "mate": score.mate(),
                "best": pv[0].uci() if pv else None,
                "depth": info.get("depth", 0),
                "nodes": nodes,
            }
        self.cache[fen] = rec
        self.pending.append(rec)
        self.new += 1
        if len(self.pending) >= 50:
            self.flush()
        return rec

    def close(self):
        self.flush()
        if self.engine is not None:
            self.engine.quit()


def analyse_game(ev: Evaluator, gid: str, pgn: str) -> dict:
    """Per-ply facts for both sides of one game."""
    game = chess.pgn.read_game(io.StringIO(pgn))
    board = game.board()
    inc = INC_MS / 1000.0
    clocks = {chess.WHITE: BASE_MS / 1000.0, chess.BLACK: BASE_MS / 1000.0}
    plies = []
    prev = ev.evaluate(board, SF_NODES, gid)
    node = game
    ply = 0
    while node.variations:
        node = node.variations[0]
        mv = node.move
        ply += 1
        mover = board.turn
        san = board.san(mv)
        capture = board.is_capture(mv)
        mat_before = material(board)
        tot_before = total_material(board)
        clk = node.clock()
        spent = None
        if clk is not None:
            spent = round(clocks[mover] - clk + inc, 3)
            clocks[mover] = clk
        board.push(mv)
        decided = abs(prev["cp"]) >= DECIDED_CP
        rec = ev.evaluate(board, SF_NODES_DECIDED if decided else SF_NODES, gid)
        if decided and abs(rec["cp"]) < DECIDED_CP and rec["nodes"] < SF_NODES:
            rec = ev.evaluate(board, SF_NODES, gid)
        sign = 1 if mover == chess.WHITE else -1
        before_pov = sign * prev["cp"]
        after_pov = sign * rec["cp"]
        plies.append(
            {
                "ply": ply,
                "mover": "white" if mover == chess.WHITE else "black",
                "san": san,
                "uci": mv.uci(),
                "cp_before": prev["cp"],
                "cp_after": rec["cp"],
                "mate_before": prev["mate"],
                "loss": max(0, min(1000, before_pov - after_pov)),
                "best": prev["best"],
                "is_best": prev["best"] == mv.uci(),
                "nodes": prev["nodes"],
                "capture": capture,
                "check": board.is_check(),
                "mat_before": mat_before,
                "mat_after": material(board),
                "tot_before": tot_before,
                "tot_after": total_material(board),
                "time": spent,
                "clock": round(clk, 3) if clk is not None else None,
            }
        )
        prev = rec
    return {"game": gid, "plies": plies, "final_cp": prev["cp"], "start_fen": game.headers.get("FEN", chess.STARTING_FEN)}


def team_view(analysis: dict, colour: str, verdicts: list) -> dict:
    """The team's own moves plus game-level summaries from the team's point of view."""
    sign = 1 if colour == "white" else -1
    own = []
    n = 0
    opp_losses = []
    opp_blunders = 0
    opp_worst = None
    opp_times = []
    vmap = {}
    for i, (san, v) in enumerate(verdicts):
        vmap[i + 1] = v
    for p in analysis["plies"]:
        if p["mover"] != colour:
            if p["time"] is not None:
                opp_times.append(p["time"])
            if abs(p["cp_before"]) <= 800 and p["nodes"] >= SF_NODES:
                opp_losses.append(p["loss"])
                if p["loss"] >= 200:
                    opp_blunders += 1
            if opp_worst is None or p["loss"] > opp_worst["loss"]:
                opp_worst = {"ply": p["ply"], "san": p["san"], "loss": p["loss"], "cp_before": -sign * p["cp_before"], "clock": p["clock"]}
            continue
        n += 1
        own.append(
            {
                "n": n,
                "ply": p["ply"],
                "san": p["san"],
                "cp_before": sign * p["cp_before"],
                "cp_after": sign * p["cp_after"],
                "loss": p["loss"],
                "counted": abs(p["cp_before"]) <= 800 and p["nodes"] >= SF_NODES,
                "is_best": p["is_best"],
                "capture": p["capture"],
                "check": p["check"],
                "mat_before": sign * p["mat_before"],
                "mat_after": sign * p["mat_after"],
                "tot_before": p["tot_before"],
                "tot_after": p["tot_after"],
                "time": p["time"],
                "clock": p["clock"],
                "verdict": vmap.get(p["ply"]),
            }
        )
    evals = [sign * p["cp_before"] for p in analysis["plies"]] + [sign * analysis["final_cp"]]
    counted = [m["loss"] for m in own if m["counted"]]
    worst = max(own, key=lambda m: m["loss"], default=None)
    return {
        "moves": own,
        "final_cp": sign * analysis["final_cp"],
        "max_adv": max(evals),
        "min_adv": min(evals),
        "eval_swing": max(evals) - min(evals),
        "cpl_mean": round(sum(counted) / len(counted), 1) if counted else None,
        "cpl_n": len(counted),
        "blunders": sum(1 for x in counted if x >= 200),
        "worst_move": {"n": worst["n"], "san": worst["san"], "loss": worst["loss"], "cp_before": worst["cp_before"]} if worst else None,
        "opp_cpl_mean": round(sum(opp_losses) / len(opp_losses), 1) if opp_losses else None,
        "opp_blunders": opp_blunders,
        "opp_worst_move": opp_worst,
        "opp_time_mean": round(sum(opp_times) / len(opp_times), 2) if opp_times else None,
    }


def write_team(t: dict, scrape: dict, analyses: dict, dry: bool) -> int:
    """Write raw/<Bot>.json from whatever games are analysed so far; returns the number analysed."""
    out_games, done = [], 0
    for g in scrape["games"]:
        og = {k: v for k, v in g.items() if k != "site_verdicts"}
        an = analyses.get(g["game"])
        if an is not None:
            og.update(team_view(an, g["colour"], g.get("site_verdicts", [])))
            done += 1
        out_games.append(og)
    out = {k: v for k, v in scrape.items() if k != "games"}
    out.update({"sf_nodes": SF_NODES, "sf_nodes_decided": SF_NODES_DECIDED, "decided_cp": DECIDED_CP,
                "analysed_games": done, "games": out_games})
    if not dry:
        dump_json(team_files(t["slug"])["json"], out)
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="count positions, no engine")
    ap.add_argument("--teams", default="", help="comma-separated bot names to analyse")
    a = ap.parse_args()
    targets = load_json(TARGETS)["targets"]
    only = {t.strip() for t in a.teams.split(",") if t.strip()}
    targets = [t for t in targets if not only or t["bot"] in only or t["slug"] in only]
    target_uuids = {t["uuid"] for t in targets}
    scrapes = {t["slug"]: load_json(team_files(t["slug"])["scrape"]) for t in targets}
    scrapes = {k: v for k, v in scrapes.items() if v}
    leader = min(targets, key=lambda t: t["rank"])

    # Priority order: the leader's losses, then games between covered teams, then teams by rank;
    # within a class the most recent rounds first (they describe the current build best).
    index: dict[str, list] = {}
    prio: dict[str, tuple] = {}
    for t in targets:
        sc = scrapes.get(t["slug"])
        if not sc:
            continue
        for g in sc["games"]:
            if g.get("void"):
                continue  # never rated, excluded from every statistic: not worth the engine time
            index.setdefault(g["game"], []).append((t, sc, g))
            if t["uuid"] == leader["uuid"] and g["score"] == 0.0:
                cls = 0
            elif g.get("opponent_uuid") in target_uuids:
                cls = 1
            else:
                cls = 2 + (t["rank"] - 1) // 3
            key = (cls, -(g["round"] or 0))
            if g["game"] not in prio or key < prio[g["game"]]:
                prio[g["game"]] = key
    order = sorted(index, key=lambda gid: prio[gid])
    print(f"{len(order)} games to analyse in priority order", flush=True)

    ev = Evaluator(dry=a.dry)
    analyses: dict[str, dict] = {}
    done_by_team: dict[str, int] = {}
    try:
        for i, gid in enumerate(order, 1):
            gdata = load_json(CACHE_GAMES / f"{gid}.json")
            if not gdata:
                continue
            t0 = time.time()
            analyses[gid] = analyse_game(ev, gid, gdata["pgn"])
            ev.flush()
            for t, sc, g in index[gid]:
                done_by_team[t["slug"]] = write_team(t, sc, analyses, a.dry)
            owners = ", ".join(f"{t['bot']} R{g['round']}" for t, _, g in index[gid])
            print(f"[{i}/{len(order)}] {owners}: {len(analyses[gid]['plies'])} plies in {time.time() - t0:.0f}s; "
                  f"{ev.new} new evals, {(time.time() - ev.t0) / 60:.1f} min", flush=True)
    finally:
        ev.close()
    for t in targets:
        if t["slug"] in scrapes:
            print(f"{t['rank']:>3} {t['bot']:<20} analysed {done_by_team.get(t['slug'], 0)}/{len(scrapes[t['slug']]['games'])} games")
    if a.dry:
        print(f"positions needing evaluation: {ev.new}")


if __name__ == "__main__":
    main()
