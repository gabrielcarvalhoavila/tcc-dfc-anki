"""Cliente de LLM compatível com a API de chat da OpenAI (OpenRouter, Ollama etc.) e um substituto para testes."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Optional

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class LLMError(RuntimeError):
    pass


class ConfigError(ValueError):
    """Configuração do LLM ausente ou inválida; `missing` indica que falta a chave ou o modelo."""

    def __init__(self, message: str, missing: bool = False):
        super().__init__(message)
        self.missing = missing


class RunAborted(RuntimeError):
    """Falhas seguidas demais (crédito, chave ou rede): a rodada pára; o que já foi feito fica gravado e --retry-errors retoma."""


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
        extra_body: Optional[dict[str, Any]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep = sleep
        self.json_mode = json_mode
        self.extra_body = dict(extra_body or {})

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "User-Agent": "dfc-pipeline/1.0"}  # o padrão do urllib é recusado por alguns provedores
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def list_models(self) -> list[str]:
        req = urllib.request.Request(f"{self.base_url}/models", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            e.close()
            raise LLMError(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            raise LLMError(f"rede ou resposta inválida: {e}") from e
        return sorted(str(m.get("id", "")) for m in payload.get("data", []) if isinstance(m, dict))

    def chat(self, messages: list[dict[str, str]], temperature: Optional[float] = None) -> dict[str, Any]:
        # extra_body vem depois da temperatura (permite fixar 1.0 nos Gemini 3), mas nunca troca model e messages
        body: dict[str, Any] = {"temperature": self.temperature if temperature is None else temperature, **self.extra_body, "model": self.model, "messages": messages}
        if self.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = self._headers()
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


def read_env_file(path: str) -> dict[str, str]:
    """Lê um arquivo .env (CHAVE=valor, com ou sem BOM); sem arquivo, devolve {}. Em chave repetida vale a primeira."""
    values: dict[str, str] = {}
    if not path or not os.path.exists(path):
        return values
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return values


def client_from_env(role: str, env: Mapping[str, str]) -> LLMClient:
    """Cliente do gerador (`gen`) ou do juiz (`judge`) a partir das variáveis DFC_* do .env."""
    prefix = "DFC_GEN_" if role == "gen" else "DFC_JUDGE_"
    base = env.get("DFC_LLM_BASE_URL", DEFAULT_BASE_URL)
    key = env.get("DFC_LLM_API_KEY") or env.get("OPENROUTER_API_KEY")
    model = env.get(prefix + "MODEL")
    local = "localhost" in base or "127.0.0.1" in base
    if not model or (not key and not local):
        raise ConfigError(f"Defina DFC_LLM_API_KEY e {prefix}MODEL (veja .env.example)", missing=True)
    raw_extra = env.get(prefix + "EXTRA_BODY") or env.get("DFC_EXTRA_BODY")
    try:
        extra = json.loads(raw_extra) if raw_extra else None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{prefix}EXTRA_BODY não é um JSON válido: {e}") from e
    if extra is not None and not isinstance(extra, dict):
        raise ConfigError(f"{prefix}EXTRA_BODY deve ser um objeto JSON.")
    temperature = 0.7 if role == "gen" else 0.0
    return LLMClient(base, key, model, temperature=temperature, json_mode=env.get("DFC_JSON_MODE") == "1", extra_body=extra)


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
        {"answer_preserved": True, "ambiguous": False, "leaks_answer": False, "same_language": True, "same_question": True, "same_topic": True, "comment": "fake"}
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
