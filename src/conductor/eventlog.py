import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path


class EventLog:
    """Append-only JSON lines: the data the experiment is judged on."""

    def __init__(self, path: Path, clock: Callable[[], float] = time.time):
        self.path = path
        self.clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event: str, **fields) -> None:
        at = datetime.fromtimestamp(self.clock(), UTC).isoformat()
        line = json.dumps({"at": at, "event": event, **fields}, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
