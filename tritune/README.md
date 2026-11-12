# TriTune

A fast personal music client for Linux (built for CachyOS / Arch) with a familiar
dark three-pane layout: library on the left, content in the middle, queue on the
right, player bar at the bottom.

It plays music from **YouTube Music** and **SoundCloud**, and can **import public
Spotify playlists / albums** by matching their songs on YouTube Music.

## Install

```bash
git clone https://github.com/KevinKoortzen/TriDL.git
cd TriDL
./install.sh
```

Then start **TriTune** from your app menu, or run `tritune`.

TriTune is a native desktop app: its own Qt window, with audio played by **mpv**
(no browser involved). The installer adds `mpv`, `deno`, `pyside6` and
`qt6-webengine` with pacman if missing, creates a Python venv in the repo, and
adds a launcher + app-menu entry.

Re-run `./install.sh` any time to update — do this first if playback stops
working, since YouTube changes often and yt-dlp has to keep up.

**If a song won't play**, the red message shows the reason, and the full log is in
`~/.cache/tritune/tritune.log`.

## Features

- Search songs, albums and artists (YouTube Music) and tracks (SoundCloud)
- Album and artist pages, song radio, recommendations on the home screen
- Liked Songs, playlists, recently played — stored locally in SQLite
- Import playlists/albums from Spotify, YouTube Music, YouTube and SoundCloud links
- Queue, shuffle, repeat, autoplay of similar songs when the queue ends
- Next track is resolved ahead of time, so skipping is instant
- Play/pause from desktop media controls if `mpv-mpris` is installed (`sudo pacman -S mpv-mpris`)
- Restores your queue and position on restart

| Shortcut | Action |
| --- | --- |
| `Space` | Play / pause |
| `Ctrl+→` / `Ctrl+←` | Next / previous |
| `Ctrl+↑` / `Ctrl+↓` | Volume |
| `/` or `Ctrl+K` | Search |
| `Q` | Toggle queue |
| Right-click a song | Queue, radio, add to playlist… |

## What "Spotify support" means

Spotify's audio is DRM-protected and only available to its own apps, so no
third-party client can stream it. TriTune reads the *track list* of a public
Spotify playlist, album or track link (no account or API key needed) and finds
each song on YouTube Music. Limits: the link must be public, and only the first
100 tracks of a playlist are visible.

## How it works

`python -m tritune` opens the window and runs a small backend inside the same process.

- `window.py` — the Qt window (PySide6 / QtWebEngine renders the interface)
- `player.py` — audio playback through an `mpv` process (JSON IPC); tries the
  stream URL resolved by yt-dlp first, then mpv's own yt-dlp hook as a fallback
- `providers.py` — search/browse via `ytmusicapi`, stream resolution via `yt-dlp`
- `server.py` — internal API between the window and the backend (localhost only)
- `spotify.py` — reads public Spotify links
- `library.py` — SQLite library in `~/.local/share/tritune/library.db`

## Tests

```bash
.venv/bin/python -m unittest tests.test_core     # offline unit tests
.venv/bin/python -m tests.mock_app 47990         # backend with fake sources, no network
```

## Disclaimer

For personal use. Streaming this way is not endorsed by YouTube or SoundCloud
and may be against their terms of service; support the artists you listen to.
TriTune is not affiliated with Spotify, YouTube or SoundCloud.
