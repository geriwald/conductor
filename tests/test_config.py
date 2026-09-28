import json
from pathlib import Path

import pytest

from conductor.config import load_config
from conductor.eventlog import EventLog

ROOT = Path(__file__).resolve().parent.parent


def test_the_example_config_loads():
    config = load_config(ROOT / "config.example.toml")
    assert config.default_mood in config.moods
    assert all(config.moods.values())
    assert config.request_ttl == 90 * 60
    assert config.override_ttl == 60 * 60


def test_a_default_mood_outside_the_moods_is_refused(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('default_mood = "polka"\n[moods]\ncalm = ["an album"]\n')
    with pytest.raises(ValueError, match="polka"):
        load_config(path)


def test_a_mood_without_albums_is_refused(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('default_mood = "calm"\n[moods]\ncalm = []\n')
    with pytest.raises(ValueError, match="calm"):
        load_config(path)


def test_the_event_log_appends_one_json_line_per_event(tmp_path):
    log = EventLog(tmp_path / "logs" / "events.jsonl", clock=lambda: 0.0)
    log("request", requester="bravo", mood="chore")
    log("key", key="next")
    lines = (tmp_path / "logs" / "events.jsonl").read_text().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["request", "key"]
    assert json.loads(lines[0])["at"] == "1970-01-01T00:00:00+00:00"
