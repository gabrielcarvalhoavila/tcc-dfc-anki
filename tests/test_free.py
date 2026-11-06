"""Testes do uso livre (v0.5): ajustes, escolha da variante e banco pessoal. Sem Anki e sem rede."""
import json
import os
import random
import tempfile
import unittest

import addon_pure

F = addon_pure.load("free")
V = addon_pure.load("variants")


def facts(**over):
    base = {"reps": 6, "card_type": 2, "lapses": 0, "last_ease": 3, "same_day": 0, "deck_id": 5}
    base.update(over)
    return base


def basic_entry(note_id=7, fields=("Q", "A")):
    return {
        "kind": "basic",
        "ords": [0],
        "q_field": 0,
        "fields_hash": V.fields_hash(list(fields)),
        "variants": [
            {"id": f"{note_id}-paraphrase-aaa", "type": "paraphrase", "text": "Outra forma de perguntar A?"},
            {"id": f"{note_id}-reorder-bbb", "type": "reorder", "text": "Perguntar A de outra ordem?"},
            {"id": f"{note_id}-cue_swap-ccc", "type": "cue_swap", "text": "Pergunta com pistas trocadas?"},
        ],
    }


def cloze_result(valid=(True, True, False), images=('<img src="a.png">',)):
    types = ("paraphrase", "reorder", "pergunta")
    texts = (
        "Na divisão somática ocorre [...1] e a formação dos gametas é [...2]",
        "A formação dos gametas é [...2] e na divisão somática ocorre [...1]",
        "O que ocorre na divisão somática [...1] e na formação dos gametas [...2]?",
    )
    return {
        "note_id": 8,
        "fields_hash": "abc123abc123",
        "entry": {"kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["mitose", "meiose"], "images_html": list(images)},
        "variants": [
            {"id": f"8-{t}-{i}", "type": t, "text": txt, "valid": ok, "reasons": [] if ok else ["ambiguous"]}
            for i, (t, txt, ok) in enumerate(zip(types, texts, valid))
        ],
    }


class SettingsTest(unittest.TestCase):
    def test_defaults_keep_the_feature_off(self):
        s = F.Settings()
        self.assertEqual((s.enabled, s.probability, s.deck_ids, s.badge), (False, 50, None, False))
        self.assertEqual(tuple(s.types), F.ALL_TYPES)
        self.assertTrue(s.avoid_repeat and s.avoid_same_day and not s.include_learning and not s.suspects_only)

    def test_from_raw_ignores_junk_and_clamps(self):
        self.assertEqual(F.Settings.from_raw(None).to_dict(), F.Settings().to_dict())
        self.assertEqual(F.Settings.from_raw("x").to_dict(), F.Settings().to_dict())
        self.assertEqual(F.Settings.from_raw({"probability": 250}).probability, 100)
        self.assertEqual(F.Settings.from_raw({"probability": -3}).probability, 0)
        self.assertEqual(F.Settings.from_raw({"probability": "abc"}).probability, 50)
        self.assertEqual(F.Settings.from_raw({"probability": "30"}).probability, 30)
        self.assertEqual(F.Settings.from_raw({"types": ["paraphrase", "x", "paraphrase", "reorder"]}).types, ["paraphrase", "reorder"])
        self.assertEqual(F.Settings.from_raw({"types": "paraphrase"}).types, list(F.ALL_TYPES))
        self.assertEqual(F.Settings.from_raw({"deck_ids": [1, "2", True, 3]}).deck_ids, [1, 3])
        self.assertIsNone(F.Settings.from_raw({"deck_ids": "todos"}).deck_ids)

    def test_roundtrip(self):
        s = F.Settings(enabled=True, probability=20, types=["reorder"], deck_ids=[4, 9], include_learning=True, suspects_only=True, avoid_repeat=False, avoid_same_day=False, badge=True)
        self.assertEqual(F.Settings.from_raw(json.loads(json.dumps(s.to_dict()))), s)


class CardAllowedTest(unittest.TestCase):
    def test_review_card_with_history_is_allowed(self):
        self.assertTrue(F.card_allowed(F.Settings(), facts(), None))

    def test_new_and_learning_cards(self):
        s = F.Settings()
        self.assertFalse(F.card_allowed(s, facts(card_type=0, reps=0), None))
        self.assertFalse(F.card_allowed(s, facts(card_type=2, reps=0), None))
        self.assertFalse(F.card_allowed(s, facts(card_type=1), None))
        self.assertFalse(F.card_allowed(s, facts(card_type=3), None))
        s.include_learning = True
        self.assertTrue(F.card_allowed(s, facts(card_type=1), None))
        self.assertTrue(F.card_allowed(s, facts(card_type=3), None))
        self.assertFalse(F.card_allowed(s, facts(card_type=0, reps=0), None))

    def test_same_day(self):
        s = F.Settings()
        self.assertFalse(F.card_allowed(s, facts(same_day=1), None))
        self.assertTrue(F.card_allowed(s, facts(same_day=None), None))
        s.avoid_same_day = False
        self.assertTrue(F.card_allowed(s, facts(same_day=1), None))

    def test_deck_scope(self):
        s = F.Settings()
        self.assertTrue(F.card_allowed(s, facts(deck_id=5), {5, 6}))
        self.assertFalse(F.card_allowed(s, facts(deck_id=7), {5, 6}))
        self.assertFalse(F.card_allowed(s, facts(deck_id=7), set()))
        self.assertTrue(F.card_allowed(s, facts(deck_id=7), None))

    def test_suspects_only_uses_the_protocol_definition(self):
        s = F.Settings(suspects_only=True)
        self.assertTrue(F.card_allowed(s, facts(reps=5, lapses=0, last_ease=3), None))
        self.assertTrue(F.card_allowed(s, facts(reps=9, lapses=0, last_ease=4), None))
        self.assertFalse(F.card_allowed(s, facts(reps=4), None))
        self.assertFalse(F.card_allowed(s, facts(lapses=1), None))
        self.assertFalse(F.card_allowed(s, facts(last_ease=1), None))
        self.assertFalse(F.card_allowed(s, facts(last_ease=None), None))


class PickVariantTest(unittest.TestCase):
    def setUp(self):
        self.entry = basic_entry()
        self.rng = random.Random(1)

    def test_respects_chosen_types_and_banned(self):
        s = F.Settings(types=["reorder"])
        self.assertEqual(F.pick_variant(self.entry, s, [], [], self.rng)["type"], "reorder")
        self.assertIsNone(F.pick_variant(self.entry, s, ["7-reorder-bbb"], [], self.rng))
        self.assertIsNone(F.pick_variant(self.entry, F.Settings(types=[]), [], [], self.rng))

    def test_prefers_variants_not_shown_recently(self):
        s = F.Settings()
        picks = {F.pick_variant(self.entry, s, [], ["7-paraphrase-aaa", "7-reorder-bbb"], random.Random(i))["id"] for i in range(30)}
        self.assertEqual(picks, {"7-cue_swap-ccc"})

    def test_when_all_were_shown_only_the_latest_is_avoided(self):
        s = F.Settings()
        recent = ["7-reorder-bbb", "7-paraphrase-aaa", "7-cue_swap-ccc"]
        picks = {F.pick_variant(self.entry, s, [], recent, random.Random(i))["id"] for i in range(60)}
        self.assertEqual(picks, {"7-paraphrase-aaa", "7-cue_swap-ccc"})

    def test_repeat_allowed_when_setting_is_off(self):
        s = F.Settings(avoid_repeat=False)
        picks = {F.pick_variant(self.entry, s, [], ["7-reorder-bbb"], random.Random(i))["id"] for i in range(60)}
        self.assertEqual(picks, {v["id"] for v in self.entry["variants"]})

    def test_single_variant_is_always_picked(self):
        s = F.Settings(types=["paraphrase"])
        self.assertEqual(F.pick_variant(self.entry, s, [], ["7-paraphrase-aaa"], self.rng)["id"], "7-paraphrase-aaa")

    def test_roll_follows_the_probability(self):
        rng = random.Random(7)
        for p, low, high in ((0, 0, 0), (100, 5000, 5000), (30, 1350, 1650), (50, 2350, 2650)):
            hits = sum(F.roll(F.Settings(probability=p), rng) for _ in range(5000))
            self.assertTrue(low <= hits <= high, (p, hits))


class EntryFromResultTest(unittest.TestCase):
    def test_keeps_only_approved_variants_and_adds_sem_imagem(self):
        entry = F.entry_from_result(cloze_result())
        self.assertEqual([v["type"] for v in entry["variants"]], ["paraphrase", "reorder", "sem_imagem"])
        self.assertEqual(entry["variants"][-1], {"id": "8-sem_imagem", "type": "sem_imagem"})
        self.assertEqual((entry["kind"], entry["ords"], entry["q_field"], entry["fields_hash"]), ("cloze", [0], 0, "abc123abc123"))
        self.assertEqual((entry["answers_html"], entry["images_html"]), (["mitose", "meiose"], ['<img src="a.png">']))
        self.assertIsNotNone(V._clean_entry(entry))

    def test_no_image_means_no_sem_imagem(self):
        entry = F.entry_from_result(cloze_result(images=()))
        self.assertEqual([v["type"] for v in entry["variants"]], ["paraphrase", "reorder"])
        self.assertEqual(entry["images_html"] if "images_html" in entry else [], [])

    def test_type_filter(self):
        entry = F.entry_from_result(cloze_result(), types=["reorder"])
        self.assertEqual([v["type"] for v in entry["variants"]], ["reorder"])
        entry = F.entry_from_result(cloze_result(), types=["reorder", "sem_imagem"])
        self.assertEqual([v["type"] for v in entry["variants"]], ["reorder", "sem_imagem"])

    def test_only_ids_filter(self):
        entry = F.entry_from_result(cloze_result(valid=(True, True, True)), only_ids=["8-pergunta-2", "8-sem_imagem"])
        self.assertEqual([v["id"] for v in entry["variants"]], ["8-pergunta-2", "8-sem_imagem"])

    def test_nothing_approved_gives_none(self):
        self.assertIsNone(F.entry_from_result(cloze_result(valid=(False, False, False))))
        self.assertIsNone(F.entry_from_result(cloze_result(), types=["cue_swap"]))

    def test_basic_entry_has_no_cloze_fields(self):
        result = {
            "note_id": 3, "fields_hash": "h" * 12,
            "entry": {"kind": "basic", "ords": [0], "q_field": 0, "answers_html": ["R"], "images_html": []},
            "variants": [{"id": "3-paraphrase-x", "type": "paraphrase", "text": "Outra pergunta?", "valid": True, "reasons": []}],
        }
        entry = F.entry_from_result(result)
        self.assertEqual(entry, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": "h" * 12, "variants": [{"id": "3-paraphrase-x", "type": "paraphrase", "text": "Outra pergunta?"}]})

    def test_id_falls_back_to_the_pipeline_formula(self):
        result = cloze_result(valid=(True, False, False), images=())
        del result["variants"][0]["id"]
        entry = F.entry_from_result(result)
        self.assertEqual(entry["variants"][0]["id"], f"8-paraphrase-{V.sha1_short(result['variants'][0]['text'], 6)}")


class FreeBankTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "sub", "free_bank.json")

    def tearDown(self):
        self.tmp.cleanup()

    def bank(self):
        return F.FreeBank(self.path)

    def test_empty_when_file_is_missing(self):
        b = self.bank()
        self.assertEqual(b.stats(), {"notes": 0, "variants": 0, "by_type": {}, "skipped": 0, "banned": 0})
        b.save()
        self.assertFalse(os.path.exists(self.path))

    def test_roundtrip_and_compatibility_with_the_study_loader(self):
        b = self.bank()
        self.assertTrue(b.set_entry(7, basic_entry(), "gen-model", "judge-model"))
        b.skip(9, "hhh", "not_conceptual")
        b.remember_shown(7, "7-reorder-bbb")
        b.save()
        self.assertEqual([n for n in os.listdir(os.path.dirname(self.path)) if n.endswith(".tmp")], [])
        again = self.bank()
        self.assertEqual(again.entry(7), b.entry(7))
        self.assertTrue(again.has_current(7, V.fields_hash(["Q", "A"])))
        self.assertFalse(again.has_current(7, "other"))
        self.assertTrue(again.is_skipped(9, "hhh"))
        self.assertFalse(again.is_skipped(9, "zzz"))
        self.assertEqual(again.recent(7), ["7-reorder-bbb"])
        self.assertEqual((again.generator_models, again.judge_models), ({"gen-model"}, {"judge-model"}))
        bank = V.Bank.load(self.path)  # o mesmo arquivo é um banco válido para o carregador do estudo
        self.assertEqual((len(bank.notes), bank.n_variants, bank.is_fake), (1, 3, False))

    def test_set_entry_rejects_invalid(self):
        b = self.bank()
        bad = basic_entry()
        bad["variants"] = [{"id": "x", "type": "paraphrase", "text": "tem {{c1::marca}} de template"}]
        self.assertFalse(b.set_entry(7, bad))
        self.assertIsNone(b.entry(7))

    def test_set_entry_clears_the_negative_cache(self):
        b = self.bank()
        b.skip(7, "old", "no_valid_variant")
        b.set_entry(7, basic_entry())
        self.assertFalse(b.is_skipped(7, "old"))

    def test_ban_removes_the_variant_and_survives_reload(self):
        b = self.bank()
        b.set_entry(7, basic_entry())
        b.ban("7-reorder-bbb")
        self.assertEqual([v["id"] for v in b.entry(7)["variants"]], ["7-paraphrase-aaa", "7-cue_swap-ccc"])
        b.save()
        self.assertEqual(self.bank().banned, {"7-reorder-bbb"})

    def test_banning_the_last_text_variant_drops_the_note_and_its_sem_imagem(self):
        b = self.bank()
        entry = F.entry_from_result(cloze_result(valid=(True, False, False)))
        self.assertEqual([v["type"] for v in entry["variants"]], ["paraphrase", "sem_imagem"])
        b.set_entry(8, entry)
        b.ban("8-paraphrase-0")
        self.assertIsNone(b.entry(8))

    def test_shown_memory_is_most_recent_first_and_capped(self):
        b = self.bank()
        for i in range(F.SHOWN_MEMORY + 3):
            b.remember_shown(7, f"v{i}")
        b.remember_shown(7, "v5")
        self.assertEqual(len(b.recent(7)), F.SHOWN_MEMORY)
        self.assertEqual(b.recent(7)[0], "v5")
        self.assertEqual(len(set(b.recent(7))), F.SHOWN_MEMORY)

    def test_corrupt_file_is_kept_aside_not_deleted(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{não é json")
        b = self.bank()
        self.assertEqual(b.stats()["notes"], 0)
        kept = [n for n in os.listdir(os.path.dirname(self.path)) if ".corrompido-" in n]
        self.assertEqual(len(kept), 1)
        b.set_entry(7, basic_entry())
        b.save()
        self.assertEqual(self.bank().stats()["notes"], 1)

    def test_delete_and_clear(self):
        b = self.bank()
        b.set_entry(7, basic_entry(7))
        b.set_entry(8, basic_entry(8))
        b.skip(9, "h", "x")
        self.assertEqual(b.delete_notes([7, 99]), 1)
        self.assertEqual(b.stats()["notes"], 1)
        b.clear()
        self.assertEqual((b.stats()["notes"], b.stats()["skipped"]), (0, 0))

    def test_stats_by_type(self):
        b = self.bank()
        b.set_entry(7, basic_entry())
        self.assertEqual(b.stats(), {"notes": 1, "variants": 3, "by_type": {"paraphrase": 1, "reorder": 1, "cue_swap": 1}, "skipped": 0, "banned": 0})

    def test_export_and_merge(self):
        a = self.bank()
        a.set_entry(7, basic_entry(7), "g", "j")
        a.set_entry(8, basic_entry(8))
        out = os.path.join(self.tmp.name, "export.json")
        a.export_to(out)
        self.assertEqual(a.path, self.path)
        self.assertFalse(os.path.exists(self.path))  # exportar não grava o banco da coleção
        other = F.FreeBank(os.path.join(self.tmp.name, "other.json"))
        other.set_entry(7, basic_entry(7, fields=("X", "Y")))
        self.assertEqual(other.merge_from(out), 2)
        self.assertEqual(other.entry(7)["fields_hash"], V.fields_hash(["Q", "A"]))
        self.assertEqual(other.stats()["notes"], 2)
        self.assertIn("g", other.generator_models)

    def test_merge_accepts_a_study_bank(self):
        study = os.path.join(self.tmp.name, "study.json")
        with open(study, "w", encoding="utf-8") as f:
            json.dump({"schema": 3, "generated_at": "t", "generator_models": ["gem"], "judge_models": ["j"], "notes": {"7": basic_entry(7)}}, f)
        b = self.bank()
        self.assertEqual(b.merge_from(study), 1)
        self.assertEqual(b.entry(7)["variants"][0]["id"], "7-paraphrase-aaa")

    def test_merge_rejects_what_is_not_a_bank(self):
        junk = os.path.join(self.tmp.name, "junk.json")
        with open(junk, "w", encoding="utf-8") as f:
            f.write("[]")
        with self.assertRaises(ValueError):
            self.bank().merge_from(junk)


if __name__ == "__main__":
    unittest.main()
