"""Fontes de notas: AnkiConnect (Anki aberto) ou arquivo JSONL exportado pelo add-on (para outra pessoa)."""
from __future__ import annotations

import random
from typing import Any, Callable

from . import ankiconnect
from .util import read_jsonl


def from_ankiconnect(
    query: str,
    invoke: Callable[..., Any] = ankiconnect.invoke,
    batch: int = 100,
    log: Callable[[str], None] = print,
    limit: int | None = None,
    seed: int = 0,
) -> list[dict[str, Any]]:
    ids = invoke("findNotes", query=query)
    log(f"{len(ids)} notas encontradas")
    if limit is not None and len(ids) > limit:
        ids = sorted(random.Random(seed).sample(ids, limit))  # só o texto dessas notas sai do Anki
        log(f"lendo uma amostra de {len(ids)} (semente {seed})")
    records: list[dict[str, Any]] = []
    for i in range(0, len(ids), batch):
        infos = [n for n in invoke("notesInfo", notes=ids[i : i + batch]) if n]
        first = [n["cards"][0] for n in infos if n.get("cards")]
        cinfo = {c["cardId"]: c for c in invoke("cardsInfo", cards=first)} if first else {}
        for n in infos:
            c = cinfo.get(n["cards"][0]) if n.get("cards") else None
            if c:
                n["decks"] = [c.get("deckName", "")]
                n["stats"] = {
                    "card_id": c["cardId"],
                    "reps": c.get("reps"),
                    "lapses": c.get("lapses"),
                    "ivl": c.get("interval"),
                    "queue": c.get("queue"),
                }
            records.append(n)
        log(f"  {min(i + batch, len(ids))}/{len(ids)}")
    return records


def from_jsonl(path: str) -> list[dict[str, Any]]:
    return list(read_jsonl(path))
