"""Open a URL in the player's page over the Chrome DevTools protocol.

The player's API server can only fire and forget queue edits, which arrive out of
order and leave the player unable to skip; opening the album's page is the one
reliable way to start it (checked 2026-09-28).
"""

import json
import urllib.request

import websocket


def navigator(devtools_url: str):
    def navigate(url: str) -> None:
        with urllib.request.urlopen(f"{devtools_url}/json", timeout=5) as resp:
            targets = json.load(resp)
        page = next((t for t in targets if t["type"] == "page"), None)
        if page is None:
            raise RuntimeError(f"no page to drive at {devtools_url}")
        # Chromium refuses DevTools websockets that carry an Origin header it was not told about.
        ws = websocket.create_connection(
            page["webSocketDebuggerUrl"], timeout=10, suppress_origin=True
        )
        try:
            ws.send(json.dumps({"id": 1, "method": "Page.navigate", "params": {"url": url}}))
            reply = json.loads(ws.recv())
        finally:
            ws.close()
        if "error" in reply or reply.get("result", {}).get("errorText"):
            raise RuntimeError(f"could not open {url}: {reply}")

    return navigate
