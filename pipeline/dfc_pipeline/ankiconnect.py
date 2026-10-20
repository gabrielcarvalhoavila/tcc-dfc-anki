"""Cliente mínimo do AnkiConnect (add-on 2055492159) em http://127.0.0.1:8765."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

URL = "http://127.0.0.1:8765"


class AnkiConnectError(RuntimeError):
    pass


def invoke(action: str, url: str = URL, timeout: int = 120, **params: Any) -> Any:
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(url, payload, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        raise AnkiConnectError(f"Sem resposta do AnkiConnect em {url}. O Anki está aberto? ({e})") from e
    if data.get("error"):
        raise AnkiConnectError(str(data["error"]))
    return data["result"]
