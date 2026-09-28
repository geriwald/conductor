"""Arbitration between agents' mood requests, and what the listener's keys mean."""

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple, Protocol

KEYS = ("play-pause", "stop", "next", "previous")
DEFAULT_TTL = 90 * 60
OVERRIDE_TTL = 60 * 60
LISTENER = "listener"


class Track(NamedTuple):
    video_id: str
    title: str
    artist: str
    album: str | None = None
    is_paused: bool = False


class Player(Protocol):
    def load(self, album: str) -> None:
        """Replace the queue with the album, then its radio, and start playing."""

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def next(self) -> None: ...
    def like(self) -> None: ...
    def dislike(self) -> None: ...
    def now_playing(self) -> Track | None: ...


@dataclass
class Request:
    requester: str
    mood: str
    reason: str
    at: float
    expires_at: float


class Conductor:
    def __init__(
        self,
        player: Player,
        *,
        moods: dict[str, list[str]],
        default_mood: str,
        ranks: list[str],
        log: Callable[..., None],
        clock: Callable[[], float] = time.time,
        choose: Callable[[list[str]], str] = random.choice,
        override_ttl: float = OVERRIDE_TTL,
    ):
        if default_mood not in moods:
            raise ValueError(f"default mood {default_mood!r} is not among the moods")
        self.player = player
        self.moods = moods
        self.default_mood = default_mood
        self.ranks = ranks
        self.log = log
        self.clock = clock
        self.choose = choose
        self.override_ttl = override_ttl

        self.requests: dict[str, Request] = {}
        self.override: Request | None = None
        self.current_mood: str | None = None
        self.locked = False
        self.last_track_id: str | None = None

    # --- agents -----------------------------------------------------------

    def request(self, requester: str, mood: str, reason: str, ttl: float = DEFAULT_TTL) -> None:
        if mood not in self.moods:
            raise ValueError(f"unknown mood {mood!r}, expected one of {sorted(self.moods)}")
        now = self.clock()
        self.requests[requester] = Request(requester, mood, reason, now, now + ttl)
        self.log("request", requester=requester, mood=mood, reason=reason, ttl=ttl)
        self._start_if_idle()

    def release(self, requester: str) -> None:
        if self.requests.pop(requester, None) is not None:
            self.log("release", requester=requester)

    # --- the listener -----------------------------------------------------

    def key(self, name: str) -> None:
        if name not in KEYS:
            raise ValueError(f"unknown key {name!r}, expected one of {KEYS}")
        track = self.player.now_playing()
        self.log("key", key=name, mood=self.current_mood, **_track_fields(track))

        if name == "play-pause":
            if track is not None and not track.is_paused:
                self.player.pause()
                self.locked = True
                return
            self.locked = False
            mood, holder = self._target()
            if mood == self.current_mood and track is not None:
                self.player.play()
            else:
                self._start(mood, holder)
        elif track is None:
            return
        elif name == "next":
            self.player.dislike()
            self.player.next()
        elif name == "previous":
            self.player.like()
        elif name == "stop":
            _, holder = self._target()
            held = self.requests.get(holder) if holder else None
            self.log(
                "mismatch",
                mood=self.current_mood,
                holder=holder,
                reason=held.reason if held else None,
                **_track_fields(track),
            )
            mood = self._mood_after(self.current_mood)
            now = self.clock()
            self.override = Request(LISTENER, mood, "stop key", now, now + self.override_ttl)
            self.locked = False
            self._start(mood, LISTENER)

    # --- time -------------------------------------------------------------

    def tick(self) -> None:
        """Expire requests, and change the mood when a track ends. Call every few seconds."""
        now = self.clock()
        for requester, req in list(self.requests.items()):
            if req.expires_at <= now:
                del self.requests[requester]
                self.log("expire", requester=requester, mood=req.mood)
        if self.override and self.override.expires_at <= now:
            self.override = None

        if self.locked or self.current_mood is None:
            return
        track = self.player.now_playing()
        if track is None or track.video_id == self.last_track_id:
            return
        self.last_track_id = track.video_id
        mood, holder = self._target()
        if mood != self.current_mood:
            self._start(mood, holder)

    def status(self) -> dict:
        mood, holder = self._target()
        track = self.player.now_playing()
        return {
            "mood": self.current_mood,
            "target": mood,
            "holder": holder,
            "locked": self.locked,
            "override": self.override.mood if self.override else None,
            "requests": [
                {
                    "requester": r.requester,
                    "mood": r.mood,
                    "reason": r.reason,
                    "expires_in": round(r.expires_at - self.clock()),
                }
                for r in self.requests.values()
            ],
            "track": track._asdict() if track else None,
        }

    # --- internals --------------------------------------------------------

    def _target(self) -> tuple[str, str | None]:
        now = self.clock()
        if self.override and self.override.expires_at > now:
            return self.override.mood, LISTENER
        live = [r for r in self.requests.values() if r.expires_at > now]
        if not live:
            return self.default_mood, None

        def rank(r: Request) -> tuple[int, float]:
            ranked = self.ranks.index(r.requester) if r.requester in self.ranks else len(self.ranks)
            return ranked, -r.at

        winner = min(live, key=rank)
        return winner.mood, winner.requester

    def _start_if_idle(self) -> None:
        if self.current_mood is None and not self.locked:
            self._start(*self._target())

    def _start(self, mood: str, holder: str | None) -> None:
        album = self.choose(self.moods[mood])
        self.player.load(album)
        self.current_mood = mood
        track = self.player.now_playing()
        self.last_track_id = track.video_id if track else None
        held = self.requests.get(holder) if holder else None
        self.log(
            "play",
            mood=mood,
            holder=holder,
            reason=held.reason if held else None,
            album=album,
        )

    def _mood_after(self, mood: str | None) -> str:
        names = list(self.moods)
        if mood not in names:
            return self.default_mood
        return names[(names.index(mood) + 1) % len(names)]


def _track_fields(track: Track | None) -> dict:
    if track is None:
        return {}
    return {"video_id": track.video_id, "track": f"{track.artist} — {track.title}"}
