# Astra Note — Book Pipeline Audit

**Scope:** directive §7. Audit the actual builder for the behaviours Astra described, and separate provenance from evidence of inferiority.
**Sources:** `bini_v65/tools/make_book.py`, `bini_v65/bini_engine.py::pv_line`, and the shipped `bini_v8_ship/book.json` (md5 `51c97f3f4e8ab4c1801543945d749906`).
**Conclusion up front: the pipeline has every defect Astra named, and the book should nevertheless be left exactly as it is.**

## Every predicted behaviour is confirmed in the source

| claim | verdict | evidence |
|---|---|---|
| reads a PV from mutable TT entries | **confirmed** | `pv_line()` walks `tt_probe`/`tt_move` from the live table, stopping only when the entry is empty or the move is illegal. It does not check bound type, stored depth, or whether the entry came from a completed iteration — a fail-low `TT_UPPER` entry's "best move" is accepted as PV. |
| copies the root's score and depth onto every child | **confirmed** | `book[k] = {..., "depth": int(depth), "score": int(score), ...}` — `depth` and `score` are the **root's** values, written unchanged onto every ply of the line. |
| can replace a mismatched first PV move while keeping the suffix | **confirmed** | `if not line or line[0] != mv: line = [mv] + line[1:]` — when the TT's PV does not begin with the move actually chosen, the chosen move is spliced onto the front and the **suffix computed for a different first move is retained**. |
| stops only when a move becomes illegal | **confirmed** | `if m not in b.legal_moves: break` is the only termination test in the entry loop. |
| stale entries retained silently through a resumed output file | **confirmed** | the builder loads any existing `book.json` and writes a child entry only `if k not in book or ply == 0`, so a child written by an **earlier net** is never refreshed. |

One mitigation Astra did not have from the outside: child entries do record `"ms": 0`, so the metadata at least admits they received no independent search. `depth` and `score`, however, still assert the root's.

## What that means for the book we actually ship

| | count | share |
|---|---|---|
| entries | 6,105 | |
| distinct root positions | 1,226 | |
| **independently searched** (`ms > 0`) | **900** | **14.7%** |
| **metadata copied from a parent** (`ms = 0`) | **5,205** | **85.3%** |

The 900 searched entries are not uniform either: **266 at 60 s and 634 at 30 s**. The `depth` field spans 12–24, mean 19.0 — and every one of the 5,205 child entries claims its root's depth as if it were its own.

Entries by ply: 900 / 635 / 847 / 964 / 1,048 / 1,175 / 266 / 270 for plies 0–7. That 1,226 roots produced only 900 ply-0 entries indicates roughly 326 root positions transposing onto keys already written, one silently overwriting another — the "explicit treatment of repeated/transposed positions and conflicting analyses" the directive asks for does not exist.

**Separately, the book key omits en passant** (`board_fen + side + castling_xfen`). I demonstrated one concrete aliasing case where two positions share a book key and have different legal move sets (test `C3.book_key_ep_aliasing`). `agent.py` legality-checks the book move before playing it, so the worst outcome is a move analysed for a different position — never an illegal one.

## Why I am not changing anything

Astra's caution is right and I am applying it against my own earlier reasoning: the old book being built by a different net is **provenance, not proof**, and new-net disagreement is not a blunder rate. I previously treated a 55% move-disagreement figure as evidence the book was stale. It was not evidence of anything.

The actual evidence points the other way. A full rebuild with the current net was gated over 400 games and scored **−16.5 Elo with a ±13.9 interval** — the only one of the five V8.5 candidates that is *significantly worse* rather than null, and a result that only became visible once the Bernoulli interval was replaced with a draw-aware one. So:

* **Do not ship a rebuilt book.** It was measured and it lost.
* **Do not ship a book-key change.** Adding en passant to the key invalidates all 6,105 existing entries, which is a rebuild by another name and strands every entry silently — precisely what the directive forbids.
* **Do not ship a wrapper guard that skips the book when en passant is available.** It is a playing-behaviour change, and §8 requires independent quality evidence and representative timed tests before one of those, which I do not have.

The repairs worth making are to the **pipeline**, for use after the lock: extract the PV only from completed iterations with exact bounds, give each child its own search or record honest `depth: null` / `score: null` provenance, refuse to retain entries whose net hash differs from the current one, and resolve transpositions explicitly instead of by last-write-wins. None of that changes a single move the engine plays today, and all of it is out of scope before an 11:00 lock.

**Net recommendation: `book.json` ships byte-identical to the incumbent** — md5 `51c97f3f4e8ab4c1801543945d749906` — and the pipeline repair is filed as post-lock work.
