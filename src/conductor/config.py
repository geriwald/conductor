import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = ROOT / "config.toml"


@dataclass(frozen=True)
class Config:
    moods: dict[str, list[str]]
    default_mood: str
    ranks: list[str]
    request_ttl: float
    override_ttl: float
    port: int
    youtube_music_url: str
    devtools_url: str


def load_config(path: Path = DEFAULT_PATH) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    moods = {name: list(albums) for name, albums in raw.get("moods", {}).items()}
    for name, albums in moods.items():
        if not albums:
            raise ValueError(f"mood {name!r} lists no album")
    default_mood = raw.get("default_mood", "calm")
    if default_mood not in moods:
        raise ValueError(f"default mood {default_mood!r} is not among the moods {sorted(moods)}")
    return Config(
        moods=moods,
        default_mood=default_mood,
        ranks=list(raw.get("ranks", [])),
        request_ttl=raw.get("request_ttl_minutes", 90) * 60,
        override_ttl=raw.get("override_minutes", 60) * 60,
        port=raw.get("server", {}).get("port", 7117),
        youtube_music_url=raw.get("youtube_music", {}).get("url", "http://127.0.0.1:26538"),
        devtools_url=raw.get("youtube_music", {}).get("devtools", "http://127.0.0.1:9333"),
    )
