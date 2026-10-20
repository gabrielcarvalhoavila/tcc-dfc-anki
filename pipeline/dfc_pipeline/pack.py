"""Empacota o banco de variantes que o add-on (v1) lê. Só entram variantes aprovadas."""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from .cards import Card
from .util import now_iso


def build_bank(
    cards: list[Card],
    generation: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    *,
    audit_report: Optional[dict[str, Any]] = None,
    exclude_types: tuple[str, ...] = (),
    allow_fake: bool = False,
) -> dict[str, Any]:
    gen = {r["note_id"]: r for r in generation}
    val = {v["variant_id"]: v for v in validation}
    rejected = set((audit_report or {}).get("rejected_variant_ids", []))
    excluded = set(exclude_types) | set((audit_report or {}).get("exclude_types", []))
    notes: dict[str, Any] = {}
    generators, judges = set(), set()
    for card in cards:
        g = gen.get(card.note_id)
        if not card.eligible or not g or g.get("error") or not g.get("conceptual"):
            continue
        if g["generator"]["model"] == "fake" and not allow_fake:
            raise ValueError("O banco contém saídas do modelo 'fake' (dry-run). Use --allow-fake só para testes.")
        if g.get("fields_hash") != card.fields_hash:
            continue  # a nota foi editada depois da geração
        variants = []
        for v in g["variants"]:
            ver = val.get(v["variant_id"])
            if not ver or not ver.get("auto_valid") or v["variant_id"] in rejected or v["type"] in excluded:
                continue
            variants.append({"id": v["variant_id"], "type": v["type"], "text": v["text"]})
            judges.add(ver.get("judge_model"))
        if not variants:
            continue
        sem_imagem_id = f"{card.note_id}-sem_imagem"
        if card.kind == "cloze" and card.images_html and "sem_imagem" not in excluded and sem_imagem_id not in rejected:
            variants.append({"id": sem_imagem_id, "type": "sem_imagem"})  # há variante válida feita só do texto: a imagem é ilustrativa
        generators.add(g["generator"]["model"])
        entry: dict[str, Any] = {"kind": card.kind, "ords": card.ords, "q_field": card.q_field, "fields_hash": card.fields_hash, "variants": variants}
        if card.kind == "cloze":
            entry["answers_html"] = card.answers_html
            if card.images_html:
                entry["images_html"] = card.images_html
        notes[str(card.note_id)] = entry
    return {
        "schema": 3,
        "generated_at": now_iso(),
        "generator_models": sorted(generators),
        "judge_models": sorted(j for j in judges if j),
        "excluded_types": sorted(excluded),
        "notes": notes,
    }


def write_bank(bank: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=1)
