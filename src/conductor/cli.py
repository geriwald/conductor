"""`conductor` — the command agents and media keys call, and the daemon's entry point."""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

from conductor.config import ROOT, load_config

TOKEN_PATH = ROOT / "youtube-music.token"
LOG_PATH = ROOT / "logs" / "events.jsonl"
KEY_NAMES = ("play-pause", "stop", "next", "previous")


class ClientError(Exception):
    pass


class Client:
    def __init__(self, port: int):
        self.base = f"http://127.0.0.1:{port}"

    def mood(self, requester: str, mood: str, reason: str, ttl: float | None = None):
        return self._post(
            "/mood", {"requester": requester, "mood": mood, "reason": reason, "ttl": ttl}
        )

    def release(self, requester: str):
        return self._post("/release", {"requester": requester})

    def key(self, name: str):
        return self._post("/key", {"name": name})

    def status(self) -> dict:
        return self._send(urllib.request.Request(self.base + "/status"))

    def _post(self, path: str, body: dict):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(req)

    def _send(self, req):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            raise ClientError(json.load(e).get("error", str(e))) from e
        except urllib.error.URLError as e:
            raise ClientError(f"conductor is not running on {self.base} ({e.reason})") from e


def parse_ttl(text: str) -> float:
    match = re.fullmatch(r"(\d+)([smh]?)", text.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"bad duration {text!r}: use 30s, 90m or 2h")
    value, unit = int(match[1]), match[2] or "m"
    return value * {"s": 1, "m": 60, "h": 3600}[unit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="conductor", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    mood = sub.add_parser("mood", help="ask for a mood")
    mood.add_argument("mood")
    mood.add_argument("--from", dest="requester", required=True, help="who asks (agent name)")
    mood.add_argument("--reason", required=True, help="why this mood, in a few words")
    mood.add_argument("--ttl", type=parse_ttl, help="how long the request lives (90m, 2h…)")

    release = sub.add_parser("release", help="withdraw a request")
    release.add_argument("--from", dest="requester", required=True)

    key = sub.add_parser("key", help="a media key was pressed")
    key.add_argument("name", choices=KEY_NAMES)

    sub.add_parser("status", help="who holds the music, which mood, what plays")
    sub.add_parser("serve", help="run the daemon")
    sub.add_parser("auth", help="get a token from the player (accept its dialog)")

    args = parser.parse_args(argv)
    config = load_config()

    if args.command == "serve":
        return _serve(config)
    if args.command == "auth":
        return _auth(config)

    client = Client(config.port)
    try:
        if args.command == "mood":
            result = client.mood(args.requester, args.mood, args.reason, args.ttl)
        elif args.command == "release":
            result = client.release(args.requester)
        elif args.command == "key":
            result = client.key(args.name)
        else:
            result = client.status()
    except ClientError as e:
        print(f"conductor: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _serve(config) -> int:
    from conductor.core import Conductor
    from conductor.eventlog import EventLog
    from conductor.server import serve
    from conductor.youtube_music import YouTubeMusic

    conductor = Conductor(
        YouTubeMusic.from_token_file(config.youtube_music_url, config.devtools_url, TOKEN_PATH),
        moods=config.moods,
        default_mood=config.default_mood,
        ranks=config.ranks,
        log=EventLog(LOG_PATH),
        request_ttl=config.request_ttl,
        override_ttl=config.override_ttl,
    )
    serve(conductor, config.port)
    return 0


def _auth(config) -> int:
    from conductor.youtube_music import request_token

    print("Accept the dialog in the YouTube Music window…", file=sys.stderr)
    token = request_token(config.youtube_music_url)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    print(f"token saved to {TOKEN_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
