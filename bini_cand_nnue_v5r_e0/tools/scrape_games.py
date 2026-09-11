"""Download the public PGNs of a team's rated games from aichessathon.com.

    python tools/scrape_games.py <team-uuid> <out.pgn>   (or a team name substring, looked up on the leaderboard)
"""

from __future__ import annotations

import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://aichessathon.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def team_uuid(name: str) -> str:
    html = fetch(BASE + "/leaderboard")
    # rows: data-href="/team/<uuid>?from=lb" ... bot name ... <small>team</small>
    for row in html.split("<tr")[1:]:
        m = re.search(r'data-href="/team/([0-9a-f-]{36})', row)
        if m and name.lower() in row.lower():
            return m.group(1)
    raise SystemExit(f"team {name!r} not found on the leaderboard")


def main() -> None:
    ident, out = sys.argv[1], Path(sys.argv[2])
    uuid = ident if re.fullmatch(r"[0-9a-f-]{36}", ident) else team_uuid(ident)
    html = fetch(f"{BASE}/team/{uuid}")
    games = sorted(set(re.findall(r'href="/game/([0-9a-f-]{36})', html)))
    pgns = []
    for gid in games:
        page = fetch(f"{BASE}/game/{gid}")
        m = re.search(r'href="data:application/x-chess-pgn;charset=utf-8,([^"]+)"', page)
        if m:
            pgns.append(urllib.parse.unquote(m.group(1)))
    out.write_text("\n\n".join(pgns) + "\n")
    print(f"{uuid}: {len(games)} games, {len(pgns)} PGNs -> {out}")


if __name__ == "__main__":
    main()
