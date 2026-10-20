"""Extrai do Anki o estado do cartão antes da resposta. Defensivo: atributo ausente vira None."""
from __future__ import annotations

import time
from typing import Any, Callable


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
        dyn = _safe(lambda: col.decks.get(card.did, default=False)) if odid else None
        resched = int(bool(dyn.get("resched", True))) if dyn else None
        if odid:
            mode = "filtered" if resched else "filtered_no_resched"
        else:
            mode = "regular"
        ms = _safe(lambda: card.memory_state)
        return {
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
            "last_ease": eases[0] if eases else None,
            "prev_eases": eases,
            "in_filtered": int(bool(odid)),
            "resched": resched,
            "mode": mode,
            "fsrs_stability": _safe(lambda: ms.stability) if ms else None,
            "fsrs_difficulty": _safe(lambda: ms.difficulty) if ms else None,
        }

    return snapshot
