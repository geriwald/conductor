# Conductor

Let your AI agents choose your music, and answer them with your media keys.

Agents that organize your work know what they are about to put in front of
you: a hard review, a boring chore, a quiet stretch. Conductor lets each of
them ask for a *mood*, arbitrates between them, and plays matching albums
on YouTube Music. Your media keys become feedback: like, dislike, "wrong
music for right now", pause everything. Every reaction is logged, so you
can check whether the moods actually fit.

**Status: early experiment.** Nothing runs yet. The design is in
[`docs/specs/2026-09-28-conductor-design.md`](docs/specs/2026-09-28-conductor-design.md).

## How it will work

```bash
conductor mood chore --from bravo --reason "tax forms review"
conductor status
```

- Player: [th-ch/youtube-music](https://github.com/th-ch/youtube-music) with
  its API server plugin, bound to `127.0.0.1`.
- Moods: a few YouTube Music albums each, then their radio, defined in
  `config.toml` at the root of your checkout (gitignored; start from
  `config.example.toml`).
- Keys: GNOME media keys rebound to `conductor key <name>`.

Contributions and ideas are welcome: open an issue.
