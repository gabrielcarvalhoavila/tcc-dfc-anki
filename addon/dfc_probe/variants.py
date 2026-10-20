"""Banco de variantes e sorteio (protocolo 6.3). Sem imports do Anki, para testar fora dele."""
from __future__ import annotations

import datetime
import hashlib
import hmac
import html
import json
import random
import re
from dataclasses import dataclass
from typing import Any, Optional

PLACEHOLDER = "[...]"
VARIANT_PROBABILITY = 0.5
SUPPORTED_SCHEMAS = (1, 2, 3)
MAX_BLANKS = 3  # lacunas ocultas ao mesmo tempo no cartão Cloze (protocolo v1.2)
BLANK_RE = re.compile(r"\[\.\.\.\d*\]")
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"'&]+)["']""", re.I)


def sha1_short(text: str, n: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def fields_hash(fields: list[str]) -> str:
    """Mesmo cálculo do pipeline: SHA-1 dos campos, na ordem do tipo de nota, separados por \\x1f."""
    return sha1_short("\x1f".join(fields), 12)


def blank_markers(n: int) -> list[str]:
    """Marcadores das lacunas no texto da variante: `[...]` se há uma, `[...1]`, `[...2]`... se há várias."""
    return [PLACEHOLDER] if n == 1 else [f"[...{i}]" for i in range(1, n + 1)]


def usable_text(kind: str, text: str, blanks: int = 1) -> bool:
    """Texto que o add-on aceita mostrar: sem marcas de template e, em Cloze, cada marcador de lacuna exatamente uma vez."""
    if not text.strip() or "{{" in text or "}}" in text:
        return False
    if kind != "cloze":
        return True
    markers = blank_markers(blanks)
    return len(BLANK_RE.findall(text)) == len(markers) and all(text.count(m) == 1 for m in markers)


def _clean_entry(e: Any) -> Optional[dict[str, Any]]:
    if not isinstance(e, dict) or e.get("kind") not in ("basic", "cloze"):
        return None
    ords, fh = e.get("ords"), e.get("fields_hash")
    if not (isinstance(ords, list) and ords and all(isinstance(o, int) for o in ords) and isinstance(fh, str)):
        return None
    answers: list[str] = []
    images: list[str] = []
    if e["kind"] == "cloze":
        raw = e.get("answers_html")
        if raw is None and isinstance(e.get("answer_html"), str):  # schemas 1 e 2: uma lacuna
            raw = [e["answer_html"]]
        if not (isinstance(raw, list) and 1 <= len(raw) <= MAX_BLANKS and all(isinstance(a, str) and a for a in raw)):
            return None
        answers = raw
        imgs = e.get("images_html") or []
        if not (isinstance(imgs, list) and all(isinstance(i, str) and i for i in imgs)):
            return None
        images = imgs
    try:
        q_field = int(e.get("q_field", 0))
    except (TypeError, ValueError):
        return None
    variants = []
    for v in e.get("variants") or []:
        if not (isinstance(v, dict) and all(isinstance(v.get(k), str) and v[k] for k in ("id", "type"))):
            continue
        if v["type"] == "sem_imagem":  # sem texto: o add-on tira as imagens do campo; só faz sentido se há imagem
            if images:
                variants.append({"id": v["id"], "type": "sem_imagem"})
        elif isinstance(v.get("text"), str) and usable_text(e["kind"], v["text"], len(answers) or 1):
            variants.append({"id": v["id"], "type": v["type"], "text": v["text"]})
    if not variants:
        return None
    out: dict[str, Any] = {"kind": e["kind"], "ords": ords, "fields_hash": fh, "q_field": q_field, "variants": variants}
    if e["kind"] == "cloze":
        out["answers_html"] = answers
        out["images_html"] = images
    return out


class Bank:
    """Banco de variantes (saída do `pack`): só notas com ao menos uma variante utilizável."""

    def __init__(self, notes: dict[int, dict[str, Any]], meta: dict[str, Any], bank_hash: str, skipped: int = 0):
        self.notes, self.meta, self.hash, self.skipped = notes, meta, bank_hash, skipped

    @property
    def n_variants(self) -> int:
        return sum(len(e["variants"]) for e in self.notes.values())

    @property
    def is_fake(self) -> bool:
        """Banco gerado com o LLM falso do `--dry-run`: serve para testar a tela, nunca para a coleta."""
        return "fake" in (self.meta.get("generator_models") or [])

    def entry(self, note_id: Any) -> Optional[dict[str, Any]]:
        try:
            return self.notes.get(int(note_id))
        except (TypeError, ValueError):
            return None

    @classmethod
    def from_bytes(cls, raw: bytes) -> "Bank":
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"JSON inválido: {e}") from e
        if not isinstance(data, dict) or data.get("schema") not in SUPPORTED_SCHEMAS or not isinstance(data.get("notes"), dict):
            raise ValueError("não é um banco de variantes (esperado schema 1 ou 2)")
        notes: dict[int, dict[str, Any]] = {}
        skipped = 0
        for key, raw_entry in data["notes"].items():
            entry = _clean_entry(raw_entry)
            try:
                note_id = int(key)
            except ValueError:
                entry = None
            if entry is None:
                skipped += 1
                continue
            notes[note_id] = entry
        meta = {k: data.get(k) for k in ("generated_at", "generator_models", "judge_models", "excluded_types")}
        return cls(notes, meta, hashlib.sha1(raw).hexdigest()[:12], skipped)

    @classmethod
    def load(cls, path: str) -> "Bank":
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())


