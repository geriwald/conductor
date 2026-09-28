<p align="center"><img src="logo/conductor.svg" width="128" alt="Conductor logo: a music note whose stem is a conductor's baton"></p>

# Conductor

Let your AI agents choose your music, and answer them with your keyboard's media keys (play/pause, stop, next, previous).

Agents that organize your work know what they are about to put in front of
you: a hard review, a boring chore, a quiet stretch. Conductor lets each of
them ask for a *mood*, arbitrates between them, and plays matching music on
your streaming service. Your keyboard's media keys become feedback: like, dislike,
"wrong music for right now", pause everything. Every reaction is logged, so
you can check whether the moods actually fit.

**Status: early experiment.** The daemon, the CLI and the YouTube Music backend
are written and unit-tested; they have not yet driven a real player. The design is in
[`docs/specs/2026-09-28-conductor-design.md`](docs/specs/2026-09-28-conductor-design.md).

## How it will work

```bash
conductor mood chore --from bravo --reason "tax forms review"
conductor status
```

- **Agents** request a mood, never a track. Any agent that can run a shell
  command can take part; you rank them in your config.
- **Moods** are yours to define: a few albums each, then the service's own
  radio around them, in `config.toml` at the root of your checkout
  (gitignored; start from `config.example.toml`).
- **Players** sit behind a small backend interface, so Conductor is not tied
  to one service. The first backend is YouTube Music, because it is the main
  contributor's subscription: it drives the
  [th-ch/youtube-music](https://github.com/th-ch/youtube-music) desktop
  client: its API server plugin (bound to `127.0.0.1`) for playback, and
  its DevTools port (`--remote-debugging-port=9333`) to open an album.
- **Keys**: the first target is a Linux desktop with GNOME, whose keyboard media keys
  are rebound to `conductor key <name>`.

## Setup (Linux, systemd)

1. Install the [th-ch/youtube-music](https://github.com/th-ch/youtube-music)
   AppImage, sign in, and enable *Plugins → API Server* with hostname
   `127.0.0.1`. Enable *Plugins → Video Toggle* too and switch it to
   *Song*, so official videos play as their audio version.
2. `uv venv && uv pip install -e .` in this checkout, then
   `cp config.example.toml config.toml` and pick your albums.
3. `.venv/bin/conductor auth`, and accept the dialog in the player.
4. `tools/install-systemd.sh /path/to/YouTube-Music.AppImage` starts the
   player (with its DevTools port) and the daemon with your desktop session.

A backend for another service (Spotify, Deezer, Apple Music, a local
library…) or key handling for another desktop would be a welcome
contribution: open an issue first.
