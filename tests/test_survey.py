"""Testes do levantamento de viabilidade (AnkiConnect simulado, sem Anki)."""
import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from dfc_pipeline import ankiconnect, cards, cli, survey  # noqa: E402


def at(day, hour=12):
    """Horário local em ms (o `id` do revlog), `day` dias depois de 1/10/2026."""
    return int(datetime.datetime(2026, 10, 1 + day, hour).timestamp() * 1000)


def answer(day, ease=3, type=1, hour=12):
    return {"id": at(day, hour), "ease": ease, "type": type}


def history(days, eases=None):
    """Uma resposta por dia (a primeira em aprendizado, as outras em revisão)."""
    return [answer(d, (eases or {}).get(d, 3), 0 if d == days[0] else 1) for d in days]


class ClassifyTest(unittest.TestCase):
    def flags(self, entries, reps, lapses=0, key="event"):
        return [r[key] for r in survey.classify(entries, reps, lapses)]

    def test_event_needs_the_previous_answer_on_another_anki_day(self):
        entries = [answer(0, type=0), answer(0, type=0, hour=13), answer(1, type=1, hour=2), answer(2), answer(3)]
        # 2/10 às 2h ainda é o dia do Anki de 1/10 (a virada é às 4h)
        self.assertEqual(self.flags(entries, reps=5), [False, False, False, True, True])
        self.assertFalse(any(self.flags(entries, reps=5, key="suspect")))

    def test_suspect_stratum_follows_the_protocol(self):
        eight = history(range(8))
        self.assertEqual(self.flags(eight, reps=8, key="suspect"), [False] * 5 + [True] * 3)
        lapse = [*eight[:6], answer(6, ease=1), answer(7)]
        self.assertEqual(self.flags(lapse, reps=8, lapses=1, key="suspect"), [False] * 5 + [True, True, False])  # a falha também é exposição de suspeito
        hard = history(range(8), eases={5: 2})
        self.assertEqual(self.flags(hard, reps=8, key="suspect")[5:], [True, False, True])  # a anterior precisa ser Good ou mais

    def test_manual_entries_are_ignored(self):
        entries = [*history(range(8)), {"id": at(3, 18), "ease": 0, "type": 4}]
        self.assertEqual(self.flags(entries, reps=8, key="suspect"), [False] * 5 + [True] * 3)

    def test_missing_old_history_does_not_invent_events(self):
        entries = [answer(8), answer(9)]  # o cartão tem 10 respostas, mas o revlog só tem as duas últimas
        self.assertEqual(self.flags(entries, reps=10), [False, True])
        self.assertEqual(self.flags(entries, reps=10, key="suspect"), [False, True])


def ac_note(note_id, card_id, front, back, model="Basic"):
    return {
        "noteId": note_id,
        "modelName": model,
        "tags": [],
        "fields": {"Front": {"value": front, "order": 0}, "Back": {"value": back, "order": 1}},
        "cards": [card_id],
    }


def cloze_note(note_id, card_id, text):
    return {
        "noteId": note_id, "modelName": "Omissão de Palavras", "tags": [], "cards": [card_id],
        "fields": {"Texto": {"value": text, "order": 0}, "Extra": {"value": "", "order": 1}},
    }


# nota -> (nota no formato do AnkiConnect, baralho, contadores do cartão, revlog)
NOTES = {
    1: (ac_note(1, 101, "O que é NAT na prática?", "Tradução de endereços de rede."), "Redes", {"reps": 8, "lapses": 0, "queue": 2}, history(range(8))),
    2: (cloze_note(2, 102, "O {{c1::TCP}} é confiável"), "Redes::Camada 4", {"reps": 3, "lapses": 0, "queue": 2}, history([5, 6, 7])),
    3: (ac_note(3, 103, "Figura <img src='x.png'>", "resposta longa qualquer"), "Redes", {"reps": 9, "lapses": 0, "queue": 2}, history(range(9))),
    4: (ac_note(4, 104, "Qual a função do DNS?", "Converter nomes em endereços IP."), "Outro", {"reps": 6, "lapses": 0, "queue": -1}, []),
    5: (cloze_note(5, 105, "O {{c1::TCP}} e o {{c2::UDP}} são protocolos"), "Redes", {"reps": 7, "lapses": 0, "queue": 2}, history(range(7))),
}
BY_CARD = {n[0]["cards"][0]: n for n in NOTES.values()}


def fake_invoke(action, **params):
    if action == "findNotes":
        return list(NOTES)
    if action == "notesInfo":
        return [NOTES[i][0] for i in params["notes"]]
    if action == "cardsInfo":
        return [{"cardId": c, "note": BY_CARD[c][0]["noteId"], "ord": 0, "deckName": BY_CARD[c][1], "interval": 10, **BY_CARD[c][2]} for c in params["cards"]]
    if action == "findCards":
        assert params["query"].startswith("rated:")
        return [101, 102, 103, 105]  # com resposta recente (o 104 está suspenso e sem histórico)
    if action == "getReviewsOfCards":
        assert all(isinstance(c, int) for c in params["cards"])  # o AnkiConnect só aceita ids inteiros
        return {str(c): BY_CARD[c][3] for c in params["cards"]}
    raise AssertionError(action)


