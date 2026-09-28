from conductor.youtube_music import YouTubeMusic, build_queue


class FakeCatalog:
    def __init__(self):
        self.searches = []

    def search(self, query, filter, limit):
        self.searches.append((query, filter))
        return [{"browseId": "MPREb_found"}]

    def get_album(self, browse_id):
        assert browse_id in ("MPREb_found", "MPREb_given")
        return {"audioPlaylistId": "OLAK5uy_x", "tracks": [{"videoId": "a1"}, {"videoId": "a2"}]}

    def get_watch_playlist(self, playlistId, limit):
        assert playlistId == "RDAMPLOLAK5uy_x"
        return {"tracks": [{"videoId": "a2"}, {"videoId": "r1"}, {"videoId": None}]}


def test_queue_is_the_album_then_its_radio_without_repeats():
    assert build_queue(FakeCatalog(), "Some Artist Some Album") == ["a1", "a2", "r1"]


def test_a_browse_id_skips_the_search():
    catalog = FakeCatalog()
    build_queue(catalog, "MPREb_given")
    assert catalog.searches == []


class RecordingYouTubeMusic(YouTubeMusic):
    def __init__(self):
        super().__init__("http://127.0.0.1:1", token="t", catalog=FakeCatalog())
        self.calls = []

    def _call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/song":
            return {"videoId": "a1", "title": "T", "artist": "A", "album": "Al", "isPaused": True}
        return None


def test_load_replaces_the_queue_and_plays_from_the_top():
    ytm = RecordingYouTubeMusic()
    ytm.load("Some Artist Some Album")
    assert ytm.calls[0] == ("DELETE", "/queue", None)
    added = [c[2]["videoId"] for c in ytm.calls if c[:2] == ("POST", "/queue")]
    assert added == ["a1", "a2", "r1"]
    assert ytm.calls[-2:] == [("PATCH", "/queue", {"index": 0}), ("POST", "/play", None)]


def test_now_playing_reads_the_song():
    track = RecordingYouTubeMusic().now_playing()
    assert (track.video_id, track.artist, track.title, track.is_paused) == ("a1", "A", "T", True)
