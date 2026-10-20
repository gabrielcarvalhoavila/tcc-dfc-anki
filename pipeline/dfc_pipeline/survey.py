"""Levantamento de viabilidade de uma coleção: tipos de nota, elegibilidade e quantos eventos ela geraria na janela do estudo.

Só agregados (nenhum texto de cartão), para poder colar o resultado numa conversa.
"""
from __future__ import annotations

import datetime
import time
from collections import Counter, defaultdict
from typing import Any, Callable

from . import source
from .cards import Card, parse_note

WINDOW_DAYS = 21  # janela do estudo: 2/11 a 22/11 (protocolo, seção 5)


def anki_day(ms: int, rollover_hour: int = 4) -> datetime.date:
    """Dia do Anki de uma revisão (o `id` do revlog é o horário em ms): a virada é às `rollover_hour`, no horário local."""
    return (datetime.datetime.fromtimestamp(ms / 1000) - datetime.timedelta(hours=rollover_hour)).date()


def classify(entries: list[dict[str, Any]], reps_now: int, lapses_now: int, rollover_hour: int = 4) -> list[dict[str, Any]]:
    """Cada resposta real do cartão: `event` (a anterior foi em outro dia do Anki, então o add-on sortearia) e `suspect` (estrato do protocolo).

    O estado de antes de cada resposta sai dos contadores atuais do cartão menos o que veio depois, para não depender de o revlog ser completo.
    """
    answers = sorted((e for e in entries if (e.get("ease") or 0) > 0), key=lambda e: e["id"])
    out = []
    for k, e in enumerate(answers):
        reps_before = reps_now - (len(answers) - k)
        lapses_before = max(0, lapses_now - sum(1 for x in answers[k:] if x.get("type") == 1 and x["ease"] == 1))
        prev = answers[k - 1] if k else None
        event = prev is not None and anki_day(e["id"], rollover_hour) != anki_day(prev["id"], rollover_hour)
        suspect = event and reps_before >= 5 and lapses_before == 0 and prev["ease"] >= 3
        out.append({"id": e["id"], "event": event, "suspect": suspect})
    return out


def root_deck(card: Card) -> str:
    return card.decks[0].split("::")[0] if card.decks else "(sem baralho)"


def window_counts(cards: list[Card], reviews: dict[int, list[dict[str, Any]]], since_ms: float, rollover_hour: int = 4) -> dict[tuple[str, str], Counter]:
    """Por (baralho raiz, tipo), só notas elegíveis: respostas, eventos, eventos suspeitos e cartões com evento desde `since_ms`."""
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for c in cards:
        card_id = c.stats.get("card_id")
        if not c.eligible or card_id is None:
            continue
        done = classify(reviews.get(card_id, []), c.stats.get("reps") or 0, c.stats.get("lapses") or 0, rollover_hour)
        mine = [r for r in done if r["id"] >= since_ms]
        n = counts[(root_deck(c), c.kind)]
        n["respostas"] += len(mine)
        n["eventos"] += sum(r["event"] for r in mine)
        n["suspeitos"] += sum(r["suspect"] for r in mine)
        n["cartoes"] += int(any(r["event"] for r in mine))
    return counts


def collect(query: str, invoke: Callable[..., Any], log: Callable[[str], None] = print) -> tuple[list[Card], dict[int, list[dict[str, Any]]]]:
    """Notas e histórico de revisões (só do primeiro cartão das notas elegíveis, o mesmo que o add-on sorteia)."""
    cards = [parse_note(r) for r in source.from_ankiconnect(query, invoke=invoke, log=log)]
    ids = [c.stats["card_id"] for c in cards if c.eligible and c.stats.get("card_id") is not None]
    reviews: dict[int, list[dict[str, Any]]] = {}
    for i in range(0, len(ids), 200):
        got = invoke("getReviewsOfCards", cards=[int(x) for x in ids[i : i + 200]])
        reviews.update({int(k): v for k, v in got.items()})
    return cards, reviews


def report(cards: list[Card], counts: dict[tuple[str, str], Counter], days: int, window_days: int = WINDOW_DAYS) -> list[str]:
    lines = [f"notas: {len(cards)}  elegiveis: {sum(c.eligible for c in cards)}", ""]

    by_model: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for c in cards:
        by_model[(c.model, c.kind)]["notas"] += 1
        by_model[(c.model, c.kind)]["elegiveis"] += int(c.eligible)
    lines.append(f"{'tipo de nota':36} {'tipo':8} {'notas':>6} {'elegiveis':>9}")
    for (model, kind), n in sorted(by_model.items(), key=lambda kv: -kv[1]["notas"]):
        lines.append(f"{model[:36]:36} {kind:8} {n['notas']:>6} {n['elegiveis']:>9}")
    reasons = Counter(r for c in cards for r in c.reasons)
    lines += ["motivos de inelegibilidade: " + (", ".join(f"{r} {n}" for r, n in reasons.most_common()) or "nenhum"), ""]

    by_deck: dict[str, Counter] = defaultdict(Counter)
    for c in cards:
        n = by_deck[root_deck(c)]
        n["notas"] += 1
        if c.eligible:
            active = c.stats.get("queue") != -1  # -1 = suspenso
            n["elegiveis"] += 1
            n["ativas"] += int(active)
            n["suspeitas_ativas"] += int(active and c.suspect_by_history)
    lines.append(f"{'baralho raiz':30} {'notas':>6} {'elegiveis':>9} {'ativas':>7} {'suspeitas (reps>=5, lapses=0) ativas':>38}")
    for deck, n in sorted(by_deck.items(), key=lambda kv: -kv[1]["notas"]):
        lines.append(f"{deck[:30]:30} {n['notas']:>6} {n['elegiveis']:>9} {n['ativas']:>7} {n['suspeitas_ativas']:>38}")
    lines.append("")

    lines.append(f"Ultimos {days} dias (so notas elegiveis; evento = revisao cuja anterior foi em outro dia do Anki)")
    lines.append(f"{'baralho raiz':30} {'tipo':8} {'cartoes':>8} {'eventos':>8} {'suspeitos':>10} {'controles':>10}")
    total = Counter()
    for (deck, kind), n in sorted(counts.items(), key=lambda kv: -kv[1]["eventos"]):
        total.update(n)
        lines.append(f"{deck[:30]:30} {kind:8} {n['cartoes']:>8} {n['eventos']:>8} {n['suspeitos']:>10} {n['eventos'] - n['suspeitos']:>10}")
    scale = window_days / days
    lines.append(
        f"total: {total['eventos']} eventos ({total['suspeitos']} suspeitos, {total['eventos'] - total['suspeitos']} controles) em {total['cartoes']} cartoes; "
        f"na janela de {window_days} dias, se a rotina continuar igual: ~{round(total['eventos'] * scale)} eventos (~{round(total['suspeitos'] * scale)} suspeitos)"
    )
    return lines


def run(query: str, invoke: Callable[..., Any], days: int, rollover_hour: int, now: float | None = None, log: Callable[[str], None] = print) -> tuple[list[Card], list[str]]:
    cards, reviews = collect(query, invoke, log=log)
    since_ms = ((time.time() if now is None else now) - days * 86400) * 1000
    return cards, report(cards, window_counts(cards, reviews, since_ms, rollover_hour), days)
