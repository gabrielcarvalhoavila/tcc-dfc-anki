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

    def test_reorder_variant_keeps_each_answer_in_the_blank_of_its_own_item(self):
        note, card = self.ficha()
        variant = {"id": "v", "type": "reorder", "text": "Governo Mussolini\nConsiste: [...2]\nAntecedentes: [...1]"}
        value, needles = self.variants.field_value(self.FICHA_ENTRY, variant, note.fields[0])
        var_q, var_a = self.adapter.render_pair(self.col, card, 0, value)
        self.assertTrue(all(n in var_q for n in needles), needles)
        shown = re.sub(r"<[^>]+>", "", var_a)
        self.assertIn("Consiste: reconhecimento do Vaticano", shown)  # o marcador leva a sua própria resposta, mesmo fora de ordem
        self.assertIn("Antecedentes: Questão Romana", shown)
        self.assertLess(shown.index("Consiste:"), shown.index("Antecedentes:"))

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

    def test_new_variant_note_is_a_valid_unsaved_note_of_the_same_type(self):
        note, _ = self.ficha()
        variant = {"id": "v", "type": "pergunta", "text": "No governo Mussolini, quais foram os antecedentes do tratado? [...1]\nEm que consistiu o tratado? [...2]"}
        value, _ = self.variants.field_value(self.FICHA_ENTRY, variant)
        before = self.col.note_count()
        new = self.adapter.new_variant_note(self.col, note, 0, value, "dfc_variante")
        self.assertEqual((new.id, self.col.note_count()), (0, before))  # nada foi gravado: quem salva é a janela Adicionar
        self.assertEqual((new.note_type()["name"], new.tags), ("Cloze", ["dfc_variante"]))
        self.assertEqual(new.fields[1], "Pacto de 1929")  # os outros campos vêm da original
        self.assertIn('<img src="d.png">', new.fields[0])
        self.assertIn("{{c1::Questão Romana}}", new.fields[0])
        self.assertIn("{{c1::reconhecimento do Vaticano}}", new.fields[0])
        self.assertEqual(self.col.get_note(note.id)["Text"], self.FICHA)  # a original continua intacta
        self.col.add_note(new, 1)  # o que a janela Adicionar faz ao clicar em Adicionar
        self.assertEqual((len(new.cards()), self.col.note_count()), (1, before + 1))
        self.assertIn("No governo Mussolini", new.cards()[0].question())


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
            addonManager=types.SimpleNamespace(getConfig=lambda name: self.cfg, writeConfig=lambda name, c: self.cfg.update(c), setConfigUpdatedAction=lambda name, fn: None),
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


