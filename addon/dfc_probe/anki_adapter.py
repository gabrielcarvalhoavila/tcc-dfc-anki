"""Extrai do Anki o estado do cartão antes da resposta. Defensivo: atributo ausente vira None."""
from __future__ import annotations

import time
from typing import Any, Callable, Optional


def _safe(fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception:
        return default


def anki_version() -> str:
    try:
        from anki.buildinfo import version

        return str(version)
    except Exception:
        pass
    try:
        from aqt import appVersion

        return str(appVersion)
    except Exception:
        return "unknown"


def scheduler_name(col: Any) -> Any:
    # sem a chave "fsrs" na configuração (nunca ligado), o Anki considera desligado
    try:
        return "fsrs" if col.get_config("fsrs") else "sm2"
    except Exception:
        return None


def _same_day(last_id_ms: Any, day_cutoff: Any, now_ms: float) -> Optional[int]:
    if not last_id_ms:
        return None
    if day_cutoff:
        return int(last_id_ms / 1000 >= day_cutoff - 86_400)  # dia do Anki, não 24 h corridas
    return int(now_ms - last_id_ms < 43_200_000)  # sem day_cutoff: meio dia


def make_revlog_matcher(mw: Any) -> Callable[[int, int, float], bool]:
    """Diz se o histórico de revisões do Anki tem a resposta do evento (o id do revlog sai alguns ms antes do nosso horário)."""

    def match(card_id: int, ease: int, answered_at: float) -> bool:
        ms = int(answered_at * 1000)
        return bool(mw.col.db.scalar("select count(*) from revlog where cid = ? and ease = ? and id between ? and ?", card_id, ease, ms - 2000, ms + 500))

    return match


def render_pair(col: Any, card: Any, field_index: Optional[int] = None, value: Optional[str] = None) -> tuple[str, str]:
    """Pergunta e resposta como o Anki as renderiza; com `value`, troca esse campo numa cópia da nota (nada é gravado)."""
    from anki.template import TemplateRenderContext

    note = col.get_note(card.nid)
    if field_index is not None:
        note.fields[field_index] = value
    out = TemplateRenderContext.from_card_layout(note, card, note.note_type(), card.template(), False).render()
    return out.question_text, out.answer_text


def new_variant_note(col: Any, src: Any, q_field: int, value: str, tag: str) -> Any:
    """Nota nova do tipo da original, com o campo da pergunta trocado por `value`. Nada é gravado: quem salva é a janela Adicionar do Anki."""
    note = col.new_note(src.note_type())
    for i, field in enumerate(src.fields):
        note.fields[i] = field
    note.fields[q_field] = value
    note.tags = [*src.tags, tag]
    return note


def collect_records(col: Any, deck_id: int, to_record: Callable[..., dict[str, Any]], *, children: bool = True, skip_new: bool = True, skip_suspended: bool = True) -> list[dict[str, Any]]:
    """Notas de um baralho (e dos subbaralhos) no formato de `core.note_to_record`; as de cartões que vencem primeiro vêm na frente."""
    from anki.utils import ids2str

    dids = list(col.decks.deck_and_child_ids(deck_id)) if children else [deck_id]
    query = "(" + " or ".join(f"did:{d}" for d in dids) + ")" + (" -is:new" if skip_new else "") + (" -is:suspended" if skip_suspended else "")
    card_ids = col.find_cards(query)
    if not card_ids:
        return []
    rows = col.db.all(
        "select nid, case when type = 0 then 2000000000 when queue = 1 then 0 when odid != 0 then odue else due end "
        f"from cards where id in {ids2str(card_ids)}"
    )
    first_due: dict[int, int] = {}
    for nid, due in rows:
        first_due[nid] = min(due, first_due.get(nid, due))
    deck_name = col.decks.name(deck_id)
    records = []
    for nid in sorted(first_due, key=lambda n: (first_due[n], n)):
        note = col.get_note(nid)
        records.append(to_record(nid, note.guid, note.note_type()["name"], note.items(), note.tags, [deck_name]))
    return records


def _model_name(card: Any) -> Any:
    note = _safe(lambda: card.note())
    nt = _safe(lambda: note.note_type()) if note is not None else None
    if nt is None:
        nt = _safe(lambda: card.model())
    return nt.get("name") if nt else None


def make_snapshot_fn(mw: Any) -> Callable[[Any], dict[str, Any]]:
    """Cria a função que lê o estado do cartão no momento em que a pergunta aparece."""

    def snapshot(card: Any) -> dict[str, Any]:
        col = mw.col
        odid = _safe(lambda: card.odid, 0) or 0
        deck_id = odid or card.did
        due = _safe(lambda: card.odue if odid else card.due)
        today = _safe(lambda: col.sched.today)
        queue = _safe(lambda: card.queue)
        overdue = None
        if due is not None and today is not None and queue in (2, 3):
            overdue = int(today - due)
        last_id = _safe(lambda: col.db.scalar("select max(id) from revlog where cid = ? and ease > 0", card.id))
        eases = _safe(lambda: col.db.list("select ease from revlog where cid = ? and ease > 0 order by id desc limit 3", card.id), []) or []
        n_reviews = _safe(lambda: col.db.scalar("select count(*) from revlog where cid = ? and type = 1 and ease > 0", card.id))
        same_day = _same_day(last_id, _safe(lambda: col.sched.day_cutoff), time.time() * 1000)
        dyn = _safe(lambda: col.decks.get(card.did, default=False)) if odid else None
        resched = int(bool(dyn.get("resched", True))) if dyn else None
        if odid:
            mode = "filtered" if resched else "filtered_no_resched"
        else:
            mode = "regular"
        ms = _safe(lambda: card.memory_state)
        scheduler = scheduler_name(col)
        retention = _safe(lambda: col.decks.config_dict_for_deck_id(deck_id).get("desiredRetention")) if scheduler == "fsrs" else None
        return {
            "profile": _safe(lambda: mw.pm.name),
            "card_id": card.id,
            "note_id": card.nid,
            "card_ord": _safe(lambda: card.ord),
            "deck_id": deck_id,
            "deck_name": _safe(lambda: col.decks.name(deck_id)),
            "model_name": _model_name(card),
            "card_type": _safe(lambda: card.type),
            "queue": queue,
            "reps": _safe(lambda: card.reps),
            "lapses": _safe(lambda: card.lapses),
            "ivl": _safe(lambda: card.ivl),
            "factor": _safe(lambda: card.factor),
            "overdue_days": overdue,
            "days_since_last_review": round((time.time() * 1000 - last_id) / 86_400_000, 3) if last_id else None,
            "same_day": same_day,
            "n_reviews": n_reviews,
            "last_ease": eases[0] if eases else None,
            "prev_eases": eases,
            "in_filtered": int(bool(odid)),
            "resched": resched,
            "mode": mode,
            "fsrs_stability": _safe(lambda: ms.stability) if ms else None,
            "fsrs_difficulty": _safe(lambda: ms.difficulty) if ms else None,
            "scheduler": scheduler,
            "desired_retention": retention,
        }

    return snapshot
