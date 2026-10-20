"""Testes do núcleo do add-on (sem Anki): armazenamento, rastreio de eventos e exportação."""
import csv
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load_core():
    spec = importlib.util.spec_from_file_location("dfc_core", os.path.join(ROOT, "addon", "dfc_probe", "core.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dfc_core"] = mod
    spec.loader.exec_module(mod)
    return mod


core = load_core()


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def snapshot(card):
    return {"card_id": card.id, "note_id": card.id * 10, "deck_id": 3, "deck_name": "Deck", "profile": "Perfil", "reps": 7, "lapses": 0, "prev_eases": [3, 3, 2], "mode": "regular"}


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = core.EventStore(os.path.join(self.tmp.name, "e.sqlite3"))
        self.clock = FakeClock()
        self.tracker = core.EventTracker(self.store, snapshot, "26.05", self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def test_full_review_cycle(self):
        card = types.SimpleNamespace(id=5)
        self.tracker.question_shown(card)
        self.clock.advance(1.5)
        self.tracker.answer_shown(card)
        self.clock.advance(0.7)
        self.tracker.answered(card, 3)
        (row,) = self.store.rows()
        self.assertEqual(row["t_reveal_ms"], 1500)
        self.assertEqual(row["t_total_ms"], 2200)
        self.assertEqual(row["ease"], 3)
        self.assertEqual(row["reps"], 7)
        self.assertEqual(row["note_id"], 50)
        self.assertEqual(json.loads(row["prev_eases"]), [3, 3, 2])
        self.assertEqual(row["anki_version"], "26.05")
        self.assertEqual(row["addon_version"], core.ADDON_VERSION)
        self.assertIsNone(row["arm"])
        self.assertEqual(row["flag_bad"], 0)

    def test_answer_without_question_event_keeps_nulls(self):
        self.tracker.answered(types.SimpleNamespace(id=9), 1)
        (row,) = self.store.rows()
        self.assertEqual(row["card_id"], 9)
        self.assertIsNone(row["t_reveal_ms"])
        self.assertIsNone(row["t_total_ms"])

    def test_events_of_other_card_do_not_mix(self):
        a, b = types.SimpleNamespace(id=1), types.SimpleNamespace(id=2)
        self.tracker.question_shown(a)
        self.clock.advance(1)
        self.tracker.answer_shown(b)  # outro cartão: ignorado
        self.tracker.answered(a, 2)
        (row,) = self.store.rows()
        self.assertIsNone(row["t_reveal_ms"])
        self.assertEqual(row["t_total_ms"], 1000)

    def test_sequence_and_session(self):
        for cid in (1, 2, 3):
            card = types.SimpleNamespace(id=cid)
            self.tracker.question_shown(card)
            self.clock.advance(1)
            self.tracker.answered(card, 3)
        rows = self.store.rows()
        self.assertEqual([r["seq"] for r in rows], [1, 2, 3])
        self.assertEqual(len({r["session_id"] for r in rows}), 1)
        self.assertEqual(self.store.count(), 3)

    def test_mark_bad(self):
        rec = self.tracker.answered(types.SimpleNamespace(id=1), 3)
        self.assertEqual(self.store.mark_bad(rec["event_id"]), 1)
        self.assertEqual(self.store.rows()[0]["flag_bad"], 1)
        self.assertEqual(self.store.mark_bad("nao-existe"), 0)

    def test_exposure_inherits_the_decision_only_after_an_undone_answer_of_the_same_card(self):
        reps = {"v": 7}
        tracker = core.EventTracker(self.store, lambda c: {**snapshot(c), "reps": reps["v"]}, "26.05", self.clock)
        a, b = types.SimpleNamespace(id=1), types.SimpleNamespace(id=2)
        first = tracker.begin_exposure(a)
        self.assertIsNone(first["inherit"])
        first["extra"].update(arm="variant", variant_id="v1")
        tracker.answered(a, 3)
        again = tracker.begin_exposure(a)  # Ctrl+Z: mesmo cartão e mesmo reps
        self.assertEqual(again["inherit"]["variant_id"], "v1")
        tracker.answered(a, 3)
        reps["v"] = 8  # a resposta valeu: reps avançou
        self.assertIsNone(tracker.begin_exposure(a)["inherit"])
        tracker.answered(a, 3)
        tracker.begin_exposure(b)
        tracker.answered(b, 3)
        self.assertIsNone(tracker.begin_exposure(a)["inherit"])  # outra resposta no meio

    def test_same_exposure_is_reused_until_answered(self):
        a = types.SimpleNamespace(id=1)
        first = self.tracker.begin_exposure(a)
        self.assertIs(self.tracker.begin_exposure(a), first)
        self.tracker.question_shown(a)
        self.assertIs(self.tracker.pending, first)
        self.assertIsNot(self.tracker.begin_exposure(types.SimpleNamespace(id=2)), first)


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = core.EventStore(os.path.join(self.tmp.name, "e.sqlite3"))
        tracker = core.EventTracker(self.store, snapshot, "26.05", FakeClock())
        card = types.SimpleNamespace(id=5)
        tracker.question_shown(card)
        tracker.answered(card, 3)

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, path):
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_csv_has_all_columns(self):
        path = os.path.join(self.tmp.name, "o.csv")
        self.assertEqual(core.export_csv(self.store, path), 1)
        (row,) = self.read(path)
        self.assertEqual(list(row.keys()), core.COLUMN_NAMES + list(core.EXPORT_EXTRA))
        self.assertEqual(row["note_id"], "50")
        self.assertEqual(row["deck_name"], "Deck")
        self.assertEqual((row["revlog_match"], row["superseded"], row["after_undo"]), ("", "0", "0"))  # sem conciliador: desconhecido

    def test_anonymize_hashes_ids_with_salt(self):
        salt_path = os.path.join(self.tmp.name, "salt.txt")
        salt = core.get_salt(salt_path)
        self.assertEqual(salt, core.get_salt(salt_path))  # persistente
        path = os.path.join(self.tmp.name, "o.csv")
        core.export_csv(self.store, path, anonymize=True, salt=salt)
        (row,) = self.read(path)
        for col in core.ID_COLUMNS:
            self.assertNotIn(row[col], ("50", "5", "3", "Deck", "Perfil"))
            self.assertEqual(len(row[col]), 16)
        other = os.path.join(self.tmp.name, "o2.csv")
        core.export_csv(self.store, other, anonymize=True, salt=b"outro-sal")
        self.assertNotEqual(self.read(other)[0]["note_id"], row["note_id"])
        self.assertEqual(row["reps"], "7")  # covariáveis ficam

    def test_note_record(self):
        rec = core.note_to_record(7, "g", "Basic", [("Front", "q"), ("Back", "a")], ["t"], ["B", "A", "A"])
        self.assertEqual(rec, {"note_id": 7, "guid": "g", "model": "Basic", "fields": {"Front": "q", "Back": "a"}, "tags": ["t"], "decks": ["A", "B"]})

    def test_undone_answer_is_superseded_and_has_no_revlog_pair(self):
        tracker = core.EventTracker(self.store, snapshot, "26.05", FakeClock(2000.0))
        card = types.SimpleNamespace(id=5)
        tracker.question_shown(card)
        tracker.answered(card, 1)  # mesmo cartão e mesmo reps do setUp: a resposta 3 foi desfeita
        path = os.path.join(self.tmp.name, "o.csv")
        core.export_csv(self.store, path, revlog_match=lambda cid, ease, ts: ease == 1)
        first, second = self.read(path)
        self.assertEqual((first["ease"], first["superseded"], first["revlog_match"], first["after_undo"]), ("3", "1", "0", "0"))
        self.assertEqual((second["ease"], second["superseded"], second["revlog_match"], second["after_undo"]), ("1", "0", "1", "1"))

    def test_reconciliation_uses_real_ids_even_when_anonymizing(self):
        path = os.path.join(self.tmp.name, "o.csv")
        core.export_csv(self.store, path, anonymize=True, salt=b"s", revlog_match=lambda cid, ease, ts: cid == 5)
        (row,) = self.read(path)
        self.assertEqual(row["revlog_match"], "1")

    def test_reconciliation_failure_leaves_blank(self):
        path = os.path.join(self.tmp.name, "o.csv")
        core.export_csv(self.store, path, revlog_match=lambda *a: 1 / 0)
        (row,) = self.read(path)
        self.assertEqual(row["revlog_match"], "")

    def test_mark_superseded_ignores_unknown_reps(self):
        rows = [{"card_id": 1, "reps": 4}, {"card_id": 1, "reps": 4}, {"card_id": 1, "reps": 5}, {"card_id": 2, "reps": None}, {"card_id": 2, "reps": None}]
        self.assertEqual(core.mark_superseded(rows), [1, 0, 0, 0, 0])
        self.assertEqual(core.mark_after_undo(rows), [0, 1, 0, 0, 0])

    def test_after_undo_marks_every_event_after_the_first_of_a_group(self):
        rows = [{"card_id": 1, "reps": 4}] * 3 + [{"card_id": 1, "reps": 5}]
        self.assertEqual(core.mark_superseded(rows), [1, 1, 0, 0])
        self.assertEqual(core.mark_after_undo(rows), [0, 1, 1, 0])  # a válida (3ª) já tinha visto a resposta


class MigrationTest(unittest.TestCase):
    def test_old_schema_gets_new_columns_and_keeps_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.sqlite3")
            db = sqlite3.connect(path)
            db.execute("CREATE TABLE events (event_id TEXT PRIMARY KEY, note_id INTEGER, ease INTEGER)")
            db.execute("INSERT INTO events VALUES ('e1', 5, 3)")
            db.commit()
            db.close()
            store = core.EventStore(path)
            store.insert({"event_id": "e2", "scheduler": "sm2"})
            rows = {r["event_id"]: r for r in store.rows()}
            self.assertEqual((rows["e1"]["note_id"], rows["e1"]["ease"], rows["e1"]["scheduler"]), (5, 3, None))
            self.assertEqual(rows["e2"]["scheduler"], "sm2")
            core.EventStore(path)  # reabrir não falha nem duplica colunas


if __name__ == "__main__":
    unittest.main()
