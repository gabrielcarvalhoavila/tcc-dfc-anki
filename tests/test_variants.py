"""Testes do banco de variantes e do sorteio do add-on (sem Anki)."""
import datetime
import importlib.util
import json
import os
import random
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))


def load_variants():
    spec = importlib.util.spec_from_file_location("dfc_variants", os.path.join(ROOT, "addon", "dfc_probe", "variants.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dfc_variants"] = mod
    spec.loader.exec_module(mod)
    return mod


V = load_variants()


def basic_entry(**over):
    entry = {
        "kind": "basic",
        "ords": [0],
        "q_field": 0,
        "fields_hash": "abc123abc123",
        "variants": [
            {"id": "n-paraphrase-1", "type": "paraphrase", "text": "Variante um?"},
            {"id": "n-reorder-2", "type": "reorder", "text": "Variante dois?"},
            {"id": "n-cue-3", "type": "cue_swap", "text": "Variante três?"},
        ],
    }
    entry.update(over)
    return entry


def decide(entry, **over):
    args = dict(card_ord=0, fields_hash_now="abc123abc123", reps=5, same_day=0, draw_on=True, window_ok=True, last_shown=[], event_id="evt1", salt=b"s")
    args.update(over)
    return V.decide(entry, **args)


class DecideTest(unittest.TestCase):
    def test_no_draw_for_each_ineligibility_reason(self):
        cases = [
            (dict(draw_on=False), "off"),
            (dict(bank_ok=False), "fake_bank"),
            (dict(window_ok=False), "outside_window"),
            (dict(card_ord=1), "ord_mismatch"),
            (dict(fields_hash_now="outro"), "note_edited"),
            (dict(reps=0), "reps0"),
            (dict(reps=None), "reps0"),
            (dict(same_day=None), "no_history"),
            (dict(same_day=1), "same_day"),
        ]
        for over, reason in cases:
            d = decide(basic_entry(), **over)
            self.assertEqual((d.arm, d.reason), (None, reason), over)
        self.assertEqual(decide(None).reason, "no_entry")

    def test_eligible_card_is_drawn(self):
        d = decide(basic_entry())
        self.assertEqual(d.reason, "ok")
        self.assertIn(d.arm, ("original", "variant"))
        self.assertEqual(d.variant is not None, d.arm == "variant")

    def test_draw_is_reproducible_and_about_half(self):
        self.assertEqual(decide(basic_entry()), decide(basic_entry()))
        arms = [decide(basic_entry(), event_id=f"e{i}").arm for i in range(400)]
        share = arms.count("variant") / len(arms)
        self.assertTrue(0.4 < share < 0.6, share)

    def test_logged_seed_reproduces_the_arm(self):
        for i in range(20):
            d = decide(basic_entry(), event_id=f"x{i}")
            self.assertEqual(random.Random(int(d.seed, 16)).random() < 0.5, d.arm == "variant")

    def test_new_variant_each_exposure_until_all_were_seen(self):
        old = V.VARIANT_PROBABILITY
        V.VARIANT_PROBABILITY = 1.0
        try:
            entry = basic_entry()
            for i in range(30):
                picked = decide(entry, event_id=f"a{i}", last_shown=["n-paraphrase-1"]).variant["id"]
                self.assertNotEqual(picked, "n-paraphrase-1")  # há outras ainda não vistas
            for i in range(30):
                shown = ["n-cue-3", "n-reorder-2", "n-paraphrase-1"]  # todas vistas, a mais recente primeiro
                self.assertNotEqual(decide(entry, event_id=f"b{i}", last_shown=shown).variant["id"], "n-cue-3")
            single = basic_entry(variants=[{"id": "u", "type": "paraphrase", "text": "Só uma?"}])
            self.assertEqual(decide(single, last_shown=["u"]).variant["id"], "u")  # sem alternativa, repete
        finally:
            V.VARIANT_PROBABILITY = old


class BankTest(unittest.TestCase):
    def bank_json(self, notes, schema=2):
        return json.dumps({"schema": schema, "generated_at": "x", "generator_models": ["g"], "judge_models": ["j"], "notes": notes}).encode()

    def test_loads_valid_entries_and_skips_invalid(self):
        cloze = {"kind": "cloze", "ords": [0], "q_field": 1, "fields_hash": "f", "answer_html": "TCP", "variants": [{"id": "c1", "type": "reorder", "text": "É [...] confiável"}]}
        notes = {
            "1": basic_entry(),
            "2": cloze,
            "3": basic_entry(variants=[{"id": "x", "type": "paraphrase", "text": "marca {{c1::proibida}}"}]),
            "4": {"kind": "outro", "ords": [0], "fields_hash": "f", "variants": []},
            "abc": basic_entry(),
            "5": {**cloze, "variants": [{"id": "c2", "type": "reorder", "text": "sem lacuna"}]},
        }
        bank = V.Bank.from_bytes(self.bank_json(notes))
        self.assertEqual((sorted(bank.notes), bank.skipped, bank.n_variants), ([1, 2], 4, 4))
        self.assertEqual(bank.entry("2")["q_field"], 1)
        self.assertIsNone(bank.entry(99))
        self.assertEqual(len(bank.hash), 12)

    def test_schema_1_without_q_field_defaults_to_the_first_field(self):
        old = basic_entry()
        del old["q_field"]
        self.assertEqual(V.Bank.from_bytes(self.bank_json({"1": old}, schema=1)).entry(1)["q_field"], 0)

    def test_rejects_other_files(self):
        for raw in (b"nao e json", b'{"schema": 3, "notes": {}}', b'["x"]', b'{"schema": 2}'):
            with self.assertRaises(ValueError):
                V.Bank.from_bytes(raw)

    def test_fake_bank_is_recognized(self):
        raw = lambda models: json.dumps({"schema": 2, "generator_models": models, "notes": {"1": basic_entry()}}).encode()
        self.assertTrue(V.Bank.from_bytes(raw(["fake"])).is_fake)
        self.assertFalse(V.Bank.from_bytes(raw(["anthropic/claude"])).is_fake)
        self.assertFalse(V.Bank.from_bytes(raw(None)).is_fake)

    def test_usable_text(self):
        self.assertFalse(V.usable_text("basic", "  "))
        self.assertFalse(V.usable_text("basic", "tem {{c1::marca}}"))
        self.assertFalse(V.usable_text("cloze", "sem lacuna"))
        self.assertFalse(V.usable_text("cloze", "[...] e [...]"))
        self.assertTrue(V.usable_text("cloze", "uma [...] só"))
        self.assertTrue(V.usable_text("basic", "O que é NAT?"))

    def test_bank_built_by_the_pipeline_loads_in_the_addon(self):
        from dfc_pipeline import cards, generate, pack, validate
        from dfc_pipeline.llm import FakeLLM
        from dfc_pipeline.util import read_jsonl

        recs = [
            {"noteId": 1, "modelName": "Basic", "fields": {"Front": {"value": "O que é NAT?", "order": 0}, "Back": {"value": "Tradução de endereços de rede", "order": 1}}},
            {"noteId": 2, "modelName": "Cloze", "fields": {"Extra": {"value": "", "order": 0}, "Text": {"value": "O {{c1::TCP}} é confiável", "order": 1}}},
        ]
        parsed = [cards.parse_note(r) for r in recs]
        with tempfile.TemporaryDirectory() as tmp:
            gen_path, val_path = os.path.join(tmp, "g.jsonl"), os.path.join(tmp, "v.jsonl")
            generate.generate(parsed, FakeLLM(), gen_path, log=lambda s: None)
            gen = list(read_jsonl(gen_path))
            validate.validate({c.note_id: c for c in parsed}, gen, FakeLLM(), val_path, log=lambda s: None)
            raw = json.dumps(pack.build_bank(parsed, gen, list(read_jsonl(val_path)), allow_fake=True)).encode()
        bank = V.Bank.from_bytes(raw)
        self.assertEqual(sorted(bank.notes), [1, 2])
        self.assertEqual((bank.entry(1)["kind"], bank.entry(1)["q_field"]), ("basic", 0))
        self.assertEqual((bank.entry(2)["kind"], bank.entry(2)["q_field"], bank.entry(2)["answer_html"]), ("cloze", 1, "TCP"))
        self.assertEqual(bank.skipped, 0)


class TextTest(unittest.TestCase):
    def test_basic_value_is_escaped_with_line_breaks(self):
        value, needles = V.field_value(basic_entry(), {"id": "v", "type": "t", "text": "A & B <i>\nlinha"})
        self.assertEqual(value, "A &amp; B &lt;i&gt;<br>linha")
        self.assertEqual(needles, [value])

    def test_cloze_value_places_the_blank_with_the_original_number(self):
        entry = {"kind": "cloze", "ords": [1], "q_field": 0, "answer_html": "ferro", "fields_hash": "f", "variants": []}
        value, needles = V.field_value(entry, {"id": "v", "type": "t", "text": "Protoporfirina e [...] formam o heme."})
        self.assertEqual(value, "Protoporfirina e {{c2::ferro}} formam o heme.")
        self.assertEqual(needles, ["Protoporfirina e", "formam o heme."])

    def test_cloze_blank_at_the_edges(self):
        entry = {"kind": "cloze", "ords": [0], "q_field": 0, "answer_html": "ferro", "fields_hash": "f", "variants": []}
        value, needles = V.field_value(entry, {"id": "v", "type": "t", "text": "[...] forma o heme."})
        self.assertEqual((value, needles), ("{{c1::ferro}} forma o heme.", ["forma o heme."]))


class MiscTest(unittest.TestCase):
    def test_window_is_inclusive_and_tolerates_bad_config(self):
        d = datetime.date
        self.assertTrue(V.in_window(d(2026, 11, 2), "2026-11-02", "2026-11-22"))
        self.assertTrue(V.in_window(d(2026, 11, 22), "2026-11-02", "2026-11-22"))
        self.assertFalse(V.in_window(d(2026, 11, 1), "2026-11-02", "2026-11-22"))
        self.assertFalse(V.in_window(d(2026, 11, 23), "2026-11-02", "2026-11-22"))
        self.assertFalse(V.in_window(d(2026, 11, 10), "amanhã", "2026-11-22"))

    def test_fields_hash_matches_the_pipeline(self):
        from dfc_pipeline.cards import parse_note

        rec = {"noteId": 1, "modelName": "Basic", "fields": {"Front": {"value": "Q?", "order": 0}, "Back": {"value": "A", "order": 1}}}
        self.assertEqual(parse_note(rec).fields_hash, V.fields_hash(["Q?", "A"]))


if __name__ == "__main__":
    unittest.main()
