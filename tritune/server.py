"""Local HTTP server: JSON API, audio stream proxy and the web UI."""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import aiohttp
from aiohttp import web

from . import providers, spotify
from .library import Library

WEB_DIR = Path(__file__).parent / "web"
HLS_CACHE_LIMIT = 512 * 1024 * 1024
_EXT = {"opus": "ogg", "m4a": "m4a", "mp3": "mp3", "aac": "m4a"}


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    p = Path(os.environ.get("TRITUNE_DATA") or Path(base) / "tritune")
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    p = Path(os.environ.get("TRITUNE_CACHE") or Path(base) / "tritune")
    p.mkdir(parents=True, exist_ok=True)
    return p


class Resolver:
    """Caches resolved stream URLs and de-duplicates concurrent lookups."""

    def __init__(self, run):
        self.run = run
        self.cache: dict[str, dict] = {}
        self.pending: dict[str, asyncio.Task] = {}

    async def get(self, tid: str, force: bool = False) -> dict:
        hit = self.cache.get(tid)
        if hit and not force and hit["expires"] > time.time():
            return hit
        task = self.pending.get(tid)
        if task is None:
            task = asyncio.ensure_future(self._resolve(tid))
            self.pending[tid] = task
            task.add_done_callback(lambda _: self.pending.pop(tid, None))
        return await asyncio.shield(task)

    async def _resolve(self, tid: str) -> dict:
        info = await self.run(providers.resolve, tid)
        if info.get("hls"):
            info["file"] = await self._remux(tid, info)
            info["expires"] = time.time() + 30 * 86400
        self.cache[tid] = info
        if len(self.cache) > 500:
            now = time.time()
            self.cache = {k: v for k, v in self.cache.items() if v["expires"] > now}
        return info

    async def _remux(self, tid: str, info: dict) -> str:
        """HLS-only streams (some SoundCloud tracks) are remuxed to a seekable file."""
        folder = cache_dir() / "hls"
        folder.mkdir(exist_ok=True)
        out = folder / f"{tid.replace(':', '_')}.{_EXT.get(info['ext'], 'mka')}"
        if out.exists():
            return str(out)
        if not shutil.which("ffmpeg"):
            raise RuntimeError("this track needs ffmpeg (sudo pacman -S ffmpeg)")
        tmp = out.with_name("tmp_" + out.name)
        heads = "".join(f"{k}: {v}\r\n" for k, v in info["headers"].items())
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error", "-headers", heads, "-i", info["url"],
            "-vn", "-c", "copy", str(tmp),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await proc.communicate()
        if proc.returncode != 0:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("ffmpeg failed: " + err.decode(errors="replace")[-300:])
        tmp.rename(out)
        return str(out)