def numbers(record):
    return {k: record[k] for k in ("respostas", "eventos", "suspeitos")}


class SurveyTest(unittest.TestCase):
    now = at(10) / 1000

    def test_recent_cards_count_answers_events_and_suspects_since_the_cutoff(self):
        by_note = {r["note"]: r for r in survey.recent_cards(fake_invoke, 28, at(5))}
        self.assertEqual(sorted(by_note), [1, 2, 3, 5])  # o 104 não tem resposta
        self.assertEqual(numbers(by_note[1]), {"respostas": 3, "eventos": 3, "suspeitos": 3})
        self.assertEqual(numbers(by_note[2]), {"respostas": 3, "eventos": 2, "suspeitos": 0})  # a primeira do revlog não tem anterior
        self.assertEqual(numbers(by_note[5]), {"respostas": 2, "eventos": 2, "suspeitos": 2})
        self.assertEqual((by_note[2]["deck"], by_note[2]["ord"]), ("Redes", 0))  # baralho raiz

    def test_buckets_say_why_an_answer_cannot_be_drawn(self):
        parsed, _ = survey.collect("deck:*", fake_invoke, 28, at(0), log=lambda s: None)
        by_id = {c.note_id: c for c in parsed}
        self.assertEqual(survey.bucket(by_id[1], 0), "sorteavel")
        self.assertEqual(survey.bucket(by_id[1], 1), "outro cartao da nota")
        self.assertEqual(survey.bucket(by_id[3], 0), "media_or_latex")
        self.assertEqual(survey.bucket(by_id[5], 0), "so_multi_cloze")
        self.assertEqual(survey.bucket(None, 0), "nota fora da busca")
        img = cards.parse_note(cloze_note(9, 109, "O {{c1::TCP}} e o {{c2::UDP}} <img src='a.png'>"))
        self.assertEqual(survey.bucket(img, 0), "multi_cloze+media_or_latex")

    def test_report_has_note_types_decks_coverage_and_projections(self):
        _, lines = survey.run("deck:*", fake_invoke, days=28, rollover_hour=4, now=self.now, log=lambda s: None)
        text = "\n".join(lines)
        self.assertIn("notas: 5  elegiveis: 3", text)
        self.assertRegex(text, r"Omissão de Palavras\s+cloze\s+2\s+1")
        self.assertIn("media_or_latex 1", text)
        self.assertRegex(text, r"Outro\s+1\s+1\s+0\s+0")  # elegível, mas suspensa: não conta como ativa
        self.assertRegex(text, r"Redes\s+4\s+2\s+2\s+1")  # 4 notas (uma com imagem e uma com duas lacunas), 2 elegíveis, 2 ativas, 1 suspeita
        self.assertIn("respostas de qualquer nota: 27", text)
        self.assertRegex(text, r"sorteavel\s+11\s+41%\s+9\s+3")
        self.assertRegex(text, r"media_or_latex\s+9\s+33%")
        self.assertRegex(text, r"so_multi_cloze\s+7\s+26%\s+6\s+2")
        self.assertRegex(text, r"Redes\s+27\s+11\n")
        self.assertRegex(text, r"Redes\s+basic\s+1\s+7\s+3\s+4")
        self.assertIn("~7 eventos (~2 suspeitos)", text)  # 21/28 de 9 e de 3
        self.assertIn("+6 eventos (+2 suspeitos) em 28 dias; na janela: ~11 eventos (~4 suspeitos)", text)

    def test_cli_prints_only_aggregates_and_can_save_the_notes(self):
        out = os.path.join(tempfile.mkdtemp(), "notas.jsonl")
        buf = io.StringIO()
        with mock.patch.object(ankiconnect, "invoke", fake_invoke), mock.patch("dfc_pipeline.survey.time.time", return_value=self.now), contextlib.redirect_stdout(buf):
            self.assertEqual(cli.main(["survey", "--out", out]), 0)
        printed = buf.getvalue()
        self.assertIn("respostas de qualquer nota: 27", printed)
        self.assertNotIn("Tradução de endereços", printed)  # nenhum texto de cartão
        with open(out, encoding="utf-8") as f:
            saved = [json.loads(line) for line in f]
        self.assertEqual([d["note_id"] for d in saved], [1, 2, 3, 4, 5])
        self.assertEqual(cards.Card.from_dict(saved[0]).decks, ["Redes"])


if __name__ == "__main__":
    unittest.main()
