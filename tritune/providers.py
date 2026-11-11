"""Music sources: YouTube Music (ytmusicapi + yt-dlp) and SoundCloud (yt-dlp).

Everything in this module is blocking and is meant to be called from a
thread pool. A track is a plain dict:

    {"id": "ytm:<videoId>" | "sc:<trackId>", "source", "title", "artist",
     "artist_id", "album", "album_id", "duration" (seconds), "thumb", "url"}
"""

from __future__ import annotations

import re
import threading
import time
from urllib.parse import parse_qs, urlparse

_YTM_ID = re.compile(r"^[\w-]{6,20}$")
_SC_ID = re.compile(r"^\d+$")

_ytm_client = None
_ytm_lock = threading.Lock()
_local = threading.local()


def ytm():
    global _ytm_client
    with _ytm_lock:
        if _ytm_client is None:
            from ytmusicapi import YTMusic

            _ytm_client = YTMusic()
        return _ytm_client


def _ydl(fmt: str | None = None, flat: bool = False):
    """One reusable YoutubeDL per thread and option set (construction is slow)."""
    from yt_dlp import YoutubeDL

    key = (fmt, flat)
    cache = _local.__dict__.setdefault("ydl", {})
    if key not in cache:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                "noplaylist": not flat, "socket_timeout": 15}
        if fmt:
            opts["format"] = fmt
        if flat:
            opts["extract_flat"] = True
        cache[key] = YoutubeDL(opts)
    return cache[key]


# ── helpers ─────────────────────────────────────────────────────────────

