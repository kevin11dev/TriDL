"""Offline unit tests:  python -m unittest tests.test_core"""
import json
import os
import tempfile
import unittest

from tritune import providers, spotify
from tritune.library import Library


class SpotifyTest(unittest.TestCase):
    def test_links(self):
        sid = "37i9dQZF1DXcBWIGoYBM5M"
        self.assertEqual(spotify.parse_link(f"https://open.spotify.com/playlist/{sid}?si=abc"), ("playlist", sid))
        self.assertEqual(spotify.parse_link(f"https://open.spotify.com/intl-de/album/{sid}"), ("album", sid))
        self.assertEqual(spotify.parse_link(f"spotify:track:{sid}"), ("track", sid))
        self.assertIsNone(spotify.parse_link("https://music.youtube.com/playlist?list=PL123"))

    def test_embed(self):
        entity = {"name": "Mix", "trackList": [
            {"title": "One More Time", "subtitle": "Daft Punk", "duration": 320357},
            {"title": "", "subtitle": "skip me"}]}
        html = ('<html><script id="__NEXT_DATA__" type="application/json">'
                + json.dumps({"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}) + "</script></html>")
        res = spotify.parse_embed(html)
        self.assertEqual(res, {"name": "Mix", "tracks": [{"title": "One More Time", "artist": "Daft Punk", "duration": 320}]})
        with self.assertRaises(RuntimeError):
            spotify.parse_embed("<html></html>")


class ProviderTest(unittest.TestCase):
    def test_ytm_track(self):
        t = providers._ytm_track({
            "videoId": "abcdefghijk", "title": "Song", "duration": "1:02:03",
            "artists": [{"name": "A", "id": "UC1"}, {"name": "B", "id": None}],
            "album": {"name": "Alb", "id": "MPRE1"},
            "thumbnails": [{"url": "https://x/y=w60-h60-l90-rj"}, {"url": "https://x/y=w120-h120-l90-rj"}]})
        self.assertEqual((t["id"], t["artist"], t["artist_id"], t["album_id"], t["duration"]),
                         ("ytm:abcdefghijk", "A, B", "UC1", "MPRE1", 3723))
        self.assertEqual(t["thumb"], "https://x/y=w226-h226-l90-rj")
        self.assertIsNone(providers._ytm_track({"title": "no id"}))

    def test_ydl_track(self):
        t = providers._ydl_track({"id": 123, "title": "T", "uploader": "U", "duration": 61.7,
                                  "url": "https://soundcloud.com/u/t", "thumbnails": [{"url": "a"}, {"url": "b"}]}, "sc")
        self.assertEqual((t["id"], t["artist"], t["duration"], t["thumb"], t["url"]),
                         ("sc:123", "U", 61, "b", "https://soundcloud.com/u/t"))

    def test_resolve_rejects_bad_ids(self):
        for bad in ("ytm:../../etc", "sc:abc", "file:/etc/passwd", "nope"):
            with self.assertRaises(ValueError):
                providers.resolve(bad)


class LibraryTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            lib = Library(os.path.join(d, "l.db"))
            a = {"id": "ytm:a", "title": "A", "thumb": "ta", "junk": 1}
            b = {"id": "sc:2", "title": "B"}
            lib.like(a); lib.like(a)
            self.assertEqual([t["id"] for t in lib.likes()], ["ytm:a"])
            self.assertNotIn("junk", lib.likes()[0])
            pid = lib.create_playlist("P", [a, b])
            self.assertEqual(lib.add_tracks(pid, [b]), 0)
            self.assertEqual([t["id"] for t in lib.playlist(pid)["tracks"]], ["ytm:a", "sc:2"])
            self.assertEqual(lib.playlists()[0], {"id": pid, "name": "P", "count": 2, "thumb": "ta"})
            lib.remove_track(pid, "ytm:a"); lib.unlike("ytm:a"); lib.played(b)
            self.assertEqual(len(lib.playlist(pid)["tracks"]), 1)
            self.assertEqual(lib.likes(), [])
            self.assertEqual(lib.history()[0]["id"], "sc:2")
            lib.delete_playlist(pid)
            self.assertIsNone(lib.playlist(pid))
            with self.assertRaises(ValueError):
                lib.like({"title": "no id"})


if __name__ == "__main__":
    unittest.main()
