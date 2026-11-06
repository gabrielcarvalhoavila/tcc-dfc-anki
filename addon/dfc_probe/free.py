"""Variantes no uso livre (v0.5.0): o banco pessoal, os ajustes e a escolha da variante na revisão.

Nada aqui toca o estudo (protocolo 6.8): o banco oficial, a base de eventos e o CSV ficam como estão. Sem imports do Anki, para testar sem interface.
"""
from __future__ import annotations

import datetime
import json
import os
import random
import tempfile
import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

try:
    from . import variants
except ImportError:  # os testes carregam o módulo fora do pacote
    import variants  # type: ignore

ALL_TYPES = ("paraphrase", "reorder", "cue_swap", "pergunta", "sem_imagem", "reformat")
TYPE_LABELS = {
    "paraphrase": "Paráfrase (outras palavras)",
    "reorder": "Reordenação (outra ordem)",
    "cue_swap": "Pistas iniciais (outros rótulos)",
    "pergunta": "Em forma de pergunta",
    "sem_imagem": "Sem imagem",
    "reformat": "Outro formato (cartão básico)",
}
SHORT_LABELS = {"paraphrase": "paráfrase", "reorder": "reordenação", "cue_swap": "pistas iniciais", "pergunta": "pergunta", "sem_imagem": "sem imagem", "reformat": "outro formato"}
SHOWN_MEMORY = 6  # variantes lembradas por nota para não repetir em sequência
SUSPECT_REPS = 5  # mesma definição de suspeito do estudo (protocolo 5)
SUSPECT_LAST_EASE = 3
USD_PER_NOTE = 0.003  # gerador + juiz com os modelos padrão (piloto de 21/10: ≈ US$ 0,0016 + 4 x US$ 0,00035)


@dataclass
class Settings:
    enabled: bool = False
    probability: int = 50
    types: list[str] = field(default_factory=lambda: list(ALL_TYPES))
    deck_ids: Optional[list[int]] = None  # None: todos os baralhos
    include_learning: bool = False
    suspects_only: bool = False
    avoid_repeat: bool = True
    avoid_same_day: bool = True
    badge: bool = False

    @classmethod
    def from_raw(cls, raw: Any) -> "Settings":
        s = cls()
        if not isinstance(raw, dict):
            return s
        for name in ("enabled", "include_learning", "suspects_only", "avoid_repeat", "avoid_same_day", "badge"):
            if name in raw:
                setattr(s, name, bool(raw[name]))
        try:
            s.probability = max(0, min(100, int(raw.get("probability", s.probability))))
        except (TypeError, ValueError):
            pass
        if isinstance(raw.get("types"), list):
            s.types = [t for i, t in enumerate(raw["types"]) if t in ALL_TYPES and t not in raw["types"][:i]]
        if isinstance(raw.get("deck_ids"), list):
            s.deck_ids = [i for i in raw["deck_ids"] if isinstance(i, int) and not isinstance(i, bool)]
        return s

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled, "probability": self.probability, "types": list(self.types), "deck_ids": None if self.deck_ids is None else list(self.deck_ids),
            "include_learning": self.include_learning, "suspects_only": self.suspects_only, "avoid_repeat": self.avoid_repeat, "avoid_same_day": self.avoid_same_day, "badge": self.badge,
        }


def card_allowed(settings: Settings, facts: dict[str, Any], deck_scope: Optional[set[int]]) -> bool:
    """O cartão pode receber variante agora? `facts` vem do estado do cartão antes da resposta (o mesmo que o estudo registra)."""
    reps = facts.get("reps") or 0
    if reps < 1 or facts.get("card_type") not in ((1, 2, 3) if settings.include_learning else (2,)):
        return False
    if deck_scope is not None and facts.get("deck_id") not in deck_scope:
        return False
    if settings.avoid_same_day and facts.get("same_day"):
        return False
    if settings.suspects_only:
        last = facts.get("last_ease")
        return reps >= SUSPECT_REPS and (facts.get("lapses") or 0) == 0 and last is not None and last >= SUSPECT_LAST_EASE
    return True


def roll(settings: Settings, rng: random.Random) -> bool:
    return rng.random() * 100 < settings.probability


def eligible_variants(entry: dict[str, Any], settings: Settings, banned: Iterable[str] = ()) -> list[dict[str, Any]]:
    banned = set(banned)
    return [v for v in entry.get("variants", []) if v["type"] in settings.types and v["id"] not in banned]


def pick_variant(entry: dict[str, Any], settings: Settings, banned: Iterable[str], recent: list[str], rng: random.Random) -> Optional[dict[str, Any]]:
    """Uma variante dos tipos escolhidos; com `avoid_repeat`, uma ainda não mostrada (se todas foram, qualquer uma menos a mais recente)."""
    pool = eligible_variants(entry, settings, banned)
    if settings.avoid_repeat and len(pool) > 1:
        fresh = [v for v in pool if v["id"] not in recent]
        pool = fresh or [v for v in pool if v["id"] != (recent[0] if recent else None)] or pool
    return rng.choice(pool) if pool else None


