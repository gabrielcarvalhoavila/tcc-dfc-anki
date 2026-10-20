"""Leitura de notas do Anki e regras de elegibilidade estrutural (protocolo, seção 4.2)."""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .util import sha1_short

MEDIA_RE = re.compile(
    r"<img\b|<audio\b|<video\b|<object\b|<embed\b|<svg\b|<math\b|<anki-mathjax|"
    r"\[sound:|\[latex\]|\[\$\$?\]|\\\(|\\\[",
    re.I,
)
CLOZE_RE = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.S)
NUMERIC_ANSWER_RE = re.compile(r"^[\d\s.,:/\-+()%]+$")
UNSUPPORTED_MODEL_HINTS = ("type in", "type-in", "digit", "occlusion", "oclus")
PLACEHOLDER = "[...]"


def strip_html(s: str) -> str:
    s = re.sub(r"<\s*br\s*/?>", "\n", s or "", flags=re.I)
    s = re.sub(r"</\s*(div|p|li|tr|h\d)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def normalize_fields(fields: dict[str, Any]) -> list[tuple[str, str]]:
    """AnkiConnect: {nome: {"value", "order"}}. Exportação do add-on: {nome: texto}. Devolve [(nome, valor)] em ordem."""
    items = []
    for name, v in fields.items():
        if isinstance(v, dict):
            items.append((v.get("order", len(items)), name, v.get("value", "")))
        else:
            items.append((len(items), name, v))
    items.sort(key=lambda t: t[0])
    return [(n, v) for _, n, v in items]


@dataclass
class Card:
    note_id: int
    model: str
    kind: str  # "basic" | "cloze" | "unknown"
    ords: list[int]
    question_html: str
    answer_html: str
    question_text: str
    answer_text: str
    fields_hash: str
    tags: list[str] = field(default_factory=list)
    decks: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return not self.reasons

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Card":
        return cls(**d)

    @property
    def suspect_by_history(self) -> bool:
        """Estrato de suspeito do protocolo (seção 5), só pelo que o export traz: reps >= 5 e lapses = 0."""
        return (self.stats.get("reps") or 0) >= 5 and (self.stats.get("lapses") or 0) == 0


def parse_note(rec: dict[str, Any]) -> Card:
    note_id = int(rec.get("noteId") or rec.get("note_id"))
    model = rec.get("modelName") or rec.get("model") or ""
    fields = normalize_fields(rec.get("fields") or {})
    fields_hash = sha1_short("\x1f".join(v for _, v in fields), 12)
    reasons: list[str] = []
    if any(h in model.lower() for h in UNSUPPORTED_MODEL_HINTS):
        reasons.append("model_not_supported")

    hits = [(i, m) for i, (_, v) in enumerate(fields) for m in CLOZE_RE.finditer(v)]
    kind, ords = "unknown", [0]
    q_html = a_html = ""
    if hits:
        kind = "cloze"
        if len(hits) != 1:
            reasons.append("multi_cloze")
        i, m = hits[0]
        text = fields[i][1]
        q_html = text[: m.start()] + PLACEHOLDER + text[m.end():]
        a_html = m.group(2)
        ords = [int(m.group(1)) - 1]
    elif len(fields) >= 2:
        kind = "basic"
        q_html, a_html = fields[0][1], fields[1][1]
    else:
        reasons.append("no_fields")

    q_text, a_text = strip_html(q_html), strip_html(a_html)
    if not q_text.replace(PLACEHOLDER, "").strip():
        reasons.append("empty_question")
    if not a_text:
        reasons.append("empty_answer")
    if MEDIA_RE.search(q_html) or MEDIA_RE.search(a_html):
        reasons.append("media_or_latex")
    if a_text and NUMERIC_ANSWER_RE.match(a_text):
        reasons.append("numeric_answer")

    return Card(
        note_id=note_id,
        model=model,
        kind=kind,
        ords=ords,
        question_html=q_html,
        answer_html=a_html,
        question_text=q_text,
        answer_text=a_text,
        fields_hash=fields_hash,
        tags=list(rec.get("tags") or []),
        decks=list(rec.get("decks") or []),
        stats=dict(rec.get("stats") or {}),
        reasons=reasons,
    )


def summarize(cards: list[Card]) -> dict[str, Any]:
    """Contagens por baralho e motivos de inelegibilidade, para planejar a coleta."""
    by_deck: dict[str, dict[str, int]] = {}
    reasons: dict[str, int] = {}
    for c in cards:
        deck = c.decks[0] if c.decks else "(sem baralho)"
        d = by_deck.setdefault(deck, {"notas": 0, "elegiveis": 0, "elegiveis_suspeitos": 0})
        d["notas"] += 1
        if c.eligible:
            d["elegiveis"] += 1
            if c.suspect_by_history:
                d["elegiveis_suspeitos"] += 1
        for r in c.reasons:
            reasons[r] = reasons.get(r, 0) + 1
    return {"por_baralho": by_deck, "motivos": reasons}