def trim_hls_cache():
    folder = cache_dir() / "hls"
    if not folder.is_dir():
        return
    files = sorted((f for f in folder.iterdir() if f.is_file()), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    for f in files:
        if total <= HLS_CACHE_LIMIT:
            break
        total -= f.stat().st_size
        f.unlink(missing_ok=True)


# ── middleware ──────────────────────────────────────────────────────────

@web.middleware
async def guard(request: web.Request, handler):
    # Only answer requests addressed to localhost (blocks DNS-rebinding pages).
    host = request.host.rsplit(":", 1)[0]
    if host not in ("127.0.0.1", "localhost"):
        return web.Response(status=403, text="forbidden")
    try:
        resp = await handler(request)
    except web.HTTPException:
        raise
    except (ValueError, KeyError) as e:
        return web.json_response({"error": str(e) or "bad request"}, status=400)
    except Exception as e:  # surfaced to the UI as a toast
        msg = (str(e) or type(e).__name__).split("; please report")[0]
        return web.json_response({"error": msg}, status=502)
    if not request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


def make_app() -> web.Application:
    app = web.Application(middlewares=[guard], client_max_size=8 * 1024 * 1024)
    pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="tritune")
    lib = Library(str(data_dir() / "library.db"))

    async def run(fn, *args):
        return await asyncio.get_running_loop().run_in_executor(pool, fn, *args)

    resolver = Resolver(run)

    async def on_start(app):
        app["http"] = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, connect=15, sock_read=30))
        trim_hls_cache()

    async def on_stop(app):
        await app["http"].close()
        pool.shutdown(wait=False, cancel_futures=True)

    app.on_startup.append(on_start)
    app.on_cleanup.append(on_stop)
    r = app.router
    ok = lambda **kw: web.json_response({"ok": True, **kw})

    # ── misc ──
    async def index(_):
        return web.FileResponse(WEB_DIR / "index.html")

    async def ping(_):
        return web.json_response({"app": "tritune"})

    # ── discovery ──
    async def search(req):
        q = req.query.get("q", "").strip()
        kind = req.query.get("type", "ytm")
        if not q:
            return web.json_response({"items": []})
        fn = {"ytm": providers.search_songs_ytm, "sc": providers.search_songs_sc,
              "albums": providers.search_albums, "artists": providers.search_artists}[kind]
        return web.json_response({"items": await run(fn, q)})

    async def album(req):
        return web.json_response(await run(providers.album, req.match_info["id"]))

    async def artist(req):
        return web.json_response(await run(providers.artist, req.match_info["id"]))

    async def radio(req):
        return web.json_response({"items": await run(providers.radio, await req.json())})

    # ── playback ──
    async def prefetch(req):
        await resolver.get(req.match_info["tid"])
        return ok()

    async def stream(req):
        tid = req.match_info["tid"]
        up = None
        for attempt in (0, 1):
            info = await resolver.get(tid, force=attempt == 1)
            if info.get("file"):
                if os.path.exists(info["file"]):
                    return web.FileResponse(info["file"])
                continue
            headers = dict(info["headers"])
            if "Range" in req.headers:
                headers["Range"] = req.headers["Range"]
            up = await app["http"].get(info["url"], headers=headers)
            if up.status < 400:
                break
            up.close()
            up = None
        if up is None:
            raise web.HTTPBadGateway(text="stream unavailable")

        resp = web.StreamResponse(status=up.status)
        for h in ("Content-Type", "Content-Length", "Content-Range"):
            if h in up.headers:
                resp.headers[h] = up.headers[h]
        resp.headers["Accept-Ranges"] = "bytes"
        try:
            await resp.prepare(req)
            async for chunk in up.content.iter_chunked(64 * 1024):
                await resp.write(chunk)
        except (ConnectionError, aiohttp.ClientError, asyncio.TimeoutError):
            pass  # listener skipped / seeked away, or upstream dropped
        finally:
            up.close()
        return resp

    # ── library ──
    async def library(_):
        return web.json_response({"playlists": lib.playlists(),
                                  "liked": [t["id"] for t in lib.likes()]})

    async def likes(_):
        return web.json_response({"items": lib.likes()})

    async def like(req):
        lib.like(await req.json())
        return ok()

    async def unlike(req):
        lib.unlike(req.match_info["tid"])
        return ok()

    async def history(_):
        return web.json_response({"items": lib.history()})

    async def played(req):
        lib.played(await req.json())
        return ok()

    async def playlist_new(req):
        body = await req.json()
        return ok(id=lib.create_playlist(body.get("name") or "New playlist", body.get("tracks") or []))

    async def playlist_get(req):
        p = lib.playlist(int(req.match_info["id"]))
        if not p:
            raise web.HTTPNotFound()
        return web.json_response(p)

    async def playlist_rename(req):
        lib.rename_playlist(int(req.match_info["id"]), (await req.json())["name"])
        return ok()

    async def playlist_delete(req):
        lib.delete_playlist(int(req.match_info["id"]))
        return ok()

    async def playlist_add(req):
        body = await req.json()
        return ok(added=lib.add_tracks(int(req.match_info["id"]), body["tracks"]))

    async def playlist_remove(req):
        lib.remove_track(int(req.match_info["id"]), req.match_info["tid"])
        return ok()

    async def import_url(req):
        url = ((await req.json()).get("url") or "").strip()
        sp = spotify.parse_link(url)
        missing = 0
        if sp:
            meta = await spotify.fetch(app["http"], *sp)
            found = await asyncio.gather(
                *(run(providers.match, t["title"], t["artist"], t["duration"]) for t in meta["tracks"]),
                return_exceptions=True)
            tracks = [t for t in found if isinstance(t, dict)]
            missing = len(found) - len(tracks)
            name = meta["name"]
        elif url.startswith(("http://", "https://")):
            res = await run(providers.import_playlist, url)
            name, tracks = res["name"], res["tracks"]
        else:
            raise ValueError("paste a Spotify, YouTube Music or SoundCloud link")
        if not tracks:
            raise ValueError("no tracks found at that link")
        pid = lib.create_playlist(name, tracks)
        return ok(id=pid, name=name, count=len(tracks), missing=missing)

    r.add_get("/", index)
    r.add_get("/api/ping", ping)
    r.add_get("/api/search", search)
    r.add_get("/api/album/{id}", album)
    r.add_get("/api/artist/{id}", artist)
    r.add_post("/api/radio", radio)
    r.add_get("/api/prefetch/{tid}", prefetch)
    r.add_get("/api/stream/{tid}", stream)
    r.add_get("/api/library", library)
    r.add_get("/api/likes", likes)
    r.add_post("/api/likes", like)
    r.add_delete("/api/likes/{tid}", unlike)
    r.add_get("/api/history", history)
    r.add_post("/api/history", played)
    r.add_post("/api/playlists", playlist_new)
    r.add_get("/api/playlists/{id}", playlist_get)
    r.add_patch("/api/playlists/{id}", playlist_rename)
    r.add_delete("/api/playlists/{id}", playlist_delete)
    r.add_post("/api/playlists/{id}/tracks", playlist_add)
    r.add_delete("/api/playlists/{id}/tracks/{tid}", playlist_remove)
    r.add_post("/api/import", import_url)
    r.add_static("/", WEB_DIR)
    return app
