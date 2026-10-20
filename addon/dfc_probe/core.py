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

ADDON_VERSION = "0.1.1"
SCHEMA_VERSION = 1

# Esquema do protocolo (seção 6.3). arm, variant_id e variant_type ficam vazios até o v1.
EVENT_COLUMNS: list[tuple[str, str]] = [
    ("event_id", "TEXT PRIMARY KEY"),
    ("session_id", "TEXT"),
    ("seq", "INTEGER"),
    ("addon_version", "TEXT"),
    ("anki_version", "TEXT"),
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
    ("last_ease", "INTEGER"),
    ("prev_eases", "TEXT"),
    ("in_filtered", "INTEGER"),
    ("resched", "INTEGER"),
    ("mode", "TEXT"),
    ("fsrs_stability", "REAL"),
    ("fsrs_difficulty", "REAL"),
    ("ease", "INTEGER"),
    ("t_reveal_ms", "INTEGER"),
    ("t_total_ms", "INTEGER"),
    ("arm", "TEXT"),
    ("variant_id", "TEXT"),
    ("variant_type", "TEXT"),
    ("flag_bad", "INTEGER DEFAULT 0"),
]
COLUMN_NAMES = [name for name, _ in EVENT_COLUMNS]
ID_COLUMNS = ("note_id", "card_id", "deck_id", "deck_name")


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
            db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
            db.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
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

    def question_shown(self, card: Any) -> None:
        snap = self.snapshot_fn(card)
        self.pending = {"card_id": snap.get("card_id"), "q_shown_at": self.clock(), "a_shown_at": None, "snap": snap}

    def answer_shown(self, card: Any) -> None:
        p = self.pending
        if p and p["card_id"] == card.id and p["a_shown_at"] is None:
            p["a_shown_at"] = self.clock()

    def answered(self, card: Any, ease: int) -> dict[str, Any]:
        now = self.clock()
        p = self.pending if (self.pending and self.pending["card_id"] == card.id) else None
        rec: dict[str, Any] = dict(p["snap"]) if p else {"card_id": card.id}
        self.seq += 1
        rec.update(
            event_id=uuid.uuid4().hex,
            session_id=self.session_id,
            seq=self.seq,
            addon_version=ADDON_VERSION,
            anki_version=self.anki_version,
            answered_at=now,
            ease=int(ease),
        )
        if p:
            rec["q_shown_at"] = p["q_shown_at"]
            rec["a_shown_at"] = p["a_shown_at"]
            rec["t_total_ms"] = int((now - p["q_shown_at"]) * 1000)
            if p["a_shown_at"] is not None:
                rec["t_reveal_ms"] = int((p["a_shown_at"] - p["q_shown_at"]) * 1000)
        self.store.insert(rec)
        self.pending = None
        return rec


def get_salt(path: str) -> bytes:
    """Sal por instalação, usado só para anonimizar IDs na exportação."""
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


def export_csv(store: EventStore, path: str, anonymize: bool = False, salt: bytes = b"") -> int:
    rows = store.rows()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMN_NAMES)
        for row in rows:
            if anonymize:
                row = anonymize_row(row, salt)
            writer.writerow([row.get(c) for c in COLUMN_NAMES])
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
