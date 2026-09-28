"""Open a URL in the player's page over the Chrome DevTools protocol.

The player's API server can only fire and forget queue edits, which arrive out of
order and leave the player unable to skip; opening the album's page is the one
reliable way to start it (checked 2026-09-28).
"""

import json
import time
import urllib.request

import websocket

LOAD_TIMEOUT = 20

# YouTube Music renames the page on every track; this pins the window title until
# the next page load.
PIN_TITLE = """(() => {
  const want = %s;
  Object.defineProperty(document, 'title', {configurable: true, get: () => want, set: () => {}});
  const apply = () => {
    let t = document.querySelector('head > title');
    if (!t) { t = document.createElement('title'); document.head.appendChild(t); }
    if (t.textContent !== want) t.textContent = want;
  };
  apply();
  new MutationObserver(apply).observe(document.head, {subtree: true, childList: true, characterData: true});
})()"""


def navigator(devtools_url: str):
    def navigate(url: str, title: str) -> None:
        with urllib.request.urlopen(f"{devtools_url}/json", timeout=5) as resp:
            targets = json.load(resp)
        page = next((t for t in targets if t["type"] == "page"), None)
        if page is None:
            raise RuntimeError(f"no page to drive at {devtools_url}")
        # Chromium refuses DevTools websockets that carry an Origin header it was not told about.
        ws = websocket.create_connection(
            page["webSocketDebuggerUrl"], timeout=LOAD_TIMEOUT, suppress_origin=True
        )
        try:
            _command(ws, 1, "Page.enable")
            reply = _command(ws, 2, "Page.navigate", url=url)
            if reply.get("errorText"):
                raise RuntimeError(f"could not open {url}: {reply['errorText']}")
            _wait_for(ws, "Page.loadEventFired")
            _command(ws, 3, "Runtime.evaluate", expression=PIN_TITLE % json.dumps(title))
        finally:
            ws.close()

    return navigate


def _command(ws, id_: int, method: str, **params) -> dict:
    ws.send(json.dumps({"id": id_, "method": method, "params": params}))
    while True:
        message = json.loads(ws.recv())
        if message.get("id") == id_:
            if "error" in message:
                raise RuntimeError(f"{method}: {message['error']}")
            return message.get("result", {})


def _wait_for(ws, event: str) -> None:
    deadline = time.monotonic() + LOAD_TIMEOUT
    while time.monotonic() < deadline:
        if json.loads(ws.recv()).get("method") == event:
            return
    raise RuntimeError(f"the page did not finish loading ({event})")