def entry_from_result(result: dict[str, Any], types: Optional[Iterable[str]] = None, only_ids: Optional[Iterable[str]] = None) -> Optional[dict[str, Any]]:
    """Entrada do banco com as variantes aprovadas de `live.generate_variants` (`types` e `only_ids` restringem).

    A `sem_imagem` entra, com as imagens do cartão, se algum texto foi aprovado (a imagem é ilustrativa), como no `pack`.
    """
    note_id, base = result["note_id"], result["entry"]
    wanted = set(types) if types is not None else None
    ids = set(only_ids) if only_ids is not None else None
    chosen: list[dict[str, Any]] = []
    approved = False
    for v in result["variants"]:
        vid = v.get("id") or variant_id(note_id, v["type"], v["text"])
        approved = approved or bool(v["valid"])
        if v["valid"] and (wanted is None or v["type"] in wanted) and (ids is None or vid in ids):
            chosen.append({"id": vid, "type": v["type"], "text": v["text"]})
    if base["kind"] == "cloze" and base["images_html"] and approved and (wanted is None or "sem_imagem" in wanted):
        sid = f"{note_id}-sem_imagem"
        if ids is None or sid in ids:
            chosen.append({"id": sid, "type": "sem_imagem"})
    if not chosen:
        return None
    entry: dict[str, Any] = {"kind": base["kind"], "ords": list(base["ords"]), "q_field": base["q_field"], "fields_hash": result["fields_hash"], "variants": chosen}
    if base["kind"] == "cloze":
        entry["answers_html"] = list(base["answers_html"])
        if base["images_html"]:
            entry["images_html"] = list(base["images_html"])
    return entry


def variant_id(note_id: Any, vtype: str, text: str) -> str:
    return f"{note_id}-{vtype}-{variants.sha1_short(text, 6)}"


def merge_entries(old: Optional[dict[str, Any]], new: dict[str, Any]) -> dict[str, Any]:
    """Soma as variantes novas às que a nota já tem, se o texto da nota não mudou; senão, fica só a entrada nova."""
    if not old or old["fields_hash"] != new["fields_hash"]:
        return new
    have = {v["id"] for v in old["variants"]}
    return {**new, "variants": list(old["variants"]) + [v for v in new["variants"] if v["id"] not in have]}


def describe_bank(bank: "FreeBank") -> str:
    st = bank.stats()
    kinds = ", ".join(f"{SHORT_LABELS.get(t, t)} {n}" for t, n in sorted(st["by_type"].items(), key=lambda kv: -kv[1]))
    lines = [f"Notas com variantes: {st['notes']}", f"Variantes: {st['variants']}" + (f" ({kinds})" if kinds else "")]
    if st["skipped"]:
        lines.append(f"Avaliadas sem variantes (não conceituais ou sem variante aprovada): {st['skipped']}")
    if st["banned"]:
        lines.append(f"Variantes que você marcou como ruins (não voltam): {st['banned']}")
    lines.append(f"Arquivo: {bank.path}")
    return "\n".join(lines)