@unittest.skipUnless(HAS_ANKI, "pacote anki não instalado (opcional)")
class RealFreeModeTest(unittest.TestCase):
    """O uso livre (v0.5) sobre uma coleção real: troca na revisão, gravação das configurações na coleção e geração em lote a partir de baralhos reais."""

    setUp = RealHooksTest.setUp
    tearDown = RealHooksTest.tearDown
    variants_mod = RealHooksTest.variants_mod
    basic_note = RealHooksTest.basic_note
    age = RealHooksTest.age
    add_revlog = RealHooksTest.add_revlog

    FICHA = 'Governo Mussolini<br><div><img src="d.png"></div><br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}'

    def load_free(self):
        """Importa o add-on sem banco do estudo; o banco pessoal fica por conta de cada teste."""
        import importlib

        user_files = os.environ["DFC_PROBE_USER_FILES"]
        os.makedirs(user_files, exist_ok=True)
        self.mod = importlib.import_module("dfc_probe")
        self.free = importlib.import_module("dfc_probe.free")
        self.fm = self.mod._free
        self.fm.save_settings(self.free.Settings(enabled=True, probability=100))

    def chain(self, text, card, kind):
        for fn in self.hooks.card_will_show:
            text = fn(text, card, kind)
        return text

    def study(self, card, ease=3):
        munge = self.col.media.escape_media_filenames
        shown_q = self.chain(munge(card.question()), card, "reviewQuestion")
        self.hooks.reviewer_did_show_question[0](card)
        shown_a = self.chain(munge(card.answer()), card, "reviewAnswer")
        self.hooks.reviewer_did_show_answer[0](card)
        self.hooks.reviewer_did_answer_card[0](None, card, ease)
        return shown_q, shown_a

    def cloze_note(self, text=None):
        note = self.col.new_note(self.col.models.by_name("Cloze"))
        note["Text"], note["Back Extra"] = text or self.FICHA, "Pacto de 1929"
        self.col.add_note(note, 1)
        return note

    def test_free_variant_on_a_real_basic_card_and_the_event_says_so(self):
        note = self.basic_note()
        card = self.age(note)
        self.load_free()
        entry = {
            "kind": "basic", "ords": [0], "q_field": 0, "fields_hash": self.variants_mod().fields_hash(note.fields),
            "variants": [{"id": f"{note.id}-paraphrase-1", "type": "paraphrase", "text": "Que propriedade distingue a transmissão do TCP da do UDP?"}],
        }
        self.assertTrue(self.fm.bank().set_entry(note.id, entry))
        shown_q, shown_a = self.study(card)
        self.assertTrue(shown_q.startswith("<style>") and shown_q.endswith("Que propriedade distingue a transmissão do TCP da do UDP?"))
        self.assertIn("Entrega confiável e ordenada", shown_a)
        self.assertNotIn("O que o TCP", shown_q + shown_a)
        self.assertEqual(self.col.get_note(note.id)["Front"], "O que o TCP garante que o UDP não garante?")  # nada foi gravado
        (row,) = self.mod._store.rows()
        self.assertEqual((row["arm"], row["draw_note"], row["variant_id"], row["same_day"]), (None, "free_variant", None, 0))
        self.assertEqual(self.fm.bank().recent(note.id), [f"{note.id}-paraphrase-1"])

    def test_settings_live_in_the_collection(self):
        self.load_free()
        self.fm.save_settings(self.free.Settings(enabled=True, probability=25, types=["reorder"], deck_ids=[1]))
        s = self.free.Settings.from_raw(self.col.get_config("dfc_free"))
        self.assertEqual((s.probability, s.types, s.deck_ids), (25, ["reorder"], [1]))
        path = self.fm.bank().path  # o identificador do banco pessoal nasce na primeira vez que o banco é aberto
        self.assertEqual(self.col.get_config("dfc_free_id"), os.path.basename(path)[len("free_bank_"):-len(".json")])

    def test_card_filters_with_the_real_state(self):
        note = self.basic_note()
        new_card = note.cards()[0]  # cartão novo, nunca estudado
        self.load_free()
        entry = {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": self.variants_mod().fields_hash(note.fields), "variants": [{"id": "1-a", "type": "paraphrase", "text": "Outra pergunta sobre o TCP e o UDP?"}]}
        self.fm.bank().set_entry(note.id, entry)
        shown_q, _ = self.study(new_card)
        self.assertNotIn("Outra pergunta", shown_q)  # novo: sem variante
        card = self.age(note, reviews=((30, 0), (15, 1)))
        self.add_revlog(card.id, int(time.time() * 1000) - 120_000)  # respondido há dois minutos: mesmo dia
        shown_q, _ = self.study(self.col.get_card(card.id))
        self.assertNotIn("Outra pergunta", shown_q)
        self.fm.save_settings(self.free.Settings(enabled=True, probability=100, avoid_same_day=False))
        again = self.col.get_card(card.id)
        again.reps += 1  # a resposta anterior foi dada: o cartão volta como uma exposição nova
        self.col.update_card(again)
        shown_q, _ = self.study(self.col.get_card(card.id))
        self.assertIn("Outra pergunta", shown_q)

    def test_deck_scope_uses_the_real_deck_tree(self):
        parent = self.col.decks.id("Pai")
        child = self.col.decks.id("Pai::Filho")
        other = self.col.decks.id("Outro")
        notes = {}
        for name, did in (("filho", child), ("outro", other)):
            note = self.col.new_note(self.col.models.by_name("Basic"))
            note["Front"], note["Back"] = f"Pergunta do baralho {name} com texto suficiente?", "Resposta"
            self.col.add_note(note, did)
            notes[name] = note
        cards = {k: self.age(n) for k, n in notes.items()}
        self.load_free()
        self.fm.save_settings(self.free.Settings(enabled=True, probability=100, deck_ids=[parent]))
        for name, note in notes.items():
            self.fm.bank().set_entry(note.id, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": self.variants_mod().fields_hash(note.fields), "variants": [{"id": f"{name}-a", "type": "paraphrase", "text": f"Variante da pergunta {name}?"}]})
        self.assertIn("Variante da pergunta filho?", self.study(cards["filho"])[0])  # o subbaralho entra com o pai
        self.assertNotIn("Variante da pergunta outro?", self.study(cards["outro"])[0])

    def test_batch_from_real_decks_feeds_the_review_with_matching_hashes(self):
        from dfc_pipeline.llm import FakeLLM

        parent = self.col.decks.id("Estudo")
        child = self.col.decks.id("Estudo::Redes")
        basic, ficha = self.basic_note(), self.cloze_note()
        self.col.set_deck([c.id for n in (basic, ficha) for c in n.cards()], parent)
        short = self.col.new_note(self.col.models.by_name("Cloze"))
        short["Text"] = "A {{c1::água}} ferve."
        self.col.add_note(short, child)
        cards = {"basic": self.age(basic), "ficha": self.age(ficha), "short": self.age(short)}
        self.load_free()
        batch = importlib.import_module("dfc_probe.batch")
        core = importlib.import_module("dfc_probe.core")
        adapter = importlib.import_module("dfc_probe.anki_adapter")
        records = adapter.collect_records(self.col, parent, core.note_to_record)
        self.assertEqual({r["note_id"] for r in records}, {basic.id, ficha.id, short.id})  # o subbaralho vem junto
        plan = batch.make_plan(records, self.fm.bank(), set(), batch.Options())
        self.assertEqual(({r["note_id"] for r in plan.todo}, plan.ineligible), ({basic.id, ficha.id}, 1))
        summary = batch.run(plan.todo, FakeLLM(), FakeLLM(), self.fm.bank(), batch.Options(workers=2))
        self.assertEqual((summary.with_variants, summary.errors), (2, 0))
        self.assertEqual(sorted(v["type"] for v in self.fm.bank().entry(ficha.id)["variants"]), ["cue_swap", "paraphrase", "pergunta", "reorder", "sem_imagem"])
        # o hash que o pipeline calculou sobre `note.items()` é o mesmo que o gancho calcula sobre `note.fields`: as variantes aparecem
        shown_basic, answer_basic = self.study(cards["basic"])
        self.assertNotIn("O que o TCP", shown_basic + answer_basic)
        self.assertIn("Entrega confiável e ordenada", answer_basic)
        shown_ficha, answer_ficha = self.study(cards["ficha"])
        self.assertNotEqual(shown_ficha, self.col.media.escape_media_filenames(cards["ficha"].question()))
        self.assertIn("Pacto de 1929", answer_ficha)

    def test_collect_records_filters_and_orders_by_due_date(self):
        parent = self.col.decks.id("Pai")
        child = self.col.decks.id("Pai::Filho")
        made = {}
        for name, did, text in (("tarde", parent, "tarde"), ("cedo", child, "cedo"), ("nova", parent, "nova"), ("suspensa", parent, "suspensa"), ("fora", self.col.decks.id("Outro"), "fora")):
            note = self.col.new_note(self.col.models.by_name("Basic"))
            note["Front"], note["Back"] = f"Pergunta {text} com texto suficiente para o teste?", "Resposta"
            self.col.add_note(note, did)
            made[name] = note
        for name, due_offset in (("tarde", 5), ("cedo", -3), ("suspensa", -9), ("fora", -1)):
            card = self.age(made[name])
            card.due = self.col.sched.today + due_offset
            self.col.update_card(card)
        self.col.sched.suspend_cards([made["suspensa"].cards()[0].id])
        self.load_free()
        adapter = importlib.import_module("dfc_probe.anki_adapter")
        core = importlib.import_module("dfc_probe.core")

        def ids(**kw):
            return [r["note_id"] for r in adapter.collect_records(self.col, parent, core.note_to_record, **kw)]

        self.assertEqual(ids(), [made["cedo"].id, made["tarde"].id])  # sem novas nem suspensas; as que vencem primeiro na frente
        self.assertEqual(ids(children=False), [made["tarde"].id])
        self.assertEqual(ids(skip_suspended=False), [made["suspensa"].id, made["cedo"].id, made["tarde"].id])
        self.assertEqual(ids(skip_new=False), [made["cedo"].id, made["tarde"].id, made["nova"].id])  # novas por último
        self.assertEqual(adapter.collect_records(self.col, parent, core.note_to_record)[0]["decks"], ["Pai"])
        self.assertEqual(adapter.collect_records(self.col, self.col.decks.id("Vazio"), core.note_to_record), [])


if __name__ == "__main__":
    unittest.main()
