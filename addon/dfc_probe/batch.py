"""Variantes em lote para o uso livre (v0.5.0): planejar e gerar variantes para muitas notas de uma vez.

Fora do estudo: o texto das notas vai ao provedor configurado pela pessoa e o resultado vai só para o banco pessoal. Sem imports do Anki, para testar sem interface.
"""
from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

try:
    from . import free, live
except ImportError:  # os testes carregam o módulo fora do pacote
    import free  # type: ignore
    import live  # type: ignore

DEFAULT_MAX_NOTES = 200
DEFAULT_WORKERS = 3
ABORT_AFTER = 8  # falhas seguidas (chave, crédito ou rede) que interrompem o lote
GRACE_SECONDS = 15.0  # ao cancelar, quanto esperar pelas chamadas em andamento
SAVE_EVERY = 10
JUDGE_CALLS_PER_NOTE = 3.2  # ≈ 80% das notas são conceituais, com ≈ 4 variantes cada


@dataclass
class Options:
    workers: int = DEFAULT_WORKERS
    max_notes: int = DEFAULT_MAX_NOTES
    reprocess: bool = False  # refazer notas que já têm variantes ou foram dispensadas antes
    types: Optional[list[str]] = None  # None: todos os tipos
    abort_after: int = ABORT_AFTER


@dataclass
class Plan:
    todo: list[dict[str, Any]] = field(default_factory=list)
    examined: int = 0
    official: int = 0  # notas do banco do estudo: ficam de fora
    ineligible: int = 0
    reasons: Counter = field(default_factory=Counter)
    already: int = 0  # já têm variantes para o texto atual
    dismissed: int = 0  # já foram avaliadas sem variantes para o texto atual
    truncated: int = 0  # elegíveis além do limite de notas


@dataclass
class Summary:
    total: int = 0
    done: int = 0
    with_variants: int = 0
    variants: int = 0
    not_conceptual: int = 0
    no_valid: int = 0
    no_selected: int = 0
    ineligible: int = 0
    errors: int = 0
    cancelled: bool = False
    aborted: str = ""
    abandoned: int = 0
    last_error: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0


def estimate(n_notes: int) -> dict[str, Any]:
    """Chamadas e custo aproximado com os modelos padrão da configuração (confira os preços do seu provedor)."""
    return {"gen_calls": n_notes, "judge_calls": round(n_notes * JUDGE_CALLS_PER_NOTE), "usd": round(n_notes * free.USD_PER_NOTE, 2)}


def make_plan(records: Iterable[dict[str, Any]], bank: free.FreeBank, official_ids: Iterable[int], options: Options) -> Plan:
    """Separa o que gerar agora do que já está pronto ou não tem como virar variante. `records` vêm na ordem em que devem ser gerados."""
    official = set(official_ids)
    plan = Plan()
    eligible: list[dict[str, Any]] = []
    for rec in records:
        plan.examined += 1
        if int(rec["note_id"]) in official:
            plan.official += 1
            continue
        card = live.parse_note(rec)
        if card.reasons:
            plan.ineligible += 1
            plan.reasons.update(card.reasons)
            continue
        if not options.reprocess:
            if bank.has_current(rec["note_id"], card.fields_hash):
                plan.already += 1
                continue
            if bank.is_skipped(rec["note_id"], card.fields_hash):
                plan.dismissed += 1
                continue
        eligible.append(rec)
    plan.todo = eligible[: max(0, options.max_notes)]
    plan.truncated = len(eligible) - len(plan.todo)
    return plan


def describe_plan(plan: Plan) -> str:
    n = len(plan.todo)
    lines = [f"Notas examinadas: {plan.examined}", f"Para gerar agora: {n}" + (f" (mais {plan.truncated} ficam para uma próxima vez, pelo limite de notas)" if plan.truncated else "")]
    if plan.already:
        lines.append(f"Já têm variantes: {plan.already}")
    if plan.dismissed:
        lines.append(f"Já avaliadas sem variantes (cartão não conceitual ou sem variante aprovada): {plan.dismissed}")
    if plan.official:
        lines.append(f"Do banco do estudo (não são tocadas): {plan.official}")
    if plan.ineligible:
        top = ", ".join(f"{live.REASON_LABELS.get(r, r)}: {c}" for r, c in plan.reasons.most_common(3))
        lines.append(f"Sem como gerar: {plan.ineligible}" + (f" ({top})" if top else ""))
    if n:
        e = estimate(n)
        usd = f"{e['usd']:.2f}".replace(".", ",")
        lines.append(f"\nSerão cerca de {e['gen_calls']} chamadas ao gerador e {e['judge_calls']} ao juiz, uns US$ {usd} com os modelos padrão (confira o preço do seu provedor).")
    return "\n".join(lines)


def _work(record: dict[str, Any], gen: Any, judge: Any, options: Options) -> dict[str, Any]:
    return live.generate_variants(record, gen, judge, card_ord=None, workers=2, types=options.types)


