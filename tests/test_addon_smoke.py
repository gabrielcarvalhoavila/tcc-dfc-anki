"""Teste de fumaça do add-on com um Anki simulado (aqt falso): ligação dos ganchos, menu e exportações.

Não substitui testar no Anki real: só pega erros de sintaxe, de ligação e de lógica.
"""
import csv
import datetime
import hashlib
import importlib
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "addon"))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from dfc_pipeline.llm import FakeLLM  # noqa: E402

LIVE_LABEL = "Gerar variantes do cartão atual (LLM)..."


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
        self.visible = True

    def setCheckable(self, v):
        pass

    def setChecked(self, v):
        self.checked = v

    def setVisible(self, v):
        self.visible = bool(v)


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

    def __init__(self):
        self.fields = list(STATE.get("fields", ["Q", "A"]))

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

    def set_config(self, key, value):
        CONFIG[key] = value

    def find_notes(self, q):
        return [11, 12]

    def get_note(self, nid):
        return FakeNote()

    def new_note(self, notetype):
        return types.SimpleNamespace(fields=["", ""], tags=[])


def make_card(**over):
    base = dict(
        id=1, nid=2, ord=0, did=3, odid=0, due=990, odue=0, type=2, queue=2, reps=6, lapses=0, ivl=30, factor=2500,
        memory_state=None, note=lambda: FakeNote(), template=lambda: {"name": "Card 1"},
    )
    base.update(over)
    return types.SimpleNamespace(**base)


def _render(note):
    if "render_error" in STATE:
        raise RuntimeError("falha ao renderizar")
    q = note.fields[0]
    return types.SimpleNamespace(question_text=q, answer_text=q + "<hr id=answer>" + note.fields[1])


class FakeRenderContext:
    @staticmethod
    def from_card_layout(note, card, notetype, template, fill_empty):
        return types.SimpleNamespace(render=lambda: _render(note))


