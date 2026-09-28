# Conductor

Let your AI agents choose your music, and answer them with your keyboard's media keys (play/pause, stop, next, previous).

Agents that organize your work know what they are about to put in front of
you: a hard review, a boring chore, a quiet stretch. Conductor lets each of
them ask for a *mood*, arbitrates between them, and plays matching music on
your streaming service. Your keyboard's media keys become feedback: like, dislike,
"wrong music for right now", pause everything. Every reaction is logged, so
you can check whether the moods actually fit.

**Status: early experiment.** Nothing runs yet. The design is in
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
  client through its API server plugin, bound to `127.0.0.1`.
- **Keys**: the first target is a Linux desktop with GNOME, whose keyboard media keys
  are rebound to `conductor key <name>`.

A backend for another service (Spotify, Deezer, Apple Music, a local
library…) or key handling for another desktop would be a welcome
contribution: open an issue first.
