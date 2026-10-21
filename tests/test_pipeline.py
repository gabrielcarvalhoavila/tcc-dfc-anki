"""Testes do pipeline de variantes (sem rede externa e sem Anki)."""
import contextlib
import csv
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from dfc_pipeline import audit, cards, cli, generate, pack, source, validate  # noqa: E402
from dfc_pipeline.llm import FakeLLM, LLMClient, LLMError, parse_json_loose  # noqa: E402
from dfc_pipeline.util import read_jsonl, run_parallel, write_jsonl  # noqa: E402


def ac_note(note_id, front, back, model="Basic", tags=None):
    """Formato do AnkiConnect (notesInfo)."""
    return {
        "noteId": note_id,
        "modelName": model,
        "tags": tags or [],
        "fields": {"Front": {"value": front, "order": 0}, "Back": {"value": back, "order": 1}},
        "cards": [note_id],
    }


class CardsTest(unittest.TestCase):
    def test_strip_html(self):
        self.assertEqual(cards.strip_html("<div>Olá&nbsp;<b>mundo</b></div><br>fim"), "Olá mundo\nfim")

    def test_basic_eligible(self):
        c = cards.parse_note(ac_note(1, "O que é NAT?", "Network Address Translation, técnica de tradução de endereços."))
        self.assertTrue(c.eligible)
        self.assertEqual((c.kind, c.ords, c.question_text), ("basic", [0], "O que é NAT?"))

    def test_ineligible_reasons(self):
        self.assertIn("media_or_latex", cards.parse_note(ac_note(1, "Q <img src='a.png'>", "resposta longa aqui")).reasons)
        self.assertIn("media_or_latex", cards.parse_note(ac_note(1, "Valor de \\(x^2\\)?", "quatro vezes dois")).reasons)
        self.assertIn("numeric_answer", cards.parse_note(ac_note(1, "Ano da fundação?", "1998")).reasons)
        self.assertIn("empty_answer", cards.parse_note(ac_note(1, "Pergunta", "")).reasons)
        self.assertIn("model_not_supported", cards.parse_note(ac_note(1, "Q", "A longa", model="Basic (type in the answer)")).reasons)

    def test_cloze_single_and_multi(self):
        one = {"noteId": 2, "modelName": "Omissão de Palavras", "fields": {"Texto": {"value": "O {{c1::TCP}} é um protocolo de transporte confiável", "order": 0}, "Extra": {"value": "", "order": 1}}}
        c = cards.parse_note(one)
        self.assertEqual((c.kind, c.ords, c.question_text, c.answer_text, c.blanks), ("cloze", [0], "O [...] é um protocolo de transporte confiável", "TCP", 1))
        self.assertTrue(c.eligible)
        several_cards = {"noteId": 3, "modelName": "Cloze", "fields": {"Text": "{{c1::a}} e {{c2::b}} são as duas primeiras letras do alfabeto"}}
        self.assertIn("multi_cloze", cards.parse_note(several_cards).reasons)  # vários cartões por nota
        two_fields = {"noteId": 8, "modelName": "Cloze", "fields": {"Text": "O {{c1::TCP}} é um protocolo de transporte confiável", "Extra": "{{c1::UDP}} não"}}
        self.assertIn("multi_cloze", cards.parse_note(two_fields).reasons)

    def test_cloze_with_several_blanks_in_the_same_card(self):
        text = "Governo Mussolini<br>Tratado de Latrão<br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}<br>Medida: {{c1::indenização à Igreja}}"
        c = cards.parse_note({"noteId": 5, "modelName": "Cloze", "fields": {"Text": text}})
        self.assertEqual((c.blanks, c.markers, c.ords), (3, ["[...1]", "[...2]", "[...3]"], [0]))
        self.assertEqual(c.answers_text, ["Questão Romana", "reconhecimento do Vaticano", "indenização à Igreja"])
        self.assertEqual(c.answer_text, "1: Questão Romana | 2: reconhecimento do Vaticano | 3: indenização à Igreja")
        self.assertIn("Antecedentes: [...1]", c.question_text)
        self.assertTrue(c.eligible, c.reasons)
        four = cards.parse_note({"noteId": 5, "modelName": "Cloze", "fields": {"Text": text + "<br>Mais: {{c1::quarta}}"}})
        self.assertEqual((four.blanks, four.reasons), (4, ["too_many_blanks"]))

    def test_cloze_image_is_kept_and_other_media_still_block(self):
        base = 'Mrs Dalloway<br><div><img src="d.png"></div><br>Personagens<br>Lucrezia é a: {{c1::esposa}}<br>Que sofre com: {{c1::trauma}}'
        c = cards.parse_note({"noteId": 6, "modelName": "Cloze", "fields": {"Text": base}})
        self.assertTrue(c.eligible, c.reasons)
        self.assertEqual(c.images_html, ['<img src="d.png">'])
        self.assertNotIn("img", c.question_text)
        self.assertIn("media_or_latex", cards.parse_note({"noteId": 6, "modelName": "Cloze", "fields": {"Text": base + " \\(x^2\\)"}}).reasons)
        self.assertIn("media_or_latex", cards.parse_note({"noteId": 6, "modelName": "Cloze", "fields": {"Text": base.replace("{{c1::esposa}}", "{{c1::<img src='r.png'>}}")}}).reasons)  # imagem na resposta

    def test_cloze_needs_enough_visible_text_and_a_non_numeric_answer(self):
        short = cards.parse_note({"noteId": 9, "modelName": "Cloze", "fields": {"Text": "Propulsa<br><img src='p.png'><br>fórmula: {{c1::F = m.a}}"}})
        self.assertEqual(short.reasons, ["short_text"])  # a imagem seria o enunciado
        numbers = cards.parse_note({"noteId": 9, "modelName": "Cloze", "fields": {"Text": "A Revolução Francesa começou em {{c1::1789}} e terminou em {{c1::1799}}"}})
        self.assertEqual(numbers.reasons, ["numeric_answer"])
        mixed = cards.parse_note({"noteId": 9, "modelName": "Cloze", "fields": {"Text": "A Revolução Francesa começou em {{c1::1789}} na {{c1::França}} de Luís XVI"}})
        self.assertTrue(mixed.eligible, mixed.reasons)

    def test_cards_jsonl_from_before_v1_2_still_loads(self):
        old = cards.parse_note({"noteId": 2, "modelName": "Cloze", "fields": {"Text": "O {{c1::TCP}} é um protocolo de transporte confiável"}}).to_dict()
        for key in ("blanks", "answers_html", "answers_text", "images_html"):
            del old[key]
        c = cards.Card.from_dict(old)
        self.assertEqual((c.blanks, c.answers_html, c.answers_text, c.images_html), (1, ["TCP"], ["TCP"], []))

    def test_question_field_index_is_recorded(self):
        second = {"noteId": 4, "modelName": "Cloze", "fields": {"Extra": {"value": "", "order": 0}, "Text": {"value": "O {{c2::TCP}} é confiável", "order": 1}}}
        c = cards.parse_note(second)
        self.assertEqual((c.q_field, c.ords), (1, [1]))
        self.assertEqual(cards.parse_note(ac_note(1, "O que é NAT?", "Tradução de endereços de rede.")).q_field, 0)
        old = cards.parse_note(ac_note(1, "O que é NAT?", "Tradução de endereços de rede.")).to_dict()
        del old["q_field"]  # cards.jsonl gerado antes do campo existir
        self.assertEqual(cards.Card.from_dict(old).q_field, 0)

    def test_same_hash_for_both_export_shapes(self):
        a = cards.parse_note(ac_note(1, "Q?", "A longa"))
        b = cards.parse_note({"note_id": 1, "model": "Basic", "fields": {"Front": "Q?", "Back": "A longa"}})
        self.assertEqual(a.fields_hash, b.fields_hash)

    def test_summary_counts_suspects(self):
        n = ac_note(1, "O que é NAT?", "Tradução de endereços de rede.")
        n["decks"], n["stats"] = ["Redes"], {"reps": 6, "lapses": 0}
        s = cards.summarize([cards.parse_note(n)])
        self.assertEqual(s["por_baralho"]["Redes"], {"notas": 1, "elegiveis": 1, "elegiveis_suspeitos": 1})


