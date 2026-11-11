"""Local library (liked songs, playlists, history) stored in SQLite."""

from __future__ import annotations

import json
import sqlite3
import time

TRACK_KEYS = ("id", "source", "title", "artist", "artist_id", "album", "album_id",
              "duration", "thumb", "url")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS likes (track_id TEXT PRIMARY KEY, added REAL NOT NULL);
CREATE TABLE IF NOT EXISTS playlists (id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS playlist_tracks (pos INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL, track_id TEXT NOT NULL, UNIQUE(playlist_id, track_id));
CREATE TABLE IF NOT EXISTS history (track_id TEXT PRIMARY KEY, played REAL NOT NULL);
"""


def clean_track(t) -> dict:
    if not isinstance(t, dict) or not isinstance(t.get("id"), str) or ":" not in t["id"]:
        raise ValueError("invalid track")
    return {k: t.get(k) for k in TRACK_KEYS}


class Library:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)

    def _save(self, t: dict) -> dict:
        t = clean_track(t)
        self.db.execute("INSERT OR REPLACE INTO tracks VALUES (?, ?)", (t["id"], json.dumps(t)))
        return t

    def _tracks(self, sql: str, args=()) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute(sql, args)]

    # likes
    def likes(self) -> list[dict]:
        return self._tracks("SELECT t.data FROM likes l JOIN tracks t ON t.id = l.track_id "
                            "ORDER BY l.added DESC")

    def like(self, t: dict):
        t = self._save(t)
        self.db.execute("INSERT OR IGNORE INTO likes VALUES (?, ?)", (t["id"], time.time()))
        self.db.commit()

    def unlike(self, tid: str):
        self.db.execute("DELETE FROM likes WHERE track_id = ?", (tid,))
        self.db.commit()

    # history
    def played(self, t: dict):
        t = self._save(t)
        self.db.execute("INSERT OR REPLACE INTO history VALUES (?, ?)", (t["id"], time.time()))
        self.db.execute("DELETE FROM history WHERE track_id NOT IN "
                        "(SELECT track_id FROM history ORDER BY played DESC LIMIT 200)")
        self.db.commit()

    def history(self, limit: int = 50) -> list[dict]:
        return self._tracks("SELECT t.data FROM history h JOIN tracks t ON t.id = h.track_id "
                            "ORDER BY h.played DESC LIMIT ?", (limit,))

    # playlists
    def playlists(self) -> list[dict]:
        rows = self.db.execute(
            "SELECT p.id, p.name, (SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = p.id), "
            "(SELECT t.data FROM playlist_tracks pt JOIN tracks t ON t.id = pt.track_id "
            " WHERE pt.playlist_id = p.id ORDER BY pt.pos LIMIT 1) "
            "FROM playlists p ORDER BY p.created DESC")
        return [{"id": r[0], "name": r[1], "count": r[2],
                 "thumb": json.loads(r[3]).get("thumb", "") if r[3] else ""} for r in rows]

    def playlist(self, pid: int) -> dict | None:
        row = self.db.execute("SELECT id, name FROM playlists WHERE id = ?", (pid,)).fetchone()
        if not row:
            return None
        tracks = self._tracks("SELECT t.data FROM playlist_tracks pt JOIN tracks t "
                              "ON t.id = pt.track_id WHERE pt.playlist_id = ? ORDER BY pt.pos", (pid,))
        return {"id": row[0], "name": row[1], "tracks": tracks}

    def create_playlist(self, name: str, tracks=()) -> int:
        cur = self.db.execute("INSERT INTO playlists (name, created) VALUES (?, ?)",
                              (name.strip()[:200] or "New playlist", time.time()))
        pid = cur.lastrowid
        self.add_tracks(pid, tracks)
        return pid

    def add_tracks(self, pid: int, tracks) -> int:
        added = 0
        for t in tracks:
            t = self._save(t)
            added += self.db.execute("INSERT OR IGNORE INTO playlist_tracks (playlist_id, track_id) "
                                     "VALUES (?, ?)", (pid, t["id"])).rowcount
        self.db.commit()
        return added

    def remove_track(self, pid: int, tid: str):
        self.db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?", (pid, tid))
        self.db.commit()

    def rename_playlist(self, pid: int, name: str):
        self.db.execute("UPDATE playlists SET name = ? WHERE id = ?", (name.strip()[:200], pid))
        self.db.commit()

    def delete_playlist(self, pid: int):
        self.db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (pid,))
        self.db.execute("DELETE FROM playlists WHERE id = ?", (pid,))
        self.db.commit()
