"""Native audio playback: drives an mpv process over its JSON IPC socket.

mpv (ffmpeg) plays every codec and streaming protocol the sources use, so no
audio ever passes through the UI layer. Each track is tried in two ways:

  1. the direct stream URL resolved in-process by yt-dlp (fast, cacheable)
  2. mpv's own yt-dlp hook on the track's page URL (independent fallback)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import sys
import tempfile
import time
from pathlib import Path

from . import providers

log = logging.getLogger("tritune.player")
OBSERVED = ("pause", "time-pos", "duration", "paused-for-cache")
MPRIS_PLUGINS = ("/usr/lib/mpv-mpris/mpris.so", "/usr/lib/mpv/mpris.so",
                 "/usr/lib/x86_64-linux-gnu/mpv/mpris.so")


def _die_with_parent():
    """Runs in the mpv child: have the kernel stop it if TriTune dies (even on a crash)."""
    try:
        import ctypes
        import signal
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, signal.SIGTERM)   # PR_SET_PDEATHSIG
    except Exception:
        pass


class Player:
    def __init__(self, resolver):
        self.resolver = resolver
        self.listeners: set = set()          # callables taking one event dict
        self.state = {"tid": None, "paused": True, "time": 0.0, "duration": 0.0,
                      "loading": False, "volume": 0.8, "muted": False}
        self.proc = None
        self.writer = None
        self.replies: dict[int, asyncio.Future] = {}
        self.req = 0
        self.gen = 0            # bumped on every load(); stale work checks it
        self.entry = None       # mpv playlist entry id of the current file
        self.stage = 0          # 0 = direct URL, 1 = mpv yt-dlp hook
        self.err = None
        self.start_lock = asyncio.Lock()
        self.open_lock = asyncio.Lock()
        self.last_push = 0.0

    # ── events to the UI ────────────────────────────────────────────────
    def emit(self, msg: dict):
        for fn in list(self.listeners):
            fn(msg)

    def push(self, throttle: bool = False):
        now = time.monotonic()
        if throttle and now - self.last_push < 0.25:
            return
        self.last_push = now
        self.emit({"ev": "state", **self.state})

    def fail(self, msg: str):
        log.error("playback failed for %s: %s", self.state["tid"], msg)
        self.state.update(loading=False, paused=True)
        self.emit({"ev": "error", "tid": self.state["tid"], "msg": msg})
        self.push()

    # ── mpv process + IPC ───────────────────────────────────────────────
    async def _ensure(self):
        async with self.start_lock:
            if self.proc and self.proc.returncode is None and self.writer:
                return
            exe = shutil.which("mpv")
            if not exe:
                raise RuntimeError("mpv is not installed (sudo pacman -S mpv)")
            base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
            sock = os.path.join(base, f"tritune-mpv-{os.getpid()}.sock")
            if os.path.exists(sock):
                os.unlink(sock)
            args = [exe, "--idle=yes", "--no-video", "--no-terminal", "--no-config",
                    "--audio-display=no", f"--input-ipc-server={sock}",
                    "--audio-client-name=TriTune", "--ytdl-format=bestaudio/best",
                    "--cache=yes", "--demuxer-max-bytes=64MiB", "--volume-max=100"]
            ytdl = Path(sys.executable).with_name("yt-dlp")
            if ytdl.exists():   # make mpv's hook use the same up-to-date yt-dlp
                args.append(f"--script-opts=ytdl_hook-ytdl_path={ytdl}")
            mpris = next((p for p in MPRIS_PLUGINS if os.path.exists(p)), None)
            if mpris:           # desktop media controls / media keys
                args.append(f"--script={mpris}")
            args += shlex.split(os.environ.get("TRITUNE_MPV_ARGS", ""))
            self.proc = await asyncio.create_subprocess_exec(
                *args, preexec_fn=_die_with_parent, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            reader = None
            for _ in range(100):
                if self.proc.returncode is not None:
                    raise RuntimeError("mpv exited immediately - try running `mpv --version`")
                if os.path.exists(sock):
                    try:
                        reader, self.writer = await asyncio.open_unix_connection(sock)
                        break
                    except OSError:
                        pass
                await asyncio.sleep(0.05)
            if reader is None:
                raise RuntimeError("could not connect to mpv")
            asyncio.ensure_future(self._read(reader))
            for i, prop in enumerate(OBSERVED, 1):
                await self._send("observe_property", i, prop)
            await self._send("set_property", "volume", self.state["volume"] * 100)
            await self._send("set_property", "mute", self.state["muted"])

    async def _send(self, *cmd):
        if not self.writer:
            raise RuntimeError("mpv is not running")
        self.req += 1
        rid = self.req
        fut = asyncio.get_running_loop().create_future()
        self.replies[rid] = fut
        try:
            self.writer.write((json.dumps({"command": list(cmd), "request_id": rid}) + "\n").encode())
            await self.writer.drain()
            res = await asyncio.wait_for(fut, 10)
        finally:
            self.replies.pop(rid, None)
        if res.get("error") != "success":
            raise RuntimeError(f"mpv {cmd[0]}: {res.get('error')}")
        return res.get("data")

    async def _read(self, reader):
        try:
            while line := await reader.readline():
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                fut = self.replies.get(msg.get("request_id"))
                if fut is not None and "event" not in msg:
                    if not fut.done():
                        fut.set_result(msg)
                else:
                    self._on_event(msg)
        except (OSError, asyncio.IncompleteReadError, ValueError):
            pass
        self.writer = None
        for fut in self.replies.values():
            if not fut.done():
                fut.set_exception(RuntimeError("mpv exited"))
        if self.state["tid"] and not self.state["paused"]:
            self.state.update(paused=True, loading=False)
            self.push()

    def _on_event(self, m: dict):
        ev = m.get("event")
        if ev == "property-change":
            name, data = m.get("name"), m.get("data")
            if name == "pause":
                self.state["paused"] = bool(data)
                self.push()
            elif name == "time-pos" and data is not None:
                self.state["time"] = data
                self.push(throttle=True)
            elif name == "duration" and data:
                self.state["duration"] = data
                self.push()
            elif name == "paused-for-cache" and data is not None and self.entry != "opening":
                self.state["loading"] = bool(data)
                self.push()
        elif ev == "playback-restart":
            self.state["loading"] = False
            self.push()
        elif ev == "end-file":
            asyncio.ensure_future(self._ended(m))

    async def _ended(self, m: dict):
        reason = m.get("reason")
        if reason not in ("eof", "error"):
            return   # "stop"/"redirect": replaced by a newer load
        if self.entry is not None and m.get("playlist_entry_id") not in (None, self.entry):
            return
        if reason == "eof":
            self.state.update(paused=True, loading=False)
            self.emit({"ev": "ended", "tid": self.state["tid"]})
            return
        why = m.get("file_error") or "playback failed"
        if self.stage == 0:
            log.warning("direct stream failed (%s); falling back to mpv's yt-dlp hook", why)
            self.err = self.err or f"stream error: {why}"
            try:
                await self._open_page(self.state["tid"], self.state["time"], not self.state["paused"], self.gen)
            except Exception as e:
                self.fail(str(e))
        else:
            self.fail(self.err or why)

    # ── loading ─────────────────────────────────────────────────────────
    async def _open(self, url: str, headers: dict, at: float, play: bool, gen: int):
        async with self.open_lock:
            if gen != self.gen:
                return
            self.entry = "opening"
            ua = next((v for k, v in headers.items() if k.lower() == "user-agent"), None)
            fields = [f"{k}: {v}" for k, v in headers.items() if k.lower() != "user-agent"]
            await self._send("set_property", "start", f"+{at:.2f}" if at > 0.5 else "none")
            await self._send("set_property", "http-header-fields", fields)
            if ua:
                await self._send("set_property", "user-agent", ua)
            await self._send("set_property", "pause", not play)
            data = await self._send("loadfile", url, "replace")
            self.entry = (data or {}).get("playlist_entry_id")

    async def _open_page(self, tid: str, at: float, play: bool, gen: int):
        self.stage = 1
        await self._open("ytdl://" + providers.page_url(tid), {}, at, play, gen)

    async def load(self, track: dict, at: float = 0, play: bool = True):
        tid = track["id"]
        self.gen += 1
        gen = self.gen
        self.stage, self.err = 0, None
        self.state.update(tid=tid, time=float(at or 0), duration=float(track.get("duration") or 0),
                          loading=True, paused=not play)
        self.push()
        try:
            providers.page_url(tid)   # validates the id
            await self._ensure()
            info = None
            try:
                info = await self.resolver.get(tid)
            except Exception as e:
                self.err = str(e).split("; please report")[0]
                log.warning("yt-dlp could not resolve %s: %s", tid, self.err)
            if gen != self.gen:
                return
            title = " - ".join(x for x in (track.get("artist"), track.get("title")) if x)
            await self._send("set_property", "force-media-title", title or "TriTune")
            if info:
                await self._open(info["url"], info["headers"], at, play, gen)
            else:
                await self._open_page(tid, at, play, gen)
        except Exception as e:
            if gen == self.gen:
                self.fail(str(e))

    # ── transport controls ──────────────────────────────────────────────
    async def set_pause(self, value: bool):
        if self.writer:
            await self._send("set_property", "pause", bool(value))

    async def seek(self, t: float):
        if self.writer and self.state["tid"]:
            self.state["time"] = float(t)
            try:
                await self._send("seek", float(t), "absolute")
            except RuntimeError:
                pass   # nothing loaded yet

    async def set_volume(self, v: float):
        self.state["volume"] = max(0.0, min(1.0, float(v)))
        if self.writer:
            await self._send("set_property", "volume", self.state["volume"] * 100)

    async def set_mute(self, value: bool):
        self.state["muted"] = bool(value)
        if self.writer:
            await self._send("set_property", "mute", bool(value))

    def close(self):
        if self.proc and self.proc.returncode is None:
            try:
                self.proc.terminate()
            except ProcessLookupError:
                pass
