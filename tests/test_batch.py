"""Testes da geração em lote do uso livre (v0.5): plano, execução, cancelamento e falhas. LLM falso, sem Anki e sem rede."""
import json
import os
import tempfile
import threading
import unittest

import addon_pure

from dfc_pipeline.llm import FakeLLM, LLMError

B = addon_pure.load("batch")
F = addon_pure.load("free")
L = addon_pure.load("live")


def basic(i, question=None):
    q = question or f"Qual organela produz energia na célula eucarionte número {i}?"
    return {"note_id": i, "guid": f"g{i}", "model": "Basic", "fields": {"Front": q, "Back": "Mitocôndria"}, "tags": [], "decks": ["D"]}


def cloze(i, with_image=False):
    img = '<img src="figura.png"><br>' if with_image else ""
    text = f"{img}A {{{{c1::mitose}}}} ocorre em células somáticas e a {{{{c1::meiose}}}} forma os gametas no ser vivo {i}."
    return {"note_id": i, "guid": f"g{i}", "model": "Cloze", "fields": {"Text": text, "Extra": ""}, "tags": [], "decks": ["D"]}


def short_cloze(i):
    return {"note_id": i, "guid": f"g{i}", "model": "Cloze", "fields": {"Text": "A {{c1::água}} ferve.", "Extra": ""}, "tags": [], "decks": ["D"]}


def not_conceptual(messages):
    if "gera variantes" in messages[0]["content"].lower():
        return json.dumps({"conceptual": False, "reason": "vocabulário", "variants": []})
    raise AssertionError("o juiz não deveria ser chamado")


class UsageLLM(FakeLLM):
    def chat(self, messages, temperature=None):
        out = super().chat(messages, temperature)
        out["usage"] = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        return out


class BatchBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bank = F.FreeBank(os.path.join(self.tmp.name, "bank.json"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_batch(self, records, gen=None, judge=None, **opts):
        options = B.Options(workers=opts.pop("workers", 2), **opts)
        return B.run(records, gen or FakeLLM(), judge or FakeLLM(), self.bank, options, **self.run_kwargs)

    run_kwargs: dict = {}


class PlanTest(BatchBase):
    def test_separates_what_to_generate_from_what_is_ready(self):
        ready = basic(1)
        self.bank.set_entry(1, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": L.parse_note(ready).fields_hash, "variants": [{"id": "1-a", "type": "paraphrase", "text": "Outra pergunta?"}]})
        dismissed = basic(2)
        self.bank.skip(2, L.parse_note(dismissed).fields_hash, "not_conceptual")
        records = [ready, dismissed, basic(3), short_cloze(4), basic(5), basic(6), basic(7), basic(8)]
        plan = B.make_plan(records, self.bank, {3}, B.Options(max_notes=2))
        self.assertEqual([r["note_id"] for r in plan.todo], [5, 6])
        self.assertEqual((plan.examined, plan.already, plan.dismissed, plan.official, plan.ineligible, plan.truncated), (8, 1, 1, 1, 1, 2))
        self.assertEqual(plan.reasons, {"short_text": 1})

    def test_edited_note_is_planned_again(self):
        rec = basic(1)
        self.bank.set_entry(1, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": "old-hash", "variants": [{"id": "1-a", "type": "paraphrase", "text": "Outra pergunta?"}]})
        self.bank.skip(1, "old-hash", "not_conceptual")
        self.assertEqual(len(B.make_plan([rec], self.bank, [], B.Options()).todo), 1)

    def test_reprocess_includes_what_is_ready(self):
        ready = basic(1)
        self.bank.set_entry(1, {"kind": "basic", "ords": [0], "q_field": 0, "fields_hash": L.parse_note(ready).fields_hash, "variants": [{"id": "1-a", "type": "paraphrase", "text": "Outra pergunta?"}]})
        self.bank.skip(2, L.parse_note(basic(2)).fields_hash, "not_conceptual")
        plan = B.make_plan([ready, basic(2)], self.bank, [], B.Options(reprocess=True))
        self.assertEqual([r["note_id"] for r in plan.todo], [1, 2])

    def test_official_notes_are_never_planned_even_when_reprocessing(self):
        plan = B.make_plan([basic(1), basic(2)], self.bank, [1], B.Options(reprocess=True))
        self.assertEqual(([r["note_id"] for r in plan.todo], plan.official), ([2], 1))

    def test_describe_plan_mentions_counts_reasons_and_cost(self):
        plan = B.make_plan([basic(1), short_cloze(2), basic(3)], self.bank, [], B.Options(max_notes=1))
        text = B.describe_plan(plan)
        self.assertIn("Para gerar agora: 1 (mais 1 ficam para uma próxima vez", text)
        self.assertIn("texto visível curto demais", text)
        self.assertIn("US$ 0,00", text)  # 1 nota = menos de um centavo
        self.assertNotIn("chamadas", B.describe_plan(B.make_plan([], self.bank, [], B.Options())))

    def test_estimate(self):
        self.assertEqual(B.estimate(200), {"gen_calls": 200, "judge_calls": 640, "usd": 0.6})


class RunTest(BatchBase):
    def test_generates_validates_and_stores(self):
        gen, judge = FakeLLM(), FakeLLM()
        s = self.run_batch([basic(i) for i in range(1, 7)], gen, judge)
        self.assertEqual((s.total, s.done, s.with_variants, s.variants, s.errors, s.cancelled, s.aborted), (6, 6, 6, 24, 0, False, ""))
        self.assertEqual((len(gen.calls), len(judge.calls)), (6, 24))
        self.assertEqual(self.bank.stats()["notes"], 6)
        self.assertEqual(F.FreeBank(self.bank.path).stats()["variants"], 24)  # gravado em disco
        self.assertEqual((self.bank.generator_models, self.bank.judge_models), ({"fake"}, {"fake"}))

    def test_stored_notes_are_not_planned_again(self):
        records = [basic(i) for i in range(1, 4)]
        self.run_batch(records)
        plan = B.make_plan(records, self.bank, [], B.Options())
        self.assertEqual((len(plan.todo), plan.already), (0, 3))

    def test_cloze_note_with_image_gets_sem_imagem(self):
        s = self.run_batch([cloze(1, with_image=True)])
        self.assertEqual((s.with_variants, s.variants), (1, 5))
        self.assertEqual(sorted(v["type"] for v in self.bank.entry(1)["variants"]), ["cue_swap", "paraphrase", "pergunta", "reorder", "sem_imagem"])

    def test_type_filter_spares_judge_calls_and_keeps_only_those_types(self):
        gen, judge = FakeLLM(), FakeLLM()
        s = self.run_batch([basic(i) for i in range(1, 4)], gen, judge, types=["paraphrase"])
        self.assertEqual((len(gen.calls), len(judge.calls), s.variants), (3, 3, 3))
        self.assertEqual({v["type"] for i in (1, 2, 3) for v in self.bank.entry(i)["variants"]}, {"paraphrase"})

    def test_sem_imagem_only_still_needs_an_approved_text(self):
        gen, judge = FakeLLM(), FakeLLM()
        s = self.run_batch([cloze(1, with_image=True)], gen, judge, types=["sem_imagem"])
        self.assertEqual(len(judge.calls), 4)  # todos os textos são validados: a sem_imagem depende de um aprovado
        self.assertEqual([v["type"] for v in self.bank.entry(1)["variants"]], ["sem_imagem"])
        self.assertEqual(s.variants, 1)

    def test_type_filter_with_nothing_of_those_types(self):
        s = self.run_batch([basic(1)], types=["pergunta"])  # o cartão básico não tem o tipo pergunta
        self.assertEqual((s.no_selected, s.with_variants, s.errors), (1, 0, 0))
        self.assertEqual(self.bank.skipped, {})  # não vira dispensa: outros tipos podem ser pedidos depois

    def test_not_conceptual_is_remembered(self):
        s = self.run_batch([basic(1), basic(2)], FakeLLM(not_conceptual))
        self.assertEqual((s.not_conceptual, s.with_variants), (2, 0))
        plan = B.make_plan([basic(1), basic(2)], self.bank, [], B.Options())
        self.assertEqual((len(plan.todo), plan.dismissed), (0, 2))

    def test_no_approved_variant_is_remembered(self):
        def judge_rejects(messages):
            return json.dumps({"answer_preserved": False, "ambiguous": False, "leaks_answer": False, "same_language": True, "same_question": True, "same_topic": True})

        s = self.run_batch([basic(1)], FakeLLM(), FakeLLM(judge_rejects))
        self.assertEqual((s.no_valid, s.with_variants, s.errors), (1, 0, 0))
        self.assertTrue(self.bank.is_skipped(1, L.parse_note(basic(1)).fields_hash))

    def test_usage_is_summed(self):
        s = self.run_batch([basic(1), basic(2)], UsageLLM(), UsageLLM())
        calls = 2 + 8
        self.assertEqual(s.usage, {"prompt_tokens": 10 * calls, "completion_tokens": 5 * calls, "total_tokens": 15 * calls})
        self.assertIn("Tokens: entrada 100, saída 50", B.format_summary(s))

    def test_reprocess_replaces_the_entry_but_keeps_banned_variants_out(self):
        self.run_batch([basic(1)])
        banned = self.bank.entry(1)["variants"][0]["id"]
        self.bank.ban(banned)
        self.assertEqual(len(self.bank.entry(1)["variants"]), 3)
        s = self.run_batch([basic(1)], reprocess=True)
        self.assertEqual(s.variants, 3)
        self.assertNotIn(banned, [v["id"] for v in self.bank.entry(1)["variants"]])

    def test_reprocess_without_result_keeps_the_old_entry(self):
        self.run_batch([basic(1)])
        before = self.bank.entry(1)
        s = self.run_batch([basic(1)], FakeLLM(not_conceptual), reprocess=True)
        self.assertEqual(s.not_conceptual, 1)
        self.assertEqual(self.bank.entry(1), before)
        self.assertFalse(self.bank.is_skipped(1, L.parse_note(basic(1)).fields_hash))

    def test_progress_callback_sees_every_note(self):
        seen = []
        self.run_kwargs = {"on_progress": lambda s: seen.append(s.done)}
        self.run_batch([basic(i) for i in range(1, 5)], workers=1)
        self.assertEqual(seen, [1, 2, 3, 4])

    def test_empty_todo(self):
        s = self.run_batch([])
        self.assertEqual((s.total, s.done), (0, 0))
        self.assertFalse(os.path.exists(self.bank.path))


class FailureTest(BatchBase):
    def failing_gen(self, _messages):
        raise LLMError("sem crédito")

    def test_consecutive_failures_abort_without_storing_or_dismissing(self):
        s = self.run_batch([basic(i) for i in range(1, 11)], FakeLLM(self.failing_gen), workers=1, abort_after=3)
        self.assertIn("3 falhas seguidas", s.aborted)
        self.assertIn("sem crédito", s.aborted)
        self.assertTrue(3 <= s.done <= 4, s.done)
        self.assertEqual((s.errors, s.with_variants), (s.done, 0))
        self.assertEqual((self.bank.stats()["notes"], self.bank.stats()["skipped"]), (0, 0))  # tentar de novo custa só a chamada que falhou
        self.assertIn("Interrompido", B.format_summary(s))

    def test_a_success_resets_the_streak(self):
        count = {"n": 0}
        lock = threading.Lock()
        default = FakeLLM()

        def flaky(messages):
            if "gera variantes" in messages[0]["content"].lower():
                with lock:
                    count["n"] += 1
                    if count["n"] % 2:
                        raise LLMError("instável")
            return default.responder(messages)

        s = self.run_batch([basic(i) for i in range(1, 9)], FakeLLM(flaky), workers=1, abort_after=2)
        self.assertEqual((s.aborted, s.done, s.errors, s.with_variants), ("", 8, 4, 4))

    def test_judge_that_never_answers_counts_as_failure(self):
        def broken(_messages):
            raise LLMError("juiz fora do ar")

        s = self.run_batch([basic(i) for i in range(1, 4)], FakeLLM(), FakeLLM(broken), workers=1, abort_after=2)
        self.assertEqual(s.with_variants, 0)
        self.assertIn("o juiz não respondeu", s.last_error)
        self.assertTrue(s.aborted)
        self.assertEqual(self.bank.stats()["skipped"], 0)

    def test_unexpected_exception_is_a_failure_not_a_crash(self):
        def bug(_messages):
            raise RuntimeError("bug inesperado")

        s = self.run_batch([basic(1)], FakeLLM(bug))
        self.assertEqual((s.errors, s.done), (1, 1))
        self.assertIn("RuntimeError: bug inesperado", s.last_error)

    def test_ineligible_record_is_counted_not_charged(self):
        gen = FakeLLM()
        s = self.run_batch([short_cloze(1)], gen)
        self.assertEqual((s.ineligible, len(gen.calls)), (1, 0))


class CancelTest(BatchBase):
    def test_cancel_stops_submitting_and_keeps_what_was_done(self):
        state = {"done": 0}
        self.run_kwargs = {"on_progress": lambda s: state.update(done=s.done), "cancelled": lambda: state["done"] >= 3, "grace": 5.0}
        s = self.run_batch([basic(i) for i in range(1, 21)], workers=1)
        self.assertTrue(s.cancelled)
        self.assertTrue(3 <= s.done < 20, s.done)
        self.assertEqual(s.with_variants, s.done)
        self.assertEqual(F.FreeBank(self.bank.path).stats()["notes"], s.done)
        self.assertIn("Cancelado", B.format_summary(s))

    def test_cancel_does_not_wait_forever_for_a_stuck_call(self):
        release, started = threading.Event(), threading.Event()
        default = FakeLLM()

        def stuck(messages):
            started.set()
            release.wait(10)
            return default.responder(messages)

        self.run_kwargs = {"cancelled": started.is_set, "grace": 0.3}
        try:
            s = self.run_batch([basic(1), basic(2)], FakeLLM(stuck), workers=1)
        finally:
            release.set()
        self.assertEqual((s.cancelled, s.done, s.abandoned), (True, 0, 2))
        self.assertIn("descartadas", B.format_summary(s))


class FormatSummaryTest(unittest.TestCase):
    def test_done_summary(self):
        s = B.Summary(total=10, done=10, with_variants=6, variants=22, not_conceptual=2, no_valid=1, no_selected=1, seconds=125.0)
        text = B.format_summary(s)
        self.assertIn("Concluído.", text)
        self.assertIn("10 de 10 notas processadas em 2 min 5 s", text)
        self.assertIn("Com variantes: 6 notas (22 variantes no banco)", text)
        self.assertIn("2 não conceituais", text)
        self.assertIn("1 sem variante aprovada", text)
        self.assertIn("1 sem nenhum dos tipos escolhidos", text)
        self.assertNotIn("Falhas", text)

    def test_errors_are_reported_with_the_last_one(self):
        text = B.format_summary(B.Summary(total=3, done=3, errors=2, last_error="HTTP 429", seconds=3))
        self.assertIn("Falhas (podem ser tentadas de novo): 2. Último erro: HTTP 429", text)


if __name__ == "__main__":
    unittest.main()
