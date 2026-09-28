from conductor.youtube_music import YouTubeMusic, album_url


class FakeCatalog:
    def __init__(self):
        self.searches = []

    def search(self, query, filter, limit):
        self.searches.append((query, filter))
        return [{"browseId": "MPREb_found"}]

    def get_album(self, browse_id):
        assert browse_id in ("MPREb_found", "MPREb_given")
        return {"audioPlaylistId": "OLAK5uy_x", "tracks": [{"videoId": "a1"}, {"videoId": "a2"}]}


def test_an_album_opens_on_its_first_track_within_its_playlist():
    url = album_url(FakeCatalog(), "Some Artist Some Album")
    assert url == "https://music.youtube.com/watch?v=a1&list=OLAK5uy_x"


def test_a_browse_id_skips_the_search():
    catalog = FakeCatalog()
    album_url(catalog, "MPREb_given")
    assert catalog.searches == []


class RecordingYouTubeMusic(YouTubeMusic):
    def __init__(self):
        self.opened = []
        super().__init__(
            "http://127.0.0.1:1", token="t", navigate=self.opened.append, catalog=FakeCatalog()
        )
        self.calls = []

    def _call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/song":
            return {"videoId": "a1", "title": "T", "artist": "A", "album": "Al", "isPaused": True}
        return None


def test_load_opens_the_album_page_and_leaves_the_queue_alone():
    ytm = RecordingYouTubeMusic()
    ytm.load("Some Artist Some Album")
    assert ytm.opened == ["https://music.youtube.com/watch?v=a1&list=OLAK5uy_x"]
    assert not [c for c in ytm.calls if c[1] == "/queue"]


def test_now_playing_reads_the_song():
    track = RecordingYouTubeMusic().now_playing()
    assert (track.video_id, track.artist, track.title, track.is_paused) == ("a1", "A", "T", True)
