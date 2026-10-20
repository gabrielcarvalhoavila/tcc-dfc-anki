"""Linha de comando: python -m dfc_pipeline <comando> (rodar na raiz do repositório com PYTHONPATH=pipeline)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any

from . import audit, pack, source
from .cards import Card, parse_note, summarize
from .generate import generate
from .llm import FakeLLM, LLMClient
from .util import read_jsonl, write_jsonl
from .validate import LEAK_MAX, MIN_DISTANCE, validate

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def load_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_client(role: str, dry_run: bool) -> Any:
    if dry_run:
        return FakeLLM()
    base = os.environ.get("DFC_LLM_BASE_URL", DEFAULT_BASE_URL)
    key = os.environ.get("DFC_LLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("DFC_GEN_MODEL" if role == "gen" else "DFC_JUDGE_MODEL")
    local = "localhost" in base or "127.0.0.1" in base
    if not model or (not key and not local):
        var = "DFC_GEN_MODEL" if role == "gen" else "DFC_JUDGE_MODEL"
        raise SystemExit(f"Defina DFC_LLM_API_KEY e {var} (veja .env.example), ou use --dry-run para testar o fluxo sem LLM.")
    temperature = 0.7 if role == "gen" else 0.0
    return LLMClient(base, key, model, temperature=temperature, json_mode=os.environ.get("DFC_JSON_MODE") == "1")


def load_cards(path: str) -> list[Card]:
    return [Card.from_dict(d) for d in read_jsonl(path)]


def cmd_export(a: argparse.Namespace) -> int:
    if a.source == "ankiconnect":
        if not a.query:
            raise SystemExit('Informe --query (busca do Anki), por exemplo: --query "deck:HTTPS".')
        records = source.from_ankiconnect(a.query)
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


def cmd_generate(a: argparse.Namespace) -> int:
    cards = load_cards(a.cards)
    client = make_client("gen", a.dry_run)
    stats = generate(cards, client, a.out, limit=a.limit, delay=a.delay, retry_errors=a.retry_errors)
    print("geracao:", dict(stats), f"-> {a.out}")
    return 0


def cmd_validate(a: argparse.Namespace) -> int:
    cards = {c.note_id: c for c in load_cards(a.cards)}
    client = make_client("judge", a.dry_run)
    stats = validate(
        cards, list(read_jsonl(a.generation)), client, a.out,
        limit=a.limit, delay=a.delay, retry_errors=a.retry_errors, min_distance=a.min_distance, leak_max=a.leak_max,
    )
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
        for (t, ok), n in sorted(by.items()):
            print(f"  {t:12} {'ok' if ok else 'reprovada':9} {n}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dfc_pipeline", description="Pipeline de variantes do projeto DFC")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("export", help="le notas do Anki e aplica a elegibilidade estrutural")
    e.add_argument("--source", choices=["ankiconnect", "file"], default="ankiconnect")
    e.add_argument("--query", help='busca do Anki, por exemplo "deck:HTTPS"')
    e.add_argument("--in-file", help="JSONL exportado pelo add-on (para outra pessoa)")
    e.add_argument("--out", default="data/cards.jsonl")
    e.set_defaults(func=cmd_export)

    g = sub.add_parser("generate", help="gera variantes com o LLM (DFC_GEN_MODEL)")
    g.add_argument("--cards", default="data/cards.jsonl")
    g.add_argument("--out", default="data/generation.jsonl")
    g.add_argument("--limit", type=int)
    g.add_argument("--delay", type=float, default=0.0)
    g.add_argument("--retry-errors", action="store_true")
    g.add_argument("--dry-run", action="store_true", help="usa um LLM falso; so para testar o fluxo")
    g.set_defaults(func=cmd_generate)

    v = sub.add_parser("validate", help="valida as variantes (checagens lexicais + juiz DFC_JUDGE_MODEL)")
    v.add_argument("--cards", default="data/cards.jsonl")
    v.add_argument("--generation", default="data/generation.jsonl")
    v.add_argument("--out", default="data/validation.jsonl")
    v.add_argument("--limit", type=int)
    v.add_argument("--delay", type=float, default=0.0)
    v.add_argument("--retry-errors", action="store_true")
    v.add_argument("--min-distance", type=float, default=MIN_DISTANCE)
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
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    load_env()
    args = build_parser().parse_args(argv)
    return args.func(args) or 0
