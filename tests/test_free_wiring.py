"""Ligação do uso livre (v0.5) ao add-on com um Anki simulado: ordem dos ganchos, precedência do estudo, tecla x, menus e status.

Reaproveita o Anki simulado de test_addon_smoke (aqt falso). Não substitui o teste no Anki real.
"""
import importlib
import json
import os
import sys
import types
import unittest
from unittest import mock

import test_addon_smoke as S

NOTE_ID = 5  # nota que não está no banco do estudo (a do estudo é a 2)


def free_entry(note_id=NOTE_ID):
    return {
        "kind": "basic", "ords": [0], "q_field": 0, "fields_hash": S.sha1_12("\x1f".join(("Q", "A"))),
        "variants": [{"id": f"{note_id}-paraphrase-aaa", "type": "paraphrase", "text": "Variante livre A?"}, {"id": f"{note_id}-reorder-bbb", "type": "reorder", "text": "Variante livre B?"}],
    }


class FreeWiringTest(unittest.TestCase):
    setUp = S.SmokeTest.setUp
    tearDown = S.SmokeTest.tearDown
    review = S.SmokeTest.review
    menu_action = S.SmokeTest.menu_action
    rows = S.SmokeTest.rows
    force = S.SmokeTest.force

    def chain(self, text, card, kind):
        for fn in self.hooks.card_will_show:
            text = fn(text, card, kind)
        return text

    def study(self, card, ease=3):
        q = self.chain("Q", card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        a = self.chain("Q<hr id=answer>A", card, "reviewAnswer")
        self.hooks.reviewer_did_show_answer[0](card)
        self.hooks.reviewer_did_answer_card[0](None, card, ease)
        return q, a

    def turn_on(self, probability=100, **settings):
        from dfc_probe import free

        fm = self.mod._free
        fm.save_settings(free.Settings(enabled=True, probability=probability, **settings))
        bank = fm.bank()
        for nid in (NOTE_ID, 2):
            bank.set_entry(nid, free_entry(nid))
        return fm

    def test_free_hook_comes_after_the_study_hook(self):
        self.assertEqual(len(self.hooks.card_will_show), 2)
        self.assertEqual(self.hooks.card_will_show[0].__name__, "_on_card_will_show")
        self.assertEqual(self.hooks.card_will_show[1].__name__, "_on_card_will_show_free")
        self.assertEqual(len(self.hooks.profile_will_close), 1)
        self.assertEqual(len(self.hooks.deck_browser_will_show_options_menu), 1)

    def test_off_by_default_nothing_changes(self):
        self.assertFalse(self.mod._free.settings().enabled)
        self.assertEqual(self.study(S.make_card(nid=NOTE_ID)), ("Q", "Q<hr id=answer>A"))
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["draw_note"]), (None, "no_entry"))

    def test_free_variant_is_swapped_on_both_sides_and_marked_in_the_event(self):
        self.turn_on()
        q, a = self.study(S.make_card(nid=NOTE_ID))
        self.assertIn(q, ("Variante livre A?", "Variante livre B?"))
        self.assertEqual(a, q + "<hr id=answer>A")
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["draw_note"], row["variant_id"]), (None, "free_variant", None))  # nunca entra como sorteio do estudo
        self.assertEqual(self.mod._free.bank().recent(NOTE_ID), [{"Variante livre A?": f"{NOTE_ID}-paraphrase-aaa", "Variante livre B?": f"{NOTE_ID}-reorder-bbb"}[q]])

    def test_the_study_always_wins(self):
        self.turn_on()
        self.force(1.0)
        q, _a = self.study(S.make_card())  # nota 2: está no banco do estudo e também no pessoal
        self.assertIn(q, ("Variante A?", "Variante B?"))  # a do estudo, não a livre
        (row,) = self.rows()
        self.assertEqual((row["arm"], row["draw_note"]), ("variant", "ok"))
        self.force(0.0)
        q, _a = self.study(S.make_card(reps=7))  # braço original do estudo: o uso livre também não mexe
        self.assertEqual(q, "Q")
        self.assertEqual(self.rows()[-1]["arm"], "original")
        self.force(1.0)
        self.mod._bank = None  # sem banco do estudo importado, a nota 2 ainda é do pessoal e o uso livre age
        q, _a = self.study(S.make_card(reps=8))
        self.assertIn(q, ("Variante livre A?", "Variante livre B?"))

    def test_x_removes_a_free_variant_from_the_personal_bank(self):
        fm = self.turn_on()
        shortcuts = []
        self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
        card = S.make_card(nid=NOTE_ID)
        shown = self.chain("Q", card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shortcuts[0][1]()
        vid = {"Variante livre A?": f"{NOTE_ID}-paraphrase-aaa", "Variante livre B?": f"{NOTE_ID}-reorder-bbb"}[shown]
        self.assertIn(vid, fm.bank().banned)
        self.assertTrue(any("removida do banco pessoal" in m for m in self.messages))
        self.hooks.reviewer_did_answer_card[0](None, card, 3)
        (row,) = self.rows()
        self.assertEqual(row["flag_bad"], 0)  # a marca do estudo fica só para variantes do estudo

    def test_x_without_any_variant_keeps_the_old_message(self):
        self.turn_on(probability=0)
        shortcuts = []
        self.hooks.state_shortcuts_will_change[0]("review", shortcuts)
        card = S.make_card(nid=NOTE_ID)
        self.chain("Q", card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shortcuts[0][1]()
        self.assertIn("não mostra uma variante", self.messages[-1])

    def test_menu_mark_last_reaches_the_free_variant(self):
        fm = self.turn_on()
        self.study(S.make_card(nid=NOTE_ID))
        self.menu_action("Marcar a última resposta como variante ruim").triggered.emit(False)
        self.assertEqual(len(fm.bank().banned), 1)

    def test_free_errors_never_break_the_review(self):
        self.turn_on()
        with mock.patch.object(self.mod._free, "_decide", side_effect=RuntimeError("falha")):
            self.assertEqual(self.chain("Q", S.make_card(nid=NOTE_ID), "reviewQuestion"), "Q")
        self.assertTrue(os.path.exists(self.mod.ERR_LOG))

    def test_free_part_missing_leaves_the_add_on_working(self):
        self.mod._free = None
        self.assertEqual(self.hooks.card_will_show[1]("t", S.make_card(), "reviewQuestion"), "t")
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("indisponível", self.messages[-1])

    def test_status_shows_the_free_mode(self):
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("Variantes nos meus cartões (uso livre): desligado; banco pessoal: 0 notas, 0 variantes", self.messages[-1])
        self.turn_on(probability=30)
        self.menu_action("Status").triggered.emit(False)
        self.assertIn("ligado (30% das revisões elegíveis); banco pessoal: 2 notas, 4 variantes", self.messages[-1])

    def test_profile_close_saves_the_bank(self):
        fm = self.turn_on()
        path = fm.bank().path
        self.assertFalse(os.path.exists(path))
        self.hooks.profile_will_close[0]()
        self.assertTrue(os.path.exists(path))

    def test_submenu_and_its_actions(self):
        (submenu,) = self.menu_tools.menus[0].menus
        self.assertEqual(submenu.title, "Variantes nos meus cartões (uso livre)")
        self.assertEqual([a.text for a in submenu.actions], ["Configurar...", "Gerar variantes de um baralho...", "Banco pessoal..."])
        free_ui = importlib.import_module("dfc_probe.free_ui")
        with mock.patch.object(free_ui, "open_settings") as settings, mock.patch.object(free_ui, "open_batch") as batch, mock.patch.object(free_ui, "open_bank") as bank:
            for action in submenu.actions:
                action.triggered.emit(False)
        (s_args,) = settings.call_args_list
        self.assertEqual((s_args.args[0], s_args.args[1]), (self.mw, self.mod._free))
        (b_args,) = batch.call_args_list
        self.assertEqual(b_args.args[:2], (self.mw, self.mod._free))
        self.assertEqual(b_args.args[4], None)
        self.assertEqual(b_args.args[3](), {2})  # notas do banco do estudo: ficam de fora da geração
        self.assertEqual(bank.call_count, 1)

    def test_settings_screen_can_open_the_other_two(self):
        free_ui = importlib.import_module("dfc_probe.free_ui")
        with mock.patch.object(free_ui, "open_settings") as settings, mock.patch.object(free_ui, "open_batch") as batch, mock.patch.object(free_ui, "open_bank") as bank:
            self.menu_tools.menus[0].menus[0].actions[0].triggered.emit(False)
            on_generate, on_bank = settings.call_args.args[2:4]
            on_generate()
            on_bank()
        self.assertEqual((batch.call_count, bank.call_count), (1, 1))

    def test_deck_menu_entry_opens_the_batch_for_that_deck(self):
        menu = S.ContextMenu()
        self.hooks.deck_browser_will_show_options_menu[0](menu, 77)
        (action,) = menu.actions
        self.assertEqual(action.text, "Gerar variantes do baralho (DFC Probe)...")
        free_ui = importlib.import_module("dfc_probe.free_ui")
        with mock.patch.object(free_ui, "open_batch") as batch:
            action.triggered.emit(False)
        self.assertEqual(batch.call_args.args[4], 77)

    def test_screen_errors_become_a_message(self):
        free_ui = importlib.import_module("dfc_probe.free_ui")
        with mock.patch.object(free_ui, "open_bank", side_effect=RuntimeError("tela quebrou")):
            self.menu_tools.menus[0].menus[0].actions[2].triggered.emit(False)
        self.assertIn("Não foi possível abrir esta tela", self.messages[-1])
        self.assertTrue(os.path.exists(self.mod.ERR_LOG))

    def test_single_card_window_can_save_to_the_personal_bank(self):
        self.cfg["live_enabled"] = True
        live = importlib.import_module("dfc_probe.live")
        free_ui = importlib.import_module("dfc_probe.free_ui")
        with mock.patch.object(live, "build_clients", return_value=(S.FakeLLM(), S.FakeLLM())):
            self.menu_action(S.LIVE_LABEL).triggered.emit(False)
        ((text, _kwargs, _dialog, box),) = self.texts
        self.assertIn("banco pessoal", text)
        save = next(b for b in box.buttons if b.text == "Guardar no banco pessoal...")
        with mock.patch.object(free_ui, "open_save_picker") as picker:
            save.clicked.emit(False)
        (call,) = picker.call_args_list
        self.assertEqual(call.args[:2], (self.mw, self.mod._free))
        self.assertEqual(call.args[2]["note_id"], 2)


if __name__ == "__main__":
    unittest.main()
