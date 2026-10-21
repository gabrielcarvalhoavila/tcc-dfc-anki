"""Prompts versionados. Mudar o texto exige mudar a versão, que é registrada em cada variante."""
from __future__ import annotations

import json
from typing import Any

from .cards import Card

GEN_PROMPT_VERSION = "gen-v4"
JUDGE_PROMPT_VERSION = "judge-v4"
# Tipos gerados pelo LLM, por tipo de cartão. `sem_imagem` não aparece aqui: é determinística e entra no `pack`.
VARIANT_TYPES = {"basic": ("paraphrase", "reorder", "reformat", "cue_swap"), "cloze": ("paraphrase", "reorder", "cue_swap", "pergunta")}

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

Responda somente com JSON, sem texto extra:
{"conceptual": true, "reason": "...", "variants": [{"type": "paraphrase", "text": "..."}, {"type": "reorder", "text": "..."}, {"type": "reformat", "text": "..."}, {"type": "cue_swap", "text": "..."}]}"""

GEN_SYSTEM_CLOZE = """Você gera variantes de flashcards para um estudo que mede se alguém memorizou a FORMA do cartão em vez do conteúdo.
Contexto: as fichas são de um estudante brasileiro de vestibular (ENEM e UFRGS), em português do Brasil, com conteúdo de Ensino Médio. Use a terminologia dos livros didáticos brasileiros só para escolher as palavras: o conteúdo de cada variante é o da ficha, nada mais.
O cartão é uma "ficha" com lacunas: um texto (por exemplo, título, subtítulo e linhas "rótulo: lacuna") com uma ou mais lacunas ocultas ao mesmo tempo, marcadas como [...] (se há uma) ou [...1], [...2], [...3] (se há várias). Você recebe o texto, a resposta esperada de cada marcador e se o cartão tem uma imagem ilustrativa (que será mantida e não aparece aqui).
Devolva variantes do TEXTO que mudam só a forma e mantêm as lacunas.

Regras (mundo fechado):
1. Cada marcador aparece exatamente uma vez em cada variante, escrito exatamente como no original. A resposta esperada de cada marcador é exatamente a do cartão.
2. Use só o que o cartão diz. Não use conhecimento externo, não acrescente fatos nem exigências e não retire o contexto necessário para responder. Em especial, não acrescente nomes científicos em latim, categorias (filo, classe, ordem, sistema), siglas, exemplos nem números que o cartão não traga, mesmo que estejam corretos.
3. O assunto do título e dos rótulos tem de ser o mesmo em toda variante, no mesmo nível de generalidade: nada de termo mais amplo, mais restrito ou de outra área, e nada de frase de enchimento (como "em análise" ou "em estudo"). Cada rótulo novo tem de pedir exatamente a mesma informação que o original.
4. Nenhuma variante pode conter nem entregar as respostas esperadas (de nenhum marcador).
5. Mantenha o idioma e o nível de dificuldade do cartão.
6. Cada variante deve ser claramente diferente do original, do modo descrito no seu tipo. Escreva texto simples, sem HTML nem Markdown, e separe as linhas com "\\n".
7. Se o cartão não for conceitual (vocabulário, número, data, lista ordenada, sigla sem contexto), se o texto sozinho não permitir variantes fiéis a estas regras ou se parecer depender da imagem para ser respondido, responda conceptual=false e variants=[]. Se só alguns tipos não puderem ser feitos com fidelidade (por exemplo, reorder num cartão de um só item), omita esses tipos.

