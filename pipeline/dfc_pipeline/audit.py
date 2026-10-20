"""Auditoria humana (H1): planilha estratificada por tipo e cálculo da taxa de variantes válidas."""
from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from typing import Any, Optional

from .cards import Card

SHEET_COLUMNS = ["variant_id", "note_id", "type", "original_question", "expected_answer", "variant_text", "human_ok", "human_note"]
YES = {"y", "yes", "s", "sim", "1", "true", "ok"}
NO = {"n", "no", "nao", "não", "0", "false"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[Optional[float], Optional[float]]:
    if n == 0:
        return None, None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - adj) / denom, (centre + adj) / denom


def build_sheet(cards_by_id: dict[int, Card], validation: list[dict[str, Any]], n: int, seed: int, out_csv: str) -> int:
    pool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for v in validation:
        if v.get("auto_valid") and v["note_id"] in cards_by_id:
            pool[v["type"]].append(v)
    with_image = {v["note_id"] for v in validation if v.get("auto_valid") and cards_by_id.get(v["note_id"]) and cards_by_id[v["note_id"]].images_html}
    for note_id in sorted(with_image):  # sem_imagem não passa pelo LLM: entra na auditoria humana, que decide se a imagem era dispensável
        pool["sem_imagem"].append({"variant_id": f"{note_id}-sem_imagem", "note_id": note_id, "type": "sem_imagem", "text": "(a mesma ficha, sem a imagem)"})
    types = sorted(pool)
    if not types:
        raise ValueError("Nenhuma variante aprovada na validação automática.")
    rng = random.Random(seed)
    chosen: list[dict[str, Any]] = []
    for idx, t in enumerate(types):
        quota = n // len(types) + (1 if idx < n % len(types) else 0)
        items = sorted(pool[t], key=lambda r: r["variant_id"])
        chosen += rng.sample(items, min(quota, len(items)))
    if len(chosen) < n:
        taken = {r["variant_id"] for r in chosen}
        rest = sorted((r for t in types for r in pool[t] if r["variant_id"] not in taken), key=lambda r: r["variant_id"])
        chosen += rng.sample(rest, min(n - len(chosen), len(rest)))
    rng.shuffle(chosen)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(SHEET_COLUMNS)
        for r in chosen:
            c = cards_by_id[r["note_id"]]
            w.writerow([r["variant_id"], r["note_id"], r["type"], c.question_text, c.answer_text, r["text"], "", ""])
    return len(chosen)


def score_sheet(path: str, *, h1_min: float = 0.85, type_min: float = 0.70, min_n: int = 100, min_n_type: int = 5) -> dict[str, Any]:
    per_type: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # tipo -> [válidas, auditadas]
    rejected: list[str] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            mark = (row.get("human_ok") or "").strip().lower()
            if mark in YES:
                per_type[row["type"]][0] += 1
                per_type[row["type"]][1] += 1
            elif mark in NO:
                per_type[row["type"]][1] += 1
                rejected.append(row["variant_id"])
    valid = sum(v for v, _ in per_type.values())
    audited = sum(n for _, n in per_type.values())
    lo, hi = wilson(valid, audited)
    rate = valid / audited if audited else None
    types = {}
    exclude = []
    for t, (v, n) in sorted(per_type.items()):
        r = v / n if n else None
        types[t] = {"validas": v, "auditadas": n, "taxa": r}
        if n >= min_n_type and r is not None and r < type_min:
            exclude.append(t)
    return {
        "auditadas": audited,
        "validas": valid,
        "taxa": rate,
        "ic95_wilson": [lo, hi],
        "h1_limiar": h1_min,
        "h1_ok": (rate >= h1_min) if (rate is not None and audited >= min_n) else None,
        "amostra_minima": min_n,
        "por_tipo": types,
        "exclude_types": exclude,
        "rejected_variant_ids": rejected,
    }


def write_report(report: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
