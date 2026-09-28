from conductor.youtube_music import YouTubeMusic, album_page


class FakeCatalog:
    def __init__(self):
        self.searches = []

    def search(self, query, filter, limit):
        self.searches.append((query, filter))
        return [{"browseId": "MPREb_found"}]

    def get_album(self, browse_id):
        assert browse_id in ("MPREb_found", "MPREb_given")
        return {
            "title": "Some Album",
            "audioPlaylistId": "OLAK5uy_x",
            "tracks": [{"videoId": "a1"}, {"videoId": "a2"}],
        }


def test_an_album_opens_on_its_first_track_within_its_playlist():
    url, _ = album_page(FakeCatalog(), "Some Artist Some Album")
    assert url == "https://music.youtube.com/watch?v=a1&list=OLAK5uy_x"


def test_the_window_is_named_after_the_album():
    _, title = album_page(FakeCatalog(), "Some Artist Some Album")
    assert title == "CONDUCTOR - Some Album"


def test_a_browse_id_skips_the_search():
    catalog = FakeCatalog()
    album_page(catalog, "MPREb_given")
    assert catalog.searches == []


class RecordingYouTubeMusic(YouTubeMusic):
    def __init__(self):
        self.opened = []
        super().__init__(
            "http://127.0.0.1:1",
            token="t",
            navigate=lambda url, title: self.opened.append((url, title)),
            catalog=FakeCatalog(),
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
    assert ytm.opened == [
        ("https://music.youtube.com/watch?v=a1&list=OLAK5uy_x", "CONDUCTOR - Some Album")
    ]
    assert not [c for c in ytm.calls if c[1] == "/queue"]


def test_now_playing_reads_the_song():
    track = RecordingYouTubeMusic().now_playing()
    assert (track.video_id, track.artist, track.title, track.is_paused) == ("a1", "A", "T", True)


def test_only_audio_and_official_videos_count_as_songs():
    ytm = RecordingYouTubeMusic()
    for media_type, is_song in [
        ("AUDIO", True),
        ("ORIGINAL_MUSIC_VIDEO", True),
        ("USER_GENERATED_CONTENT", False),
        ("OTHER_VIDEO", False),
        ("PODCAST_EPISODE", False),
    ]:
        ytm._call = lambda method, path, body=None, mt=media_type: {
            "videoId": "v",
            "title": "T",
            "artist": "A",
            "mediaType": mt,
        }
        assert ytm.now_playing().is_song is is_song, media_type
