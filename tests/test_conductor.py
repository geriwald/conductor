import pytest

from conductor.core import Conductor, Track

MOODS = {
    "calm": ["calm album"],
    "stress": ["stress album"],
    "chore": ["chore album"],
}
MINUTE = 60


class FakePlayer:
    def __init__(self):
        self.calls = []
        self.track = None
        self._n = 0

    def load(self, album):
        self.calls.append(("load", album))
        self._n += 1
        self.track = Track(video_id=f"{album}#{self._n}", title="t", artist="a", is_paused=False)

    def play(self):
        self.calls.append(("play",))
        self.track = self.track._replace(is_paused=False)

    def pause(self):
        self.calls.append(("pause",))
        self.track = self.track._replace(is_paused=True)

    def next(self):
        self.calls.append(("next",))
        self.end_of_track()

    def like(self):
        self.calls.append(("like",))

    def dislike(self):
        self.calls.append(("dislike",))

    def now_playing(self):
        return self.track

    def end_of_track(self):
        self._n += 1
        self.track = self.track._replace(video_id=f"next#{self._n}")

    def loaded(self):
        return [c[1] for c in self.calls if c[0] == "load"]


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def env():
    player, clock, events = FakePlayer(), Clock(), []

    def log(event, **fields):
        events.append({"event": event, **fields})

    conductor = Conductor(
        player,
        moods=MOODS,
        default_mood="calm",
        ranks=["alpha", "bravo"],
        log=log,
        clock=clock,
        choose=lambda albums: albums[0],
    )
    return conductor, player, clock, events


def names(events):
    return [e["event"] for e in events]


def test_first_request_plays_at_once(env):
    conductor, player, _, _ = env
    conductor.request("bravo", "chore", reason="tax forms")
    assert player.loaded() == ["chore album"]


def test_unknown_mood_is_refused(env):
    conductor, player, _, _ = env
    with pytest.raises(ValueError):
        conductor.request("bravo", "polka", reason="x")
    assert player.loaded() == []


def test_higher_rank_holds_the_music(env):
    conductor, player, _, _ = env
    conductor.request("alpha", "stress", reason="deadline")
    conductor.request("bravo", "chore", reason="tax forms")
    player.end_of_track()
    conductor.tick()
    assert player.loaded() == ["stress album"]
    assert conductor.status()["holder"] == "alpha"


def test_release_hands_over_at_the_end_of_the_track(env):
    conductor, player, _, _ = env
    conductor.request("alpha", "stress", reason="deadline")
    conductor.request("bravo", "chore", reason="tax forms")
    conductor.release("alpha")
    conductor.tick()
    assert player.loaded() == ["stress album"], "must wait for the track to end"
    player.end_of_track()
    conductor.tick()
    assert player.loaded() == ["stress album", "chore album"]


def test_unranked_requesters_come_after_ranked_ones_latest_first(env):
    conductor, _, clock, _ = env
    conductor.request("zulu", "stress", reason="z")
    clock.now += 1
    conductor.request("yankee", "chore", reason="y")
    assert conductor.status()["holder"] == "yankee"
    conductor.request("bravo", "calm", reason="b")
    assert conductor.status()["holder"] == "bravo"


def test_request_expires_after_its_ttl(env):
    conductor, player, clock, events = env
    conductor.request("bravo", "chore", reason="tax forms", ttl=30 * MINUTE)
    clock.now += 31 * MINUTE
    player.end_of_track()
    conductor.tick()
    assert player.loaded() == ["chore album", "calm album"]
    assert "expire" in names(events)


def test_play_pause_with_no_request_plays_the_default_mood(env):
    conductor, player, _, _ = env
    conductor.key("play-pause")
    assert player.loaded() == ["calm album"]


def test_play_pause_while_playing_pauses_and_locks(env):
    conductor, player, _, _ = env
    conductor.request("bravo", "calm", reason="quiet")
    conductor.key("play-pause")
    assert player.track.is_paused
    conductor.request("alpha", "stress", reason="deadline")
    player.end_of_track()
    conductor.tick()
    assert player.track.is_paused, "no agent may resume the music during the lock"
    assert player.loaded() == ["calm album"]


def test_play_pause_while_paused_rechooses_and_plays(env):
    conductor, player, _, _ = env
    conductor.request("bravo", "calm", reason="quiet")
    conductor.key("play-pause")
    conductor.request("alpha", "stress", reason="deadline")
    conductor.key("play-pause")
    assert player.loaded() == ["calm album", "stress album"]
    assert not player.track.is_paused


def test_play_pause_resumes_the_same_track_when_the_mood_still_holds(env):
    conductor, player, _, _ = env
    conductor.request("bravo", "calm", reason="quiet")
    conductor.key("play-pause")
    conductor.key("play-pause")
    assert player.loaded() == ["calm album"]
    assert player.calls[-1] == ("play",)


def test_next_dislikes_and_skips_in_the_same_mood(env):
    conductor, player, _, events = env
    conductor.request("bravo", "chore", reason="tax forms")
    conductor.key("next")
    assert player.calls[-2:] == [("dislike",), ("next",)]
    assert player.loaded() == ["chore album"]
    assert events[-1]["event"] == "key" and events[-1]["key"] == "next"


def test_previous_likes_and_keeps_the_track(env):
    conductor, player, _, _ = env
    conductor.request("bravo", "chore", reason="tax forms")
    before = player.track.video_id
    conductor.key("previous")
    assert player.calls[-1] == ("like",)
    assert player.track.video_id == before


def test_stop_records_a_mismatch_and_switches_mood(env):
    conductor, player, _, events = env
    conductor.request("bravo", "chore", reason="tax forms")
    conductor.key("stop")
    assert player.loaded() == ["chore album", "calm album"]
    mismatch = next(e for e in events if e["event"] == "mismatch")
    assert mismatch["mood"] == "chore" and mismatch["reason"] == "tax forms"


def test_stop_override_holds_for_an_hour_against_agents(env):
    conductor, player, clock, _ = env
    conductor.request("bravo", "chore", reason="tax forms")
    conductor.key("stop")
    conductor.request("alpha", "stress", reason="deadline")
    player.end_of_track()
    conductor.tick()
    assert player.loaded()[-1] == "calm album"
    clock.now += 61 * MINUTE
    conductor.request("alpha", "stress", reason="deadline")
    player.end_of_track()
    conductor.tick()
    assert player.loaded()[-1] == "stress album"


def test_every_action_is_logged(env):
    conductor, _, _, events = env
    conductor.request("bravo", "chore", reason="tax forms")
    conductor.key("previous")
    conductor.key("next")
    conductor.key("stop")
    conductor.key("play-pause")
    conductor.release("bravo")
    assert names(events) == [
        "request",
        "play",
        "key",
        "key",
        "key",
        "mismatch",
        "play",
        "key",
        "release",
    ]


def test_unknown_key_is_refused(env):
    conductor, _, _, _ = env
    with pytest.raises(ValueError):
        conductor.key("eject")
