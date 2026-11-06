"""Testes da troca de variante na revisão (uso livre, v0.5) com um Anki simulado: sem interface e sem rede."""
import os
import random
import tempfile
import types
import unittest

import addon_pure

FM = addon_pure.load("freemode")
F = addon_pure.load("free")
V = addon_pure.load("variants")

FIELDS = ["Qual organela produz energia na célula?", "Mitocôndria"]


def entry(fields=FIELDS):
    return {
        "kind": "basic",
        "ords": [0],
        "q_field": 0,
        "fields_hash": V.fields_hash(list(fields)),
        "variants": [
            {"id": "7-paraphrase-aaa", "type": "paraphrase", "text": "Em outras palavras: qual organela gera a energia celular?"},
            {"id": "7-reorder-bbb", "type": "reorder", "text": "Na célula, qual organela produz a energia?"},
        ],
    }


class FakeCol:
    def __init__(self, fields=FIELDS):
        self.config = {}
        self.fields = list(fields)

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def set_config(self, key, value):
        self.config[key] = value

    def get_note(self, nid):
        return types.SimpleNamespace(fields=list(self.fields))


def render(col, card, field_index=None, value=None):
    fields = list(col.fields)
    if field_index is not None:
        fields[field_index] = value
    return f"<div>{fields[0]}</div>", f"<div>{fields[0]}</div><hr id=answer>{fields[1]}"


def card(reps=6, cid=10, ord_=0, nid=7):
    return types.SimpleNamespace(id=cid, nid=nid, ord=ord_, reps=reps)


class FreeModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.col = FakeCol()
        self.facts = {"reps": 6, "card_type": 2, "lapses": 0, "last_ease": 3, "same_day": 0, "deck_id": 5}
        self.official, self.drew, self.marked, self.tips, self.errors = set(), set(), [], [], []
        self.snapshot_error = None

        def snapshot(c):
            if self.snapshot_error:
                raise self.snapshot_error
            return dict(self.facts)

        self.env = FM.Env(
            col=lambda: self.col, user_files=self.tmp.name, snapshot=snapshot, render=render, munge=lambda t: t,
            official_has=lambda nid: nid in self.official, study_drew=lambda c: c.id in self.drew,
            mark_event=lambda c: self.marked.append(c.id), expand_decks=lambda ids: set(ids) | {99},
            tooltip=self.tips.append, log_error=lambda: self.errors.append(1),
        )
        self.fm = FM.FreeMode(self.env, random.Random(3))
        self.bank = self.fm.bank()
        self.bank.set_entry(7, entry())

    def tearDown(self):
        self.tmp.cleanup()

    def on(self, **over):
        s = F.Settings(enabled=True, probability=100)
        for k, v in over.items():
            setattr(s, k, v)
        self.fm.save_settings(s)

    def show(self, c=None, kind="reviewQuestion", text=None):
        c = c or card()
        base = "<div>%s</div>" % FIELDS[0] if kind == "reviewQuestion" else "<div>%s</div><hr id=answer>%s" % tuple(FIELDS)
        return self.fm.on_card_will_show(text if text is not None else "<style>x</style>" + base, c, kind)

    def test_off_by_default(self):
        self.assertEqual(self.show(), "<style>x</style><div>%s</div>" % FIELDS[0])
        self.assertEqual(self.marked, [])

    def test_swaps_question_then_answer_with_the_same_variant(self):
        self.on()
        q = self.show()
        self.assertTrue(q.startswith("<style>x</style><div>"))
        variant = self.fm._cur["variant"]
        self.assertIn(variant["text"], q)
        self.assertNotIn(FIELDS[0], q)
        a = self.show(kind="reviewAnswer")
        self.assertIn(variant["text"], a)
        self.assertTrue(a.endswith("<hr id=answer>Mitocôndria"))
        self.assertEqual(self.marked, [10])
        self.assertEqual(self.bank.recent(7), [variant["id"]])

    def test_probability_zero_and_hundred(self):
        self.on(probability=0)
        self.assertIn(FIELDS[0], self.show())
        self.on(probability=100)
        self.assertNotIn(FIELDS[0], self.show(card(reps=7)))

    def test_probability_in_between(self):
        self.on(probability=40, avoid_same_day=False)
        shown = sum(FIELDS[0] not in self.show(card(reps=i)) for i in range(1, 1001))
        self.assertTrue(340 <= shown <= 460, shown)

    def test_same_exposure_keeps_the_decision_and_does_not_log_twice(self):
        self.on()
        first = self.show()
        again = self.show()  # Ctrl+Z: o mesmo cartão, o mesmo reps
        self.assertEqual(first, again)
        self.assertEqual((self.marked, len(self.bank.recent(7))), ([10], 1))

    def test_next_exposure_avoids_the_variant_just_seen(self):
        self.on()
        self.show(card(reps=6))
        first = self.fm._cur["variant"]["id"]
        self.show(card(reps=7))
        self.assertNotEqual(self.fm._cur["variant"]["id"], first)

    def test_only_review_kinds_are_touched(self):
        self.on()
        for kind in ("previewQuestion", "clayoutQuestion", "previewAnswer"):
            self.assertEqual(self.fm.on_card_will_show("texto", card(), kind), "texto")
        self.assertEqual(self.marked, [])

    def test_conditions_that_leave_the_card_alone(self):
        self.on()
        original = "<style>x</style><div>%s</div>" % FIELDS[0]
        cases = {
            "other note": lambda: card(nid=8),
            "other ord": lambda: card(ord_=1),
            "official bank": lambda: (self.official.add(7), card())[1],
            "study drew": lambda: (self.drew.add(10), card())[1],
            "edited note": lambda: (setattr(self.col, "fields", ["Mudou?", "Mitocôndria"]), card())[1],
        }
        for name, make in cases.items():
            c = make()
            text = original if name != "edited note" else "<style>x</style><div>Mudou?</div>"
            self.assertEqual(self.show(c, text=text), text, name)
            self.official.clear(), self.drew.clear()
            self.col.fields = list(FIELDS)
        self.assertEqual(self.marked, [])

    def test_card_state_filters(self):
        original = "<style>x</style><div>%s</div>" % FIELDS[0]
        self.on()
        for i, facts in enumerate((
            {"same_day": 1}, {"card_type": 0, "reps": 0}, {"card_type": 1}, {"deck_id": 77},
        )):
            self.facts = {"reps": 6, "card_type": 2, "lapses": 0, "last_ease": 3, "same_day": 0, "deck_id": 5, **facts}
            self.on(deck_ids=[5])
            self.assertEqual(self.show(card(reps=10 + i)), original, facts)
        self.facts = {"reps": 6, "card_type": 1, "lapses": 0, "last_ease": 3, "same_day": 0, "deck_id": 5}
        self.on(include_learning=True, deck_ids=[5])
        self.assertNotEqual(self.show(card(reps=30)), original)

    def test_deck_scope_includes_subdecks(self):
        self.on(deck_ids=[5])
        self.facts["deck_id"] = 99  # subbaralho devolvido por expand_decks
        self.assertNotIn(FIELDS[0], self.show())

    def test_suspects_only(self):
        self.on(suspects_only=True)
        self.facts.update(lapses=2)
        self.assertIn(FIELDS[0], self.show())
        self.facts.update(lapses=0)
        self.assertNotIn(FIELDS[0], self.show(card(reps=7)))

    def test_only_chosen_types(self):
        self.on(types=["reorder"])
        for reps in range(1, 6):
            self.show(card(reps=reps))
            self.assertEqual(self.fm._cur["variant"]["type"], "reorder")

    def test_render_guard_falls_back_to_the_original(self):
        self.on()
        self.env.render = lambda col, c, i=None, v=None: ("<div>%s</div>" % FIELDS[0], "<div>%s</div><hr id=answer>x" % FIELDS[0])
        self.assertIn(FIELDS[0], self.show())
        self.assertEqual((self.marked, self.bank.recent(7)), ([], []))

    def test_answer_that_does_not_match_is_left_alone(self):
        self.on()
        self.show()
        self.assertEqual(self.show(kind="reviewAnswer", text="outro HTML"), "outro HTML")

    def test_badge(self):
        self.on(badge=True)
        q = self.show()
        self.assertIn("variante: ", q)
        self.on(badge=False)
        self.assertNotIn("variante: ", self.show(card(reps=7)))

    def test_errors_never_break_the_review(self):
        self.on()
        self.snapshot_error = RuntimeError("falha")
        text = "<style>x</style><div>%s</div>" % FIELDS[0]
        self.assertEqual(self.show(text=text), text)
        self.assertEqual(len(self.errors), 1)

    def test_mark_bad_current_bans_and_persists(self):
        self.on()
        self.show()
        vid = self.fm._cur["variant"]["id"]
        self.assertTrue(self.fm.mark_bad_current())
        self.assertIn(vid, self.bank.banned)
        self.assertEqual(len(self.tips), 1)
        self.assertEqual(F.FreeBank(self.bank.path).banned, {vid})  # já gravado em disco
        self.show(card(reps=7))  # a variante banida não volta
        self.assertNotEqual(self.fm._cur["variant"]["id"], vid)

    def test_mark_bad_current_without_a_variant_on_screen(self):
        self.assertFalse(self.fm.mark_bad_current())
        self.on(probability=0)
        self.show()
        self.assertFalse(self.fm.mark_bad_current())
        self.assertFalse(self.fm.mark_bad_last())

    def test_mark_bad_last_after_moving_on(self):
        self.on()
        self.show()
        vid = self.fm._cur["variant"]["id"]
        self.on(probability=0)
        self.show(card(reps=7, cid=11))
        self.assertFalse(self.fm.mark_bad_current())
        self.assertTrue(self.fm.mark_bad_last())
        self.assertIn(vid, self.bank.banned)

    def test_settings_roundtrip_in_the_collection(self):
        self.fm.save_settings(F.Settings(enabled=True, probability=25, types=["reorder"], deck_ids=[1, 2], badge=True))
        s = self.fm.settings()
        self.assertEqual((s.enabled, s.probability, s.types, s.deck_ids, s.badge), (True, 25, ["reorder"], [1, 2], True))
        self.assertIn(FM.CONFIG_KEY, self.col.config)

    def test_bank_belongs_to_the_collection_and_flushes(self):
        self.assertTrue(os.path.basename(self.bank.path).startswith("free_bank_"))
        self.assertEqual(self.col.config[FM.ID_KEY], os.path.basename(self.bank.path)[len("free_bank_"):-len(".json")])
        self.fm.flush()
        self.assertEqual(F.FreeBank(self.bank.path).stats()["notes"], 1)
        other = FakeCol()
        self.env.col = lambda: other
        self.assertEqual(self.fm.bank().stats()["notes"], 0)  # outro perfil, outro banco
        self.assertNotEqual(self.fm.bank().path, self.bank.path)

    def test_no_collection(self):
        self.env.col = lambda: None
        self.assertEqual(self.fm.on_card_will_show("t", card(), "reviewQuestion"), "t")
        self.assertIsNone(self.fm.bank())
        self.assertEqual(self.fm.status_line(), "sem perfil aberto")
        self.assertFalse(self.fm.settings().enabled)

    def test_status_line(self):
        self.assertEqual(self.fm.status_line(), "desligado; banco pessoal: 1 notas, 2 variantes")
        self.on(probability=30)
        self.assertEqual(self.fm.status_line(), "ligado (30% das revisões elegíveis); banco pessoal: 1 notas, 2 variantes")


if __name__ == "__main__":
    unittest.main()