def sha1_12(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def bank_bytes(fields=("Q", "A"), note_id=2):
    entry = {
        "kind": "basic",
        "ords": [0],
        "q_field": 0,
        "fields_hash": sha1_12("\x1f".join(fields)),
        "variants": [
            {"id": f"{note_id}-paraphrase-aaa", "type": "paraphrase", "text": "Variante A?"},
            {"id": f"{note_id}-reorder-bbb", "type": "reorder", "text": "Variante B?"},
        ],
    }
    return json.dumps({"schema": 2, "generated_at": "t", "generator_models": ["g"], "judge_models": ["j"], "notes": {str(note_id): entry}}).encode()


class ContextMenu:
    def __init__(self):
        self.actions = []

    def addAction(self, text):
        action = Action(text)
        self.actions.append(action)
        return action


class FakeQueryOp:
    """QueryOp do Anki, mas síncrono: roda a operação e chama success ou failure."""

    def __init__(self, *, parent, op, success):
        self.op, self.success, self.on_failure = op, success, None

    def failure(self, fn):
        self.on_failure = fn
        return self

    def with_progress(self, label=None):
        return self

    def run_in_background(self):
        try:
            result = self.op(None)
        except Exception as e:
            self.on_failure(e)
            return
        self.success(result)


class FakeButton:
    def __init__(self, text):
        self.text, self.clicked = text, Signal()


class FakeButtonBox:
    def __init__(self):
        self.buttons = []

    def addButton(self, text, role):
        button = FakeButton(text)
        self.buttons.append(button)
        return button


class FakeDialog:
    shown = False

    def show(self):
        self.shown = True


class ClozeNote(FakeNote):
    """Ficha Cloze com duas lacunas (texto longo o bastante para entrar no pipeline)."""

    def __init__(self, text="A {{c1::mitose}} ocorre em células somáticas e a {{c1::meiose}} forma os gametas nos seres vivos."):
        self.fields = [text, ""]

    def items(self):
        return [("Text", self.fields[0]), ("Extra", "")]

    def note_type(self):
        return {"name": "Cloze"}


class SmokeTest(unittest.TestCase):
    def setUp(self):
        CONFIG.clear()
        CONFIG["fsrs"] = True
        now = time.time()
        STATE.clear()
        STATE.update(cutoff=int(now) + 3600, last_ms=int((now - 5 * 86400) * 1000), n_reviews=3, match=1)
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DFC_PROBE_USER_FILES"] = self.tmp.name
        today = datetime.date.today()
        self.cfg = {
            "enabled": True,
            "anonymize_export": False,
            "draw_enabled": True,
            "draw_start": (today - datetime.timedelta(days=1)).isoformat(),
            "draw_end": (today + datetime.timedelta(days=30)).isoformat(),
            "bad_shortcut": "x",
        }
        self.hooks = types.SimpleNamespace(
            reviewer_did_show_question=[],
            reviewer_did_show_answer=[],
            reviewer_did_answer_card=[],
            card_will_show=[],
            state_shortcuts_will_change=[],
            reviewer_will_show_context_menu=[],
            profile_will_close=[],
            deck_browser_will_show_options_menu=[],
        )
        with open(os.path.join(self.tmp.name, "variant_bank.json"), "wb") as f:
            f.write(bank_bytes())
        self.menu_tools = Menu()
        self.messages, self.dialog = [], {"path": ""}
        self.texts, self.config_updated, self.added = [], [], []
        mw = types.SimpleNamespace(
            col=FakeCol(),
            pm=types.SimpleNamespace(name="Perfil"),
            addonManager=types.SimpleNamespace(
                getConfig=lambda name: self.cfg,
                writeConfig=lambda name, c: self.cfg.update(c),
                setConfigUpdatedAction=lambda name, fn: self.config_updated.append(fn),
            ),
            form=types.SimpleNamespace(menuTools=self.menu_tools),
            state="review",
            reviewer=types.SimpleNamespace(card=make_card()),
        )
        self.mw = mw
        aqt = types.ModuleType("aqt")
        aqt.mw, aqt.gui_hooks = mw, self.hooks
        aqt.dialogs = types.SimpleNamespace(open=lambda name, parent: types.SimpleNamespace(set_note=lambda note, deck_id: self.added.append((name, note, deck_id))))
        qt = types.ModuleType("aqt.qt")
        qt.QAction = Action
        qt.QDialogButtonBox = types.SimpleNamespace(ButtonRole=types.SimpleNamespace(ActionRole="action"))
        qt.QFileDialog = types.SimpleNamespace(
            getSaveFileName=lambda *a, **k: (self.dialog["path"], ""),
            getOpenFileName=lambda *a, **k: (self.dialog.get("open", ""), ""),
        )
        qt.QInputDialog = types.SimpleNamespace(getText=lambda *a, **k: ("deck:x", True))
        utils = types.ModuleType("aqt.utils")
        utils.showInfo = self.messages.append
        utils.tooltip = self.messages.append
        def show_text(text, **kwargs):
            dialog, box = FakeDialog(), FakeButtonBox()
            self.texts.append((text, kwargs, dialog, box))
            return dialog, box

        utils.showText = show_text
        operations = types.ModuleType("aqt.operations")
        operations.QueryOp = FakeQueryOp
        anki = types.ModuleType("anki")
        anki_template = types.ModuleType("anki.template")
        anki_template.TemplateRenderContext = FakeRenderContext
        anki.template = anki_template
        names = ("aqt", "aqt.qt", "aqt.utils", "aqt.operations", "anki", "anki.template")
        self.saved = {m: sys.modules.get(m) for m in names}
        sys.modules.update({"aqt": aqt, "aqt.qt": qt, "aqt.utils": utils, "aqt.operations": operations, "anki": anki, "anki.template": anki_template})
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

    # ---- sorteio e exibição das variantes ----

    def force(self, probability):
        self.mod.variants.VARIANT_PROBABILITY = probability

    def study(self, card, ease=3, question="Q", answer="Q<hr id=answer>A"):
        """Sequência do Reviewer: texto da pergunta, pergunta mostrada, texto da resposta, resposta mostrada, nota."""
        shown_q = self.hooks.card_will_show[0](question, card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shown_a = self.hooks.card_will_show[0](answer, card, "reviewAnswer")
        self.hooks.reviewer_did_show_answer[0](card)
        self.hooks.reviewer_did_answer_card[0](None, card, ease)
        return shown_q, shown_a

    def rows(self):
        return self.mod._store.rows()

    def test_variant_is_shown_on_both_sides_and_logged(self):
        self.force(1.0)
        q, a = self.study(make_card())
        self.assertIn(q, ("Variante A?", "Variante B?"))
        self.assertEqual(a, q + "<hr id=answer>A")
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["shown_ok"], row["draw_note"], row["same_day"]), ("variant", 1, "ok", 0))
        self.assertIn(row["variant_id"], ("2-paraphrase-aaa", "2-reorder-bbb"))
        self.assertEqual(row["shown_hash"], sha1_12(q))
        self.assertTrue(row["draw_seed"] and row["bank_hash"])
        self.assertEqual((row["note_kind"], row["n_blanks"], row["has_image"]), ("basic", None, 0))

    def test_original_arm_shows_the_card_untouched(self):
        self.force(0.0)
        self.assertEqual(self.study(make_card()), ("Q", "Q<hr id=answer>A"))
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["shown_ok"], row["variant_id"], row["shown_hash"]), ("original", 1, None, sha1_12("Q")))
        self.assertEqual(row["note_kind"], "basic")  # as covariáveis da nota também vêm no braço original

    def test_same_day_exposure_is_logged_without_a_draw(self):
        self.force(1.0)
        STATE["last_ms"] = (STATE["cutoff"] - 600) * 1000
        self.assertEqual(self.study(make_card())[0], "Q")
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["draw_note"], row["same_day"]), (None, "same_day", 1))
        self.assertIsNone(row["note_kind"])  # sem sorteio não há covariáveis da nota

    def test_ineligible_cards_are_not_drawn(self):
        self.force(1.0)
        self.study(make_card(id=1, reps=0))
        STATE["fields"] = ["Q editada", "A"]
        self.study(make_card(id=2))
        STATE.pop("fields")
        self.study(make_card(id=3, ord=1))
        self.study(make_card(id=4, nid=99))
        self.assertEqual([r["draw_note"] for r in self.rows()], ["reps0", "note_edited", "ord_mismatch", "no_entry"])
        self.assertTrue(all(r["arm"] is None for r in self.rows()))

    def test_outside_the_window_or_switched_off_nothing_is_drawn(self):
        self.force(1.0)
        today = datetime.date.today()
        self.cfg["draw_start"] = (today + datetime.timedelta(days=5)).isoformat()
        self.study(make_card(id=1))
        self.cfg["draw_start"] = (today - datetime.timedelta(days=1)).isoformat()
        self.cfg["draw_enabled"] = False
        self.study(make_card(id=2))
        self.assertEqual([r["draw_note"] for r in self.rows()], ["outside_window", "off"])

    def test_logging_off_leaves_the_card_alone(self):
        self.force(1.0)
        self.cfg["enabled"] = False
        self.assertEqual(self.study(make_card()), ("Q", "Q<hr id=answer>A"))
        self.assertEqual(self.mod._store.count(), 0)

    def test_decision_is_kept_for_the_whole_exposure(self):
        self.force(1.0)
        card = make_card()
        first = self.hooks.card_will_show[0]("Q", card, "reviewQuestion")
        self.force(0.0)  # um novo sorteio daria o original
        again = self.hooks.card_will_show[0]("Q", card, "reviewQuestion")  # por exemplo, depois de editar a nota
        self.assertEqual(first, again)
        self.assertNotEqual(first, "Q")

    def test_variants_do_not_repeat_on_the_same_card(self):
        self.force(1.0)
        shown = [self.study(make_card(reps=reps))[0] for reps in (6, 7)]  # reps avança: respostas válidas, não Ctrl+Z
        self.assertEqual(sorted(shown), ["Variante A?", "Variante B?"])

    def test_template_mismatch_falls_back_to_the_original_text(self):
        self.force(1.0)
        q, a = self.study(make_card(), question="Texto sem o original", answer="Outra resposta")
        self.assertEqual((q, a), ("Texto sem o original", "Outra resposta"))
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["shown_ok"], row["draw_note"]), ("variant", 0, "template_mismatch"))

    def test_answer_side_mismatch_invalidates_the_exposure(self):
        self.force(1.0)
        q, a = self.study(make_card(), answer="Resposta sem a pergunta")
        self.assertNotEqual(q, "Q")
        self.assertEqual(a, "Resposta sem a pergunta")
        (row,) = self.rows()
        self.assertEqual((row["shown_ok"], row["draw_note"]), (0, "answer_mismatch"))

    def test_render_error_falls_back_and_is_logged(self):
        self.force(1.0)
        STATE["render_error"] = True
        self.assertEqual(self.study(make_card()), ("Q", "Q<hr id=answer>A"))
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["shown_ok"], row["draw_note"]), ("variant", 0, "render_error"))
        self.assertTrue(os.path.exists(self.mod.ERR_LOG))

    def test_bad_variant_shortcut_marks_the_current_exposure(self):
        self.force(1.0)
        shortcuts = []
        self.hooks.state_shortcuts_will_change[0]("deckBrowser", shortcuts)
        self.assertEqual(shortcuts, [])
        self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
        ((key, press),) = shortcuts
        self.assertEqual(key, "x")
        card = make_card()
        self.hooks.card_will_show[0]("Q", card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        press()
        self.hooks.reviewer_did_answer_card[0](None, card, 3)
        (row,) = self.rows()
        self.assertEqual(row["flag_bad"], 1)

    def test_bad_variant_shortcut_ignores_the_original_arm(self):
        self.force(0.0)
        card = make_card()
        self.hooks.card_will_show[0]("Q", card, "reviewQuestion")
        shortcuts = []
        self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
        shortcuts[0][1]()
        self.hooks.reviewer_did_answer_card[0](None, card, 3)
        self.assertTrue(any("não mostra uma variante" in m for m in self.messages))
        self.assertEqual(self.rows()[0]["flag_bad"], 0)

    def test_bad_variant_menu_marks_the_last_answer_and_context_menu_entry_exists(self):
        self.force(1.0)
        self.study(make_card())
        self.menu_action("Marcar a última resposta como variante ruim").triggered.emit(False)
        self.assertEqual(self.rows()[-1]["flag_bad"], 1)
        menu = ContextMenu()
        self.hooks.reviewer_will_show_context_menu[0](None, menu)
        (action,) = menu.actions
        self.assertEqual(action.text, "Variante ruim (DFC Probe)")
        self.force(0.0)
        self.study(make_card(id=7))
        self.menu_action("Marcar a última resposta como variante ruim").triggered.emit(False)
        self.assertEqual(self.rows()[-1]["flag_bad"], 0)  # a última foi o original

    def test_import_bank_from_the_menu_and_status(self):
        path = os.path.join(self.tmp.name, "novo.json")
        with open(path, "wb") as f:
            f.write(bank_bytes(note_id=77))
        self.dialog["open"] = path
        self.menu_action("Importar banco de variantes...").triggered.emit(False)
        self.assertTrue(any("Banco importado: 1 notas, 2 variantes" in m for m in self.messages))
        self.menu_action("Status").triggered.emit(False)
        self.assertTrue(any("Banco de variantes: 1 notas, 2 variantes" in m and "Sorteio: ligado" in m for m in self.messages))
        bad = os.path.join(self.tmp.name, "ruim.json")
        with open(bad, "wb") as f:
            f.write(b"nao e json")
        self.dialog["open"] = bad
        self.menu_action("Importar banco de variantes...").triggered.emit(False)
        self.assertTrue(any("Não foi possível importar" in m for m in self.messages))
        self.force(1.0)
        self.assertEqual(self.study(make_card(nid=2))[0], "Q")  # o banco novo só tem a nota 77

    def test_fake_bank_never_draws_unless_allowed(self):
        fake = json.loads(bank_bytes())
        fake["generator_models"] = ["fake"]
        path = os.path.join(self.tmp.name, "fake.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fake, f)
        self.dialog["open"] = path
        self.menu_action("Importar banco de variantes...").triggered.emit(False)
        self.force(1.0)
        self.assertEqual(self.study(make_card())[0], "Q")
        self.menu_action("Status").triggered.emit(False)
        self.assertTrue(any("BANCO DE TESTE" in m and "não sorteia" in m for m in self.messages))
        self.cfg["allow_fake_bank"] = True
        self.assertNotEqual(self.study(make_card(id=9))[0], "Q")
        self.assertEqual([r["draw_note"] for r in self.rows()], ["fake_bank", "ok"])

    def test_conflicting_bad_shortcut_falls_back_to_x_and_warns_once(self):
        self.cfg["bad_shortcut"] = "b"  # no Anki, b abre o Navegador: a tecla repetida não faria nada
        for _ in range(2):
            shortcuts = []
            self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
            self.assertEqual([k for k, _f in shortcuts], ["x"])
        self.assertEqual(sum("'b' já é tecla do Anki" in m for m in self.messages), 1)
        self.menu_action("Status").triggered.emit(False)
        self.assertTrue(any("Atalho de variante ruim: x ('b' configurada conflita com o Anki)" in m for m in self.messages))
        taken = [("x", lambda: None)]  # outro add-on já usa o x
        self.hooks.state_shortcuts_will_change[0]("review", taken)
        self.assertEqual(len(taken), 1)
        self.cfg["bad_shortcut"] = ""
        free = []
        self.hooks.state_shortcuts_will_change[0]("review", free)
        self.assertEqual(free, [])

    def test_after_ctrl_z_the_card_keeps_the_same_arm_and_variant(self):
        self.force(1.0)
        first_q, _ = self.study(make_card())
        self.force(0.0)  # um novo sorteio daria o original
        again_q, _ = self.study(make_card())  # Ctrl+Z: mesmo cartão, mesmo reps
        self.assertEqual(first_q, again_q)
        self.assertNotEqual(again_q, "Q")
        first, again = self.rows()
        self.assertEqual((first["arm"], first["draw_note"]), ("variant", "ok"))
        self.assertEqual((again["arm"], again["draw_note"], again["variant_id"]), ("variant", "undo_redo", first["variant_id"]))
        self.assertEqual(again["draw_seed"], first["draw_seed"])

    def test_after_ctrl_z_an_original_stays_original(self):
        self.force(0.0)
        self.study(make_card())
        self.force(1.0)
        self.assertEqual(self.study(make_card())[0], "Q")
        self.assertEqual([r["arm"] for r in self.rows()], ["original", "original"])

    def test_another_card_in_between_means_a_fresh_draw(self):
        self.force(1.0)
        self.study(make_card(id=1))
        self.study(make_card(id=2))
        self.force(0.0)
        self.study(make_card(id=1))  # a última resposta foi a do cartão 2: não herda
        self.assertEqual([(r["arm"], r["draw_note"]) for r in self.rows()], [("variant", "ok"), ("variant", "ok"), ("original", "ok")])

    def test_after_ctrl_z_the_bad_flag_of_the_variant_stays(self):
        self.force(1.0)
        shortcuts = []
        self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
        card = make_card()
        self.hooks.card_will_show[0]("Q", card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shortcuts[0][1]()
        self.hooks.reviewer_did_answer_card[0](None, card, 3)
        self.study(make_card())  # Ctrl+Z e responder de novo, sem apertar a tecla outra vez
        self.study(make_card())
        self.assertEqual([r["flag_bad"] for r in self.rows()], [1, 1, 1])
        self.study(make_card(reps=7))  # resposta válida: a marca não passa para a exposição seguinte
        self.assertEqual(self.rows()[-1]["flag_bad"], 0)

    def test_after_ctrl_z_a_variant_marked_from_the_menu_stays_marked(self):
        self.force(1.0)
        self.study(make_card())
        self.menu_action("Marcar a última resposta como variante ruim").triggered.emit(False)
        self.study(make_card())  # Ctrl+Z e responder de novo
        self.assertEqual([r["flag_bad"] for r in self.rows()], [1, 1])

    def test_draw_switch_in_the_menu_writes_the_config(self):
        draw = self.menu_tools.menus[0].actions[1]
        draw.toggled.emit(False)
        self.assertFalse(self.cfg["draw_enabled"])
        draw.toggled.emit(True)
        self.assertTrue(self.cfg["draw_enabled"])

    def click_live(self):
        self.menu_action(LIVE_LABEL).triggered.emit(False)

    def test_live_item_is_hidden_by_default_and_follows_the_saved_config(self):
        action = self.menu_action(LIVE_LABEL)
        self.assertFalse(action.visible)
        self.config_updated[0]({"live_enabled": True})
        self.assertTrue(action.visible)
        self.config_updated[0]({"live_enabled": False})
        self.assertFalse(action.visible)

    def test_live_off_only_explains_and_does_not_load_the_pipeline(self):
        self.click_live()
        self.assertIn("desligada", self.messages[-1])
        self.assertNotIn("dfc_probe.live", sys.modules)
        self.assertEqual(self.texts, [])

    def test_live_shows_variants_without_touching_events_bank_or_note(self):
        self.cfg["live_enabled"] = True
        bank_path = os.path.join(self.tmp.name, "variant_bank.json")
        with open(bank_path, "rb") as f:
            bank_before = f.read()
        live = importlib.import_module("dfc_probe.live")
        with mock.patch.object(live, "build_clients", return_value=(FakeLLM(), FakeLLM())):
            self.click_live()
        ((text, kwargs, dialog, box),) = self.texts
        self.assertEqual((kwargs["type"], kwargs["run"]), ("html", False))
        self.assertTrue(dialog.shown)
        self.assertIn("Variantes", text)
        self.assertEqual([b.text for b in box.buttons], ["Criar cartão: Paráfrase", "Criar cartão: Reordenação", "Criar cartão: Formato", "Criar cartão: Pistas iniciais", "Guardar no banco pessoal..."])
        self.assertEqual(self.mod._store.count(), 0)
        self.assertEqual(self.added, [])
        with open(bank_path, "rb") as f:
            self.assertEqual(f.read(), bank_before)

    def click_variant_button(self, card):
        self.cfg["live_enabled"] = True
        self.mw.reviewer.card = card
        live = importlib.import_module("dfc_probe.live")
        with mock.patch.object(live, "build_clients", return_value=(FakeLLM(), FakeLLM())):
            self.click_live()
        ((_text, _kwargs, _dialog, box),) = self.texts
        box.buttons[0].clicked.emit(False)

    def test_variant_button_opens_the_add_window_prefilled_and_saves_nothing(self):
        self.click_variant_button(make_card())
        ((name, note, deck_id),) = self.added
        self.assertEqual((name, deck_id), ("AddCards", 3))  # o baralho do cartão original
        self.assertEqual(note.fields, ["Reformulação do tipo paraphrase desta pergunta: Q", "A"])
        self.assertEqual(note.tags, ["t", "dfc_variante"])
        self.assertEqual(self.mod._store.count(), 0)  # FakeCol não tem add_note: gravar na coleção falharia

    def test_variant_button_on_a_cloze_card_rebuilds_the_blanks(self):
        self.click_variant_button(make_card(note=lambda: ClozeNote()))
        ((_name, note, _deck),) = self.added
        self.assertEqual(note.fields, ["Em outras palavras: {{c1::mitose}} e {{c1::meiose}}", ""])

    def test_card_that_cannot_have_variants_gets_a_short_message_not_a_window(self):
        self.cfg["live_enabled"] = True
        self.mw.reviewer.card = make_card(note=lambda: ClozeNote("A {{c1::mitose}} divide."))
        gen, judge = FakeLLM(), FakeLLM()
        live = importlib.import_module("dfc_probe.live")
        with mock.patch.object(live, "build_clients", return_value=(gen, judge)):
            self.click_live()
        self.assertIn("texto visível curto demais", self.messages[-1])
        self.assertEqual((self.texts, gen.calls, judge.calls), ([], [], []))

    def test_live_outside_the_review_screen_asks_for_a_card(self):
        self.cfg["live_enabled"] = True
        self.mw.state = "deckBrowser"
        self.click_live()
        self.assertIn("abra um cartão", self.messages[-1])
        self.assertEqual(self.texts, [])

    def test_live_reports_a_missing_key_without_calling_the_llm(self):
        self.cfg.update(live_enabled=True, live_api_key="", live_base_url="https://exemplo.test/v1", live_gen_model="g", live_judge_model="j")
        self.click_live()
        self.assertIn("live_api_key", self.messages[-1])
        self.assertEqual(self.texts, [])
        self.cfg["live_api_key"] = "chave"
        self.cfg["live_gen_model"] = ""
        self.click_live()
        self.assertIn("live_gen_model", self.messages[-1])
        self.assertEqual(self.texts, [])

    def test_live_failure_is_shown_to_the_user(self):
        self.cfg["live_enabled"] = True
        live = importlib.import_module("dfc_probe.live")
        with mock.patch.object(live, "build_clients", return_value=(FakeLLM(), FakeLLM())):
            with mock.patch.object(live, "generate_variants", side_effect=RuntimeError("rede caiu")):
                self.click_live()
        self.assertIn("rede caiu", self.messages[-1])
        self.assertEqual(self.texts, [])

    def test_status_reports_the_live_switch_and_whether_the_key_is_filled_without_showing_it(self):
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("Variante sob demanda (LLM): desligada", self.messages[-1])
        self.cfg["live_enabled"] = True
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("Variante sob demanda (LLM): ligada (chave ausente)", self.messages[-1])
        self.cfg["live_api_key"] = "segredo-123"
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("ligada (chave preenchida)", self.messages[-1])
        self.assertNotIn("segredo-123", self.messages[-1])


if __name__ == "__main__":
    unittest.main()
