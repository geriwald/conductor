import threading

import pytest

from conductor.cli import Client, ClientError, parse_ttl
from conductor.core import Conductor
from conductor.server import make_server
from tests.test_conductor import MOODS, FakePlayer


@pytest.fixture
def client():
    player, events = FakePlayer(), []
    conductor = Conductor(
        player,
        moods=MOODS,
        default_mood="calm",
        ranks=["alpha", "bravo"],
        log=lambda event, **fields: events.append(event),
        choose=lambda albums: albums[0],
    )
    server = make_server(conductor, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield Client(server.server_address[1]), player
    server.shutdown()
    server.server_close()


def test_a_mood_request_goes_through_to_the_player(client):
    cli, player = client
    cli.mood("bravo", "chore", reason="tax forms", ttl=600)
    assert player.loaded() == ["chore album"]
    status = cli.status()
    assert status["holder"] == "bravo" and status["mood"] == "chore"


def test_keys_and_release_go_through(client):
    cli, player = client
    cli.mood("bravo", "chore", reason="tax forms")
    cli.key("previous")
    cli.release("bravo")
    assert ("like",) in player.calls
    assert cli.status()["requests"] == []


def test_a_bad_request_comes_back_as_an_error(client):
    cli, _ = client
    with pytest.raises(ClientError, match="polka"):
        cli.mood("bravo", "polka", reason="x")


@pytest.mark.parametrize(
    ("text", "seconds"), [("90m", 5400), ("2h", 7200), ("45", 2700), ("30s", 30)]
)
def test_ttl_accepts_seconds_minutes_and_hours(text, seconds):
    assert parse_ttl(text) == seconds