class SourceTest(unittest.TestCase):
    def test_limit_reads_only_a_seeded_sample_of_the_notes(self):
        asked = []

        def invoke(action, **params):
            if action == "findNotes":
                return list(range(1, 51))
            if action == "notesInfo":
                asked.extend(params["notes"])
                return [{"noteId": i, "modelName": "Basic", "fields": {}, "cards": []} for i in params["notes"]]
            return []

        quiet = {"invoke": invoke, "log": lambda s: None}
        recs = source.from_ankiconnect("deck:X", limit=7, seed=3, **quiet)
        self.assertEqual((len(recs), len(set(asked))), (7, 7))  # o texto das outras 43 notas não foi pedido ao Anki
        again = source.from_ankiconnect("deck:X", limit=7, seed=3, **quiet)
        self.assertEqual([r["noteId"] for r in again], [r["noteId"] for r in recs])
        self.assertEqual(len(source.from_ankiconnect("deck:X", limit=100, **quiet)), 50)


class LLMTest(unittest.TestCase):
    def test_parse_json_loose(self):
        self.assertEqual(parse_json_loose('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(parse_json_loose('Claro! {"a": {"b": 2}} pronto'), {"a": {"b": 2}})
        for bad in ("sem json", "{quebrado", "[1, 2]"):
            with self.assertRaises(ValueError):
                parse_json_loose(bad)

    def serve(self, handler):
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        # addCleanup roda na ordem inversa: o shutdown precisa vir antes de fechar o soquete.
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}/v1"

    def test_retry_on_429_then_success_and_auth_header(self):
        seen = {"calls": 0, "auth": None, "agent": None}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["calls"] += 1
                seen["auth"] = self.headers.get("Authorization")
                seen["agent"] = self.headers.get("User-Agent")
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if seen["calls"] == 1:
                    self.send_response(429)
                    self.send_header("Retry-After", "0")
                    self.end_headers()
                    self.wfile.write(b'{"error": "rate"}')
                    return
                data = json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {"total_tokens": 7}, "model": body["model"]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        sleeps = []
        client = LLMClient(self.serve(H), "chave-teste", "m1", sleep=sleeps.append)
        out = client.chat([{"role": "user", "content": "oi"}])
        self.assertEqual((out["text"], out["usage"], out["model"]), ('{"ok": true}', {"total_tokens": 7}, "m1"))
        self.assertEqual((seen["calls"], sleeps, seen["auth"]), (2, [0.0], "Bearer chave-teste"))
        self.assertTrue(seen["agent"].startswith("dfc-pipeline/"))

    def test_client_error_is_not_retried(self):
        calls = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append(1)
                self.rfile.read(int(self.headers["Content-Length"]))
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"no")

            def log_message(self, *a):
                pass

        client = LLMClient(self.serve(H), "x", "m", sleep=lambda s: None)
        with self.assertRaises(LLMError):
            client.chat([{"role": "user", "content": "oi"}])
        self.assertEqual(len(calls), 1)

    def test_extra_body_is_sent_but_cannot_replace_model_or_messages(self):
        seen = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                data = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        client = LLMClient(self.serve(H), "x", "m1", temperature=0.0, extra_body={"reasoning_effort": "minimal", "temperature": 1.0, "model": "outro", "messages": []})
        client.chat([{"role": "user", "content": "oi"}])
        body = seen["body"]
        self.assertEqual((body["reasoning_effort"], body["temperature"], body["model"], len(body["messages"])), ("minimal", 1.0, "m1", 1))

    def test_ping_lists_models_hides_the_key_and_fails_on_a_bad_model(self):
        class H(http.server.BaseHTTPRequestHandler):
            def reply(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self.reply(200, {"data": [{"id": "models/gemini-3.8-flash"}, {"id": "models/gemini-3.5-flash-lite"}, {"id": "models/embedding-001"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if body["model"] == "inexistente":
                    self.reply(404, {"error": {"message": "model not found"}})
                else:
                    self.reply(200, {"choices": [{"message": {"content": '{"soma": 42, "idioma": "pt"}'}}], "usage": {"total_tokens": 9}})

            def log_message(self, *a):
                pass

        env = {
            "DFC_LLM_BASE_URL": self.serve(H), "DFC_LLM_API_KEY": "SEGREDO-123", "DFC_GEN_MODEL": "gemini-3.8-flash",
            "DFC_JUDGE_MODEL": "gemini-3.5-flash-lite", "DFC_JUDGE_EXTRA_BODY": '{"reasoning_effort": "minimal"}',
        }
        args = cli.build_parser().parse_args(["ping", "--models", "flash"])
        out = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out):
            self.assertEqual(cli.cmd_ping(args), 0)
        text = out.getvalue()
        self.assertIn("models/gemini-3.5-flash-lite, models/gemini-3.8-flash", text)
        self.assertNotIn("embedding", text)  # o filtro tira o que não contém o texto
        self.assertIn("'soma': 42", text)
        self.assertNotIn("SEGREDO-123", text)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {**env, "DFC_JUDGE_MODEL": "inexistente"}, clear=True), contextlib.redirect_stdout(out):
            self.assertEqual(cli.cmd_ping(args), 1)
        self.assertIn("FALHOU", out.getvalue())

    def test_make_client_reads_extra_body_per_role_and_rejects_bad_json(self):
        env = {"DFC_LLM_BASE_URL": "http://localhost:1/v1", "DFC_GEN_MODEL": "g", "DFC_JUDGE_MODEL": "j", "DFC_EXTRA_BODY": '{"x": 1}', "DFC_JUDGE_EXTRA_BODY": '{"reasoning_effort": "minimal"}'}
        with mock.patch.dict(os.environ, env, clear=True):
            gen, judge = cli.make_client("gen", False), cli.make_client("judge", False)
        self.assertEqual((gen.extra_body, judge.extra_body), ({"x": 1}, {"reasoning_effort": "minimal"}))
        for bad in ("{quebrado", "[1]"):
            with mock.patch.dict(os.environ, {**env, "DFC_GEN_EXTRA_BODY": bad}, clear=True):
                with self.assertRaises(SystemExit):
                    cli.make_client("gen", False)

    def test_load_env_accepts_a_file_saved_with_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write('DFC_PRIMEIRA=1\nDFC_SEGUNDA="dois"\n')
            with mock.patch.dict(os.environ, {}, clear=True):
                cli.load_env(path)
                self.assertEqual((os.environ["DFC_PRIMEIRA"], os.environ["DFC_SEGUNDA"]), ("1", "dois"))


class RunParallelTest(unittest.TestCase):
    def test_results_arrive_in_the_main_thread_and_cover_every_item(self):
        main = threading.get_ident()
        worker_threads, seen = set(), []

        def fn(x):
            worker_threads.add(threading.get_ident())
            return x * 2

        def on_result(item, result):
            self.assertEqual(threading.get_ident(), main)
            seen.append((item, result))

        run_parallel(range(20), fn, 4, on_result)
        self.assertEqual(sorted(seen), [(i, i * 2) for i in range(20)])
        self.assertNotIn(main, worker_threads)

    def test_one_worker_is_sequential_and_in_order(self):
        seen = []
        run_parallel([3, 1, 2], lambda x: x + 1, 1, lambda item, result: seen.append((item, result)))
        self.assertEqual(seen, [(3, 4), (1, 2), (2, 3)])

    def test_a_failing_worker_stops_the_run(self):
        def boom(x):
            raise RuntimeError("falhou")

        with self.assertRaises(RuntimeError):
            run_parallel([1, 2, 3], boom, 2, lambda item, result: None)

    def test_only_a_bounded_number_of_items_is_in_flight(self):
        gate, started, consumed = threading.Event(), [], []

        def fn(x):
            started.append(x)
            gate.wait(5)
            return x

        def items():
            for i in range(50):
                consumed.append(i)
                yield i

        runner = threading.Thread(target=run_parallel, args=(items(), fn, 2, lambda item, result: None))
        runner.start()
        deadline = time.time() + 5
        while len(started) < 2 and time.time() < deadline:
            time.sleep(0.01)
        self.assertLessEqual(len(consumed), 4)  # 2 x workers: interromper no meio perde poucos itens
        gate.set()
        runner.join(10)
        self.assertEqual(len(consumed), 50)


class ValidateTest(unittest.TestCase):
    def card(self):
        return cards.parse_note(ac_note(1, "Qual a diferença entre TCP e UDP?", "TCP é confiável e orientado à conexão; UDP é mais rápido, mas não confiável."))

    def test_metrics(self):
        self.assertAlmostEqual(validate.jaccard_distance("a b c", "a b c"), 0.0)
        self.assertAlmostEqual(validate.jaccard_distance("a b", "c d"), 1.0)
        self.assertFalse(validate.first_words_differ("Qual a diferença", "Qual a diferença entre"))
        self.assertTrue(validate.first_words_differ("Qual a diferença", "Em que o UDP"))

    def test_decide_accepts_good_variant(self):
        ok, reasons, _ = validate.decide(self.card(), {"type": "reorder", "text": "Em que o UDP se diferencia do TCP?"}, {"answer_preserved": True})
        self.assertTrue(ok, reasons)

    def test_decide_rejections(self):
        c = self.card()
        _, r, _ = validate.decide(c, {"type": "paraphrase", "text": "Qual a diferença entre TCP e UDP??"}, {"answer_preserved": True})
        self.assertIn("too_similar", r)
        _, r, _ = validate.decide(c, {"type": "paraphrase", "text": "Explique: TCP confiável orientado conexão, UDP rápido, não confiável"}, {"answer_preserved": True})
        self.assertIn("leak_heuristic", r)
        _, r, _ = validate.decide(c, {"type": "cue_swap", "text": "Qual a diferença entre UDP e TCP no transporte?"}, {"answer_preserved": True})
        self.assertIn("same_start", r)
        _, r, _ = validate.decide(c, {"type": "reorder", "text": "Em que o UDP se diferencia do TCP?"}, None)
        self.assertEqual(r, ["judge_error"])
        _, r, _ = validate.decide(c, {"type": "reorder", "text": "Em que o UDP se diferencia do TCP?"}, {"answer_preserved": "false", "ambiguous": "true", "leaks_answer": True, "same_language": False, "same_question": False})
        self.assertEqual(set(r), {"answer_not_preserved", "ambiguous", "leaks_answer", "language_changed", "question_changed"})

    def test_cloze_needs_one_placeholder(self):
        c = cards.parse_note({"noteId": 2, "modelName": "Cloze", "fields": {"Text": "O {{c1::TCP}} é confiável e ordenado"}})
        _, r, _ = validate.decide(c, {"type": "reformat", "text": "Protocolo de transporte confiável: [...] e [...]"}, {"answer_preserved": True})
        self.assertIn("cloze_placeholder", r)

    def test_cloze_several_blanks_need_every_marker_once_in_order_and_a_question(self):
        c = cards.parse_note({"noteId": 7, "modelName": "Cloze", "fields": {"Text": "Governo Mussolini<br>Tratado de Latrão<br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}"}})
        good = "No governo Mussolini, quais foram os antecedentes do Tratado de Latrão? [...1]\nEm que consiste esse tratado? [...2]"
        judge = {"answer_preserved": True}
        ok, reasons, _ = validate.decide(c, {"type": "pergunta", "text": good}, judge)
        self.assertTrue(ok, reasons)
        for bad in (good.replace(" [...2]", ""), good + " [...1]", good.replace("[...1]", "[...2]")):
            self.assertIn("cloze_placeholder", validate.decide(c, {"type": "pergunta", "text": bad}, judge)[1], bad)
        swapped = "No governo Mussolini, em que consiste esse tratado? [...2]\nQuais foram os antecedentes do Tratado de Latrão? [...1]"
        self.assertIn("cloze_placeholder", validate.decide(c, {"type": "pergunta", "text": swapped}, judge)[1])
        statement = "No governo Mussolini, os antecedentes do Tratado de Latrão foram [...1] e o tratado consiste em [...2]."
        self.assertEqual(validate.decide(c, {"type": "pergunta", "text": statement}, judge)[1], ["not_a_question"])
        leaking = "Sobre a Questão Romana no governo Mussolini e o Tratado de Latrão: quais foram os antecedentes? [...1]\nEm que consiste? [...2]"
        self.assertIn("leak_heuristic", validate.decide(c, {"type": "pergunta", "text": leaking}, judge)[1])

    def test_cloze_reorder_may_move_the_markers_but_the_other_types_keep_them_in_order(self):
        c = cards.parse_note({"noteId": 7, "modelName": "Cloze", "fields": {"Text": "Governo Mussolini<br>Tratado de Latrão<br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}"}})
        judge = {"answer_preserved": True}
        reordered = "Consiste: [...2]\nAntecedentes: [...1]\nGoverno Mussolini\nTratado de Latrão"
        ok, reasons, _ = validate.decide(c, {"type": "reorder", "text": reordered}, judge)
        self.assertTrue(ok, reasons)
        swapped_cues = "Fascismo italiano\nAcordo com a Igreja\nO que veio antes: [...2]\nO que ficou: [...1]"
        self.assertIn("cloze_placeholder", validate.decide(c, {"type": "cue_swap", "text": swapped_cues}, judge)[1])
        self.assertIn("cloze_placeholder", validate.decide(c, {"type": "reorder", "text": reordered.replace(" [...2]", "")}, judge)[1])
        three = cards.parse_note({"noteId": 8, "modelName": "Cloze", "fields": {"Text": "Mitose<br>Fases<br>Prófase: {{c1::condensação}}<br>Metáfase: {{c1::alinhamento}}<br>Anáfase: {{c1::separação}}"}})
        moved_one = "Mitose\nFases\nAnáfase: [...3]\nPrófase: [...1]\nMetáfase: [...2]"
        self.assertTrue(validate.decide(three, {"type": "reorder", "text": moved_one}, judge)[0])  # um só item mudou de lugar: poucas palavras mudam, mas a ordem das lacunas sim
        self.assertIn("too_similar", validate.decide(three, {"type": "reorder", "text": three.question_text}, judge)[1])
        one = cards.parse_note({"noteId": 9, "modelName": "Cloze", "fields": {"Text": "O heme é formado por protoporfirina e {{c1::ferro}}"}})
        self.assertTrue(validate.decide(one, {"type": "reorder", "text": "[...] e protoporfirina formam o heme"}, judge)[0])
        self.assertIn("too_similar", validate.decide(one, {"type": "reorder", "text": one.question_text}, judge)[1])

    def test_pure_reordering_passes_as_reorder_but_not_as_another_type(self):
        c = cards.parse_note(ac_note(1, "O que o TCP garante que o UDP não garante?", "A entrega ordenada e confiável dos dados."))
        judge = {"answer_preserved": True}
        text = "O que o UDP não garante e o TCP garante?"
        self.assertTrue(validate.decide(c, {"type": "reorder", "text": text}, judge)[0])
        self.assertIn("too_similar", validate.decide(c, {"type": "paraphrase", "text": text}, judge)[1])  # as mesmas palavras: Jaccard zero
        self.assertIn("too_similar", validate.decide(c, {"type": "reorder", "text": c.question_text}, judge)[1])
        self.assertAlmostEqual(validate.sequence_distance("a b c d", "c d a b"), 0.5)

    def test_judge_flagging_a_topic_change_rejects_the_variant(self):
        c = cards.parse_note({"noteId": 11, "modelName": "Cloze", "fields": {"Text": "Tecido Ósseo<br>Hormônio: {{c1::GH}}<br>Cresce por: {{c1::alongamento ósseo}}"}})
        text = "Sistema Esquelético\nFator hormonal: [...1]\nMecanismo: [...2]"
        ok, reasons, _ = validate.decide(c, {"type": "cue_swap", "text": text}, {"answer_preserved": True, "same_topic": False})
        self.assertEqual((ok, reasons), (False, ["topic_changed"]))
        self.assertTrue(validate.decide(c, {"type": "cue_swap", "text": text}, {"answer_preserved": True})[0])  # juiz sem o campo (modelos do Básico): não reprova


class PipelineEndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        notes = [
            ac_note(1, "O que é NAT na prática de redes domésticas?", "Técnica que permite vários dispositivos compartilharem um único endereço IP público."),
            ac_note(2, "Para que serve o DNS na internet moderna?", "Converter nomes de domínio em endereços IP numéricos."),
            ac_note(3, "Qual protocolo garante entrega ordenada dos dados?", "O TCP garante entrega confiável, ordenada e sem duplicação."),
            ac_note(4, "Figura <img src='x.png'>", "resposta qualquer longa"),
        ]
        self.cards = [cards.parse_note(n) for n in notes]
        self.p = lambda name: os.path.join(self.tmp.name, name)

    def test_generate_validate_audit_pack(self):
        client = FakeLLM()
        stats = generate.generate(self.cards, client, self.p("gen.jsonl"), log=lambda s: None)
        self.assertEqual(stats["com_variantes"], 3)  # a nota 4 é inelegível e nem vai ao LLM
        self.assertEqual(len(client.calls), 3)
        gen = list(read_jsonl(self.p("gen.jsonl")))
        self.assertTrue(all(len(g["variants"]) == 4 for g in gen))
        # retomada: nada novo a gerar
        generate.generate(self.cards, client, self.p("gen.jsonl"), log=lambda s: None)
        self.assertEqual(len(client.calls), 3)

        by_id = {c.note_id: c for c in self.cards}
        vstats = validate.validate(by_id, gen, FakeLLM(), self.p("val.jsonl"), log=lambda s: None)
        self.assertEqual(vstats["validas"], 12, dict(vstats))
        val = list(read_jsonl(self.p("val.jsonl")))

        n = audit.build_sheet(by_id, val, 8, 1, self.p("sheet.csv"))
        self.assertEqual(n, 8)
        with open(self.p("sheet.csv"), newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for i, r in enumerate(rows):
            r["human_ok"] = "n" if i == 0 else "s"
        with open(self.p("sheet.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=audit.SHEET_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        report = audit.score_sheet(self.p("sheet.csv"), min_n=5)
        self.assertEqual((report["auditadas"], report["validas"]), (8, 7))
        self.assertEqual(report["rejected_variant_ids"], [rows[0]["variant_id"]])
        self.assertTrue(report["h1_ok"])  # 7/8 = 87,5% >= 85%
        self.assertGreaterEqual(report["taxa"], 0.85)

        with self.assertRaises(ValueError):
            pack.build_bank(self.cards, gen, val)
        bank = pack.build_bank(self.cards, gen, val, audit_report=report, allow_fake=True)
        self.assertEqual(set(bank["notes"]), {"1", "2", "3"})
        total = sum(len(e["variants"]) for e in bank["notes"].values())
        self.assertEqual(total, 12 - 1)  # a variante rejeitada na auditoria sai
        self.assertEqual(bank["notes"]["1"]["kind"], "basic")
        self.assertEqual((bank["schema"], bank["notes"]["1"]["q_field"]), (3, 0))

    def test_parallel_workers_give_the_same_records_as_sequential(self):
        generate.generate(self.cards, FakeLLM(), self.p("g1.jsonl"), log=lambda s: None)
        stats = generate.generate(self.cards, FakeLLM(), self.p("g2.jsonl"), workers=3, log=lambda s: None)
        self.assertEqual(stats["com_variantes"], 3)
        norm = lambda path, key: [{k: v for k, v in r.items() if k not in ("generator", "ts")} for r in sorted(read_jsonl(path), key=lambda r: r[key])]
        self.assertEqual(norm(self.p("g1.jsonl"), "note_id"), norm(self.p("g2.jsonl"), "note_id"))
        gen = list(read_jsonl(self.p("g1.jsonl")))
        by_id = {c.note_id: c for c in self.cards}
        validate.validate(by_id, gen, FakeLLM(), self.p("v1.jsonl"), log=lambda s: None)
        vstats = validate.validate(by_id, gen, FakeLLM(), self.p("v2.jsonl"), workers=4, log=lambda s: None)
        self.assertEqual(vstats["validas"], 12, dict(vstats))
        self.assertEqual(norm(self.p("v1.jsonl"), "variant_id"), norm(self.p("v2.jsonl"), "variant_id"))

    def test_cloze_ficha_with_image_gets_four_text_variants_and_sem_imagem(self):
        text = 'Mrs Dalloway<br><div><img src="d.png"></div><br>Personagens<br>Lucrezia é a: {{c1::esposa de Septimus}}<br>Que sofre com: {{c1::o trauma da guerra}}'
        ficha = cards.parse_note({"noteId": 10, "modelName": "Cloze", "fields": {"Text": text}, "decks": ["Leituras"]})
        self.assertTrue(ficha.eligible, ficha.reasons)
        generate.generate([ficha], FakeLLM(), self.p("g.jsonl"), log=lambda s: None)
        gen = list(read_jsonl(self.p("g.jsonl")))
        self.assertEqual([v["type"] for v in gen[0]["variants"]], ["paraphrase", "reorder", "cue_swap", "pergunta"])  # sem_imagem é determinística: entra no pack
        validate.validate({10: ficha}, gen, FakeLLM(), self.p("v.jsonl"), log=lambda s: None)
        val = list(read_jsonl(self.p("v.jsonl")))
        self.assertTrue(all(v["auto_valid"] for v in val), [v["reasons"] for v in val])
        bank = pack.build_bank([ficha], gen, val, allow_fake=True)
        entry = bank["notes"]["10"]
        self.assertEqual((bank["schema"], entry["kind"], entry["answers_html"], entry["images_html"]), (3, "cloze", ["esposa de Septimus", "o trauma da guerra"], ['<img src="d.png">']))
        self.assertEqual([v["type"] for v in entry["variants"]], ["paraphrase", "reorder", "cue_swap", "pergunta", "sem_imagem"])
        self.assertEqual(entry["variants"][-1], {"id": "10-sem_imagem", "type": "sem_imagem"})

        self.assertEqual(audit.build_sheet({10: ficha}, val, 5, 1, self.p("s.csv")), 5)
        with open(self.p("s.csv"), newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(sorted(r["type"] for r in rows), ["cue_swap", "paraphrase", "pergunta", "reorder", "sem_imagem"])
        self.assertIn("[...1]", rows[0]["original_question"])
        for r in rows:
            r["human_ok"] = "n" if r["type"] == "sem_imagem" else "s"  # sem a imagem o cartão não se sustenta
        with open(self.p("s.csv"), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=audit.SHEET_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        report = audit.score_sheet(self.p("s.csv"), min_n=1, min_n_type=1)
        self.assertEqual((report["exclude_types"], report["rejected_variant_ids"]), (["sem_imagem"], ["10-sem_imagem"]))
        again = pack.build_bank([ficha], gen, val, audit_report=report, allow_fake=True)
        self.assertEqual([v["type"] for v in again["notes"]["10"]["variants"]], ["paraphrase", "reorder", "cue_swap", "pergunta"])

    def test_cloze_keeps_only_its_own_variant_types(self):
        c = cards.parse_note({"noteId": 9, "modelName": "Cloze", "fields": {"Text": "O {{c1::TCP}} é um protocolo de transporte confiável"}})
        raw = [{"type": t, "text": f"texto {t}"} for t in ("paraphrase", "reformat", "pergunta", "pergunta", "sem_imagem")]
        self.assertEqual([v["type"] for v in generate.clean_variants(c, raw)], ["paraphrase", "pergunta"])

    def test_pack_skips_edited_notes(self):
        generate.generate(self.cards, FakeLLM(), self.p("gen.jsonl"), log=lambda s: None)
        gen = list(read_jsonl(self.p("gen.jsonl")))
        by_id = {c.note_id: c for c in self.cards}
        validate.validate(by_id, gen, FakeLLM(), self.p("val.jsonl"), log=lambda s: None)
        val = list(read_jsonl(self.p("val.jsonl")))
        edited = cards.parse_note(ac_note(1, "O que é NAT, depois de editar?", "Outra resposta."))
        bank = pack.build_bank([edited] + self.cards[1:], gen, val, allow_fake=True)
        self.assertNotIn("1", bank["notes"])

    def test_cli_dry_run_flow(self):
        src = self.p("notas.jsonl")
        write_jsonl(src, [{"note_id": c.note_id, "model": "Basic", "fields": {"Front": c.question_html, "Back": c.answer_html}, "decks": ["Redes"]} for c in self.cards])
        run = lambda *a: self.assertEqual(cli.main(list(a)), 0)
        run("export", "--source", "file", "--in-file", src, "--out", self.p("cards.jsonl"))
        run("generate", "--dry-run", "--cards", self.p("cards.jsonl"), "--out", self.p("gen.jsonl"))
        run("validate", "--dry-run", "--cards", self.p("cards.jsonl"), "--generation", self.p("gen.jsonl"), "--out", self.p("val.jsonl"))
        run("audit-sheet", "--cards", self.p("cards.jsonl"), "--validation", self.p("val.jsonl"), "--n", "4", "--out", self.p("sheet.csv"))
        run("pack", "--cards", self.p("cards.jsonl"), "--generation", self.p("gen.jsonl"), "--validation", self.p("val.jsonl"), "--allow-fake", "--out", self.p("bank.json"))
        run("stats", "--cards", self.p("cards.jsonl"), "--generation", self.p("gen.jsonl"), "--validation", self.p("val.jsonl"))
        with open(self.p("bank.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)["notes"]), 3)
        with self.assertRaises(SystemExit):
            cli.main(["pack", "--cards", self.p("cards.jsonl"), "--generation", self.p("gen.jsonl"), "--validation", self.p("val.jsonl"), "--out", self.p("x.json")])


if __name__ == "__main__":
    unittest.main()
