"""Núcleo do DFC Probe: armazenamento e rastreio de eventos de revisão.

Não importa nada do Anki, para poder ser testado fora dele.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Any, Callable, Iterable, Optional

ADDON_VERSION = "0.2.1"
SCHEMA_VERSION = 4

# Esquema do protocolo (seção 6.3). arm e variant_* só são preenchidos nas exposições sorteadas.
EVENT_COLUMNS: list[tuple[str, str]] = [
    ("event_id", "TEXT PRIMARY KEY"),
    ("session_id", "TEXT"),
    ("seq", "INTEGER"),
    ("addon_version", "TEXT"),
    ("anki_version", "TEXT"),
    ("profile", "TEXT"),
    ("q_shown_at", "REAL"),
    ("a_shown_at", "REAL"),
    ("answered_at", "REAL"),
    ("note_id", "INTEGER"),
    ("card_id", "INTEGER"),
    ("card_ord", "INTEGER"),
    ("deck_id", "INTEGER"),
    ("deck_name", "TEXT"),
    ("model_name", "TEXT"),
    ("card_type", "INTEGER"),
    ("queue", "INTEGER"),
    ("reps", "INTEGER"),
    ("lapses", "INTEGER"),
    ("ivl", "INTEGER"),
    ("factor", "INTEGER"),
    ("overdue_days", "INTEGER"),
    ("days_since_last_review", "REAL"),
    ("same_day", "INTEGER"),
    ("n_reviews", "INTEGER"),
    ("last_ease", "INTEGER"),
    ("prev_eases", "TEXT"),
    ("in_filtered", "INTEGER"),
    ("resched", "INTEGER"),
    ("mode", "TEXT"),
    ("fsrs_stability", "REAL"),
    ("fsrs_difficulty", "REAL"),
    ("scheduler", "TEXT"),
    ("desired_retention", "REAL"),
    ("ease", "INTEGER"),
    ("t_reveal_ms", "INTEGER"),
    ("t_total_ms", "INTEGER"),
    ("arm", "TEXT"),
    ("variant_id", "TEXT"),
    ("variant_type", "TEXT"),
    ("shown_ok", "INTEGER"),
    ("shown_hash", "TEXT"),
    ("draw_seed", "TEXT"),
    ("draw_note", "TEXT"),
    ("bank_hash", "TEXT"),
    ("flag_bad", "INTEGER DEFAULT 0"),
]
COLUMN_NAMES = [name for name, _ in EVENT_COLUMNS]
EXPORT_EXTRA = ("revlog_match", "superseded", "after_undo")  # derivadas na exportação, não ficam no banco
ID_COLUMNS = ("note_id", "card_id", "deck_id", "deck_name", "profile")


def _to_db(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, bool):
        return int(value)
    return value


class EventStore:
    """SQLite local com uma linha por revisão."""

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with closing(self._connect()) as db:
            cols = ", ".join(f"{name} {kind}" for name, kind in EVENT_COLUMNS)
            db.execute(f"CREATE TABLE IF NOT EXISTS events ({cols})")
            have = {r["name"] for r in db.execute("PRAGMA table_info(events)")}
            for name, kind in EVENT_COLUMNS:
                if name not in have:
                    db.execute(f"ALTER TABLE events ADD COLUMN {name} {kind}")
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT OR REPLACE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
            db.commit()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def insert(self, rec: dict[str, Any]) -> None:
        names = [n for n in COLUMN_NAMES if n in rec]
        sql = f"INSERT INTO events ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})"
        with closing(self._connect()) as db:
            db.execute(sql, [_to_db(rec[n]) for n in names])
            db.commit()

    def count(self) -> int:
        with closing(self._connect()) as db:
            return db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def rows(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            cur = db.execute("SELECT * FROM events ORDER BY answered_at, seq")
            return [dict(r) for r in cur.fetchall()]

    def mark_bad(self, event_id: str) -> int:
        with closing(self._connect()) as db:
            cur = db.execute("UPDATE events SET flag_bad = 1 WHERE event_id = ?", (event_id,))
            db.commit()
            return cur.rowcount

    def last_event(self) -> Optional[dict[str, Any]]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM events ORDER BY answered_at DESC, seq DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def shown_variants(self, card_id: int) -> list[str]:
        """IDs das variantes já mostradas neste cartão (inclusive as de respostas desfeitas), da mais recente para a mais antiga."""
        with closing(self._connect()) as db:
            cur = db.execute(
                "SELECT variant_id FROM events WHERE card_id = ? AND arm = 'variant' AND shown_ok = 1 AND variant_id IS NOT NULL "
                "ORDER BY answered_at DESC, seq DESC",
                (card_id,),
            )
            return [r[0] for r in cur.fetchall()]


class EventTracker:
    """Junta os três momentos de uma revisão (pergunta, resposta revelada, nota) em um evento."""

    def __init__(
        self,
        store: EventStore,
        snapshot_fn: Callable[[Any], dict[str, Any]],
        anki_version: str = "unknown",
        clock: Callable[[], float] = time.time,
    ):
        self.store = store
        self.snapshot_fn = snapshot_fn
        self.anki_version = anki_version
        self.clock = clock
        self.session_id = uuid.uuid4().hex
        self.seq = 0
        self.pending: Optional[dict[str, Any]] = None
        self.last_answered: Optional[dict[str, Any]] = None  # decisão da última resposta, reaproveitada se ela for desfeita

    def begin_exposure(self, card: Any) -> dict[str, Any]:
        """Abre (ou reaproveita, se for o mesmo cartão ainda sem resposta) a exposição atual: estado do cartão, id do evento e anotações do sorteio."""
        p = self.pending
        if p and p["card_id"] == getattr(card, "id", None):
            return p
        snap = self.snapshot_fn(card)
        la = self.last_answered
        same_state = la is not None and la["card_id"] == snap.get("card_id") and la["reps"] is not None and la["reps"] == snap.get("reps")
        self.pending = {
            "event_id": uuid.uuid4().hex,
            "card_id": snap.get("card_id"),
            "q_shown_at": None,
            "a_shown_at": None,
            "snap": snap,
            "extra": {},
            "render": None,
            "inherit": la["extra"] if same_state else None,  # mesmo cartão e mesmo reps: a resposta anterior foi desfeita
        }
        return self.pending

    def question_shown(self, card: Any) -> None:
        p = self.begin_exposure(card)
        p["q_shown_at"], p["a_shown_at"] = self.clock(), None

    def answer_shown(self, card: Any) -> None:
        p = self.pending
        if p and p["card_id"] == card.id and p["a_shown_at"] is None:
            p["a_shown_at"] = self.clock()

    def answered(self, card: Any, ease: int) -> dict[str, Any]:
        now = self.clock()
        p = self.pending if (self.pending and self.pending["card_id"] == card.id) else None
        rec: dict[str, Any] = dict(p["snap"]) if p else {"card_id": card.id}
        if p:
            rec.update(p["extra"])
        self.seq += 1
        rec.update(
            event_id=p["event_id"] if p else uuid.uuid4().hex,
            session_id=self.session_id,
            seq=self.seq,
            addon_version=ADDON_VERSION,
            anki_version=self.anki_version,
            answered_at=now,
            ease=int(ease),
        )
        if p and p["q_shown_at"] is not None:
            rec["q_shown_at"] = p["q_shown_at"]
            rec["a_shown_at"] = p["a_shown_at"]
            rec["t_total_ms"] = int((now - p["q_shown_at"]) * 1000)
            if p["a_shown_at"] is not None:
                rec["t_reveal_ms"] = int((p["a_shown_at"] - p["q_shown_at"]) * 1000)
        self.store.insert(rec)
        self.last_answered = {"card_id": rec.get("card_id"), "reps": rec.get("reps"), "extra": dict(p["extra"])} if p else None
        self.pending = None
        return rec


def get_salt(path: str) -> bytes:
    """Sal por instalação: anonimiza IDs na exportação e entra na semente do sorteio."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(16))
    with open(path, encoding="utf-8") as f:
        return f.read().strip().encode("utf-8")