Tipos (no máximo um de cada):
- paraphrase: reescreva o texto todo (título, rótulos e frases) com outras palavras e outra estrutura de frase, como afirmações com lacuna (não vire pergunta), mantendo a ordem das informações e dos marcadores.
- reorder: mude a ordem dos itens (linhas, orações ou termos listados), mantendo exatamente as palavras de cada item, inclusive os rótulos; cada marcador acompanha o seu item, e a sequência dos marcadores pode mudar. Com uma só lacuna, reordene as orações ou os termos da frase.
- cue_swap: troque as palavras iniciais e as pistas superficiais (título, subtítulo e rótulos) por sinônimos ou reformulações que designem exatamente o mesmo assunto e peçam exatamente a mesma informação, sem mudar a ordem nem a estrutura; por exemplo, "Fotossíntese" pode virar "Processo fotossintético", mas não "Metabolismo vegetal", que é mais amplo. Os marcadores ficam na ordem do original e o texto não começa com as mesmas 3 palavras do original. Se não houver troca fiel para o título, omita este tipo.
- pergunta: reescreva o texto como perguntas diretas, uma por linha, na ordem do original, cada uma terminando em "?", com o marcador logo depois do "?" (ou dentro da frase) e sem outro "?" depois dele; use uma pergunta por marcador sempre que possível. Cada pergunta tem de fazer sentido sozinha: cite o assunto, sem "isso" nem "essas diferenças". Título, subtítulo e rótulos entram nas perguntas como contexto.

Responda somente com JSON, sem texto extra:
{"conceptual": true, "reason": "...", "variants": [{"type": "paraphrase", "text": "..."}, {"type": "reorder", "text": "..."}, {"type": "cue_swap", "text": "..."}, {"type": "pergunta", "text": "..."}]}"""

JUDGE_SYSTEM = """Você audita variantes de flashcards. Recebe o cartão original (pergunta e resposta esperada) e uma variante da pergunta.
Responda somente com JSON, sem texto extra:
{"answer_preserved": true, "ambiguous": false, "leaks_answer": false, "same_language": true, "same_question": true, "comment": "..."}

- answer_preserved: a resposta esperada do cartão responde correta e completamente à variante?
- ambiguous: existe outra resposta plausível e correta, diferente da esperada?
- leaks_answer: a variante contém ou entrega a resposta esperada?
- same_language: a variante está no mesmo idioma do original?
- same_question: a variante pergunta a mesma coisa que o original?
Seja rigoroso."""

JUDGE_SYSTEM_CLOZE = """Você audita variantes de flashcards do tipo ficha com lacunas, usadas para estudar para o vestibular brasileiro (Ensino Médio, português do Brasil). Recebe o cartão original (texto com marcadores [...] ou [...1], [...2], [...3] e a resposta esperada de cada marcador) e uma variante do texto (com outras palavras, com itens reordenados, com outras palavras iniciais ou em forma de perguntas), com os mesmos marcadores.
Responda somente com JSON, sem texto extra:
{"answer_preserved": true, "ambiguous": false, "leaks_answer": false, "same_language": true, "same_question": true, "same_topic": true, "comment": "..."}

- answer_preserved: para CADA marcador, a resposta esperada preenche correta e completamente a lacuna dele na variante (ou responde à pergunta em que ele aparece)?
- ambiguous: alguma lacuna admite outra resposta plausível e correta, diferente da esperada para o marcador?
- leaks_answer: a variante contém ou entrega, fora dos marcadores, alguma das respostas esperadas?
- same_language: a variante está no mesmo idioma do original?
- same_question: para cada marcador, a variante pede o mesmo que o original (mesmo assunto e mesmo aspecto), sem acrescentar nem perder exigências, e cada marcador continua ligado ao mesmo item?
- same_topic: o assunto do título e dos rótulos da variante é o mesmo do original, no mesmo nível de generalidade (sem termo mais amplo, mais restrito ou de outra área), sem acrescentar fatos, nomes em latim, categorias ou frases de enchimento que o original não traz?
Seja rigoroso."""


def card_payload(card: Card) -> dict[str, Any]:
    if card.kind == "cloze":
        return {
            "kind": "cloze",
            "text": card.question_text,
            "blanks": [{"marker": m, "answer": a} for m, a in zip(card.markers, card.answers_text)],
            "has_image": bool(card.images_html),
        }
    return {"kind": card.kind, "question": card.question_text, "answer": card.answer_text}


def build_generation_messages(card: Card) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": GEN_SYSTEM_CLOZE if card.kind == "cloze" else GEN_SYSTEM},
        {"role": "user", "content": json.dumps(card_payload(card), ensure_ascii=False)},
    ]


def build_judge_messages(card: Card, variant_text: str) -> list[dict[str, str]]:
    payload = {**card_payload(card), "variant": variant_text}
    return [
        {"role": "system", "content": JUDGE_SYSTEM_CLOZE if card.kind == "cloze" else JUDGE_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
