"""Prompts versionados. Mudar o texto exige mudar a versão, que é registrada em cada variante."""
from __future__ import annotations

import json
from typing import Any

from .cards import Card

GEN_PROMPT_VERSION = "gen-v1"
JUDGE_PROMPT_VERSION = "judge-v1"
VARIANT_TYPES = ("paraphrase", "reorder", "reformat", "cue_swap")

GEN_SYSTEM = """Você gera variantes de flashcards para um estudo que mede se alguém memorizou a FORMA do cartão em vez do conceito.
Você recebe o cartão (pergunta e resposta esperada) e devolve variantes da PERGUNTA que mudam só a forma.

Regras (mundo fechado):
1. A resposta esperada de cada variante é exatamente a resposta do cartão. Não use conhecimento externo, não acrescente nem retire exigências.
2. A variante não pode conter a resposta nem entregá-la.
3. Mantenha o idioma e o nível de dificuldade do cartão.
4. Cada variante deve ser claramente diferente do original (palavras, estrutura, início da frase) e perguntar a mesma coisa.
5. Se o cartão não for conceitual (vocabulário, número, data, lista ordenada, sigla sem contexto) ou não admitir variantes fiéis a estas regras, responda conceptual=false e variants=[].

Tipos (gere exatamente um de cada):
- paraphrase: reescreva com outras palavras e outra estrutura.
- reorder: mude a ordem dos elementos ou das orações da pergunta.
- reformat: mude o formato (por exemplo, afirmação com lacuna no lugar da resposta, ou pergunta aberta).
- cue_swap: troque ou remova as palavras iniciais e as pistas superficiais mantendo o sentido; não comece com as mesmas 3 palavras do original.

Se o cartão for do tipo cloze, a pergunta é uma frase com a lacuna "[...]". Cada variante deve ser então uma frase com exatamente uma ocorrência de "[...]" no lugar da resposta.

Responda somente com JSON, sem texto extra:
{"conceptual": true, "reason": "...", "variants": [{"type": "paraphrase", "text": "..."}, {"type": "reorder", "text": "..."}, {"type": "reformat", "text": "..."}, {"type": "cue_swap", "text": "..."}]}"""

JUDGE_SYSTEM = """Você audita variantes de flashcards. Recebe o cartão original (pergunta e resposta esperada) e uma variante da pergunta.
Responda somente com JSON, sem texto extra:
{"answer_preserved": true, "ambiguous": false, "leaks_answer": false, "same_language": true, "same_question": true, "comment": "..."}

- answer_preserved: a resposta esperada do cartão responde correta e completamente à variante?
- ambiguous: existe outra resposta plausível e correta, diferente da esperada?
- leaks_answer: a variante contém ou entrega a resposta esperada?
- same_language: a variante está no mesmo idioma do original?
- same_question: a variante pergunta a mesma coisa que o original?
Seja rigoroso."""


def card_payload(card: Card) -> dict[str, Any]:
    return {"kind": card.kind, "question": card.question_text, "answer": card.answer_text}


def build_generation_messages(card: Card) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": GEN_SYSTEM},
        {"role": "user", "content": json.dumps(card_payload(card), ensure_ascii=False)},
    ]


def build_judge_messages(card: Card, variant_text: str) -> list[dict[str, str]]:
    payload = {**card_payload(card), "variant": variant_text}
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
