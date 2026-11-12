"""Launcher: starts the in-process backend and opens the native TriTune window."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
import urllib.request

from aiohttp import web

from .server import cache_dir, data_dir, make_app


def running_instance(url: str) -> dict | None:
    """Info about a TriTune already listening on our port, if any."""
    try:
        with urllib.request.urlopen(url + "/api/ping", timeout=1) as r:
            info = json.loads(r.read())
            return info if info.get("app") == "tritune" else None
    except (OSError, ValueError):
        return None


def raise_existing(url: str) -> bool:
    try:
        req = urllib.request.Request(url + "/api/raise", data=b"", method="POST")
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def stop_stale(info: dict):
    """Stop a leftover TriTune that has no window (e.g. an older version's background server)."""
    pids = {info["pid"]} if isinstance(info.get("pid"), int) else set()
    for entry in os.listdir("/proc"):       # older versions do not report their pid
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry}/cmdline", "rb") as f:
                args = f.read().split(b"\0")
        except OSError:
            continue
        if any(a == b"-m" and b == b"tritune" for a, b in zip(args, args[1:])):
            pids.add(int(entry))
    for pid in pids - {os.getpid()}:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    ap = argparse.ArgumentParser(prog="tritune", description="Personal music client")
    ap.add_argument("--port", type=int, default=47600, help="internal port used by the app window")
    ap.add_argument("--no-window", action="store_true", help="run only the backend (for debugging)")
    ap.add_argument("--safe-graphics", action="store_true", help="software rendering, if the window stays blank")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"

    log_file = cache_dir() / "tritune.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(log_file, mode="w"), logging.StreamHandler()])

    if args.safe_graphics:   # for blank / black windows caused by GPU driver problems
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "") + " --disable-gpu").strip()
        os.environ.setdefault("QT_QUICK_BACKEND", "software")

    existing = running_instance(url)
    if existing:
        if raise_existing(url):
            print("TriTune is already open - brought its window to the front.")
            return
        logging.info("stopping a leftover TriTune without a window")
        stop_stale(existing)
        for _ in range(30):
            if not running_instance(url):
                break
            time.sleep(0.1)
        else:   # could not stop it: run next to it instead of refusing to start
            args.port = free_port()
            url = f"http://127.0.0.1:{args.port}"

    if not args.no_window:
        try:
            importlib.import_module("PySide6.QtWebEngineWidgets")
        except ImportError as e:
            sys.exit(f"The app window needs PySide6 with QtWebEngine ({e}).\n"
                     "Run ./install.sh, or: sudo pacman -S pyside6 qt6-webengine")

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    failed: list[BaseException] = []

    def serve():
        asyncio.set_event_loop(loop)
        runner = web.AppRunner(make_app(), access_log=None)
        try:
            loop.run_until_complete(runner.setup())
            loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", args.port).start())
        except BaseException as e:
            failed.append(e)
            ready.set()
            return
        ready.set()
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())   # also stops mpv

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    ready.wait()
    if failed:
        # Most likely another TriTune started at the same moment (e.g. a double click).
        for _ in range(40):
            if raise_existing(url):
                return
            time.sleep(0.2)
        sys.exit(f"could not start on port {args.port}: {failed[0]}")

    code = 0
    try:
        if args.no_window:
            print(f"TriTune backend running at {url} - press Ctrl+C to quit.")
            thread.join()
        else:
            from .window import run
            code = run(url, data_dir() / "qt")
    except KeyboardInterrupt:
        pass
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=3)
    sys.exit(code)


if __name__ == "__main__":
    main()
