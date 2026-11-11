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

The installer creates a Python venv in the repo, installs `ffmpeg` and `deno` with
pacman if missing (yt-dlp needs deno for YouTube), and adds a launcher + desktop
entry. Re-run `./install.sh` any time to update — do this first if playback stops
working, since YouTube changes often and yt-dlp has to keep up.

**Window:** by default TriTune opens in a Chromium-based browser's app mode
(Chromium, Brave, Chrome, Vivaldi, Edge) with its own profile. With none installed
it opens a tab in your default browser. For a native Qt window instead, run
`./install.sh --webview`.

## Features

- Search songs, albums and artists (YouTube Music) and tracks (SoundCloud)
- Album and artist pages, song radio, recommendations on the home screen
- Liked Songs, playlists, recently played — stored locally in SQLite
- Import playlists/albums from Spotify, YouTube Music, YouTube and SoundCloud links
- Queue, shuffle, repeat, autoplay of similar songs when the queue ends
- Next track is resolved ahead of time, so skipping is instant
- Media keys / desktop media controls (MPRIS, via the browser engine)
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

`python -m tritune` starts a small local server on `127.0.0.1:47600`
(aiohttp) and opens the UI (plain HTML/CSS/JS, no build step).

- `providers.py` — search/browse via `ytmusicapi`, stream resolution via `yt-dlp`
- `server.py` — JSON API + audio proxy with Range support (seeking), URL cache
- `spotify.py` — reads public Spotify links
- `library.py` — SQLite library in `~/.local/share/tritune/library.db`

Options: `tritune --port 47600 --window auto|webview|app|browser|none`

## Tests

```bash
.venv/bin/python -m unittest tests.test_core     # offline unit tests
.venv/bin/python -m tests.mock_app 47990         # UI with fake sources, no network
```

## Disclaimer

For personal use. Streaming this way is not endorsed by YouTube or SoundCloud
and may be against their terms of service; support the artists you listen to.
TriTune is not affiliated with Spotify, YouTube or SoundCloud.