def run(
    todo: list[dict[str, Any]],
    gen: Any,
    judge: Any,
    bank: free.FreeBank,
    options: Options,
    on_progress: Optional[Callable[[Summary], None]] = None,
    cancelled: Optional[Callable[[], bool]] = None,
    grace: float = GRACE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> Summary:
    """Gera, valida e guarda no banco pessoal as variantes de `todo`. Roda na thread que chamou; `on_progress` e `cancelled` também."""
    summary = Summary(total=len(todo))
    if not todo:
        return summary
    started = clock()
    workers = max(1, options.workers)
    pool = ThreadPoolExecutor(max_workers=workers)
    source = iter(todo)
    running: dict[Any, tuple[int, dict[str, Any]]] = {}
    submitted = 0
    streak = 0
    stopping = False
    deadline = 0.0
    gen_model, judge_model = str(getattr(gen, "model", "") or ""), str(getattr(judge, "model", "") or "")

    def settle(record: dict[str, Any], future: Any) -> int:
        """Guarda o resultado de uma nota; devolve o novo número de falhas seguidas."""
        summary.done += 1
        nid = record["note_id"]
        try:
            result = future.result()
        except Exception as e:
            summary.errors += 1
            summary.last_error = f"{type(e).__name__}: {e}"[:300]
            return streak + 1
        live.add_usage(summary.usage, result.get("usage"))
        fh = result["fields_hash"]

        def dismiss(reason: str) -> None:
            if bank.entry(nid) is None:
                bank.skip(nid, fh, reason)

        if result["reasons"]:
            summary.ineligible += 1
            return 0
        err = result["error"]
        if err == "no_valid_variants":
            summary.no_valid += 1
            dismiss("no_valid_variant")
            return 0
        if err:
            summary.errors += 1
            summary.last_error = str(err)[:300]
            return streak + 1
        if not result["conceptual"]:
            summary.not_conceptual += 1
            dismiss("not_conceptual")
            return 0
        if not result["variants"]:
            summary.no_selected += 1
            return 0
        if all("judge_error" in v["reasons"] for v in result["variants"]):
            summary.errors += 1
            summary.last_error = "o juiz não respondeu"
            return streak + 1
        ids = {v["id"] for v in result["variants"]} | {f"{result['note_id']}-sem_imagem"}
        entry = free.entry_from_result(result, types=options.types, only_ids=ids - bank.banned)
        if entry is None or not bank.set_entry(nid, entry, gen_model, judge_model):
            summary.no_valid += 1
            dismiss("no_valid_variant")
            return 0
        summary.with_variants += 1
        summary.variants += len(entry["variants"])
        return 0

    try:
        while True:
            if not stopping and cancelled is not None and cancelled():
                stopping, summary.cancelled, deadline = True, True, clock() + grace
            while not stopping and len(running) < workers * 2:
                record = next(source, None)
                if record is None:
                    break
                running[pool.submit(_work, record, gen, judge, options)] = (submitted, record)
                submitted += 1
            if not running:
                break
            finished, _pending = wait(list(running), timeout=0.25, return_when=FIRST_COMPLETED)
            for future in sorted(finished, key=lambda f: running[f][0]):  # na ordem de envio, para o resultado não depender do acaso
                streak = settle(running.pop(future)[1], future)
                if summary.done % SAVE_EVERY == 0:
                    bank.save()
                if on_progress is not None:
                    on_progress(summary)
                if not stopping and streak >= options.abort_after:
                    stopping, deadline = True, clock() + grace
                    summary.aborted = f"{streak} falhas seguidas (chave, crédito ou rede?). Último erro: {summary.last_error}"
            if stopping and running and clock() > deadline:
                summary.abandoned = len(running)
                break
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        bank.save()
        summary.seconds = clock() - started
    return summary


def format_summary(s: Summary) -> str:
    minutes, seconds = divmod(int(s.seconds), 60)
    took = f"{minutes} min {seconds} s" if minutes else f"{seconds} s"
    lines = []
    if s.aborted:
        lines.append(f"Interrompido: {s.aborted}")
    elif s.cancelled:
        lines.append("Cancelado; o que já foi gerado está no banco pessoal.")
    else:
        lines.append("Concluído.")
    lines.append(f"{s.done} de {s.total} notas processadas em {took}.")
    lines.append(f"Com variantes: {s.with_variants} notas ({s.variants} variantes no banco)")
    skipped = []
    if s.not_conceptual:
        skipped.append(f"{s.not_conceptual} não conceituais (vocabulário, memorização pura ou dependentes da imagem)")
    if s.no_valid:
        skipped.append(f"{s.no_valid} sem variante aprovada na validação")
    if s.no_selected:
        skipped.append(f"{s.no_selected} sem nenhum dos tipos escolhidos")
    if s.ineligible:
        skipped.append(f"{s.ineligible} fora do alcance")
    if skipped:
        lines.append("Sem variantes: " + "; ".join(skipped))
    if s.errors:
        lines.append(f"Falhas (podem ser tentadas de novo): {s.errors}" + (f". Último erro: {s.last_error}" if s.last_error else ""))
    if s.abandoned:
        lines.append(f"{s.abandoned} chamadas em andamento foram descartadas.")
    tokens = [f"{label} {s.usage[key]}" for label, key in (("entrada", "prompt_tokens"), ("saída", "completion_tokens")) if s.usage.get(key)]
    if tokens:
        lines.append("Tokens: " + ", ".join(tokens))
    return "\n".join(lines)
