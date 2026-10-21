"""Validação automática das variantes (protocolo, seção 6.2): checagens lexicais e juiz por LLM."""
from __future__ import annotations

import time
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Callable, Optional

from .cards import BLANK_RE, Card
from .llm import LLMError, parse_json_loose
from .prompts import JUDGE_PROMPT_VERSION, build_judge_messages
from .util import append_jsonl, as_bool, now_iso, read_jsonl, tokens, write_jsonl

MIN_DISTANCE = 0.30
MIN_DISTANCE_REORDER = 0.20  # reordenar muda pouco as palavras: a distância do reorder é pela ordem delas e o limiar é menor
LEAK_MAX = 0.5
STOPWORDS = frozenset(
    "a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre e ou que se "
    "é são foi ser ao aos à às pelo pela pelos pelas mais menos como quais qual the of and or to in on for with is are be by an this that it at from".split()
)


def jaccard_distance(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 0.0
    return 1 - len(sa & sb) / len(sa | sb)


def sequence_distance(a: str, b: str) -> float:
    """Distância pela ordem das palavras: uma reordenação pura tem distância de Jaccard zero, mas não esta."""
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 0.0
    return 1 - SequenceMatcher(None, ta, tb, autojunk=False).ratio()


def first_words_differ(a: str, b: str, n: int = 3) -> bool:
    return tokens(a)[:n] != tokens(b)[:n]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if len(t) >= 4 and t not in STOPWORDS]


def leak_ratio(question: str, answer: str, variant: str) -> float:
    """Fração das palavras de conteúdo da resposta (que não estão na pergunta original) presentes na variante."""
    q = set(tokens(question))
    ans = [t for t in content_tokens(answer) if t not in q]
    if len(ans) < 2:
        return 0.0
    v = set(tokens(variant))
    return sum(t in v for t in ans) / len(ans)


def marker_positions(card: Card, text: str) -> Optional[list[int]]:
    """Posição de cada marcador esperado no texto; None se algum falta ou se repete."""
    if any(text.count(m) != 1 for m in card.markers):
        return None
    return [text.index(m) for m in card.markers]


def markers_ok(card: Card, text: str, ordered: bool = True) -> bool:
    """Cloze: cada marcador esperado aparece uma vez (na ordem do original, salvo em `reorder`), sem outros marcadores nem marcas de template."""
    if "{{" in text or "}}" in text or len(BLANK_RE.findall(text)) != len(card.markers):
        return False
    pos = marker_positions(card, text)
    return pos is not None and (not ordered or pos == sorted(pos))


def decide(
    card: Card,
    variant: dict[str, str],
    judge: Optional[dict[str, Any]],
    *,
    min_distance: float = MIN_DISTANCE,
    min_distance_reorder: float = MIN_DISTANCE_REORDER,
    leak_max: float = LEAK_MAX,
) -> tuple[bool, list[str], dict[str, float]]:
    text = variant["text"]
    reorder = variant["type"] == "reorder"
    reasons: list[str] = []
    question, plain = BLANK_RE.sub(" ", card.question_text), BLANK_RE.sub(" ", text)
    pos = marker_positions(card, text) if card.kind == "cloze" else None
    moved = pos is not None and pos != sorted(pos)  # num reorder de Cloze, algum item (e o seu marcador) mudou de lugar
    if reorder:  # os marcadores numerados entram como palavras: mover um item move a sua lacuna
        dist = sequence_distance(card.question_text, text)
    else:
        dist = jaccard_distance(question, plain)
    lr = max(leak_ratio(question, a, plain) for a in (card.answers_text if card.kind == "cloze" else [card.answer_text]))
    if dist < (min_distance_reorder if reorder else min_distance) and not (reorder and moved):
        reasons.append("too_similar")
    if variant["type"] == "cue_swap" and not first_words_differ(card.question_text, text):
        reasons.append("same_start")
    if lr >= leak_max:
        reasons.append("leak_heuristic")
    if card.kind == "cloze":
        if not markers_ok(card, text, ordered=not reorder):
            reasons.append("cloze_placeholder")
        if variant["type"] == "pergunta" and "?" not in text:
            reasons.append("not_a_question")
    if judge is None:
        reasons.append("judge_error")
    else:
        if not as_bool(judge.get("answer_preserved")):
            reasons.append("answer_not_preserved")
        if as_bool(judge.get("ambiguous")):
            reasons.append("ambiguous")
        if as_bool(judge.get("leaks_answer")):
            reasons.append("leaks_answer")
        if not as_bool(judge.get("same_language", True)):
            reasons.append("language_changed")
        if not as_bool(judge.get("same_question", True)):
            reasons.append("question_changed")
    return not reasons, reasons, {"distance": round(dist, 3), "leak_ratio": round(lr, 3)}


def judge_variant(client: Any, card: Card, text: str) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    """Veredito do juiz e uso de tokens da chamada; (None, None) se a chamada ou o JSON falharam."""
    try:
        resp = client.chat(build_judge_messages(card, text), temperature=0.0)
        return parse_json_loose(resp["text"]), resp.get("usage")
    except (LLMError, ValueError):
        return None, None


def validate(
    cards_by_id: dict[int, Card],
    generation: list[dict[str, Any]],
    client: Any,
    out_path: str,
    *,
    limit: int | None = None,
    delay: float = 0.0,
    retry_errors: bool = False,
    min_distance: float = MIN_DISTANCE,
    min_distance_reorder: float = MIN_DISTANCE_REORDER,
    leak_max: float = LEAK_MAX,
    log: Callable[[str], None] = print,
) -> Counter:
    existing = list(read_jsonl(out_path))
    if retry_errors:
        existing = [r for r in existing if "judge_error" not in r.get("reasons", [])]
        write_jsonl(out_path, existing)
    done = {r["variant_id"] for r in existing}
    todo = [
        (rec["note_id"], v)
        for rec in generation
        if not rec.get("error") and rec.get("conceptual") and rec["note_id"] in cards_by_id
        for v in rec["variants"]
        if v["variant_id"] not in done
    ]
    if limit is not None:
        todo = todo[:limit]
    stats: Counter = Counter()
    for i, (note_id, v) in enumerate(todo, 1):
        card = cards_by_id[note_id]
        judge, usage = judge_variant(client, card, v["text"])
        ok, reasons, metrics = decide(card, v, judge, min_distance=min_distance, min_distance_reorder=min_distance_reorder, leak_max=leak_max)
        append_jsonl(
            out_path,
            {
                "variant_id": v["variant_id"],
                "note_id": note_id,
                "type": v["type"],
                "text": v["text"],
                **metrics,
                "judge": judge,
                "judge_usage": usage,
                "judge_model": getattr(client, "model", "desconhecido"),
                "judge_base_url": getattr(client, "base_url", None),
                "judge_extra_body": getattr(client, "extra_body", None) or None,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "reasons": reasons,
                "auto_valid": ok,
                "ts": now_iso(),
            },
        )
        stats["validas" if ok else "invalidas"] += 1
        for r in reasons:
            stats[f"motivo:{r}"] += 1
        if i % 20 == 0 or i == len(todo):
            log(f"  {i}/{len(todo)} {dict(stats)}")
        if delay:
            time.sleep(delay)
    return stats
