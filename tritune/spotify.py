"""Read track lists from public Spotify links (no account or API key needed).

Spotify's audio is DRM-protected and cannot be streamed by a third-party
client, so TriTune only reads the *metadata* (title / artist / duration) of
a public playlist, album or track from Spotify's embed page and then finds
the same songs on YouTube Music.
"""

from __future__ import annotations

import json
import re

_LINK = re.compile(r"(?:open\.spotify\.com/(?:intl-[\w-]+/)?(?:embed/)?|spotify:)"
                   r"(playlist|album|track)[/:]([A-Za-z0-9]{22})")
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/130.0 Safari/537.36")


def parse_link(url: str):
    m = _LINK.search(url or "")
    return (m.group(1), m.group(2)) if m else None


def parse_embed(html: str) -> dict:
    m = _NEXT_DATA.search(html)
    if not m:
        raise RuntimeError("could not read the Spotify page (layout changed?)")
    try:
        entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError("could not read the Spotify page (layout changed?)") from e

    def clean(s):
        return (s or "").replace(" ", " ").strip()

    items = entity.get("trackList")
    if items is None:  # a single track
        items = [{"title": entity.get("title") or entity.get("name"),
                  "subtitle": ", ".join(a.get("name", "") for a in entity.get("artists") or []),
                  "duration": entity.get("duration")}]
    tracks = [{"title": clean(it.get("title")), "artist": clean(it.get("subtitle")),
               "duration": int((it.get("duration") or 0) / 1000)}
              for it in items if it.get("title")]
    return {"name": clean(entity.get("name") or entity.get("title")) or "Spotify import",
            "tracks": tracks}


async def fetch(session, kind: str, sid: str) -> dict:
    url = f"https://open.spotify.com/embed/{kind}/{sid}"
    async with session.get(url, headers={"User-Agent": _UA}) as r:
        if r.status != 200:
            raise RuntimeError(f"Spotify returned HTTP {r.status} (is the link public?)")
        return parse_embed(await r.text())