@dataclass
class Decision:
    arm: Optional[str]  # None (sem sorteio), "original" ou "variant"
    reason: str  # vira `draw_note` no evento
    variant: Optional[dict[str, Any]] = None
    seed: Optional[str] = None


def in_window(today: datetime.date, start: str, end: str) -> bool:
    try:
        return datetime.date.fromisoformat(start) <= today <= datetime.date.fromisoformat(end)
    except (TypeError, ValueError):
        return False


def draw_seed(salt: bytes, event_id: str) -> int:
    return int(hmac.new(salt, event_id.encode("utf-8"), hashlib.sha256).hexdigest()[:16], 16)


def pick_variant(entry: dict[str, Any], last_shown: list[str], rng: random.Random) -> dict[str, Any]:
    """Uma variante ainda não mostrada neste cartão; se todas já foram, qualquer uma menos a mais recente."""
    variants = entry["variants"]
    seen = set(last_shown)
    pool = [v for v in variants if v["id"] not in seen]
    if not pool:
        recent = last_shown[0] if last_shown else None
        pool = [v for v in variants if v["id"] != recent] or variants
    return rng.choice(pool)


def decide(
    entry: Optional[dict[str, Any]],
    *,
    card_ord: int,
    fields_hash_now: str,
    reps: Optional[int],
    same_day: Optional[int],
    draw_on: bool,
    window_ok: bool,
    last_shown: list[str],
    event_id: str,
    salt: bytes,
    bank_ok: bool = True,
) -> Decision:
    """Elegibilidade (protocolo 4.2, 5 e 6.3.1) e sorteio 50/50 com semente por evento."""
    if not draw_on:
        return Decision(None, "off")
    if not bank_ok:
        return Decision(None, "fake_bank")
    if not window_ok:
        return Decision(None, "outside_window")
    if entry is None:
        return Decision(None, "no_entry")
    if card_ord not in entry["ords"]:
        return Decision(None, "ord_mismatch")
    if fields_hash_now != entry["fields_hash"]:
        return Decision(None, "note_edited")
    if reps is None or reps < 1:
        return Decision(None, "reps0")
    if same_day is None:
        return Decision(None, "no_history")
    if same_day:
        return Decision(None, "same_day")
    seed = draw_seed(salt, event_id)
    rng = random.Random(seed)
    arm = "variant" if rng.random() < VARIANT_PROBABILITY else "original"
    variant = pick_variant(entry, last_shown, rng) if arm == "variant" else None
    return Decision(arm, "ok", variant, f"{seed:016x}")


def _esc(text: str) -> str:
    return html.escape(text, quote=True).replace("\r\n", "\n").replace("\n", "<br>")


def field_value(entry: dict[str, Any], variant: dict[str, Any], current_field: Optional[str] = None) -> tuple[str, list[str]]:
    """HTML do campo da pergunta com a variante, e os trechos que precisam aparecer na pergunta renderizada.

    `sem_imagem` parte do campo atual da nota (`current_field`) e só tira as imagens; `pergunta` reescreve o texto e põe as imagens originais no topo.
    """
    if variant["type"] == "sem_imagem":
        return IMG_RE.sub("", current_field or ""), []
    text = variant["text"]
    if entry["kind"] != "cloze":
        return _esc(text), [_esc(text)]
    number = entry["ords"][0] + 1
    answers = entry["answers_html"]
    body = _esc(text)
    for marker, answer in zip(blank_markers(len(answers)), answers):
        body = body.replace(marker, "{{c%d::%s}}" % (number, answer), 1)
    images = entry.get("images_html") or []
    top = '<div style="text-align: center;">' + "".join(images) + "</div>" if images else ""
    pieces = [_esc(line).strip() for line in BLANK_RE.sub("\n", text).split("\n")]
    sources = [m.group(1) for img in images for m in [SRC_RE.search(img)] if m]
    return top + body, [p for p in pieces if p] + sources
