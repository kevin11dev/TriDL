"""Launcher: starts the local server and opens the TriTune window."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import subprocess
import sys
import threading
import urllib.request

from aiohttp import web

from .server import data_dir, make_app

BROWSERS = ("chromium", "google-chrome-stable", "google-chrome", "brave", "brave-browser",
            "vivaldi-stable", "vivaldi", "microsoft-edge-stable", "thorium-browser")


def already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/ping", timeout=1) as r:
            return b"tritune" in r.read()
    except OSError:
        return False


def open_window(url: str, mode: str) -> bool:
    """Show the UI. Returns False if nothing blocks (plain browser tab)."""
    if mode in ("auto", "webview"):
        try:
            import webview  # optional: pip install "pywebview[qt]"

            webview.create_window("TriTune", url, width=1280, height=820,
                                  min_size=(820, 560), background_color="#000000")
            webview.start()
            return True
        except ImportError:
            if mode == "webview":
                sys.exit("pywebview is not installed (run ./install.sh --webview)")
    if mode in ("auto", "app"):
        exe = next((p for b in BROWSERS if (p := shutil.which(b))), None)
        if exe:
            subprocess.run([exe, f"--app={url}", f"--user-data-dir={data_dir() / 'window'}",
                            "--class=TriTune", "--no-first-run", "--no-default-browser-check",
                            "--autoplay-policy=no-user-gesture-required", "--window-size=1280,820"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if mode == "app":
            sys.exit("no Chromium-based browser found")
    subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return False


def main():
    ap = argparse.ArgumentParser(prog="tritune", description="Personal music client")
    ap.add_argument("--port", type=int, default=47600)
    ap.add_argument("--window", choices=("auto", "webview", "app", "browser", "none"), default="auto",
                    help="auto: pywebview if installed, else a Chromium app window, else browser tab")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"

    if already_running(url):
        if args.window != "none":
            open_window(url, args.window)
        return

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
        loop.run_until_complete(runner.cleanup())

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    ready.wait()
    if failed:
        sys.exit(f"could not start on port {args.port}: {failed[0]}")

    print(f"TriTune running at {url}")
    try:
        if args.window == "none" or not open_window(url, args.window):
            print("Press Ctrl+C to quit.")
            thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
