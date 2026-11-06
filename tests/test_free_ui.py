"""Testes das telas do uso livre (v0.5) com o Qt real em modo offscreen e um Anki simulado. Pulam se o PyQt6 não estiver instalado."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import addon_pure
from dfc_pipeline.llm import FakeLLM

HAS_QT = importlib.util.find_spec("PyQt6") is not None

if HAS_QT:
    from PyQt6 import QtCore, QtGui, QtWidgets

    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

F = addon_pure.load("free")
B = addon_pure.load("batch")
FM = addon_pure.load("freemode")
UI = addon_pure.load("free_ui")
L = addon_pure.load("live")
V = addon_pure.load("variants")

DECKS = [(1, "Biologia"), (2, "Biologia::Genética"), (3, "História")]


def basic(i):
    return {"note_id": i, "guid": f"g{i}", "model": "Basic", "fields": {"Front": f"Qual organela produz energia na célula eucarionte número {i}?", "Back": "Mitocôndria"}, "tags": [], "decks": ["D"]}


def cloze_with_image(i):
    text = f'<img src="figura.png"><br>A {{{{c1::mitose}}}} ocorre em células somáticas e a {{{{c1::meiose}}}} forma os gametas no ser vivo {i}.'
    return {"note_id": i, "guid": f"g{i}", "model": "Cloze", "fields": {"Text": text, "Extra": ""}, "tags": [], "decks": ["D"]}


class SyncQueryOp:
    """QueryOp do Anki, mas síncrono."""

    def __init__(self, *, parent, op, success):
        self.op, self.success, self.on_failure = op, success, None

    def failure(self, fn):
        self.on_failure = fn
        return self

    def with_progress(self, label=None):
        return self

    def without_collection(self):
        return self

    def run_in_background(self):
        try:
            result = self.op(None)
        except Exception as e:
            self.on_failure(e)
            return
        self.success(result)


class FakeDecks:
    def all_names_and_ids(self, skip_empty_default=False, include_filtered=True):
        return [types.SimpleNamespace(id=i, name=n) for i, n in reversed(DECKS)]

    def get_current_id(self):
        return 2


class FakeCol:
    def __init__(self):
        self.config = {}
        self.decks = FakeDecks()

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def set_config(self, key, value):
        self.config[key] = value


class FileDialog:
    save, open = "", ""

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return FileDialog.save, ""

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return FileDialog.open, ""


@unittest.skipUnless(HAS_QT, "PyQt6 não instalado (opcional)")
class UiBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.col = FakeCol()
        self.shown, self.asked, self.warned, self.tips, self.texts = [], [], [], [], []
        self.answer = True
        qt = types.ModuleType("aqt.qt")
        for mod in (QtCore, QtGui, QtWidgets):
            for name in dir(mod):
                setattr(qt, name, getattr(mod, name))
        qt.QFileDialog = FileDialog
        utils = types.ModuleType("aqt.utils")
        utils.showInfo = self.shown.append
        utils.showWarning = lambda text, parent=None, **kw: self.warned.append(text)
        utils.tooltip = self.tips.append
        utils.askUser = lambda text, parent=None, **kw: (self.asked.append(text), self.answer)[1]
        utils.showText = lambda text, **kw: self.texts.append((text, kw))
        operations = types.ModuleType("aqt.operations")
        operations.QueryOp = SyncQueryOp
        aqt = types.ModuleType("aqt")
        self.patcher = mock.patch.dict(sys.modules, {"aqt": aqt, "aqt.qt": qt, "aqt.utils": utils, "aqt.operations": operations})
        self.patcher.start()
        UI._ui = None
        self.mw = QtWidgets.QWidget()  # o mw real é uma janela Qt: as telas a usam como pai
        self.mw.col = self.col
        self.mw.taskman = types.SimpleNamespace(run_on_main=lambda fn: fn())
        self.errors = []
        env = FM.Env(
            col=lambda: self.col, user_files=self.tmp.name, snapshot=lambda c: {}, render=lambda *a, **k: ("", ""), munge=lambda t: t,
            official_has=lambda nid: False, study_drew=lambda c: False, mark_event=lambda c: None, expand_decks=lambda ids: set(ids),
            tooltip=self.tips.append, log_error=lambda: self.errors.append(1),
        )
        self.fm = FM.FreeMode(env)

    def tearDown(self):
        self.patcher.stop()
        UI._ui = None
        self.tmp.cleanup()

    def scripted_exec(self, cls_name, script, result=1):
        """Troca o exec() modal da tela por um roteiro que mexe nos widgets, como a pessoa faria."""
        cls = getattr(UI._widgets(), cls_name)

        def fake_exec(dialog):
            script(dialog)
            return result

        return mock.patch.object(cls, "exec", fake_exec)


class SettingsDialogTest(UiBase):
    def make(self, settings=None):
        return UI._widgets().SettingsDialog(None, settings or F.Settings(), DECKS, "desligado; banco pessoal: 0 notas", lambda: self.tips.append("gerar"), lambda: self.tips.append("banco"))

    def test_shows_the_current_settings(self):
        s = F.Settings(enabled=True, probability=30, types=["reorder", "pergunta"], deck_ids=[2], include_learning=True, suspects_only=True, avoid_repeat=False, avoid_same_day=False, badge=True)
        d = self.make(s)
        self.assertEqual((d.enabled.isChecked(), d.spin.value(), d.slider.value()), (True, 30, 30))
        self.assertEqual([t for t, c in d.type_boxes.items() if c.isChecked()], ["reorder", "pergunta"])
        self.assertTrue(d.some_decks.isChecked() and d.deck_list.isEnabled())
        self.assertEqual([d.deck_list.item(i).text() for i in range(d.deck_list.count())], ["Biologia", "Biologia::Genética", "História"])
        self.assertEqual(d.result_settings(), s)

    def test_defaults_roundtrip(self):
        d = self.make()
        self.assertFalse(d.deck_list.isEnabled())
        self.assertEqual(d.result_settings(), F.Settings())

    def test_slider_and_spin_stay_together(self):
        d = self.make()
        d.slider.setValue(80)
        self.assertEqual(d.spin.value(), 80)
        d.spin.setValue(15)
        self.assertEqual(d.slider.value(), 15)
        self.assertEqual(d.result_settings().probability, 15)

    def test_choosing_decks(self):
        d = self.make()
        d.some_decks.setChecked(True)
        self.assertTrue(d.deck_list.isEnabled())
        d.deck_list.item(0).setCheckState(QtCore.Qt.CheckState.Checked)
        d.deck_list.item(2).setCheckState(QtCore.Qt.CheckState.Checked)
        self.assertEqual(d.result_settings().deck_ids, [1, 3])
        d.all_decks.setChecked(True)
        self.assertIsNone(d.result_settings().deck_ids)

    def test_unchecking_types(self):
        d = self.make()
        d.type_boxes["paraphrase"].setChecked(False)
        self.assertNotIn("paraphrase", d.result_settings().types)

    def test_problems_block_saving(self):
        d = self.make(F.Settings(enabled=True))
        for c in d.type_boxes.values():
            c.setChecked(False)
        self.assertEqual(d.problem(), "Escolha ao menos um tipo de variante.")
        d.accept()
        self.assertEqual(self.warned, ["Escolha ao menos um tipo de variante."])
        self.assertEqual(d.result(), 0)
        d.type_boxes["reorder"].setChecked(True)
        d.some_decks.setChecked(True)
        self.assertIn("ao menos um baralho", d.problem())
        d.all_decks.setChecked(True)
        self.assertIsNone(d.problem())
        d.accept()
        self.assertEqual(d.result(), 1)

    def test_no_problem_while_turned_off(self):
        d = self.make()
        for c in d.type_boxes.values():
            c.setChecked(False)
        self.assertIsNone(d.problem())

    def test_buttons_call_back(self):
        d = self.make()
        d.generate_button.click()
        d.bank_button.click()
        self.assertEqual(self.tips, ["gerar", "banco"])

    def test_open_settings_saves_on_ok_and_not_on_cancel(self):
        def tweak(d):
            d.enabled.setChecked(True)
            d.spin.setValue(35)

        with self.scripted_exec("SettingsDialog", tweak, result=1):
            UI.open_settings(self.mw, self.fm, lambda: None, lambda: None)
        s = self.fm.settings()
        self.assertEqual((s.enabled, s.probability), (True, 35))
        self.assertIn("ajustes das variantes salvos", self.tips[-1])
        with self.scripted_exec("SettingsDialog", lambda d: d.spin.setValue(90), result=0):
            UI.open_settings(self.mw, self.fm, lambda: None, lambda: None)
        self.assertEqual(self.fm.settings().probability, 35)

    def test_open_settings_needs_a_profile(self):
        self.mw.col = None
        UI.open_settings(self.mw, self.fm, lambda: None, lambda: None)
        self.assertIn("Abra um perfil", self.shown[-1])


class BatchDialogTest(UiBase):
    def setUp(self):
        super().setUp()
        self.analyzed, self.started = [], []
        self.dialog = UI._widgets().BatchDialog(None, DECKS, 2, self.analyzed.append, lambda p, plan: self.started.append((p, plan)))

    def test_defaults(self):
        d = self.dialog
        self.assertEqual(d.deck.currentData(), 2)
        p = d.params()
        self.assertEqual((p["deck_id"], p["children"], p["skip_new"], p["skip_suspended"]), (2, True, True, True))
        o = p["options"]
        self.assertEqual((o.workers, o.max_notes, o.reprocess, o.types), (3, 200, False, None))
        self.assertFalse(d.go.isEnabled())

    def test_type_selection_becomes_options(self):
        d = self.dialog
        for t in ("cue_swap", "pergunta", "sem_imagem", "reformat"):
            d.type_boxes[t].setChecked(False)
        self.assertEqual(d.params()["options"].types, ["paraphrase", "reorder"])

    def test_analyze_asks_for_the_plan_and_plan_enables_generate(self):
        d = self.dialog
        d.analyze_button.click()
        self.assertEqual(len(self.analyzed), 1)
        self.assertFalse(d.analyze_button.isEnabled())
        plan = B.Plan(todo=[basic(1)], examined=3)
        d.show_plan(plan)
        self.assertTrue(d.go.isEnabled() and d.analyze_button.isEnabled())
        self.assertIn("Para gerar agora: 1", d.report.toPlainText())
        d.go.click()
        self.assertEqual(self.started[0][1], plan)

    def test_empty_plan_does_not_enable_generate(self):
        self.dialog.show_plan(B.Plan(examined=5, already=5))
        self.assertFalse(self.dialog.go.isEnabled())
        self.assertIn("Já têm variantes: 5", self.dialog.report.toPlainText())

    def test_changing_any_option_discards_the_plan(self):
        d = self.dialog
        for change in (lambda: d.skip_new.setChecked(False), lambda: d.max_notes.setValue(50), lambda: d.deck.setCurrentIndex(0), lambda: d.reprocess.setChecked(True), lambda: d.type_boxes["reorder"].setChecked(False)):
            d.show_plan(B.Plan(todo=[basic(1)]))
            self.assertTrue(d.go.isEnabled())
            change()
            self.assertFalse(d.go.isEnabled())
            self.assertIsNone(d.plan)

    def test_without_types_it_refuses_to_analyze(self):
        for c in self.dialog.type_boxes.values():
            c.setChecked(False)
        self.dialog.analyze_button.click()
        self.assertEqual(self.analyzed, [])
        self.assertIn("ao menos um tipo", self.dialog.report.toPlainText())

    def test_error_is_shown(self):
        self.dialog.show_error("Falha ao analisar")
        self.assertEqual(self.dialog.report.toPlainText(), "Falha ao analisar")
        self.assertTrue(self.dialog.analyze_button.isEnabled())


class OpenBatchTest(UiBase):
    CFG = {"live_enabled": True, "live_api_key": "k", "live_base_url": "https://exemplo.test/v1", "live_gen_model": "g", "live_judge_model": "j"}

    def setUp(self):
        super().setUp()
        self.records = [basic(1), basic(2), cloze_with_image(3), basic(4)]
        self.gen, self.judge = FakeLLM(), FakeLLM()
        self.patches = [
            mock.patch.object(UI.live, "build_clients", return_value=(self.gen, self.judge)),
            mock.patch.object(UI.anki_adapter, "collect_records", side_effect=lambda col, deck_id, to_record, **kw: list(self.records)),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def run_flow(self, script, official=lambda: set()):
        with self.scripted_exec("BatchDialog", script, result=0):
            UI.open_batch(self.mw, self.fm, dict(self.CFG), official, None)

    def test_full_flow_analyzes_confirms_and_generates(self):
        def script(d):
            d.analyze_button.click()
            self.assertIn("Para gerar agora: 4", d.report.toPlainText())
            d.go.click()

        self.run_flow(script)
        self.assertEqual(self.asked[0].count("exemplo.test"), 1)
        self.assertIn("Para gerar agora: 4", self.asked[0])
        bank = self.fm.bank()
        self.assertEqual(sorted(bank.notes), [1, 2, 3, 4])
        self.assertEqual(F.FreeBank(bank.path).stats()["notes"], 4)  # gravado
        ((text, kw),) = self.texts
        self.assertIn("Com variantes: 4 notas", text)
        self.assertEqual(kw["title"], "DFC Probe: variantes geradas")

    def test_declining_the_confirmation_generates_nothing(self):
        self.answer = False

        def script(d):
            d.analyze_button.click()
            d.go.click()

        self.run_flow(script)
        self.assertEqual((self.fm.bank().stats()["notes"], len(self.gen.calls), self.texts), (0, 0, []))

    def test_study_notes_are_left_out(self):
        def script(d):
            d.analyze_button.click()
            self.assertIn("Do banco do estudo (não são tocadas): 2", d.report.toPlainText())
            d.go.click()

        self.run_flow(script, official=lambda: {1, 2})
        self.assertEqual(sorted(self.fm.bank().notes), [3, 4])

    def test_selected_types_and_limits_reach_the_run(self):
        def script(d):
            for t in ("reorder", "cue_swap", "pergunta", "sem_imagem", "reformat"):
                d.type_boxes[t].setChecked(False)
            d.max_notes.setValue(2)
            d.analyze_button.click()
            d.go.click()

        self.run_flow(script)
        self.assertEqual(sorted(self.fm.bank().notes), [1, 2])
        self.assertEqual({v["type"] for e in self.fm.bank().notes.values() for v in e["variants"]}, {"paraphrase"})

    def test_progress_dialog_follows_the_run_and_ends_closed(self):
        seen = []
        original = UI._widgets().ProgressDialog.update_counts

        def spy(dialog, summary):
            seen.append(summary.done)
            original(dialog, summary)

        def script(d):
            d.analyze_button.click()
            d.go.click()

        with mock.patch.object(UI._widgets().ProgressDialog, "update_counts", spy):
            self.run_flow(script)
        self.assertEqual(seen, [1, 2, 3, 4])

    def test_analysis_failure_is_reported_in_the_dialog(self):
        def script(d):
            d.analyze_button.click()
            self.assertIn("Falha ao analisar o baralho: sem coleção", d.report.toPlainText())
            self.assertFalse(d.go.isEnabled())

        UI.anki_adapter.collect_records.side_effect = RuntimeError("sem coleção")
        self.run_flow(script)

    def test_generation_failure_is_reported(self):
        def script(d):
            d.analyze_button.click()
            d.go.click()

        with mock.patch.object(UI.batch, "run", side_effect=RuntimeError("explodiu")):
            self.run_flow(script)
        self.assertIn("A geração parou: explodiu", self.shown[-1])

    def test_needs_live_enabled_and_a_valid_config(self):
        self.CFG = {**self.CFG, "live_enabled": False}
        self.run_flow(lambda d: self.fail("não deveria abrir"))
        self.assertIn("live_enabled", self.shown[-1])
        self.CFG = {**self.CFG, "live_enabled": True}
        UI.live.build_clients.side_effect = L.ConfigError("preencha live_api_key")
        self.run_flow(lambda d: self.fail("não deveria abrir"))
        self.assertIn("preencha live_api_key", self.shown[-1])

    def test_needs_a_profile(self):
        self.mw.col = None
        self.run_flow(lambda d: self.fail("não deveria abrir"))
        self.assertIn("Abra um perfil", self.shown[-1])

    def test_preselects_the_deck_given_by_the_deck_menu(self):
        picked = []

        def script(d):
            picked.append(d.deck.currentData())

        with self.scripted_exec("BatchDialog", script, result=0):
            UI.open_batch(self.mw, self.fm, dict(self.CFG), lambda: set(), 3)
            UI.open_batch(self.mw, self.fm, dict(self.CFG), lambda: set(), None)
        self.assertEqual(picked, [3, 2])  # sem baralho dado, o atual


class ProgressDialogTest(UiBase):
    def test_cancel_is_requested_once_and_window_close_only_cancels(self):
        calls = []
        d = UI._widgets().ProgressDialog(None, 10, lambda: calls.append(1))
        d.update_counts(B.Summary(total=10, done=4, with_variants=3, errors=1))
        self.assertEqual(d.bar.value(), 4)
        self.assertIn("4 de 10 notas. Com variantes: 3. Falhas: 1.", d.label.text())
        d.cancel_button.click()
        d.reject()  # fechar a janela / Esc
        self.assertEqual(calls, [1])
        self.assertFalse(d.cancel_button.isEnabled())
        self.assertIn("Cancelando", d.label.text())
        self.assertEqual(d.result(), 0)
        d.finish()
        self.assertEqual(d.result(), 1)


class BankDialogTest(UiBase):
    def setUp(self):
        super().setUp()
        self.bank = self.fm.bank()
        self.bank.set_entry(7, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": "h", "variants": [{"id": "7-a", "type": "paraphrase", "text": "Outra pergunta?"}]})
        self.bank.skip(9, "h9", "not_conceptual")

    def run_buttons(self, *labels):
        def script(d):
            for label in labels:
                d.buttons[label].click()

        with self.scripted_exec("BankDialog", script, result=0):
            UI.open_bank(self.mw, self.fm)

    def test_shows_the_stats(self):
        seen = []
        with self.scripted_exec("BankDialog", lambda d: seen.append(d.report.text())):
            UI.open_bank(self.mw, self.fm)
        self.assertIn("Notas com variantes: 1", seen[0])
        self.assertIn("Avaliadas sem variantes (não conceituais ou sem variante aprovada): 1", seen[0])

    def test_export_and_import(self):
        out = os.path.join(self.tmp.name, "exportado.json")
        FileDialog.save = out
        self.run_buttons("Exportar...")
        self.assertEqual(F.FreeBank(out).stats()["notes"], 1)
        self.assertEqual(self.tips[-1], "Banco pessoal exportado.")
        self.bank.clear()
        FileDialog.open = out
        self.run_buttons("Importar...")
        self.assertEqual(self.bank.stats()["notes"], 1)
        self.assertEqual(self.tips[-1], "1 notas importadas.")

    def test_import_rejects_junk(self):
        junk = os.path.join(self.tmp.name, "lixo.json")
        with open(junk, "w", encoding="utf-8") as f:
            f.write("[]")
        FileDialog.open = junk
        self.run_buttons("Importar...")
        self.assertIn("Não foi possível importar", self.warned[-1])

    def test_cancelled_file_dialogs_do_nothing(self):
        FileDialog.save = FileDialog.open = ""
        self.run_buttons("Exportar...", "Importar...")
        self.assertEqual((self.tips, self.warned), ([], []))

    def test_forget_dismissed_notes(self):
        self.run_buttons("Esquecer as notas avaliadas sem variantes")
        self.assertEqual(self.bank.skipped, {})
        self.assertIn("1 notas serão avaliadas de novo", self.tips[-1])

    def test_wipe_asks_first(self):
        self.answer = False
        self.run_buttons("Apagar o banco pessoal")
        self.assertEqual(self.bank.stats()["notes"], 1)
        self.answer = True
        self.run_buttons("Apagar o banco pessoal")
        self.assertEqual(self.bank.stats()["notes"], 0)
        self.assertEqual(F.FreeBank(self.bank.path).stats()["notes"], 0)

    def test_needs_a_profile(self):
        self.col_none = True
        self.mw.col = None
        self.fm.env.col = lambda: None
        UI.open_bank(self.mw, self.fm)
        self.assertIn("Abra um perfil", self.shown[-1])


class SavePickerTest(UiBase):
    def result(self, valid=(True, True, False), images=('<img src="a.png">',)):
        types_ = ("paraphrase", "reorder", "pergunta")
        texts = (
            "Na divisão somática ocorre [...1] e a formação dos gametas é [...2]",
            "A formação dos gametas é [...2] e na divisão somática ocorre [...1]",
            "O que ocorre na divisão somática [...1] e na formação dos gametas [...2]?",
        )
        return {
            "note_id": 8, "fields_hash": "abc123abc123",
            "entry": {"kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["mitose", "meiose"], "images_html": list(images)},
            "models": {"gen": "gen-x", "judge": "judge-x"},
            "variants": [{"id": f"8-{t}-{i}", "type": t, "text": x, "valid": ok, "reasons": []} for i, (t, x, ok) in enumerate(zip(types_, texts, valid))],
        }

    def test_lists_only_approved_variants_and_sem_imagem(self):
        rows = []
        with self.scripted_exec("SavePickerDialog", lambda d: rows.append(list(d.checks))):
            UI.open_save_picker(self.mw, self.fm, self.result())
        self.assertEqual(rows[0], ["8-paraphrase-0", "8-reorder-1", "8-sem_imagem"])

    def test_saves_the_checked_ones_into_the_bank(self):
        def script(d):
            d.checks["8-reorder-1"].setChecked(False)

        with self.scripted_exec("SavePickerDialog", script):
            UI.open_save_picker(self.mw, self.fm, self.result())
        bank = self.fm.bank()
        self.assertEqual([v["id"] for v in bank.entry(8)["variants"]], ["8-paraphrase-0", "8-sem_imagem"])
        self.assertEqual(F.FreeBank(bank.path).stats()["notes"], 1)
        self.assertIn("2 variantes guardadas", self.tips[-1])
        self.assertIn("depois de ligar o modo", self.tips[-1])
        self.assertEqual(bank.generator_models, {"gen-x"})

    def test_adds_to_what_the_note_already_has_and_unbans(self):
        bank = self.fm.bank()
        bank.set_entry(8, {"kind": "cloze", "ords": [0], "q_field": 0, "fields_hash": "abc123abc123", "answers_html": ["mitose", "meiose"], "images_html": [],
                           "variants": [{"id": "8-cue_swap-9", "type": "cue_swap", "text": "Pistas trocadas: [...1] e [...2]"}]})
        bank.ban("8-reorder-1")
        self.fm.save_settings(F.Settings(enabled=True))
        with self.scripted_exec("SavePickerDialog", lambda d: None):
            UI.open_save_picker(self.mw, self.fm, self.result(images=()))
        self.assertEqual([v["id"] for v in bank.entry(8)["variants"]], ["8-cue_swap-9", "8-paraphrase-0", "8-reorder-1"])
        self.assertNotIn("8-reorder-1", bank.banned)
        self.assertNotIn("depois de ligar o modo", self.tips[-1])

    def test_edited_note_replaces_the_old_entry(self):
        bank = self.fm.bank()
        bank.set_entry(8, {"kind": "cloze", "ords": [0], "q_field": 0, "fields_hash": "outro-hash", "answers_html": ["mitose", "meiose"], "images_html": [],
                           "variants": [{"id": "8-cue_swap-9", "type": "cue_swap", "text": "Pistas trocadas: [...1] e [...2]"}]})
        with self.scripted_exec("SavePickerDialog", lambda d: None):
            UI.open_save_picker(self.mw, self.fm, self.result(images=()))
        self.assertEqual([v["id"] for v in bank.entry(8)["variants"]], ["8-paraphrase-0", "8-reorder-1"])

    def test_cancel_and_empty_selection_save_nothing(self):
        with self.scripted_exec("SavePickerDialog", lambda d: None, result=0):
            UI.open_save_picker(self.mw, self.fm, self.result())
        with self.scripted_exec("SavePickerDialog", lambda d: [c.setChecked(False) for c in d.checks.values()]):
            UI.open_save_picker(self.mw, self.fm, self.result())
        self.assertEqual(self.fm.bank().stats()["notes"], 0)

    def test_nothing_approved(self):
        UI.open_save_picker(self.mw, self.fm, self.result(valid=(False, False, False)))
        self.assertIn("Não há variante aprovada", self.shown[-1])


class HelpersTest(unittest.TestCase):
    def test_preview(self):
        self.assertEqual(UI.preview("uma   frase\ncurta"), "uma frase curta")
        long = UI.preview("palavra " * 40)
        self.assertEqual(len(long), UI.PREVIEW_CHARS)
        self.assertTrue(long.endswith("…"))

    def test_deck_choices_sorted_by_name(self):
        col = types.SimpleNamespace(decks=FakeDecks())
        self.assertEqual(UI.deck_choices(col), DECKS)


if __name__ == "__main__":
    unittest.main()
