"""Variantes sob demanda: a geração e a validação do pipeline (mesmos prompts e checagens) para um cartão só.

Fora do estudo: nada é gravado na nota, no banco de variantes nem nos eventos. O texto do cartão vai ao provedor do .env.
Sem imports do Anki, para testar sem interface.
"""
from __future__ import annotations

import html
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Optional

try:  # instalado: o pipeline vem copiado para dfc_probe/dfc_pipeline (scripts/vendor_pipeline.ps1)
    from .dfc_pipeline.cards import parse_note
    from .dfc_pipeline.generate import generate_one
    from .dfc_pipeline.llm import client_from_env, read_env_file
    from .dfc_pipeline.prompts import GEN_PROMPT_VERSION, JUDGE_PROMPT_VERSION
    from .dfc_pipeline.validate import decide, judge_variant
except ImportError:  # repositório e testes: PYTHONPATH=pipeline
    from dfc_pipeline.cards import parse_note
    from dfc_pipeline.generate import generate_one
    from dfc_pipeline.llm import client_from_env, read_env_file
    from dfc_pipeline.prompts import GEN_PROMPT_VERSION, JUDGE_PROMPT_VERSION
    from dfc_pipeline.validate import decide, judge_variant

TYPE_LABELS = {
    "paraphrase": "Paráfrase (outras palavras)",
    "reorder": "Reordenação (outra ordem)",
    "cue_swap": "Troca das pistas iniciais",
    "pergunta": "Em forma de pergunta",
    "reformat": "Outro formato",
}
REASON_LABELS = {
    # cartão que não vira variante (elegibilidade estrutural do pipeline)
    "model_not_supported": "tipo de nota não suportado (oclusão de imagem, digitar resposta)",
    "multi_cloze": "mais de um número de lacuna na nota",
    "too_many_blanks": "mais de 3 lacunas",
    "empty_question": "pergunta vazia",
    "short_text": "texto visível curto demais (menos de 30 caracteres)",
    "empty_answer": "resposta vazia",
    "media_or_latex": "áudio, vídeo, LaTeX ou mídia nas respostas",
    "numeric_answer": "resposta só numérica",
    "no_fields": "nota sem campos suficientes",
    "other_card_of_note": "este é outro cartão da nota, não o da lacuna principal",
    # variante reprovada na validação
    "too_similar": "parecida demais com o original",
    "same_start": "começa com as mesmas palavras",
    "leak_heuristic": "pode entregar a resposta (regra de palavras)",
    "cloze_placeholder": "marcadores das lacunas errados",
    "not_a_question": "não é uma pergunta",
    "judge_error": "o juiz não respondeu",
    "answer_not_preserved": "a resposta esperada não se mantém",
    "ambiguous": "ambígua",
    "leaks_answer": "entrega a resposta",
    "language_changed": "mudou o idioma",
    "question_changed": "mudou o que se pergunta",
    "topic_changed": "mudou o assunto",
}


