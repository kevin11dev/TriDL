"""Runs TriTune with fake music sources so the UI can be tested offline."""
import io, math, struct, sys, tempfile, wave
from aiohttp import web
from tritune import providers, server


def tone(seconds=20, freq=440):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / 22050)))
                               for i in range(22050 * seconds)))
    return buf.getvalue()


def track(i, source="ytm", q="Song"):
    rid = f"mockvid{i:04d}" if source == "ytm" else str(1000 + i)
    return {"id": f"{source}:{rid}", "source": source, "title": f"{q} {i}", "artist": f"Artist {i % 3}",
            "artist_id": "UCmock" if source == "ytm" else None, "album": "Mock Album" if source == "ytm" else "",
            "album_id": "MPREmock" if source == "ytm" else None, "duration": 20, "thumb": "", "url": "https://example.com/" + rid}


providers.search_songs_ytm = lambda q, limit=20: [track(i, "ytm", q) for i in range(1, 13)]
providers.search_songs_sc = lambda q, limit=20: [track(i, "sc", q) for i in range(1, 9)]
providers.search_albums = lambda q, limit=12: [{"id": "MPREmock", "title": f"{q} Album {i}", "artist": "Artist", "year": "2024", "thumb": ""} for i in range(5)]
providers.search_artists = lambda q, limit=8: [{"id": "UCmock", "name": f"{q} Artist {i}", "thumb": ""} for i in range(4)]
providers.album = lambda bid: {"id": bid, "title": "Mock Album", "artist": "Artist 1", "artist_id": "UCmock", "year": "2024", "thumb": "", "tracks": [track(i) for i in range(1, 11)]}
providers.artist = lambda cid: {"id": cid, "name": "Mock Artist", "subscribers": "1.2M", "thumb": "", "tracks": [track(i) for i in range(1, 6)],
                                "albums": [{"id": "MPREmock", "title": "Mock Album", "year": "2024", "artist": "Mock Artist", "thumb": ""}], "singles": []}
providers.radio = lambda t, limit=25: [track(i, "ytm", "Radio") for i in range(50, 60)]
providers.match = lambda title, artist="", duration=0: track(abs(hash(title)) % 900 + 100, "ytm", title)
providers.import_playlist = lambda url: {"name": "Imported", "tracks": [track(i) for i in range(20, 25)]}


async def start_upstream(app):
    """A second local server standing in for the remote audio host."""
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    f.write(tone()); f.close()
    up = web.Application()
    up.router.add_get("/upstream.wav", lambda r: web.FileResponse(f.name))
    runner = web.AppRunner(up)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", app["port"] + 1).start()


def main(port):
    app = server.make_app()
    app["port"] = port
    app.on_startup.append(start_upstream)
    # ids ending in 3 have a broken stream URL (exercises the fallback + error path)
    providers.resolve = lambda tid: {
        "url": f"http://127.0.0.1:{port + 1}/" + ("missing" if tid.endswith("3") else "upstream.wav"),
        "headers": {"User-Agent": "tritune-test", "X-Test": "1"}, "expires": 9e12}
    web.run_app(app, host="127.0.0.1", port=port, print=None)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 47990)
