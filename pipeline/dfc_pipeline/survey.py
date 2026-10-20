"""Levantamento de viabilidade de uma coleção: tipos de nota, elegibilidade e quantos eventos ela geraria na janela do estudo.

Só agregados (nenhum texto de cartão), para poder colar o resultado numa conversa.
"""
from __future__ import annotations

import datetime
import time
from collections import Counter, defaultdict
from typing import Any, Callable, Optional

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


def root_deck(name: Optional[str]) -> str:
    return (name or "").split("::")[0] or "(sem baralho)"


def recent_cards(invoke: Callable[..., Any], days: int, since_ms: float, rollover_hour: int = 4) -> list[dict[str, Any]]:
    """Cartões respondidos nos últimos `days` dias (de qualquer nota), com respostas, eventos e eventos de suspeitos desde `since_ms`."""
    ids = invoke("findCards", query=f"rated:{min(days + 1, 365)}")  # um dia a mais: `rated:N` começa na virada do dia, o corte `since_ms` é em horas
    infos: dict[int, dict[str, Any]] = {}
    revs: dict[int, list[dict[str, Any]]] = {}
    for i in range(0, len(ids), 100):
        infos.update({c["cardId"]: c for c in invoke("cardsInfo", cards=ids[i : i + 100])})
    for i in range(0, len(ids), 200):
        revs.update({int(k): v for k, v in invoke("getReviewsOfCards", cards=[int(x) for x in ids[i : i + 200]]).items()})
    out = []
    for card_id, info in infos.items():
        done = classify(revs.get(card_id, []), info.get("reps") or 0, info.get("lapses") or 0, rollover_hour)
        mine = [r for r in done if r["id"] >= since_ms]
        if mine:
            out.append({
                "note": info["note"], "ord": info.get("ord", 0), "deck": root_deck(info.get("deckName")),
                "respostas": len(mine), "eventos": sum(r["event"] for r in mine), "suspeitos": sum(r["suspect"] for r in mine),
            })
    return out


def bucket(card: Optional[Card], ord_: int) -> str:
    """Onde cai uma resposta: cartão que o add-on sortearia, ou os motivos de não cair."""
    if card is None:
        return "nota fora da busca"
    if card.eligible:
        return "sorteavel" if ord_ in card.ords else "outro cartao da nota"
    return "+".join(card.reasons)


def coverage(cards: list[Card], recent: list[dict[str, Any]]) -> tuple[dict[str, Counter], dict[tuple[str, str], Counter], dict[str, Counter]]:
    """Respostas recentes por situação do cartão, por (baralho raiz, tipo) só dos sorteáveis, e por baralho raiz (todas e sorteáveis)."""
    by_note = {c.note_id: c for c in cards}
    by_bucket: dict[str, Counter] = defaultdict(Counter)
    drawable: dict[tuple[str, str], Counter] = defaultdict(Counter)
    by_deck: dict[str, Counter] = defaultdict(Counter)
    for r in recent:
        note = by_note.get(r["note"])
        where = bucket(note, r["ord"])
        n = Counter(respostas=r["respostas"], eventos=r["eventos"], suspeitos=r["suspeitos"], cartoes=int(r["eventos"] > 0))
        by_bucket[where].update(n)
        by_deck[r["deck"]]["respostas"] += r["respostas"]
        if where == "sorteavel":
            drawable[(r["deck"], note.kind)].update(n)
            by_deck[r["deck"]]["sorteaveis"] += r["respostas"]
    return by_bucket, drawable, by_deck


def collect(query: str, invoke: Callable[..., Any], days: int, since_ms: float, rollover_hour: int = 4, log: Callable[[str], None] = print) -> tuple[list[Card], list[dict[str, Any]]]:
    cards = [parse_note(r) for r in source.from_ankiconnect(query, invoke=invoke, log=log)]
    return cards, recent_cards(invoke, days, since_ms, rollover_hour)


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}%" if whole else "-"


def report(cards: list[Card], recent: list[dict[str, Any]], days: int, window_days: int = WINDOW_DAYS) -> list[str]:
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

    notes_by_deck: dict[str, Counter] = defaultdict(Counter)
    for c in cards:
        n = notes_by_deck[root_deck(c.decks[0] if c.decks else None)]
        n["notas"] += 1
        if c.eligible:
            active = c.stats.get("queue") != -1  # -1 = suspenso
            n["elegiveis"] += 1
            n["ativas"] += int(active)
            n["suspeitas_ativas"] += int(active and c.suspect_by_history)
    lines.append(f"{'baralho raiz':30} {'notas':>6} {'elegiveis':>9} {'ativas':>7} {'suspeitas (reps>=5, lapses=0) ativas':>38}")
    for deck, n in sorted(notes_by_deck.items(), key=lambda kv: -kv[1]["notas"]):
        lines.append(f"{deck[:30]:30} {n['notas']:>6} {n['elegiveis']:>9} {n['ativas']:>7} {n['suspeitas_ativas']:>38}")
    lines.append("")

    by_bucket, drawable, by_deck = coverage(cards, recent)
    total = Counter()
    for n in by_bucket.values():
        total.update(n)
    lines.append(f"Ultimos {days} dias, respostas de qualquer nota: {total['respostas']} (evento = resposta cuja anterior foi em outro dia do Anki)")
    lines.append(f"{'onde caem':44} {'respostas':>10} {'%':>5} {'eventos':>8} {'suspeitos':>10}")
    for where, n in sorted(by_bucket.items(), key=lambda kv: -kv[1]["respostas"]):
        lines.append(f"{where[:44]:44} {n['respostas']:>10} {pct(n['respostas'], total['respostas']):>5} {n['eventos']:>8} {n['suspeitos']:>10}")
    lines.append(f"{'baralho raiz':30} {'respostas':>10} {'sorteaveis':>11}")
    for deck, n in sorted(by_deck.items(), key=lambda kv: -kv[1]["respostas"]):
        lines.append(f"{deck[:30]:30} {n['respostas']:>10} {n['sorteaveis']:>11}")
    lines.append("")

    lines.append(f"Eventos em cartoes que o add-on sortearia (ultimos {days} dias)")
    lines.append(f"{'baralho raiz':30} {'tipo':8} {'cartoes':>8} {'eventos':>8} {'suspeitos':>10} {'controles':>10}")
    for (deck, kind), n in sorted(drawable.items(), key=lambda kv: -kv[1]["eventos"]):
        lines.append(f"{deck[:30]:30} {kind:8} {n['cartoes']:>8} {n['eventos']:>8} {n['suspeitos']:>10} {n['eventos'] - n['suspeitos']:>10}")
    scale = window_days / days
    ok = by_bucket["sorteavel"]
    lines.append(f"na janela de {window_days} dias, se a rotina continuar igual: ~{round(ok['eventos'] * scale)} eventos (~{round(ok['suspeitos'] * scale)} suspeitos)")
    return lines


def run(query: str, invoke: Callable[..., Any], days: int, rollover_hour: int, now: float | None = None, log: Callable[[str], None] = print) -> tuple[list[Card], list[str]]:
    since_ms = ((time.time() if now is None else now) - days * 86400) * 1000
    cards, recent = collect(query, invoke, days, since_ms, rollover_hour, log=log)
    return cards, report(cards, recent, days)
