"""Teste com o motor real do Anki (pacote `anki`, sem interface). Pula se o pacote não estiver instalado.

Para rodar: python -m venv .venv; .venv\\Scripts\\python -m pip install anki==26.5; .\\scripts\\run_tests.ps1 -Real
"""
import importlib.util
import os
import re
import sys
import tempfile
import time
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

HAS_ANKI = importlib.util.find_spec("anki") is not None


def load(name, *relpath):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAS_ANKI, "pacote anki não instalado (opcional)")
class RealRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from anki.collection import Collection

        cls.tmp = tempfile.TemporaryDirectory()
        cls.col = Collection(os.path.join(cls.tmp.name, "collection.anki2"))
        cls.adapter = load("dfc_adapter_real", "addon", "dfc_probe", "anki_adapter.py")
        cls.variants = load("dfc_variants_real", "addon", "dfc_probe", "variants.py")

    @classmethod
    def tearDownClass(cls):
        cls.col.close()
        cls.tmp.cleanup()

    def add(self, model, **fields):
        note = self.col.new_note(self.col.models.by_name(model))
        for name, value in fields.items():
            note[name] = value
        self.col.add_note(note, 1)
        return note

    def basic(self):
        note = self.add("Basic", Front="O que o TCP garante que o UDP não garante?", Back="Entrega confiável e ordenada")
        return note, note.cards()[0]

    def cloze(self):
        note = self.add("Cloze", Text="O heme é formado por protoporfirina e {{c1::ferro}}.", **{"Back Extra": "Fe2+"})
        return note, note.cards()[0]

    def test_render_pair_is_contained_in_the_reviewer_render_for_basic(self):
        _, card = self.basic()
        question, answer = self.adapter.render_pair(self.col, card)
        self.assertIn(question, card.question())  # o Anki acrescenta o <style> antes do texto
        self.assertIn(answer, card.answer())

    def test_render_pair_is_contained_in_the_reviewer_render_for_cloze(self):
        _, card = self.cloze()
        question, answer = self.adapter.render_pair(self.col, card)
        self.assertIn(question, card.question())
        self.assertIn(answer, card.answer())

    def test_basic_variant_replaces_both_sides_like_the_hook_does(self):
        note, card = self.basic()
        entry = {"kind": "basic", "ords": [0], "q_field": 0, "variants": []}
        variant = {"id": "v1", "type": "paraphrase", "text": "Que propriedade distingue a transmissão do TCP da do UDP?"}
        value, needles = self.variants.field_value(entry, variant)
        orig_q, orig_a = self.adapter.render_pair(self.col, card)
        var_q, var_a = self.adapter.render_pair(self.col, card, 0, value)
        self.assertTrue(all(n in var_q and n in var_a for n in needles))
        self.assertNotIn("O que o TCP", var_q + var_a)
        self.assertIn("Entrega confiável e ordenada", var_a)  # a resposta continua a original
        shown_q = card.question().replace(orig_q, var_q, 1)  # é o que o gancho faz com o texto que o Anki entrega
        shown_a = card.answer().replace(orig_a, var_a, 1)
        self.assertTrue(shown_q.startswith("<style>") and shown_q.endswith(var_q))
        self.assertTrue(shown_a.startswith("<style>") and shown_a.endswith(var_a))
        self.assertNotIn("O que o TCP", shown_q + shown_a)
        self.assertEqual(self.col.get_note(note.id)["Front"], "O que o TCP garante que o UDP não garante?")  # nada foi gravado

    def test_cloze_variant_keeps_the_blank_and_the_extra_field(self):
        note, card = self.cloze()
        entry = {"kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["ferro"], "variants": []}
        variant = {"id": "v2", "type": "reorder", "text": "Protoporfirina e [...] formam o heme."}
        value, needles = self.variants.field_value(entry, variant)
        var_q, var_a = self.adapter.render_pair(self.col, card, 0, value)
        self.assertTrue(all(n in var_q for n in needles))
        self.assertIn("[...]", var_q)
        self.assertNotIn("ferro", re.sub(r"<[^>]+>", "", var_q))  # o Anki guarda a resposta num atributo data-cloze, invisível
        self.assertIn("ferro", var_a)
        self.assertIn("Fe2+", var_a)  # Back Extra preservado pelo template real
        self.assertEqual(self.col.get_note(note.id)["Text"], "O heme é formado por protoporfirina e {{c1::ferro}}.")

    def test_markup_in_a_variant_is_escaped_not_interpreted(self):
        _, card = self.basic()
        entry = {"kind": "basic", "ords": [0], "q_field": 0, "variants": []}
        value, needles = self.variants.field_value(entry, {"id": "v", "type": "t", "text": "TCP <b>e</b> UDP & mais?"})
        var_q, _ = self.adapter.render_pair(self.col, card, 0, value)
        self.assertIn("TCP &lt;b&gt;e&lt;/b&gt; UDP &amp; mais?", var_q)
        self.assertNotIn("<b>", var_q)

    def test_fields_hash_matches_the_pipeline(self):
        from dfc_pipeline.cards import parse_note

        note, _ = self.basic()
        rec = {
            "noteId": note.id,
            "modelName": "Basic",
            "fields": {"Front": {"value": note.fields[0], "order": 0}, "Back": {"value": note.fields[1], "order": 1}},
            "tags": [],
        }
        self.assertEqual(parse_note(rec).fields_hash, self.variants.fields_hash(note.fields))

    FICHA = 'Governo Mussolini<br><div><img src="d.png"></div><br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}'
    FICHA_ENTRY = {
        "kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["Questão Romana", "reconhecimento do Vaticano"],
        "images_html": ['<img src="d.png">'], "variants": [],
    }

    def ficha(self):
        note = self.add("Cloze", Text=self.FICHA, **{"Back Extra": "Pacto de 1929"})
        return note, note.cards()[0]

    def test_pergunta_variant_keeps_the_image_and_both_blanks_of_a_ficha(self):
        note, card = self.ficha()
        variant = {"id": "v", "type": "pergunta", "text": "No governo Mussolini, quais foram os antecedentes do tratado? [...1]\nEm que consistiu o tratado? [...2]"}
        value, needles = self.variants.field_value(self.FICHA_ENTRY, variant, note.fields[0])
        orig_q, orig_a = self.adapter.render_pair(self.col, card)
        var_q, var_a = self.adapter.render_pair(self.col, card, 0, value)
        self.assertTrue(all(n in var_q for n in needles), needles)  # o texto novo e a imagem original
        self.assertEqual((orig_q.count('class="cloze"'), var_q.count('class="cloze"')), (2, 2))
        visible = re.sub(r"<[^>]+>", "", var_q)
        self.assertNotIn("Questão Romana", visible)  # as respostas continuam ocultas na pergunta
        self.assertNotIn("Vaticano", visible)
        for shown in ("Questão Romana", "reconhecimento do Vaticano", "Pacto de 1929"):
            self.assertIn(shown, var_a)  # a resposta revela as duas lacunas e o Back Extra do template real
        self.assertNotIn("Antecedentes:", var_q + var_a)  # o molde de rótulos saiu
        self.assertEqual(self.col.get_note(note.id)["Text"], self.FICHA)  # nada foi gravado

    def test_sem_imagem_variant_removes_only_the_image(self):
        note, card = self.ficha()
        value, needles = self.variants.field_value(self.FICHA_ENTRY, {"id": "1-sem_imagem", "type": "sem_imagem"}, note.fields[0])
        orig_q, _ = self.adapter.render_pair(self.col, card)
        var_q, var_a = self.adapter.render_pair(self.col, card, 0, value)
        self.assertEqual(needles, [])
        self.assertIn("d.png", orig_q)
        self.assertNotIn("d.png", var_q)
        self.assertNotEqual(var_q, orig_q)
        for kept in ("Governo Mussolini", "Antecedentes:", "Consiste:"):
            self.assertIn(kept, var_q)
        self.assertEqual(var_q.count('class="cloze"'), 2)
        self.assertEqual(self.col.get_note(note.id)["Text"], self.FICHA)


@unittest.skipUnless(HAS_ANKI, "pacote anki não instalado (opcional)")
class RealHooksTest(unittest.TestCase):
    """O add-on inteiro (ganchos, sorteio, registro, exportação) sobre uma coleção real do Anki; só a interface (aqt) é simulada."""

    def setUp(self):
        import types

        import test_addon_smoke as smoke
        from anki.collection import Collection

        self.tmp = tempfile.TemporaryDirectory()
        self.col = Collection(os.path.join(self.tmp.name, "collection.anki2"))
        self.messages, self.dialog = [], {"path": ""}
        self.cfg = {"enabled": True, "draw_enabled": True, "draw_start": "2020-01-01", "draw_end": "2099-12-31", "bad_shortcut": "b", "anonymize_export": False}
        self.hooks = types.SimpleNamespace(
            reviewer_did_show_question=[], reviewer_did_show_answer=[], reviewer_did_answer_card=[],
            card_will_show=[], state_shortcuts_will_change=[], reviewer_will_show_context_menu=[],
        )
        self.mw = types.SimpleNamespace(
            col=self.col,
            pm=types.SimpleNamespace(name="Perfil"),
            addonManager=types.SimpleNamespace(getConfig=lambda name: self.cfg, writeConfig=lambda name, c: self.cfg.update(c)),
            form=types.SimpleNamespace(menuTools=smoke.Menu()),
        )
        aqt, qt, utils = types.ModuleType("aqt"), types.ModuleType("aqt.qt"), types.ModuleType("aqt.utils")
        aqt.mw, aqt.gui_hooks = self.mw, self.hooks
        qt.QAction = smoke.Action
        qt.QFileDialog = types.SimpleNamespace(getSaveFileName=lambda *a, **k: (self.dialog["path"], ""), getOpenFileName=lambda *a, **k: ("", ""))
        qt.QInputDialog = types.SimpleNamespace(getText=lambda *a, **k: ("", True))
        utils.showInfo = utils.tooltip = self.messages.append
        self.saved = {m: sys.modules.get(m) for m in ("aqt", "aqt.qt", "aqt.utils")}
        sys.modules.update({"aqt": aqt, "aqt.qt": qt, "aqt.utils": utils})
        os.environ["DFC_PROBE_USER_FILES"] = os.path.join(self.tmp.name, "user_files")
        sys.path.insert(0, os.path.join(ROOT, "addon"))
        self.pending_bank = None

    def tearDown(self):
        for name, mod in self.saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod
        for name in [m for m in sys.modules if m == "dfc_probe" or m.startswith("dfc_probe.")]:
            del sys.modules[name]
        os.environ.pop("DFC_PROBE_USER_FILES", None)
        sys.path.remove(os.path.join(ROOT, "addon"))
        self.col.close()
        self.tmp.cleanup()

    def load_addon(self, notes):
        """notes: {note: entrada do banco sem o fields_hash}. Grava o banco e importa o add-on, que o lê ao iniciar."""
        import importlib
        import json

        entries = {}
        for note, entry in notes.items():
            entries[str(note.id)] = {**entry, "fields_hash": self.variants_mod().fields_hash(note.fields)}
        user_files = os.environ["DFC_PROBE_USER_FILES"]
        os.makedirs(user_files, exist_ok=True)
        with open(os.path.join(user_files, "variant_bank.json"), "w", encoding="utf-8") as f:
            json.dump({"schema": 3, "notes": entries}, f)
        self.mod = importlib.import_module("dfc_probe")
        self.mod.variants.VARIANT_PROBABILITY = 1.0

    def variants_mod(self):
        return load("dfc_variants_for_hash", "addon", "dfc_probe", "variants.py")

    def basic_note(self):
        note = self.col.new_note(self.col.models.by_name("Basic"))
        note["Front"], note["Back"] = "O que o TCP garante que o UDP não garante?", "Entrega confiável e ordenada"
        self.col.add_note(note, 1)
        return note

    def age(self, note, reviews=((30, 0), (25, 0), (15, 1), (5, 1)), reps=4):
        """Deixa o cartão como um de revisão, com histórico no revlog (dias atrás, tipo: 0 aprender, 1 revisão)."""
        card = note.cards()[0]
        card.type, card.queue, card.ivl, card.reps, card.due = 2, 2, 10, reps, self.col.sched.today - 1
        self.col.update_card(card)
        now_ms = int(time.time() * 1000)
        for i, (days_ago, kind) in enumerate(reviews):
            self.add_revlog(card.id, now_ms - days_ago * 86_400_000 + i, kind)
        return self.col.get_card(card.id)

    def add_revlog(self, card_id, entry_id, kind=1, ease=3):
        self.col.db.execute(
            "insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) values (?, ?, -1, ?, 10, 5, 2500, 5000, ?)",
            entry_id, card_id, ease, kind,
        )

    def study(self, card, ease=3):
        munge = self.col.media.escape_media_filenames  # o Reviewer faz isso com o texto antes do gancho (_mungeQA)
        original_q = munge(card.question())
        shown_q = self.hooks.card_will_show[0](original_q, card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shown_a = self.hooks.card_will_show[0](munge(card.answer()), card, "reviewAnswer")
        self.hooks.reviewer_did_show_answer[0](card)
        self.hooks.reviewer_did_answer_card[0](None, card, ease)
        return original_q, shown_q, shown_a

    BASIC_ENTRY = {
        "kind": "basic", "ords": [0], "q_field": 0,
        "variants": [{"id": "n-paraphrase-1", "type": "paraphrase", "text": "Que propriedade distingue a transmissão do TCP da do UDP?"}],
    }

    def test_variant_is_shown_and_the_event_carries_the_real_card_state(self):
        note = self.basic_note()
        card = self.age(note)
        self.load_addon({note: self.BASIC_ENTRY})
        original_q, shown_q, shown_a = self.study(card)
        self.assertTrue(shown_q.startswith("<style>") and shown_q.endswith("Que propriedade distingue a transmissão do TCP da do UDP?"))
        self.assertIn("Que propriedade distingue", shown_a)
        self.assertIn("Entrega confiável e ordenada", shown_a)
        self.assertNotIn("O que o TCP", shown_q + shown_a)
        (row,) = self.mod._store.rows()
        self.assertEqual(
            (row["arm"], row["shown_ok"], row["draw_note"], row["reps"], row["n_reviews"], row["same_day"], row["scheduler"], row["profile"]),
            ("variant", 1, "ok", 4, 2, 0, "sm2", "Perfil"),
        )
        self.assertTrue(row["days_since_last_review"] > 4.9)
        self.assertEqual(row["variant_id"], "n-paraphrase-1")

    def test_same_day_exposure_gets_no_draw_with_the_real_day_boundary(self):
        note = self.basic_note()
        card = self.age(note, reviews=((30, 0), (15, 1)))
        self.add_revlog(card.id, int(time.time() * 1000) - 120_000)  # duas minutos atrás
        card = self.col.get_card(card.id)
        self.load_addon({note: self.BASIC_ENTRY})
        original_q, shown_q, _ = self.study(card)
        self.assertEqual(shown_q, original_q)
        (row,) = self.mod._store.rows()
        self.assertEqual((row["arm"], row["draw_note"], row["same_day"]), (None, "same_day", 1))

    def test_export_marks_the_undone_answer_with_the_real_revlog(self):
        note = self.basic_note()
        card = self.age(note)
        self.load_addon({note: self.BASIC_ENTRY})
        self.study(card, ease=3)  # desfeita: nada entra no revlog
        self.study(card, ease=1)
        first, second = self.mod._store.rows()
        self.add_revlog(card.id, int(second["answered_at"] * 1000) - 7, ease=1)  # a resposta que valeu
        import csv

        out = os.path.join(self.tmp.name, "ev.csv")
        from dfc_probe import core
        from dfc_probe.anki_adapter import make_revlog_matcher

        core.export_csv(self.mod._store, out, revlog_match=make_revlog_matcher(self.mw))
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([(r["ease"], r["revlog_match"], r["superseded"], r["after_undo"]) for r in rows], [("3", "0", "1", "0"), ("1", "1", "0", "1")])

    def test_undo_keeps_the_same_variant_on_a_real_collection(self):
        note = self.basic_note()
        card = self.age(note)
        entry = {
            **self.BASIC_ENTRY,
            "variants": [
                {"id": "n-1", "type": "paraphrase", "text": "Primeira variante?"},
                {"id": "n-2", "type": "reorder", "text": "Segunda variante?"},
            ],
        }
        self.load_addon({note: entry})
        _, first_q, _ = self.study(card)
        self.mod.variants.VARIANT_PROBABILITY = 0.0  # um novo sorteio daria o original
        _, again_q, _ = self.study(card)  # Ctrl+Z: mesmo cartão, mesmo reps
        self.assertEqual(first_q, again_q)
        self.assertTrue(first_q.endswith(("Primeira variante?", "Segunda variante?")))
        first, again = self.mod._store.rows()
        self.assertEqual((again["draw_note"], again["variant_id"], again["draw_seed"]), ("undo_redo", first["variant_id"], first["draw_seed"]))

    def test_image_filenames_escaped_by_the_reviewer_do_not_break_the_swap(self):
        text = 'Governo Mussolini<br><img src="Imagem ação 1.png"><br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}'
        entry = {
            "kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["Questão Romana", "reconhecimento do Vaticano"], "images_html": ['<img src="Imagem ação 1.png">'],
            "variants": [{"id": "x-pergunta", "type": "pergunta", "text": "Quais foram os antecedentes do tratado? [...1]\nEm que consiste? [...2]"}],
        }
        notes = []
        for _ in range(2):
            note = self.col.new_note(self.col.models.by_name("Cloze"))
            note["Text"] = text
            self.col.add_note(note, 1)
            notes.append(note)
        cards = [self.age(n) for n in notes]
        self.load_addon({n: entry for n in notes})
        original_q, shown_q, _ = self.study(cards[0])
        self.assertIn("Imagem%20ação%201.png", original_q)  # o Reviewer escapa o nome do arquivo (IRI: espaço vira %20)
        self.assertIn("Quais foram os antecedentes do tratado?", shown_q)
        self.assertIn("Imagem%20ação%201.png", shown_q)  # imagem mantida, com o mesmo escape
        self.assertEqual((self.mod._store.rows()[0]["variant_type"], self.mod._store.rows()[0]["shown_ok"]), ("pergunta", 1))
        self.mod._munge = lambda t: t  # sem o escape a troca por substring não casa e o add-on mostra o original
        original_q2, shown_q2, _ = self.study(cards[1])
        self.assertEqual(shown_q2, original_q2)
        second = self.mod._store.rows()[1]
        self.assertEqual((second["shown_ok"], second["draw_note"]), (0, "template_mismatch"))

    def test_cloze_variant_on_a_real_cloze_note(self):
        note = self.col.new_note(self.col.models.by_name("Cloze"))
        note["Text"], note["Back Extra"] = "O heme é formado por protoporfirina e {{c1::ferro}}.", "Fe2+"
        self.col.add_note(note, 1)
        card = self.age(note)
        entry = {
            "kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["ferro"],
            "variants": [{"id": "c-1", "type": "reorder", "text": "Protoporfirina e [...] formam o heme."}],
        }
        self.load_addon({note: entry})
        original_q, shown_q, shown_a = self.study(card)
        self.assertIn("Protoporfirina e", shown_q)
        self.assertIn("[...]", shown_q)
        self.assertNotIn("O heme é formado", shown_q + shown_a)
        self.assertIn("ferro", shown_a)
        self.assertIn("Fe2+", shown_a)
        (row,) = self.mod._store.rows()
        self.assertEqual((row["arm"], row["shown_ok"]), ("variant", 1))

    def test_ficha_pergunta_and_sem_imagem_through_the_real_hooks(self):
        ficha = 'Governo Mussolini<br><div><img src="d.png"></div><br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}'
        notes = {}
        for kind in ("pergunta", "sem_imagem"):
            note = self.col.new_note(self.col.models.by_name("Cloze"))
            note["Text"], note["Back Extra"] = ficha, "Pacto de 1929"
            self.col.add_note(note, 1)
            variant = {"id": f"{note.id}-{kind}", "type": kind}
            if kind == "pergunta":
                variant["text"] = "No governo Mussolini, quais foram os antecedentes do tratado? [...1]\nEm que consistiu o tratado? [...2]"
            entry = {"kind": "cloze", "ords": [0], "q_field": 0, "answers_html": ["Questão Romana", "reconhecimento do Vaticano"], "images_html": ['<img src="d.png">'], "variants": [variant]}
            notes[kind] = (note, entry)
        cards = {kind: self.age(note) for kind, (note, _) in notes.items()}
        self.load_addon({note: entry for note, entry in notes.values()})
        _, q_pergunta, a_pergunta = self.study(cards["pergunta"])
        _, q_sem, a_sem = self.study(cards["sem_imagem"])
        self.assertIn("quais foram os antecedentes do tratado?", q_pergunta)
        self.assertIn("d.png", q_pergunta)  # a imagem original continua
        self.assertNotIn("Antecedentes:", q_pergunta + a_pergunta)  # o molde de rótulos saiu nos dois lados
        self.assertIn("Pacto de 1929", a_pergunta)
        self.assertNotIn("d.png", q_sem + a_sem)  # sem imagem nos dois lados
        self.assertIn("Antecedentes:", q_sem)
        rows = self.mod._store.rows()
        self.assertEqual([(r["variant_type"], r["shown_ok"], r["draw_note"]) for r in rows], [("pergunta", 1, "ok"), ("sem_imagem", 1, "ok")])
        self.assertEqual([(r["note_kind"], r["n_blanks"], r["has_image"]) for r in rows], [("cloze", 2, 1), ("cloze", 2, 1)])


if __name__ == "__main__":
    unittest.main()
