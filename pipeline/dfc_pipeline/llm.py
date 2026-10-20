"""Cliente de LLM compatível com a API de chat da OpenAI (OpenRouter, Ollama etc.) e um substituto para testes."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional


class LLMError(RuntimeError):
    pass


class LLMClient:
    RETRY_STATUS = (408, 429, 500, 502, 503, 504)

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        model: str,
        temperature: float = 0.7,
        timeout: int = 120,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
        json_mode: bool = False,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.json_mode = json_mode

    def chat(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
        }
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        data = json.dumps(body).encode("utf-8")
        last_error = "erro desconhecido"
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(f"{self.base_url}/chat/completions", data, headers)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.load(resp)
                text = payload["choices"][0]["message"]["content"]
                return {"text": text or "", "usage": payload.get("usage"), "model": payload.get("model", self.model)}
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                retry_after = e.headers.get("Retry-After") if e.headers else None
                e.close()
                last_error = f"HTTP {e.code}: {detail}"
                if e.code not in self.RETRY_STATUS:
                    raise LLMError(last_error) from e
                wait = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(2**attempt, 30)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_error = f"rede: {e}"
                wait = min(2**attempt, 30)
            except (KeyError, IndexError, ValueError) as e:
                raise LLMError(f"resposta inesperada do servidor: {e}") from e
            if attempt < self.max_retries:
                self.sleep(wait)
        raise LLMError(f"falhou após {self.max_retries + 1} tentativas: {last_error}")


def parse_json_loose(text: str) -> dict[str, Any]:
    """Extrai um objeto JSON de uma resposta que pode vir com cercas de código ou texto em volta."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("sem objeto JSON na resposta")
    try:
        obj = json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON inválido: {e}") from e
    if not isinstance(obj, dict):
        raise ValueError("JSON não é um objeto")
    return obj


def _default_responder(messages: list[dict[str, str]]) -> str:
    system = messages[0]["content"].lower()
    user = json.loads(messages[-1]["content"])
    if "gera variantes" in system:
        if user.get("kind") == "cloze":
            marks = [b["marker"] for b in user["blanks"]]
            texts = {
                "paraphrase": "Em outras palavras: " + " e ".join(marks),
                "reorder": "Em outra ordem: " + " e ".join(reversed(marks)),
                "cue_swap": "Outras pistas iniciais: " + " e ".join(marks),
                "pergunta": "Reformulação em forma de pergunta? " + " e ".join(marks),
            }
            variants = [{"type": t, "text": x} for t, x in texts.items()]
            return json.dumps({"conceptual": True, "reason": "fake", "variants": variants})
        q = user["question"]
        variants = [
            {"type": t, "text": f"Reformulação do tipo {t} desta pergunta: " + " ".join(reversed(q.split()))}
            for t in ("paraphrase", "reorder", "reformat", "cue_swap")
        ]
        return json.dumps({"conceptual": True, "reason": "fake", "variants": variants})
    return json.dumps(
        {"answer_preserved": True, "ambiguous": False, "leaks_answer": False, "same_language": True, "same_question": True, "comment": "fake"}
    )


class FakeLLM:
    """Substituto determinístico para testes e --dry-run. Os resultados NÃO servem para o estudo."""

    model = "fake"
    temperature = 0.0

    def __init__(self, responder: Optional[Callable[[list[dict[str, str]]], str]] = None):
        self.responder = responder or _default_responder
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> dict[str, Any]:
        self.calls.append(messages)
        return {"text": self.responder(messages), "usage": None, "model": "fake"}
