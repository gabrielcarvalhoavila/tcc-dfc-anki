"""Teste de fumaça do add-on com um Anki simulado (aqt falso): ligação dos ganchos, menu e exportações.

Não substitui testar no Anki real: só pega erros de sintaxe, de ligação e de lógica.
"""
import csv
import importlib
import json
import os
import sys
import tempfile
import time
import types
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "addon"))


class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, f):
        self.slots.append(f)

    def emit(self, *args):
        for f in self.slots:
            f(*args)


class Action:
    def __init__(self, text, parent=None):
        self.text = text
        self.triggered = Signal()
        self.toggled = Signal()
        self.checked = False

    def setCheckable(self, v):
        pass

    def setChecked(self, v):
        self.checked = v


class Menu:
    def __init__(self):
        self.actions, self.menus = [], []

    def addMenu(self, title):
        m = Menu()
        m.title = title
        self.menus.append(m)
        return m

    def addAction(self, a):
        self.actions.append(a)


class FakeNote:
    guid = "g1"
    tags = ["t"]

    def items(self):
        return [("Front", "Q"), ("Back", "A")]

    def note_type(self):
        return {"name": "Basic"}

    def cards(self):
        return [types.SimpleNamespace(odid=0, did=1)]


QUERIES = []
CONFIG = {}
STATE = {}


def _scalar(sql, *args):
    QUERIES.append(sql)
    if "type = 1" in sql:
        return STATE["n_reviews"]
    if "between" in sql:
        return STATE["match"]
    return STATE["last_ms"]


class FakeSched:
    today = 1000

    @property
    def day_cutoff(self):
        if "no_cutoff" in STATE:
            raise AttributeError("sem day_cutoff")
        return STATE["cutoff"]


class FakeCol:
    sched = FakeSched()
    db = types.SimpleNamespace(scalar=_scalar, list=lambda sql, *a: [3, 3, 1])
    decks = types.SimpleNamespace(
        name=lambda did: f"Deck{did}",
        get=lambda did, default=True: {"resched": False},
        config_dict_for_deck_id=lambda did: {"desiredRetention": 0.9},
    )

    def get_config(self, key, default=None):
        if "raise" in CONFIG:
            raise AttributeError("sem get_config")
        return CONFIG.get(key, default)

    def find_notes(self, q):
        return [11, 12]

    def get_note(self, nid):
        return FakeNote()


def make_card(**over):
    base = dict(id=1, nid=2, ord=0, did=3, odid=0, due=990, odue=0, type=2, queue=2, reps=6, lapses=0, ivl=30, factor=2500, memory_state=None, note=lambda: FakeNote())
    base.update(over)
    return types.SimpleNamespace(**base)