def load_env(path: str, environ: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Variáveis do .env do pipeline; as do ambiente do Anki valem mais, como no pipeline."""
    env: dict[str, str] = {}
    path = os.path.expanduser(path.strip()) if path else ""
    if path:
        if not os.path.exists(path):
            raise FileNotFoundError(f"arquivo não encontrado: {path}")
        env = read_env_file(path)
    for key, value in (os.environ if environ is None else environ).items():
        if key.startswith("DFC_") or key == "OPENROUTER_API_KEY":
            env[key] = value
    return env


def build_clients(env: Mapping[str, str]) -> tuple[Any, Any]:
    """Gerador e juiz do .env, com menos tentativas e prazo menor que no lote: aqui uma pessoa espera a resposta."""
    gen, judge = client_from_env("gen", env), client_from_env("judge", env)
    for client in (gen, judge):
        client.max_retries, client.timeout = 1, 60
    return gen, judge


def generate_variants(record: dict[str, Any], gen_client: Any, judge_client: Any, card_ord: int = 0, workers: int = 4) -> dict[str, Any]:
    """Variantes do cartão (registro no formato de `core.note_to_record`), cada uma com o veredito da validação do pipeline."""
    card = parse_note(record)
    answers = list(zip(card.markers, card.answers_text)) if card.kind == "cloze" else [("", card.answer_text)]
    reasons = list(card.reasons)
    if card_ord not in card.ords:
        reasons.append("other_card_of_note")
    result: dict[str, Any] = {
        "text": card.question_text,
        "answers": answers,
        "images": len(card.images_html),
        "reasons": reasons,
        "conceptual": None,
        "reason": "",
        "error": None,
        "variants": [],
        "models": {
            "gen": getattr(gen_client, "model", "?"),
            "judge": getattr(judge_client, "model", "?"),
            "gen_prompt": GEN_PROMPT_VERSION,
            "judge_prompt": JUDGE_PROMPT_VERSION,
        },
    }
    if reasons:
        return result
    rec = generate_one(card, gen_client)
    result.update(conceptual=rec["conceptual"], reason=rec["reason"], error=rec["error"])
    if rec["error"] or not rec["variants"]:
        return result

    def check(variant: dict[str, str]) -> dict[str, Any]:
        verdict, _usage = judge_variant(judge_client, card, variant["text"])
        ok, why, _metrics = decide(card, variant, verdict)
        return {"type": variant["type"], "text": variant["text"], "valid": ok, "reasons": why}

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(rec["variants"])))) as pool:
        result["variants"] = list(pool.map(check, rec["variants"]))
    return result


def _p(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def _labels(reasons: list[str]) -> str:
    return "; ".join(REASON_LABELS.get(r, r) for r in reasons)


def render_html(result: dict[str, Any]) -> str:
    """Janela de resultado: o cartão, as variantes e o veredito de cada uma. Todo texto vindo do cartão ou do LLM é escapado."""
    parts = ["<h3>Cartão original</h3>", f"<p>{_p(result['text'])}</p>"]
    if result["images"]:
        parts.append(f"<p><i>O cartão tem {result['images']} imagem(ns); nas variantes de texto ela ficaria acima do texto.</i></p>")
    answers = [f"{_p(marker)} {_p(answer)}".strip() for marker, answer in result["answers"]]
    parts.append("<p><b>Resposta esperada:</b><br>" + "<br>".join(answers) + "</p>")
    if result["reasons"]:
        parts += ["<h3>Sem variantes</h3>", f"<p>Este cartão não entra no pipeline: {_p(_labels(result['reasons']))}.</p>"]
    elif result["error"]:
        parts += ["<h3>Sem variantes</h3>", f"<p>Falha na geração: {_p(result['error'])}</p>"]
    elif not result["variants"]:
        parts += ["<h3>Sem variantes</h3>", f"<p>O gerador considerou o cartão não conceitual: {_p(result['reason'])}</p>"]
    else:
        parts.append("<h3>Variantes geradas</h3>")
        for v in result["variants"]:
            label = _p(TYPE_LABELS.get(v["type"], v["type"]))
            if v["valid"]:
                verdict = '<span style="color:#2e7d32">aprovada</span>'
            else:
                verdict = f'<span style="color:#c62828">reprovada: {_p(_labels(v["reasons"]))}</span>'
            parts.append(f"<p><b>{label}</b> &mdash; {verdict}<br>{_p(v['text'])}</p>")
    m = result["models"]
    parts += [
        "<hr>",
        f"<p><small>Gerador {_p(str(m['gen']))} ({m['gen_prompt']}) e juiz {_p(str(m['judge']))} ({m['judge_prompt']}), conforme o .env; "
        "prompts e checagens iguais aos do estudo, sem auditoria humana. Nada foi gravado: nota, banco de variantes e eventos ficam como estavam.</small></p>",
    ]
    return "".join(parts)
