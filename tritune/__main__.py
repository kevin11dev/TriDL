"""Launcher: starts the in-process backend and opens the native TriTune window."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys
import threading
import urllib.request

from aiohttp import web

from .server import cache_dir, data_dir, make_app


def already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/ping", timeout=1) as r:
            return b"tritune" in r.read()
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser(prog="tritune", description="Personal music client")
    ap.add_argument("--port", type=int, default=47600, help="internal port used by the app window")
    ap.add_argument("--no-window", action="store_true", help="run only the backend (for debugging)")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"

    log_file = cache_dir() / "tritune.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(log_file, mode="w"), logging.StreamHandler()])

    if already_running(url):
        sys.exit("TriTune is already running.")

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
