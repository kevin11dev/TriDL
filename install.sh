#!/usr/bin/env bash
# TriTune installer for CachyOS / Arch Linux.
# Re-run any time to update (do this first if playback ever stops working).
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
ROOT=$PWD

# System packages:
#   mpv            native audio engine        deno   needed by yt-dlp for YouTube
#   pyside6 + qt6-webengine   the application window
if command -v pacman >/dev/null; then
  missing=()
  for pkg in python mpv deno pyside6 qt6-webengine; do
    pacman -Qq "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
  done
  if ((${#missing[@]})); then
    echo "Installing system packages: ${missing[*]}"
    sudo pacman -S --needed "${missing[@]}"
  fi
else
  command -v mpv >/dev/null || echo "Please install mpv with your package manager." >&2
fi

# The venv can see system packages (PySide6 from pacman); recreate older venvs that cannot.
PY=$(command -v python || command -v python3)
if [ -f .venv/pyvenv.cfg ] && ! grep -q "include-system-site-packages = true" .venv/pyvenv.cfg; then
  rm -rf .venv
fi
[ -d .venv ] || "$PY" -m venv --system-site-packages .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --upgrade -r tritune/requirements.txt
if ! .venv/bin/python -c "import PySide6.QtWebEngineWidgets" 2>/dev/null; then
  echo "Installing PySide6 into the venv (large download)..."
  .venv/bin/pip install --quiet --upgrade PySide6
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
StartupWMClass=tritune
DESKTOP

echo "Done. Start TriTune from your app menu, or run: tritune"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "(note: $BIN is not on your PATH - use $BIN/tritune)";; esac