def anonymize_row(row: dict[str, Any], salt: bytes) -> dict[str, Any]:
    out = dict(row)
    for col in ID_COLUMNS:
        if out.get(col) is not None:
            out[col] = hmac.new(salt, str(out[col]).encode("utf-8"), hashlib.sha256).hexdigest()[:16]
    return out


def mark_superseded(rows: list[dict[str, Any]]) -> list[int]:
    """O Anki só avança `reps` com resposta válida: se (cartão, reps) reaparece depois, a resposta anterior foi desfeita."""
    last = {(r.get("card_id"), r.get("reps")): i for i, r in enumerate(rows)}
    return [int(r.get("reps") is not None and last[(r.get("card_id"), r.get("reps"))] != i) for i, r in enumerate(rows)]


def mark_after_undo(rows: list[dict[str, Any]]) -> list[int]:
    """1 para a resposta que refaz uma desfeita: antes dela há outro evento do mesmo cartão com o mesmo `reps` (a pessoa já viu a resposta)."""
    seen: set[Any] = set()
    out = []
    for r in rows:
        key = (r.get("card_id"), r.get("reps"))
        out.append(int(r.get("reps") is not None and key in seen))
        seen.add(key)
    return out


def _revlog_pair(match: Optional[Callable[[int, int, float], bool]], row: dict[str, Any]) -> Optional[int]:
    if match is None or None in (row.get("card_id"), row.get("ease"), row.get("answered_at")):
        return None
    try:
        return int(bool(match(row["card_id"], row["ease"], row["answered_at"])))
    except Exception:
        return None


def export_csv(store: EventStore, path: str, anonymize: bool = False, salt: bytes = b"", revlog_match: Optional[Callable[[int, int, float], bool]] = None) -> int:
    rows = store.rows()
    superseded = mark_superseded(rows)
    after_undo = mark_after_undo(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMN_NAMES + list(EXPORT_EXTRA))
        for row, sup, aft in zip(rows, superseded, after_undo):
            pair = _revlog_pair(revlog_match, row)
            if anonymize:
                row = anonymize_row(row, salt)
            writer.writerow([row.get(c) for c in COLUMN_NAMES] + [pair, sup, aft])
    return len(rows)


def note_to_record(note_id: int, guid: str, model: str, fields: Iterable[tuple[str, str]], tags: Iterable[str], decks: Iterable[str]) -> dict[str, Any]:
    """Formato lido pelo pipeline (`dfc_pipeline export --source file`)."""
    return {
        "note_id": int(note_id),
        "guid": guid,
        "model": model,
        "fields": {name: value for name, value in fields},
        "tags": list(tags),
        "decks": sorted(set(decks)),
    }


def write_jsonl(path: str, records: Iterable[dict[str, Any]]) -> int:
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n
