"""Validação automática das variantes (protocolo, seção 6.2): checagens lexicais e juiz por LLM."""
from __future__ import annotations

import time
from collections import Counter
from typing import Any, Callable, Optional

from .cards import Card, PLACEHOLDER
from .llm import LLMError, parse_json_loose
from .prompts import JUDGE_PROMPT_VERSION, build_judge_messages
from .util import append_jsonl, as_bool, now_iso, read_jsonl, tokens, write_jsonl

MIN_DISTANCE = 0.30
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


def decide(card: Card, variant: dict[str, str], judge: Optional[dict[str, Any]], *, min_distance: float = MIN_DISTANCE, leak_max: float = LEAK_MAX) -> tuple[bool, list[str], dict[str, float]]:
    text = variant["text"]
    reasons: list[str] = []
    dist = jaccard_distance(card.question_text, text)
    lr = leak_ratio(card.question_text, card.answer_text, text)
    if dist < min_distance:
        reasons.append("too_similar")
    if variant["type"] == "cue_swap" and not first_words_differ(card.question_text, text):
        reasons.append("same_start")
    if lr >= leak_max:
        reasons.append("leak_heuristic")
    if card.kind == "cloze" and text.count(PLACEHOLDER) != 1:
        reasons.append("cloze_placeholder")
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


def judge_variant(client: Any, card: Card, text: str) -> Optional[dict[str, Any]]:
    try:
        resp = client.chat(build_judge_messages(card, text), temperature=0.0)
        return parse_json_loose(resp["text"])
    except (LLMError, ValueError):
        return None


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
        judge = judge_variant(client, card, v["text"])
        ok, reasons, metrics = decide(card, v, judge, min_distance=min_distance, leak_max=leak_max)
        append_jsonl(
            out_path,
            {
                "variant_id": v["variant_id"],
                "note_id": note_id,
                "type": v["type"],
                "text": v["text"],
                **metrics,
                "judge": judge,
                "judge_model": getattr(client, "model", "desconhecido"),
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
