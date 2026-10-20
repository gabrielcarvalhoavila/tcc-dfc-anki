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
NON_IMAGE_MEDIA_RE = re.compile(
    r"<audio\b|<video\b|<object\b|<embed\b|<svg\b|<math\b|<anki-mathjax|\[sound:|\[latex\]|\[\$\$?\]|\\\(|\\\[",
    re.I,
)
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
CLOZE_RE = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.S)
BLANK_RE = re.compile(r"\[\.\.\.\d*\]")
NUMERIC_ANSWER_RE = re.compile(r"^[\d\s.,:/\-+()%]+$")
UNSUPPORTED_MODEL_HINTS = ("type in", "type-in", "digit", "occlusion", "oclus")
PLACEHOLDER = "[...]"
MAX_BLANKS = 3  # lacunas ocultas ao mesmo tempo no cartão Cloze (protocolo v1.2)
MIN_CLOZE_TEXT = 30  # caracteres visíveis (sem lacunas nem imagens) para o Cloze admitir uma pergunta


def blank_markers(n: int) -> list[str]:
    """Marcadores das lacunas no texto: `[...]` se há uma, `[...1]`, `[...2]`... se há várias."""
    return [PLACEHOLDER] if n == 1 else [f"[...{i}]" for i in range(1, n + 1)]


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
    q_field: int = 0  # índice do campo que contém a pergunta (em Cloze, o da lacuna)
    blanks: int = 1  # lacunas ocultas ao mesmo tempo no cartão (Cloze: 1 a 3)
    answers_html: list[str] = field(default_factory=list)  # uma resposta por lacuna, na ordem dos marcadores
    answers_text: list[str] = field(default_factory=list)
    images_html: list[str] = field(default_factory=list)  # <img> do campo da lacuna (Cloze), mantidos nas variantes

    def __post_init__(self) -> None:
        if not self.answers_html:  # cards.jsonl gerado antes do v1.2
            self.answers_html = [self.answer_html]
            self.answers_text = [self.answer_text]

    @property
    def markers(self) -> list[str]:
        return blank_markers(self.blanks)

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

    cloze_fields = [(i, list(CLOZE_RE.finditer(v))) for i, (_, v) in enumerate(fields)]
    cloze_fields = [(i, hs) for i, hs in cloze_fields if hs]
    kind, ords = "unknown", [0]
    q_field = 0
    q_html = a_html = ""
    blanks = 1
    answers_html: list[str] = []
    images_html: list[str] = []
    if cloze_fields:
        kind = "cloze"
        q_field, hits = cloze_fields[0]
        number = int(hits[0].group(1))
        if len(cloze_fields) > 1 or any(int(m.group(1)) != number for m in hits):
            reasons.append("multi_cloze")  # vários cartões por nota
        own = [m for m in hits if int(m.group(1)) == number]  # lacunas ocultas neste cartão; as de outro número aparecem reveladas
        if len(own) > MAX_BLANKS:
            reasons.append("too_many_blanks")
        markers = blank_markers(len(own))
        text = fields[q_field][1]
        q_html, pos = "", 0
        for m in hits:
            q_html += text[pos : m.start()] + (markers[own.index(m)] if m in own else m.group(2))
            pos = m.end()
        q_html += text[pos:]
        blanks = len(own)
        answers_html = [m.group(2) for m in own]
        images_html = IMG_RE.findall(text)
        a_html = " | ".join(answers_html)
        ords = [number - 1]
    elif len(fields) >= 2:
        kind = "basic"
        q_html, a_html = fields[0][1], fields[1][1]
        answers_html = [a_html]
    else:
        reasons.append("no_fields")

    q_text = strip_html(IMG_RE.sub("", q_html) if kind == "cloze" else q_html)
    answers_text = [strip_html(a) for a in answers_html]
    a_text = answers_text[0] if len(answers_text) == 1 else " | ".join(f"{k}: {t}" for k, t in enumerate(answers_text, 1))
    visible = re.sub(r"\s+", " ", BLANK_RE.sub("", q_text)).strip()
    if not visible:
        reasons.append("empty_question")
    elif kind == "cloze" and len(visible) < MIN_CLOZE_TEXT:
        reasons.append("short_text")
    if not answers_text or any(not t for t in answers_text):
        reasons.append("empty_answer")
    if kind == "cloze":
        media = bool(NON_IMAGE_MEDIA_RE.search(q_html)) or any(MEDIA_RE.search(a) for a in answers_html)
    else:
        media = bool(MEDIA_RE.search(q_html) or MEDIA_RE.search(a_html))
    if media:
        reasons.append("media_or_latex")
    nonempty = [t for t in answers_text if t]
    if nonempty and all(NUMERIC_ANSWER_RE.match(t) for t in nonempty):
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
        q_field=q_field,
        blanks=blanks,
        answers_html=answers_html,
        answers_text=answers_text,
        images_html=images_html,
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
