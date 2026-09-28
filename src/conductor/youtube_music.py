"""YouTube Music backend: th-ch/youtube-music's API server plays, ytmusicapi reads the catalogue."""

import json
import urllib.error
import urllib.request
from pathlib import Path

from conductor.core import Track

CLIENT_ID = "conductor"
RADIO_SIZE = 50


def build_queue(catalog, album: str) -> list[str]:
    """The album's tracks, then YouTube Music's radio around the album, without repeats."""
    browse_id = album if album.startswith("MPREb_") else _find_album(catalog, album)
    found = catalog.get_album(browse_id)
    tracks = list(found["tracks"])
    # "RDAMPL" + the album's playlist is its radio; radio=True on the bare playlist
    # only returns the album again (checked 2026-09-28).
    radio = catalog.get_watch_playlist(
        playlistId="RDAMPL" + found["audioPlaylistId"], limit=RADIO_SIZE
    )
    tracks += radio["tracks"]
    queue: list[str] = []
    for track in tracks:
        video_id = track.get("videoId")
        if video_id and video_id not in queue:
            queue.append(video_id)
    return queue


def _find_album(catalog, query: str) -> str:
    results = catalog.search(query, filter="albums", limit=1)
    if not results:
        raise LookupError(f"no album found for {query!r}")
    return results[0]["browseId"]


def request_token(url: str) -> str:
    """Ask the player for an access token; the player shows an allow/deny dialog."""
    req = urllib.request.Request(f"{url}/auth/{CLIENT_ID}", method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["accessToken"]


class YouTubeMusic:
    def __init__(self, url: str, token: str, catalog=None):
        self.api = f"{url}/api/v1"
        self.token = token
        if catalog is None:
            from ytmusicapi import YTMusic

            catalog = YTMusic()
        self.catalog = catalog

    @classmethod
    def from_token_file(cls, url: str, token_path: Path) -> "YouTubeMusic":
        if not token_path.exists():
            raise RuntimeError(f"no player token at {token_path}: run `conductor auth` first")
        return cls(url, token_path.read_text().strip())

    def load(self, album: str) -> None:
        queue = build_queue(self.catalog, album)
        self._call("DELETE", "/queue")
        for video_id in queue:
            self._call("POST", "/queue", {"videoId": video_id, "insertPosition": "INSERT_AT_END"})
        self._call("PATCH", "/queue", {"index": 0})
        self._call("POST", "/play")

    def play(self) -> None:
        self._call("POST", "/play")

    def pause(self) -> None:
        self._call("POST", "/pause")

    def next(self) -> None:
        self._call("POST", "/next")

    def like(self) -> None:
        self._call("POST", "/like")

    def dislike(self) -> None:
        self._call("POST", "/dislike")

    def now_playing(self) -> Track | None:
        song = self._call("GET", "/song")
        if not song:
            return None
        return Track(
            video_id=song["videoId"],
            title=song["title"],
            artist=song["artist"],
            album=song.get("album"),
            is_paused=bool(song.get("isPaused")),
        )

    def _call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.api + path, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("the player refused the token: run `conductor auth`") from e
            raise
        return json.loads(raw) if raw else None
