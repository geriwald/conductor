# Conductor — AI agents choose your music, keyboard media keys answer back

Date: 2026-09-28
Status: draft
Scope: first experiment, Linux desktop with GNOME

## Problem

For many people, music drives concentration: the kind of music decides
which kind of task one can take on. Calm music for unwinding, fast music
under pressure, something grand to get through a chore.

When AI agents organize a person's work (long-running assistant sessions
that hand out tasks, review requests, chores), they know what they are
about to put in front of that person. Conductor lets them act on it: each
agent can ask for a *mood*, Conductor arbitrates between agents and plays
the music. The listener answers with the media keys of their keyboard (play/pause, stop, next, previous), which become a
feedback channel instead of plain transport controls, and every reaction
is logged so the heuristic can be judged against reality.

## Decisions

### D1. Player: a backend interface, YouTube Music first

Conductor is not tied to one streaming service. The daemon talks to the
player through a small backend interface (enqueue an album and its radio,
play, pause, next, like, dislike, current track), and the arbitration and
key logic never see which service is behind it. The first backend is
YouTube Music, because it is the main contributor's subscription.

The YouTube Music backend drives the open-source desktop client
[th-ch/youtube-music](https://github.com/th-ch/youtube-music) (Electron,
~33.6k stars, active), logged into the listener's YouTube Music account,
with its `api-server` plugin enabled. That plugin exposes what Conductor
needs (read from `src/plugins/api-server/backend/routes/control.ts` on
2026-09-28): `play`, `pause`, `toggle-play`, `next`, `previous`, `like`,
`dislike`, `like-state`, `song-info`, `queue` (get / add / clear),
`search`, `volume`, plus a websocket for state changes.

The plugin's default hostname is `0.0.0.0`; Conductor's setup instructions
require `127.0.0.1`.

The API server cannot start an album. Its queue edits are fire and
forget: each track is fetched on its own and lands out of order, setting
the queue index does not change the playing track, and after a queue clear
the player stops obeying `next` (all observed on 2026-09-28). So the
player is launched with `--remote-debugging-port=9333` (bound to
`127.0.0.1`), and Conductor starts an album by opening its page over the
DevTools protocol (`Page.navigate`). That is the only DevTools call: every
other action goes through the API server, and nothing scrapes YouTube
Music's DOM.

### D2. A local daemon and a CLI

Conductor is a Python package with two entry points:

- `conductor serve` — the daemon, run as a systemd user unit. It holds the
  requests, arbitrates, drives the player, and listens on `127.0.0.1`.
- `conductor <command>` — the CLI, a thin HTTP client of the daemon. It is
  what agents call from a shell tool.

### D3. Protocol: agents request a mood, never a track

```bash
conductor mood chore --from bravo --reason "tax forms review" [--ttl 90m]
conductor release --from bravo      # withdraw my request
conductor status                    # who holds the music, which mood, what plays
```

An agent says *why* (`--reason`) and *what kind* (the mood); it never
picks a track. The heuristic lives in one table the listener edits, and
agents do not fight over individual songs.

### D4. A mood is a set of albums, then their radio

Moods are defined in the listener's config file, `config.toml` at the
root of the checkout. It is gitignored: each listener's moods, albums and
agent ranks stay on their machine and never reach the repository.

Each mood lists a few albums of the listener's service. To play a mood,
Conductor picks one of its albums and has the backend start it; when the
album runs out, the service carries on with its own suggestions around
it, which stay close to the mood and bring new music in.

With YouTube Music, the backend finds the album with
[ytmusicapi](https://github.com/sigma67/ytmusicapi) (`search`, then
`get_album`; unauthenticated, it only reads the catalogue) and opens
`https://music.youtube.com/watch?v=<first track>&list=<audioPlaylistId>`
(see D1). The album plays in order, then YouTube Music's autoplay takes
over. That autoplay continuation has not been watched through to the end
of an album yet.

The repository ships `config.example.toml` with three illustrative moods
(`calm`, the default; `stress`; `chore`) and neutral example albums; a
listener copies it to `config.toml` and edits it.

### D5. Arbitration: the listener, then agents by configured rank

Each requester holds at most one live request, with a TTL (default 90 min).
The config file ranks requesters (for example `ranks = ["alpha", "bravo"]`).
The music follows the live request of the highest-ranked requester:

1. **The listener's keys** — always win (see D6).
2. Ranked requesters, in config order.
3. Any other requester, latest request first.

When the winning request expires or is released, the next one applies.
With no live request, the default mood plays. A mood change waits for the
end of the current track, except after a key press, which is immediate.

### D6. Media keys become feedback

The GNOME static media-key bindings are cleared and the media keys are
bound to `conductor key <name>` through GNOME custom shortcuts. The first
target is a keyboard with one play/pause toggle, stop, next and previous.

| key              | meaning for the listener          | Conductor action                                             |
|------------------|-----------------------------------|--------------------------------------------------------------|
| ⏭ next           | "I don't like this track"         | `dislike` + `next`, same mood                                |
| ⏮ previous       | "I like this track"               | `like`, the track keeps playing                              |
| ⏹ stop           | "wrong music for right now"       | record a mismatch for (mood, reason), switch to another mood |
| ⏯ while playing  | "stop everything" (a phone call…) | pause, and lock: no agent request can resume the music       |
| ⏯ while paused   | "find me the right music"         | lift the lock, re-run arbitration, play the result at once   |

The single play/pause key carries both meanings through the state it
finds. Agent requests received during the lock are recorded and apply when
it lifts. After a stop, the listener's override holds the new mood for 60
minutes; agent requests in that window are recorded, not applied.

Stop and next grade by how much they change: next changes the track, stop
changes the whole music. Whether they should be swapped is an open
question; the mapping is one table in the code.

Likes and dislikes also go to YouTube Music itself, so its recommendations
learn from the same gestures.

The play/pause key is deterministic and instant. Waking an LLM to choose
would mean ten to thirty seconds of silence; it can come later, fed by the
log.

### D7. Every event is logged: the log is the experiment

Each request, arbitration result, track change and key press is appended
to `logs/events.jsonl` in the checkout (gitignored, like the config) with its timestamp, requester,
mood, reason and current track. The stop / next / previous presses against
(mood, reason) measure whether the heuristic matches the listener.

## Acceptance criteria

1. `conductor mood chore --from bravo --reason test` makes a `chore` album
   play within 5 s when Conductor is idle (it has started nothing yet).
   The daemon never starts music on its own when it boots.
2. With `alpha` (ranked first) holding `stress` and `bravo` requesting
   `chore`, `stress` keeps playing; `conductor release --from alpha`
   switches to `chore` at the end of the current track.
3. With no live request, the play/pause key plays the default mood.
4. When the album runs out, its radio follows.
5. Play/pause while playing stops the sound within half a second, and a
   later `conductor mood …` from any agent does not resume it; play/pause
   again re-runs arbitration and plays.
6. Next dislikes the track and skips it; previous likes it and the track
   keeps playing; `song-info` confirms the like state.
7. Stop changes the mood and records a mismatch event.
8. Every action above leaves a line in `events.jsonl`.
9. Conductor logic (arbitration, TTL, locks, key semantics) is unit-tested
   against a fake player; the real client is only exercised by hand.

## Out of scope

- Other desktops and operating systems.
- Voice or chat control, MCP tools.
- An LLM choosing tracks, or learning from the log: this experiment only
  collects the data.
- Detecting the listener's state automatically (calendar, deadlines,
  heart rate).
- Teaching agents *when* to request which mood: that belongs to each
  agent setup's own instructions.
