"""Testes do pipeline de variantes (sem rede externa e sem Anki)."""
import csv
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from dfc_pipeline import audit, cards, cli, generate, pack, validate  # noqa: E402
from dfc_pipeline.llm import FakeLLM, LLMClient, LLMError, parse_json_loose  # noqa: E402
from dfc_pipeline.util import read_jsonl, write_jsonl  # noqa: E402


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
        one = {"noteId": 2, "modelName": "Omissão de Palavras", "fields": {"Texto": {"value": "O {{c1::TCP}} é confiável", "order": 0}, "Extra": {"value": "", "order": 1}}}
        c = cards.parse_note(one)
        self.assertEqual((c.kind, c.ords, c.question_text, c.answer_text), ("cloze", [0], "O [...] é confiável", "TCP"))
        self.assertTrue(c.eligible)
        many = {"noteId": 3, "modelName": "Cloze", "fields": {"Text": "{{c1::a}} e {{c1::b}}"}}
        self.assertIn("multi_cloze", cards.parse_note(many).reasons)

    def test_same_hash_for_both_export_shapes(self):
        a = cards.parse_note(ac_note(1, "Q?", "A longa"))
        b = cards.parse_note({"note_id": 1, "model": "Basic", "fields": {"Front": "Q?", "Back": "A longa"}})
        self.assertEqual(a.fields_hash, b.fields_hash)

    def test_summary_counts_suspects(self):
        n = ac_note(1, "O que é NAT?", "Tradução de endereços de rede.")
        n["decks"], n["stats"] = ["Redes"], {"reps": 6, "lapses": 0}
        s = cards.summarize([cards.parse_note(n)])
        self.assertEqual(s["por_baralho"]["Redes"], {"notas": 1, "elegiveis": 1, "elegiveis_suspeitos": 1})


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
        seen = {"calls": 0, "auth": None}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["calls"] += 1
                seen["auth"] = self.headers.get("Authorization")
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
