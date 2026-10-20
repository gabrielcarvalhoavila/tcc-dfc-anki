"""Geração das variantes por LLM (protocolo, seção 6.1). Retomável: pula notas já geradas."""
from __future__ import annotations

import time
from collections import Counter
from typing import Any, Callable

from .cards import Card
from .llm import LLMError, parse_json_loose
from .prompts import GEN_PROMPT_VERSION, VARIANT_TYPES, build_generation_messages
from .util import append_jsonl, as_bool, now_iso, read_jsonl, sha1_short, write_jsonl


def clean_variants(card: Card, raw: Any) -> list[dict[str, str]]:
    """Mantém no máximo uma variante por tipo conhecido do tipo de cartão, com texto não vazio."""
    allowed = VARIANT_TYPES.get(card.kind, ())
    seen: dict[str, str] = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        t = str(item.get("type", "")).strip().lower()
        text = str(item.get("text", "")).strip()
        if t in allowed and text and t not in seen:
            seen[t] = text
    return [{"variant_id": f"{card.note_id}-{t}-{sha1_short(text, 6)}", "type": t, "text": text} for t, text in seen.items()]


def generate_one(card: Card, client: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "model": getattr(client, "model", "desconhecido"),
        "prompt_version": GEN_PROMPT_VERSION,
        "temperature": getattr(client, "temperature", None),
        "ts": now_iso(),
    }
    rec: dict[str, Any] = {
        "note_id": card.note_id,
        "fields_hash": card.fields_hash,
        "kind": card.kind,
        "conceptual": None,
        "reason": "",
        "variants": [],
        "generator": meta,
        "error": None,
    }
    try:
        resp = client.chat(build_generation_messages(card))
        data = parse_json_loose(resp["text"])
    except (LLMError, ValueError) as e:
        rec["error"] = str(e)[:300]
        return rec
    meta["usage"] = resp.get("usage")
    rec["conceptual"] = as_bool(data.get("conceptual"))
    rec["reason"] = str(data.get("reason", ""))[:300]
    if rec["conceptual"]:
        rec["variants"] = clean_variants(card, data.get("variants"))
        if not rec["variants"]:
            rec["error"] = "no_valid_variants"
    return rec


def generate(
    cards: list[Card],
    client: Any,
    out_path: str,
    *,
    limit: int | None = None,
    delay: float = 0.0,
    retry_errors: bool = False,
    log: Callable[[str], None] = print,
) -> Counter:
    existing = {r["note_id"]: r for r in read_jsonl(out_path)}
    if retry_errors:
        existing = {k: r for k, r in existing.items() if not r.get("error")}
        write_jsonl(out_path, existing.values())
    todo = [c for c in cards if c.eligible and c.note_id not in existing]
    if limit is not None:
        todo = todo[:limit]
    stats: Counter = Counter()
    for i, card in enumerate(todo, 1):
        rec = generate_one(card, client)
        append_jsonl(out_path, rec)
        if rec["error"]:
            stats["erro"] += 1
        elif rec["conceptual"]:
            stats["com_variantes"] += 1
        else:
            stats["nao_conceitual"] += 1
        if i % 10 == 0 or i == len(todo):
            log(f"  {i}/{len(todo)} {dict(stats)}")
        if delay:
            time.sleep(delay)
    return stats
