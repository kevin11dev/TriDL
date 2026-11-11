#!/usr/bin/env bash
# TriTune installer for CachyOS / Arch Linux.
#   ./install.sh            install or update (re-run any time to update yt-dlp)
#   ./install.sh --webview  also install a native Qt window (pywebview) instead
#                           of using a Chromium-based browser in app mode
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ROOT=$PWD

# System packages: ffmpeg for some SoundCloud streams, deno for yt-dlp's YouTube support.
missing=()
for cmd in python ffmpeg deno; do command -v "$cmd" >/dev/null || missing+=("$cmd"); done
if ((${#missing[@]})); then
  if command -v pacman >/dev/null; then
    echo "Installing system packages: ${missing[*]}"
    sudo pacman -S --needed "${missing[@]}"
  else
    echo "Please install: ${missing[*]}" >&2
  fi
fi

PY=$(command -v python || command -v python3)
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --upgrade -r tritune/requirements.txt
if [[ "${1:-}" == "--webview" ]]; then
  .venv/bin/pip install --quiet --upgrade "pywebview[qt]"
fi

BIN=$HOME/.local/bin
APPS=${XDG_DATA_HOME:-$HOME/.local/share}/applications
ICONS=${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps
mkdir -p "$BIN" "$APPS" "$ICONS"

cat > "$BIN/tritune" <<LAUNCH
#!/bin/sh
cd "$ROOT" && exec .venv/bin/python -m tritune "\$@"
LAUNCH
chmod +x "$BIN/tritune"
cp tritune/web/icon.svg "$ICONS/tritune.svg"
cat > "$APPS/tritune.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TriTune
Comment=Personal music client for YouTube Music and SoundCloud
Exec=$BIN/tritune
Icon=tritune
Terminal=false
Categories=AudioVideo;Audio;Player;
StartupWMClass=TriTune
DESKTOP

echo "Done. Start TriTune from your app menu, or run: tritune"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "(note: $BIN is not on your PATH - use $BIN/tritune)";; esac