def _seconds(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value:
        try:
            total = 0
            for part in value.split(":"):
                total = total * 60 + int(part)
            return total
        except ValueError:
            return 0
    return 0


def _thumb(thumbs, size: int = 226) -> str:
    if isinstance(thumbs, dict):
        thumbs = thumbs.get("thumbnails")
    if not thumbs:
        return ""
    url = thumbs[-1].get("url", "")
    return re.sub(r"=w\d+-h\d+", f"=w{size}-h{size}", url)


def _ytm_track(it: dict, album: dict | None = None, thumb: str = "") -> dict | None:
    vid = it.get("videoId")
    if not vid:
        return None
    artists = [a for a in (it.get("artists") or []) if isinstance(a, dict) and a.get("name")]
    alb = it.get("album") if isinstance(it.get("album"), dict) else (album or {})
    return {
        "id": f"ytm:{vid}",
        "source": "ytm",
        "title": it.get("title") or "Unknown",
        "artist": ", ".join(a["name"] for a in artists),
        "artist_id": next((a["id"] for a in artists if a.get("id")), None),
        "album": alb.get("name") or "",
        "album_id": alb.get("id"),
        "duration": _seconds(it.get("duration_seconds") or it.get("duration") or it.get("length")),
        "thumb": _thumb(it.get("thumbnails") or it.get("thumbnail")) or thumb
        or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
        "url": f"https://music.youtube.com/watch?v={vid}",
    }


def _ydl_track(e: dict, source: str) -> dict | None:
    if not e or not e.get("id"):
        return None
    thumbs = e.get("thumbnails") or []
    thumb = e.get("thumbnail") or (thumbs[-1].get("url") if thumbs else "")
    if source == "ytm":
        thumb = f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg"
        url = f"https://music.youtube.com/watch?v={e['id']}"
    else:
        url = e.get("webpage_url") or e.get("url") or ""
    return {
        "id": f"{source}:{e['id']}",
        "source": source,
        "title": e.get("title") or "Unknown",
        "artist": e.get("artist") or e.get("uploader") or e.get("channel") or "",
        "artist_id": None,
        "album": e.get("album") or "",
        "album_id": None,
        "duration": _seconds(e.get("duration")),
        "thumb": thumb or "",
        "url": url,
    }


# ── search / browse ─────────────────────────────────────────────────────

def search_songs_ytm(q: str, limit: int = 20) -> list[dict]:
    res = ytm().search(q, filter="songs", limit=limit)
    return [t for it in res[:limit] if (t := _ytm_track(it))]


def search_songs_sc(q: str, limit: int = 20) -> list[dict]:
    info = _ydl(flat=True).extract_info(f"scsearch{limit}:{q}", download=False) or {}
    return [t for e in info.get("entries") or [] if (t := _ydl_track(e, "sc"))]


def search_albums(q: str, limit: int = 12) -> list[dict]:
    res = ytm().search(q, filter="albums", limit=limit)
    out = []
    for it in res[:limit]:
        if not it.get("browseId"):
            continue
        out.append({
            "id": it["browseId"],
            "title": it.get("title") or "",
            "artist": ", ".join(a.get("name", "") for a in it.get("artists") or []),
            "year": it.get("year") or "",
            "thumb": _thumb(it.get("thumbnails"), 300),
        })
    return out


def search_artists(q: str, limit: int = 8) -> list[dict]:
    res = ytm().search(q, filter="artists", limit=limit)
    return [{"id": it["browseId"], "name": it.get("artist") or it.get("title") or "",
             "thumb": _thumb(it.get("thumbnails"), 300)}
            for it in res[:limit] if it.get("browseId")]


def album(browse_id: str) -> dict:
    a = ytm().get_album(browse_id)
    thumb = _thumb(a.get("thumbnails"), 544)
    ref = {"name": a.get("title") or "", "id": browse_id}
    small = _thumb(a.get("thumbnails"), 226)
    return {
        "id": browse_id,
        "title": a.get("title") or "",
        "artist": ", ".join(x.get("name", "") for x in a.get("artists") or []),
        "artist_id": next((x["id"] for x in a.get("artists") or [] if x.get("id")), None),
        "year": a.get("year") or "",
        "thumb": thumb,
        "tracks": [t for it in a.get("tracks") or [] if (t := _ytm_track(it, ref, small))],
    }


def artist(channel_id: str) -> dict:
    a = ytm().get_artist(channel_id)

    def cards(section):
        return [{"id": it["browseId"], "title": it.get("title") or "", "year": it.get("year") or "",
                 "artist": a.get("name") or "", "thumb": _thumb(it.get("thumbnails"), 300)}
                for it in (a.get(section) or {}).get("results") or [] if it.get("browseId")]

    return {
        "id": channel_id,
        "name": a.get("name") or "",
        "subscribers": a.get("subscribers") or "",
        "thumb": _thumb(a.get("thumbnails"), 544),
        "tracks": [t for it in (a.get("songs") or {}).get("results") or [] if (t := _ytm_track(it))],
        "albums": cards("albums"),
        "singles": cards("singles"),
    }


def match(title: str, artist_name: str = "", duration: int = 0) -> dict | None:
    """Find the YouTube Music song that best matches some metadata."""
    tracks = search_songs_ytm(f"{title} {artist_name}".strip(), limit=5)
    if not tracks:
        return None
    if duration:
        for t in tracks:
            if t["duration"] and abs(t["duration"] - duration) <= 5:
                return t
    return tracks[0]


def radio(track: dict | str, limit: int = 25) -> list[dict]:
    """Tracks similar to the given one (used for autoplay and recommendations)."""
    tid = track if isinstance(track, str) else track.get("id", "")
    source, _, rid = tid.partition(":")
    if source != "ytm":
        if not isinstance(track, dict):
            return []
        m = match(track.get("title", ""), track.get("artist", ""), track.get("duration", 0))
        if not m:
            return []
        tid, rid = m["id"], m["id"].split(":", 1)[1]
    res = ytm().get_watch_playlist(videoId=rid, limit=limit)
    out = [t for it in res.get("tracks") or [] if (t := _ytm_track(it))]
    return [t for t in out if t["id"] != tid]


def import_playlist(url: str) -> dict:
    """Read a YouTube / YouTube Music / SoundCloud playlist, album or set."""
    host = urlparse(url).netloc.lower()
    source = "sc" if "soundcloud.com" in host else "ytm"
    info = _ydl(flat=True).extract_info(url, download=False) or {}
    entries = info.get("entries")
    if entries is None:
        entries = [info]
    return {"name": info.get("title") or "Imported playlist",
            "tracks": [t for e in entries if (t := _ydl_track(e, source))]}


# ── stream resolution ───────────────────────────────────────────────────

def resolve(track_id: str) -> dict:
    """Resolve a track id into a playable audio URL."""
    source, _, rid = track_id.partition(":")
    if source == "ytm" and _YTM_ID.match(rid):
        page = f"https://music.youtube.com/watch?v={rid}"
        fmt = "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best"
    elif source == "sc" and _SC_ID.match(rid):
        page = f"https://api.soundcloud.com/tracks/{rid}"
        fmt = "bestaudio[protocol^=http]/bestaudio/best"
    else:
        raise ValueError(f"bad track id: {track_id}")

    info = _ydl(fmt=fmt).extract_info(page, download=False)
    url = info.get("url")
    if not url:
        raise RuntimeError("no playable audio stream found")

    expires = time.time() + 3600
    try:
        expires = min(time.time() + 6 * 3600, int(parse_qs(urlparse(url).query)["expire"][0]))
    except (KeyError, ValueError, IndexError):
        pass
    return {
        "url": url,
        "headers": dict(info.get("http_headers") or {}),
        "ext": info.get("ext") or "",
        "hls": str(info.get("protocol") or "").startswith("m3u8"),
        "expires": expires - 120,
    }
