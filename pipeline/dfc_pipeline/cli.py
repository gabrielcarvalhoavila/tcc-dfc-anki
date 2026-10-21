"""Linha de comando: python -m dfc_pipeline <comando> (rodar na raiz do repositório com PYTHONPATH=pipeline)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
from collections import Counter
from typing import Any

from . import ankiconnect, audit, pack, source, survey
from .cards import Card, parse_note, summarize
from .generate import generate
from .llm import ConfigError, FakeLLM, LLMError, RunAborted, client_from_env, parse_json_loose, read_env_file
from .util import read_jsonl, write_jsonl
from .validate import LEAK_MAX, MIN_DISTANCE, MIN_DISTANCE_REORDER, validate


def load_env(path: str = ".env") -> None:
    for key, value in read_env_file(path).items():
        os.environ.setdefault(key, value)


def make_client(role: str, dry_run: bool) -> Any:
    if dry_run:
        return FakeLLM()
    try:
        return client_from_env(role, os.environ)
    except ConfigError as e:
        raise SystemExit(f"{e}, ou use --dry-run para testar o fluxo sem LLM." if e.missing else str(e))


def load_cards(path: str) -> list[Card]:
    return [Card.from_dict(d) for d in read_jsonl(path)]


def cmd_export(a: argparse.Namespace) -> int:
    if a.source == "ankiconnect":
        if not a.query:
            raise SystemExit('Informe --query (busca do Anki), por exemplo: --query "deck:HTTPS".')
        records = source.from_ankiconnect(a.query, limit=a.limit, seed=a.seed)
    else:
        if not a.in_file:
            raise SystemExit("Informe --in-file com o JSONL exportado pelo add-on.")
        records = source.from_jsonl(a.in_file)
    cards = [parse_note(r) for r in records]
    write_jsonl(a.out, (c.to_dict() for c in cards))
    s = summarize(cards)
    print(f"{len(cards)} notas -> {a.out}")
    print(f"{'baralho':50} {'notas':>6} {'elegiveis':>9} {'elegiveis suspeitos':>20}")
    for deck, d in sorted(s["por_baralho"].items()):
        print(f"{deck[:50]:50} {d['notas']:>6} {d['elegiveis']:>9} {d['elegiveis_suspeitos']:>20}")
    print("motivos de inelegibilidade:", json.dumps(s["motivos"], ensure_ascii=False))
    return 0


def cmd_survey(a: argparse.Namespace) -> int:
    cards, lines = survey.run(a.query, ankiconnect.invoke, a.days, a.rollover)
    if a.out:
        write_jsonl(a.out, (c.to_dict() for c in cards))
    print("\n".join(lines))
    return 0


def cmd_generate(a: argparse.Namespace) -> int:
    cards = load_cards(a.cards)
    client = make_client("gen", a.dry_run)
    try:
        stats = generate(cards, client, a.out, limit=a.limit, delay=a.delay, workers=a.workers, retry_errors=a.retry_errors, max_failures=a.max_failures, shuffle_seed=a.shuffle)
    except RunAborted as e:
        return aborted(e, a.out)
    print("geracao:", dict(stats), f"-> {a.out}")
    return 0


def aborted(e: RunAborted, out: str) -> int:
    print(f"INTERROMPIDO: {e}. O que já foi feito está em {out}; resolva (saldo, chave, rede) e rode de novo com --retry-errors.")
    return 1


def cmd_validate(a: argparse.Namespace) -> int:
    cards = {c.note_id: c for c in load_cards(a.cards)}
    client = make_client("judge", a.dry_run)
    try:
        stats = validate(
            cards, list(read_jsonl(a.generation)), client, a.out,
            limit=a.limit, delay=a.delay, workers=a.workers, retry_errors=a.retry_errors, min_distance=a.min_distance,
            min_distance_reorder=a.min_distance_reorder, leak_max=a.leak_max, max_failures=a.max_failures,
        )
    except RunAborted as e:
        return aborted(e, a.out)
    print("validacao:", dict(stats), f"-> {a.out}")
    return 0


def cmd_audit_sheet(a: argparse.Namespace) -> int:
    cards = {c.note_id: c for c in load_cards(a.cards)}
    n = audit.build_sheet(cards, list(read_jsonl(a.validation)), a.n, a.seed, a.out)
    print(f"{n} variantes na planilha {a.out}. Preencha a coluna human_ok com s/n e rode audit-score.")
    return 0


def cmd_audit_score(a: argparse.Namespace) -> int:
    report = audit.score_sheet(a.sheet)
    audit.write_report(report, a.out)
    rate = report["taxa"]
    print(f"auditadas: {report['auditadas']}  validas: {report['validas']}  taxa: {'n/d' if rate is None else f'{rate:.1%}'}  H1: {report['h1_ok']}")
    for t, d in report["por_tipo"].items():
        print(f"  {t:12} {d['validas']}/{d['auditadas']}")
    print("tipos abaixo do limiar:", report["exclude_types"] or "nenhum", f"-> {a.out}")
    return 0


def cmd_pack(a: argparse.Namespace) -> int:
    cards = load_cards(a.cards)
    report = None
    if a.audit_report:
        with open(a.audit_report, encoding="utf-8") as f:
            report = json.load(f)
    try:
        bank = pack.build_bank(
            cards, list(read_jsonl(a.generation)), list(read_jsonl(a.validation)),
            audit_report=report, exclude_types=tuple(a.exclude_types or ()), allow_fake=a.allow_fake,
        )
    except ValueError as e:
        raise SystemExit(str(e))
    pack.write_bank(bank, a.out)
    n_var = sum(len(e["variants"]) for e in bank["notes"].values())
    print(f"banco: {len(bank['notes'])} notas, {n_var} variantes -> {a.out}")
    return 0


def cmd_stats(a: argparse.Namespace) -> int:
    cards = load_cards(a.cards)
    print(f"notas: {len(cards)}  elegiveis: {sum(c.eligible for c in cards)}")
    if a.generation:
        gen = list(read_jsonl(a.generation))
        print(f"geracao: {len(gen)} notas  erros: {sum(1 for g in gen if g.get('error'))}  conceituais: {sum(1 for g in gen if g.get('conceptual'))}")
        usage = Counter()
        for g in gen:
            for k, v in ((g.get("generator") or {}).get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    usage[k] += v
        if usage:
            print("tokens (geracao):", dict(usage))
    if a.validation:
        val = list(read_jsonl(a.validation))
        by = Counter((v["type"], v["auto_valid"]) for v in val)
        print(f"validacao: {len(val)} variantes  aprovadas: {sum(v['auto_valid'] for v in val)}")
        judge_usage = Counter()
        for v in val:
            for k, n in (v.get("judge_usage") or {}).items():
                if isinstance(n, (int, float)):
                    judge_usage[k] += n
        if judge_usage:
            print("tokens (juiz):", dict(judge_usage))
        for (t, ok), n in sorted(by.items()):
            print(f"  {t:12} {'ok' if ok else 'reprovada':9} {n}")
    return 0


def cmd_ping(a: argparse.Namespace) -> int:
    """Uma chamada mínima por papel: confere URL, chave, ID do modelo, JSON e uso de tokens, sem mostrar a chave."""
    failed = False
    for role, label in (("gen", "gerador"), ("judge", "juiz")):
        client = make_client(role, False)
        host = urllib.parse.urlparse(client.base_url).netloc
        print(f"{label}: {client.model} em {host} | json_mode={'sim' if client.json_mode else 'nao'} | extra={client.extra_body or '-'}")
        try:
            if a.models is not None and role == "gen":
                ids = [m for m in client.list_models() if a.models.lower() in m.lower()]
                print(f"  modelos que contem '{a.models}': {', '.join(ids) or 'nenhum'}")
            start = time.time()
            messages = [
                {"role": "system", "content": 'Responda somente com JSON no formato {"soma": <número>, "idioma": "pt"}.'},
                {"role": "user", "content": "Quanto é 17 + 25?"},
            ]
            resp = client.chat(messages)
            data = parse_json_loose(resp["text"])
        except (LLMError, ValueError) as e:
            print(f"  FALHOU: {e}")
            failed = True
            continue
        print(f"  ok em {int((time.time() - start) * 1000)} ms | resposta: {data} | uso: {resp.get('usage')}")
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dfc_pipeline", description="Pipeline de variantes do projeto DFC")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="le notas do Anki e aplica a elegibilidade estrutural")
    e.add_argument("--source", choices=["ankiconnect", "file"], default="ankiconnect")
    e.add_argument("--query", help='busca do Anki, por exemplo "deck:HTTPS"')
    e.add_argument("--in-file", help="JSONL exportado pelo add-on (para outra pessoa)")
    e.add_argument("--limit", type=int, help="lê só uma amostra aleatória deste tamanho das notas encontradas (ankiconnect)")
    e.add_argument("--seed", type=int, default=20261021, help="semente da amostra")
    e.add_argument("--out", default="data/cards.jsonl")
    e.set_defaults(func=cmd_export)

    sv = sub.add_parser("survey", help="viabilidade de uma colecao: tipos de nota, elegiveis e eventos que ela geraria (so agregados)")
    sv.add_argument("--query", default="deck:*", help="busca do Anki (padrao: todos os baralhos)")
    sv.add_argument("--days", type=int, default=28, help="periodo observado no historico de revisoes")
    sv.add_argument("--rollover", type=int, default=4, help="hora em que o dia vira no Anki")
    sv.add_argument("--out", help="grava tambem as notas lidas (JSONL, como o export)")
    sv.set_defaults(func=cmd_survey)

    g = sub.add_parser("generate", help="gera variantes com o LLM (DFC_GEN_MODEL)")
    g.add_argument("--cards", default="data/cards.jsonl")
    g.add_argument("--out", default="data/generation.jsonl")
    g.add_argument("--limit", type=int)
    g.add_argument("--delay", type=float, default=0.0)
    g.add_argument("--workers", type=int, default=1, help="chamadas simultâneas ao provedor (o padrão 1 é sequencial)")
    g.add_argument("--max-failures", type=int, default=15, help="interrompe depois de N falhas seguidas (crédito, chave, rede); 0 desliga")
    g.add_argument("--shuffle", type=int, metavar="SEMENTE", help="sorteia a ordem das notas; com --limit, cada lote é uma amostra aleatória das que faltam")
    g.add_argument("--retry-errors", action="store_true")
    g.add_argument("--dry-run", action="store_true", help="usa um LLM falso; so para testar o fluxo")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="valida as variantes (checagens lexicais + juiz DFC_JUDGE_MODEL)")
    v.add_argument("--cards", default="data/cards.jsonl")
    v.add_argument("--generation", default="data/generation.jsonl")
    v.add_argument("--out", default="data/validation.jsonl")
    v.add_argument("--limit", type=int)
    v.add_argument("--delay", type=float, default=0.0)
    v.add_argument("--workers", type=int, default=1, help="chamadas simultâneas ao provedor (o padrão 1 é sequencial)")
    v.add_argument("--max-failures", type=int, default=15, help="interrompe depois de N falhas seguidas do juiz (crédito, chave, rede); 0 desliga")
    v.add_argument("--retry-errors", action="store_true")
    v.add_argument("--min-distance", type=float, default=MIN_DISTANCE)
    v.add_argument("--min-distance-reorder", type=float, default=MIN_DISTANCE_REORDER)
    v.add_argument("--leak-max", type=float, default=LEAK_MAX)
    v.add_argument("--dry-run", action="store_true")
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("audit-sheet", help="gera a planilha de auditoria humana (H1)")
    s.add_argument("--cards", default="data/cards.jsonl")
    s.add_argument("--validation", default="data/validation.jsonl")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, default=20261020)
    s.add_argument("--out", default="data/audit_sheet.csv")
    s.set_defaults(func=cmd_audit_sheet)

    sc = sub.add_parser("audit-score", help="calcula a taxa de variantes validas na planilha preenchida")
    sc.add_argument("--sheet", default="data/audit_sheet.csv")
    sc.add_argument("--out", default="data/audit_report.json")
    sc.set_defaults(func=cmd_audit_score)

    k = sub.add_parser("pack", help="empacota o banco de variantes para o add-on")
    k.add_argument("--cards", default="data/cards.jsonl")
    k.add_argument("--generation", default="data/generation.jsonl")
    k.add_argument("--validation", default="data/validation.jsonl")
    k.add_argument("--audit-report")
    k.add_argument("--exclude-types", nargs="*")
    k.add_argument("--out", default="data/bank/variant_bank.json")
    k.add_argument("--allow-fake", action="store_true")
    k.set_defaults(func=cmd_pack)

    st = sub.add_parser("stats", help="resumo do estado do pipeline")
    st.add_argument("--cards", default="data/cards.jsonl")
    st.add_argument("--generation")
    st.add_argument("--validation")
    st.set_defaults(func=cmd_stats)

    pg = sub.add_parser("ping", help="testa o provedor: uma chamada mínima ao gerador e ao juiz (não mostra a chave)")
    pg.add_argument("--models", nargs="?", const="", help="lista também os IDs de modelo do provedor que contenham este texto")
    pg.set_defaults(func=cmd_ping)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    load_env()
    args = build_parser().parse_args(argv)
    return args.func(args) or 0
