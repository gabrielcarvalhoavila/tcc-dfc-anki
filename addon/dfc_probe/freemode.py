"""Variantes no uso livre durante a revisão (v0.5.0).

Separado do sorteio do estudo: não usa o banco oficial, a semente nem os eventos (só anota no evento que a tela foi alterada).
Sem imports do Anki, para testar sem interface: o que vem do Anki entra por `Env`.
"""
from __future__ import annotations

import html
import os
import random
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional

try:
    from . import free, variants
except ImportError:  # os testes carregam o módulo fora do pacote
    import free  # type: ignore
    import variants  # type: ignore

CONFIG_KEY = "dfc_free"  # ajustes, guardados na coleção (cada perfil tem os seus)
ID_KEY = "dfc_free_id"  # identifica o banco pessoal da coleção em user_files


@dataclass
class Env:
    col: Callable[[], Any]  # a coleção aberta (ou None)
    user_files: str
    snapshot: Callable[[Any], dict[str, Any]]  # estado do cartão antes da resposta (anki_adapter.make_snapshot_fn)
    render: Callable[..., tuple[str, str]]  # (col, card, field_index=None, value=None) -> (pergunta, resposta)
    munge: Callable[[str], str]
    official_has: Callable[[Any], bool]  # a nota é do banco do estudo
    study_drew: Callable[[Any], bool]  # o estudo já sorteou esta exposição
    mark_event: Callable[[Any], None]  # anota no evento do estudo que a tela foi alterada
    expand_decks: Callable[[list[int]], set[int]]  # baralhos e subbaralhos
    tooltip: Callable[[str], None]
    log_error: Callable[[], None]


class FreeMode:
    def __init__(self, env: Env, rng: Optional[random.Random] = None):
        self.env = env
        self.rng = rng or random.Random()  # sem semente: aqui não há nada a reproduzir
        self._bank: Optional[free.FreeBank] = None
        self._scope: Optional[tuple[tuple[int, ...], set[int]]] = None
        self._cur: Optional[dict[str, Any]] = None
        self._last: Optional[dict[str, Any]] = None

    def settings(self) -> free.Settings:
        col = self.env.col()
        return free.Settings.from_raw(col.get_config(CONFIG_KEY, None)) if col is not None else free.Settings()

    def save_settings(self, settings: free.Settings) -> None:
        col = self.env.col()
        if col is not None:
            col.set_config(CONFIG_KEY, settings.to_dict())

    def bank(self) -> Optional[free.FreeBank]:
        """Banco pessoal da coleção aberta."""
        col = self.env.col()
        if col is None:
            return None
        bank_id = col.get_config(ID_KEY, None)
        if not isinstance(bank_id, str) or not bank_id:
            bank_id = uuid.uuid4().hex[:12]
            col.set_config(ID_KEY, bank_id)
        path = os.path.join(self.env.user_files, f"free_bank_{bank_id}.json")
        if self._bank is None or self._bank.path != path:
            self.flush()
            self._bank = free.FreeBank(path)
            self._cur = self._last = None
        return self._bank

    def flush(self) -> None:
        if self._bank is not None:
            self._bank.save()

    def status_line(self) -> str:
        bank = self.bank()
        if bank is None:
            return "sem perfil aberto"
        s, st = self.settings(), bank.stats()
        state = f"ligado ({s.probability}% das revisões elegíveis)" if s.enabled else "desligado"
        return f"{state}; banco pessoal: {st['notes']} notas, {st['variants']} variantes"

    def _deck_scope(self, settings: free.Settings) -> Optional[set[int]]:
        if settings.deck_ids is None:
            return None
        key = tuple(settings.deck_ids)
        if self._scope is None or self._scope[0] != key:
            self._scope = (key, self.env.expand_decks(list(key)))
        return self._scope[1]

    def on_card_will_show(self, text: str, card: Any, kind: str) -> str:
        """Troca a pergunta (e depois a resposta) pela variante sorteada. Em qualquer falha, devolve o texto original."""
        if kind not in ("reviewQuestion", "reviewAnswer"):
            return text
        try:
            if kind == "reviewQuestion":
                self._decide(card)
            cur = self._cur
            if cur is None or cur["variant"] is None or cur["key"] != (card.id, card.reps):
                return text
            r = cur["render"]
            old, new = (r["orig_q"], r["var_q"]) if kind == "reviewQuestion" else (r["orig_a"], r["var_a"])
            if old not in text:
                return text
            out = text.replace(old, new, 1)
            if cur["badge"]:
                label = html.escape(free.SHORT_LABELS.get(cur["variant"]["type"], cur["variant"]["type"]))
                out += f'<div style="margin-top:14px;text-align:center;font-size:11px;opacity:.55">variante: {label}</div>'
            return out
        except Exception:
            self.env.log_error()
            return text

    def _decide(self, card: Any) -> None:
        key = (card.id, card.reps)
        if self._cur is not None and self._cur["key"] == key:
            return  # a mesma exposição (por exemplo, o cartão voltou com Ctrl+Z)
        self._cur = cur = {"key": key, "variant": None, "render": None, "badge": False}
        col = self.env.col()
        settings = self.settings()
        if col is None or not settings.enabled or settings.probability <= 0:
            return
        bank = self.bank()
        entry = bank.entry(card.nid) if bank is not None else None
        if entry is None or card.ord not in entry["ords"]:
            return
        if self.env.official_has(card.nid) or self.env.study_drew(card):
            return  # o estudo manda: nota do banco oficial e exposição já sorteada ficam como estão
        if not free.roll(settings, self.rng) or not free.card_allowed(settings, self.env.snapshot(card), self._deck_scope(settings)):
            return
        note = col.get_note(card.nid)
        if variants.fields_hash(note.fields) != entry["fields_hash"]:
            return  # a nota foi editada depois de gerar as variantes
        variant = free.pick_variant(entry, settings, bank.banned, bank.recent(card.nid), self.rng)
        if variant is None:
            return
        value, needles = variants.field_value(entry, variant, note.fields[entry["q_field"]])
        orig_q, orig_a = self.env.render(col, card)
        var_q, var_a = self.env.render(col, card, entry["q_field"], value)
        if var_q == orig_q or not all(n in var_q for n in needles):
            return
        munge = self.env.munge
        cur.update(variant=variant, badge=settings.badge, render={"orig_q": munge(orig_q), "var_q": munge(var_q), "orig_a": munge(orig_a), "var_a": munge(var_a)})
        self._last = variant
        bank.remember_shown(card.nid, variant["id"])
        self.env.mark_event(card)

    def mark_bad_current(self) -> bool:
        """Tira do banco pessoal a variante que está na tela. False se a tela não mostra uma variante do uso livre."""
        cur = self._cur
        if cur is None or cur["variant"] is None:
            return False
        self._ban(cur["variant"])
        return True

    def mark_bad_last(self) -> bool:
        if self._last is None:
            return False
        self._ban(self._last)
        return True

    def _ban(self, variant: dict[str, Any]) -> None:
        bank = self.bank()
        if bank is None:
            return
        bank.ban(variant["id"])
        bank.save()
        self.env.tooltip("DFC Probe: variante removida do banco pessoal; ela não volta.")