class FreeBank:
    """Banco pessoal: JSON no formato do banco do estudo (schema 3) mais um bloco `free` com o que só o uso livre precisa."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.notes: dict[int, dict[str, Any]] = {}
        self.skipped: dict[str, dict[str, Any]] = {}  # notas sem variante e por quê (para não pagar de novo)
        self.banned: set[str] = set()
        self.shown: dict[str, list[str]] = {}
        self.generator_models: set[str] = set()
        self.judge_models: set[str] = set()
        self._dirty = False
        self.load()

    def load(self) -> None:
        with self._lock:
            if not os.path.exists(self.path):
                return
            try:
                with open(self.path, "rb") as f:
                    raw = f.read()
                data = json.loads(raw.decode("utf-8"))
                bank = variants.Bank.from_bytes(raw)
            except (OSError, ValueError):
                os.replace(self.path, f"{self.path}.corrompido-{datetime.datetime.now():%Y%m%d-%H%M%S}")  # guarda o arquivo ruim em vez de apagá-lo
                return
            self.notes = dict(bank.notes)
            extra = data.get("free") if isinstance(data.get("free"), dict) else {}
            self.skipped = {str(k): v for k, v in (extra.get("skipped") or {}).items() if isinstance(v, dict)}
            self.banned = {str(x) for x in extra.get("banned") or []}
            self.shown = {str(k): [str(x) for x in v] for k, v in (extra.get("shown") or {}).items() if isinstance(v, list)}
            self.generator_models = set(data.get("generator_models") or [])
            self.judge_models = set(data.get("judge_models") or [])

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            payload = {
                "schema": 3,
                "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "generator_models": sorted(self.generator_models),
                "judge_models": sorted(self.judge_models),
                "excluded_types": [],
                "notes": {str(k): v for k, v in self.notes.items()},
                "free": {"skipped": self.skipped, "banned": sorted(self.banned), "shown": self.shown},
            }
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.path)), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
                os.replace(tmp, self.path)
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
            self._dirty = False

    def entry(self, note_id: Any) -> Optional[dict[str, Any]]:
        with self._lock:
            try:
                return self.notes.get(int(note_id))
            except (TypeError, ValueError):
                return None

    def has_current(self, note_id: Any, fields_hash: str) -> bool:
        e = self.entry(note_id)
        return bool(e) and e["fields_hash"] == fields_hash

    def is_skipped(self, note_id: Any, fields_hash: str) -> bool:
        with self._lock:
            s = self.skipped.get(str(note_id))
            return bool(s) and s.get("fields_hash") == fields_hash

    def set_entry(self, note_id: Any, entry: dict[str, Any], gen_model: str = "", judge_model: str = "") -> bool:
        """Guarda a entrada se o formato for válido; devolve se guardou."""
        with self._lock:
            cleaned = variants._clean_entry(entry)
            if cleaned is None:
                return False
            self.notes[int(note_id)] = cleaned
            self.skipped.pop(str(note_id), None)
            self.generator_models.update(m for m in (gen_model,) if m)
            self.judge_models.update(m for m in (judge_model,) if m)
            self._dirty = True
            return True

    def skip(self, note_id: Any, fields_hash: str, reason: str) -> None:
        with self._lock:
            self.skipped[str(note_id)] = {"fields_hash": fields_hash, "reason": reason, "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            self._dirty = True

    def ban(self, variant_id_: str) -> None:
        """Tira a variante do banco para sempre (o texto gerado de novo teria outro id, mas a mesma não volta)."""
        with self._lock:
            self.banned.add(variant_id_)
            for nid, e in list(self.notes.items()):
                left = [v for v in e["variants"] if v["id"] != variant_id_]
                if len(left) != len(e["variants"]):
                    if any(v["type"] != "sem_imagem" for v in left):
                        e["variants"] = left
                    else:
                        del self.notes[nid]  # só sobraria a sem_imagem, que depende de uma variante de texto aprovada
            self._dirty = True

    def unban(self, variant_ids: Iterable[str]) -> None:
        """Quem guarda uma variante de propósito a quer de volta, mesmo que um dia a tenha marcado como ruim."""
        with self._lock:
            ids = set(variant_ids)
            if ids & self.banned:
                self.banned -= ids
                self._dirty = True

    def remember_shown(self, note_id: Any, variant_id_: str) -> None:
        with self._lock:
            seen = [x for x in self.shown.get(str(note_id), []) if x != variant_id_]
            self.shown[str(note_id)] = ([variant_id_] + seen)[:SHOWN_MEMORY]
            self._dirty = True

    def recent(self, note_id: Any) -> list[str]:
        with self._lock:
            return list(self.shown.get(str(note_id), []))

    def delete_notes(self, note_ids: Iterable[int]) -> int:
        with self._lock:
            n = 0
            for nid in note_ids:
                n += self.notes.pop(int(nid), None) is not None
                self.skipped.pop(str(nid), None)
                self.shown.pop(str(nid), None)
            self._dirty = True
            return n

    def clear(self) -> None:
        with self._lock:
            self.notes.clear()
            self.skipped.clear()
            self.shown.clear()
            self._dirty = True

    def forget_skipped(self) -> int:
        """Esquece as notas avaliadas sem variantes, para a próxima geração tentar de novo."""
        with self._lock:
            n = len(self.skipped)
            self.skipped.clear()
            self._dirty = self._dirty or bool(n)
            return n

    def stats(self) -> dict[str, Any]:
        with self._lock:
            by_type: dict[str, int] = {}
            for e in self.notes.values():
                for v in e["variants"]:
                    by_type[v["type"]] = by_type.get(v["type"], 0) + 1
            return {"notes": len(self.notes), "variants": sum(by_type.values()), "by_type": by_type, "skipped": len(self.skipped), "banned": len(self.banned)}

    def merge_from(self, path: str) -> int:
        """Importa um banco (o pessoal exportado ou um do estudo); as notas importadas substituem as de mesmo id. Devolve quantas entraram."""
        with open(path, "rb") as f:
            bank = variants.Bank.from_bytes(f.read())
        with self._lock:
            for nid, e in bank.notes.items():
                self.notes[nid] = e
            self.generator_models.update(m for m in bank.meta.get("generator_models") or [] if m)
            self.judge_models.update(m for m in bank.meta.get("judge_models") or [] if m)
            self._dirty = True
        return len(bank.notes)

    def export_to(self, path: str) -> None:
        with self._lock:
            was = self._dirty
            self._dirty = True
            old = self.path
            self.path = path
            try:
                self.save()
            finally:
                self.path = old
                self._dirty = was