class SmokeTest(unittest.TestCase):
    def setUp(self):
        CONFIG.clear()
        CONFIG["fsrs"] = True
        now = time.time()
        STATE.clear()
        STATE.update(cutoff=int(now) + 3600, last_ms=int((now - 5 * 86400) * 1000), n_reviews=3, match=1)
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DFC_PROBE_USER_FILES"] = self.tmp.name
        self.cfg = {"enabled": True, "anonymize_export": False}
        self.hooks = types.SimpleNamespace(reviewer_did_show_question=[], reviewer_did_show_answer=[], reviewer_did_answer_card=[])
        self.menu_tools = Menu()
        self.messages, self.dialog = [], {"path": ""}
        mw = types.SimpleNamespace(
            col=FakeCol(),
            pm=types.SimpleNamespace(name="Perfil"),
            addonManager=types.SimpleNamespace(getConfig=lambda name: self.cfg, writeConfig=lambda name, c: self.cfg.update(c)),
            form=types.SimpleNamespace(menuTools=self.menu_tools),
        )
        aqt = types.ModuleType("aqt")
        aqt.mw, aqt.gui_hooks = mw, self.hooks
        qt = types.ModuleType("aqt.qt")
        qt.QAction = Action
        qt.QFileDialog = types.SimpleNamespace(getSaveFileName=lambda *a, **k: (self.dialog["path"], ""))
        qt.QInputDialog = types.SimpleNamespace(getText=lambda *a, **k: ("deck:x", True))
        utils = types.ModuleType("aqt.utils")
        utils.showInfo = self.messages.append
        utils.tooltip = self.messages.append
        self.saved = {m: sys.modules.get(m) for m in ("aqt", "aqt.qt", "aqt.utils")}
        sys.modules.update({"aqt": aqt, "aqt.qt": qt, "aqt.utils": utils})
        for name in [m for m in sys.modules if m == "dfc_probe" or m.startswith("dfc_probe.")]:
            del sys.modules[name]
        self.mod = importlib.import_module("dfc_probe")

    def tearDown(self):
        for m, v in self.saved.items():
            if v is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = v
        for name in [m for m in sys.modules if m == "dfc_probe" or m.startswith("dfc_probe.")]:
            del sys.modules[name]
        os.environ.pop("DFC_PROBE_USER_FILES", None)
        self.tmp.cleanup()

    def review(self, card, ease=3):
        self.hooks.reviewer_did_show_question[0](card)
        self.hooks.reviewer_did_show_answer[0](card)
        self.hooks.reviewer_did_answer_card[0](None, card, ease)

    def menu_action(self, label):
        return next(a for a in self.menu_tools.menus[0].actions if a.text == label)

    def test_hooks_log_an_event_with_card_state(self):
        QUERIES.clear()
        self.review(make_card())
        # entradas manuais do revlog (ease 0, por exemplo "definir data") não contam como revisão
        self.assertTrue(any("max(id)" in q and "ease > 0" in q for q in QUERIES), QUERIES)
        (row,) = self.mod._store.rows()
        self.assertEqual((row["note_id"], row["card_id"], row["reps"], row["lapses"], row["ivl"]), (2, 1, 6, 0, 30))
        self.assertEqual((row["model_name"], row["deck_name"], row["mode"]), ("Basic", "Deck3", "regular"))
        self.assertEqual((row["overdue_days"], row["last_ease"], row["ease"]), (10, 3, 3))
        self.assertIsNotNone(row["days_since_last_review"])
        self.assertIsNotNone(row["t_reveal_ms"])

    def test_logs_scheduler_and_desired_retention(self):
        self.review(make_card())
        (row,) = self.mod._store.rows()
        self.assertEqual((row["scheduler"], row["desired_retention"]), ("fsrs", 0.9))

    def test_sm2_when_fsrs_is_off(self):
        CONFIG["fsrs"] = False
        self.review(make_card())
        (row,) = self.mod._store.rows()
        self.assertEqual((row["scheduler"], row["desired_retention"]), ("sm2", None))

    def test_sm2_when_fsrs_key_is_missing(self):
        CONFIG.clear()  # coleção que nunca ligou o FSRS não tem a chave
        self.review(make_card())
        (row,) = self.mod._store.rows()
        self.assertEqual((row["scheduler"], row["desired_retention"]), ("sm2", None))

    def test_unknown_scheduler_is_null(self):
        CONFIG["raise"] = True
        self.review(make_card())
        (row,) = self.mod._store.rows()
        self.assertEqual((row["scheduler"], row["desired_retention"]), (None, None))

    def test_logs_review_count_profile_and_same_day(self):
        self.review(make_card())
        (row,) = self.mod._store.rows()
        self.assertEqual((row["n_reviews"], row["profile"], row["same_day"]), (3, "Perfil", 0))

    def test_same_day_follows_the_anki_day_boundary(self):
        cutoff = STATE["cutoff"]
        for card_id, last_s in ((1, cutoff - 600), (2, cutoff - 86_400 - 600)):
            STATE["last_ms"] = last_s * 1000
            self.review(make_card(id=card_id))
        self.assertEqual([r["same_day"] for r in self.mod._store.rows()], [1, 0])

    def test_same_day_falls_back_to_half_a_day_without_day_cutoff(self):
        STATE["no_cutoff"] = True
        now_ms = time.time() * 1000
        for card_id, hours_ago in ((1, 1), (2, 48)):
            STATE["last_ms"] = int(now_ms - hours_ago * 3_600_000)
            self.review(make_card(id=card_id))
        self.assertEqual([r["same_day"] for r in self.mod._store.rows()], [1, 0])

    def test_export_reconciles_events_with_the_revlog(self):
        self.review(make_card())
        out = os.path.join(self.tmp.name, "ev.csv")
        self.dialog["path"] = out
        for match in (1, 0):
            STATE["match"] = match
            self.menu_action("Exportar eventos (CSV)...").triggered.emit(False)
            with open(out, newline="", encoding="utf-8") as f:
                (row,) = list(csv.DictReader(f))
            self.assertEqual(row["revlog_match"], str(match))

    def test_filtered_deck_without_resched_is_marked(self):
        self.review(make_card(odid=7, odue=985))
        (row,) = self.mod._store.rows()
        self.assertEqual((row["in_filtered"], row["resched"], row["mode"], row["deck_id"], row["overdue_days"]), (1, 0, "filtered_no_resched", 7, 15))

    def test_toggle_off_stops_logging(self):
        self.menu_tools.menus[0].actions[0].toggled.emit(False)
        self.assertFalse(self.cfg["enabled"])
        self.review(make_card())
        self.assertEqual(self.mod._store.count(), 0)

    def test_hook_errors_are_swallowed_and_logged(self):
        self.hooks.reviewer_did_show_question[0](types.SimpleNamespace(id=1))  # sem atributos: o snapshot falha
        self.assertEqual(self.mod._store.count(), 0)
        self.assertTrue(os.path.exists(self.mod.ERR_LOG))

    def test_menu_actions_work_without_arguments(self):
        self.review(make_card())
        self.menu_action("Status").triggered.emit(False)
        self.assertTrue(any("Eventos registrados: 1" in m for m in self.messages))
        out = os.path.join(self.tmp.name, "ev.csv")
        self.dialog["path"] = out
        self.menu_action("Exportar eventos (CSV)...").triggered.emit(False)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(len(f.read().strip().splitlines()), 2)  # cabeçalho + 1 evento
        notes = os.path.join(self.tmp.name, "notas.jsonl")
        self.dialog["path"] = notes
        self.menu_action("Exportar notas para variantes (JSONL)...").triggered.emit(False)
        with open(notes, encoding="utf-8") as f:
            recs = [json.loads(line) for line in f]
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["fields"], {"Front": "Q", "Back": "A"})
        self.assertFalse(os.path.exists(self.mod.ERR_LOG))


if __name__ == "__main__":
    unittest.main()
