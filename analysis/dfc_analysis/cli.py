"""Linha de comando da análise.

    python -m dfc_analysis monitor   --csv ARQUIVO.csv --perfil NOME          # contagem e qualidade, sem desfecho por braço
    python -m dfc_analysis cego      --csv ARQUIVO.csv --perfil NOME          # rótulos de braço embaralhados: testa o roteiro
    python -m dfc_analysis sintetico                                          # dados com efeito conhecido: confere o roteiro
    python -m dfc_analysis final     --csv ARQUIVO.csv --perfil NOME          # análise pré-registrada (rodada única, com trava)

O nome do perfil de estudo vem de `--perfil` ou da variável de ambiente `DFC_PERFIL_ESTUDO`; não fica no código nem nos relatórios.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from . import data as D
from . import prereg as P


class Recusa(Exception):
    """A análise final não pode rodar (trava do pré-registro)."""


def hoje() -> datetime.date:
    return datetime.date.today()


def checar_trava(n_validos: int, hoje: datetime.date, olhada: Optional[str]) -> Optional[str]:
    """Seção 8, linha 5: a análise do desfecho só roda no fim da coleta (22/11 ou ≈ 1000 eventos válidos), "sem olhar o desfecho antes".
    Devolve o motivo da olhada intermediária se ela foi pedida e autorizada, None se o fim da coleta chegou; levanta `Recusa` nos demais casos."""
    if hoje > P.JANELA_FIM or n_validos >= P.ALVO_EVENTOS:
        return None
    if olhada and olhada.strip():
        return olhada.strip()
    raise Recusa(
        f"A coleta ainda não terminou: {n_validos} eventos válidos (alvo {P.ALVO_EVENTOS}) e hoje é {hoje:%d/%m/%Y} (fim em {P.JANELA_FIM:%d/%m/%Y}). "
        "O protocolo manda não olhar o desfecho antes (seção 8, linha 5). Para olhar mesmo assim, use --olhada-intermediaria \"motivo\"; "
        "a olhada fica registrada em olhadas.log e o relatório sai marcado."
    )


def sha256_arquivo(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def info_codigo() -> dict[str, str]:
    """Versão, hash do código e estado do Git: liga o relatório ao script que o gerou."""
    pacote = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for f in sorted(pacote.glob("*.py")):
        h.update(f.name.encode() + b"\0" + f.read_bytes().replace(b"\r\n", b"\n"))
    out = {"versao": P.VERSAO_ANALISE, "sha256": h.hexdigest()[:16], "git": "indisponível"}
    try:
        raiz = pacote.parents[1]
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=raiz, capture_output=True, text=True, timeout=10).stdout.strip()
        sujo = subprocess.run(["git", "status", "--porcelain", "--", "analysis"], cwd=raiz, capture_output=True, text=True, timeout=10).stdout.strip()
        if commit:
            out["git"] = commit + (" (código da análise MODIFICADO desde o commit)" if sujo else " (código da análise sem modificações)")
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def _versoes() -> str:
    import numpy
    import statsmodels

    return f"Python {platform.python_version()}, pandas {pd.__version__}, numpy {numpy.__version__}, statsmodels {statsmodels.__version__}"


def _perfil(args: argparse.Namespace) -> str:
    nome = args.perfil or os.environ.get(P.PERFIL_ENV)
    if not nome:
        raise SystemExit(f"Informe o perfil de estudo com --perfil ou com a variável de ambiente {P.PERFIL_ENV}.")
    return nome


def _pasta(args: argparse.Namespace, modo: str) -> str:
    return os.path.join(args.saida, f"{datetime.datetime.now():%Y%m%d-%H%M%S}_{modo}")


def _meta(modo: str, args: argparse.Namespace, df: pd.DataFrame, caminho_csv: Optional[str]) -> dict[str, str]:
    cod = info_codigo()
    meta = {
        "Gerado em": f"{datetime.datetime.now():%d/%m/%Y %H:%M}",
        "Código": f"versão {cod['versao']}, SHA-256 {cod['sha256']}, commit {cod['git']}",
        "Ambiente": _versoes(),
        "Janela e filtros": f"{P.JANELA_INICIO:%d/%m/%Y} a {P.JANELA_FIM:%d/%m/%Y} (data local, {args.fuso}); banco `{P.BANCO_HASH}`; Anki {P.ANKI_VERSAO}; perfil de estudo informado por argumento (o nome não é gravado)",
    }
    if caminho_csv:
        meta["CSV"] = f"`{os.path.basename(caminho_csv)}`, {len(df)} linhas, SHA-256 {sha256_arquivo(caminho_csv)[:16]}"
    return meta


def rodar_monitor(args: argparse.Namespace) -> int:
    from . import figuras as F
    from . import report as R

    pasta = _pasta(args, "monitor")
    df = D.ler_csv(args.csv)
    d = D.preparar(df, _perfil(args), args.fuso)
    v, a = D.validos(d), D.analise(d)
    flx = D.fluxo(d)
    sorteios = D.reproduzir_sorteios(d)
    variantes = D.reproduzir_variantes(d, args.banco) if args.banco else None
    verif = D.verificacoes(d, a, sorteios, variantes)
    por_dia, ritmo = D.ritmo(v, hoje())
    celulas = {}
    taxa = float(a["falha"].mean()) if len(a) else None
    prec = []
    if len(a) and taxa is not None:
        tab = D.tabela_celulas(a)
        celulas = {f"{e}/{b}": int(tab.loc[e, b]) for e in tab.index for b in ("original", "variante")}
        for rot, n in (("Agora", len(a)), (f"Alvo ({P.ALVO_EVENTOS})", P.ALVO_EVENTOS), ("Projeção para 22/11", ritmo.get("projecao_fim", 0))):
            if n:
                prec.append({"rotulo": rot, **D.precisao_prevista(celulas, taxa, int(n))})
    texto = R.cabecalho("monitor", {"meta": _meta("monitor", args, df, args.csv)})
    texto += R.secao_fluxo(flx)
    if len(a):
        texto += R.secao_celulas(D.tabela_celulas(a), a.loc[a["variante"] == 1, "tipo"].value_counts(), a["deck_name"].value_counts())
        texto += R.secao_balanco(D.balanco(a))
    texto += R.secao_verificacoes(verif)
    texto += R.secao_ritmo(por_dia, ritmo, prec, taxa)
    if F.disponivel():
        fig = F.ritmo(por_dia, pasta)
        if fig:
            texto += [f"![Eventos válidos ao longo da janela]({fig})", ""]
    caminho = R.gravar(pasta, "relatorio.md", "\n".join(texto))
    R.gravar_tabela(pasta, "fluxo", flx)
    R.gravar_tabela(pasta, "eventos_por_dia", por_dia)
    R.gravar_json(pasta, "monitor.json", {"fluxo": flx, "verificacoes": verif, "ritmo": ritmo, "sorteios": sorteios, "variantes": variantes, "precisao": prec})
    print(flx.to_string(index=False))
    print(f"\nEventos válidos: {len(v)} (alvo {P.ALVO_EVENTOS}). Na análise (covariáveis completas): {len(a)}.")
    for c in verif:
        if c["status"] == "ATENÇÃO":
            print(f"ATENÇÃO: {c['item']}: {c['detalhe']}")
    print(f"Relatório: {caminho}")
    return 0


def rodar_analise(args: argparse.Namespace, modo: str, df: pd.DataFrame, perfil: str, *, caminho_csv: Optional[str] = None, verdade: Optional[dict[str, float]] = None, olhada: Optional[str] = None) -> int:
    from . import models as M
    from . import report as R
    from . import figuras as F

    semente = getattr(args, "semente", 1)
    pasta = _pasta(args, modo)
    d = D.preparar(df, perfil, args.fuso, embaralhar=semente if modo == "cego" else None)
    a = D.analise(d)
    avisos: list[str] = []
    flx = D.fluxo(d)
    minimos = M.checar_minimos(a)
    texto = R.cabecalho(modo, {"meta": _meta(modo, args, df, caminho_csv), "olhada": olhada})
    texto += R.secao_fluxo(flx)
    if len(a) == 0:
        texto += ["Nenhum evento válido: nada a analisar.", ""]
        R.gravar(pasta, "relatorio.md", "\n".join(texto))
        print("Nenhum evento válido.")
        return 1

    primario, coef = M.estimar_did(a, rotulo="Principal", n_boot=args.bootstrap, semente=semente)
    classe = M.classificar_h2(primario["did"], primario["did_lo"], primario["did_hi"]) if "did" in primario else None
    taxas = M.taxas_celulas(a)

    def tentar(nome: str, fn):
        try:
            return fn()
        except Exception as e:  # análise secundária que falha não pode derrubar a primária
            avisos.append(f"{nome} falhou: {type(e).__name__}: {e}")
            return None

    escalas = tentar("Efeito de escala", lambda: M.escalas(a))
    sens = tentar("Sensibilidades", lambda: M.sensibilidades(d, a, D.mascara, n_boot=0))
    tipo = tentar("Por tipo", lambda: M.por_tipo(a))
    dim = tentar("Por dimensão", lambda: M.por_dimensao(a))
    sub = tentar("Por subgrupo", lambda: M.por_subgrupo(a))
    dose = tentar("Dose-resposta", lambda: M.dose_resposta(a))
    custo = tentar("Custo", lambda: M.custo(D.analise(d, incluir_ruins=True), a, primario))
    e3_res = None
    if getattr(args, "notas", None):
        from . import e3 as E

        e3_res = tentar("E3", lambda: E.e3(d, a, E.ler_notas(args.notas), semente=semente, n_boot=1000))
    h1 = None
    if args.auditoria and os.path.exists(args.auditoria):
        with open(args.auditoria, encoding="utf-8") as f:
            h1 = json.load(f)
    if primario.get("avisos"):
        avisos.append("Modelo primário: " + primario["avisos"])
    if primario["estado"] != "ok":
        avisos.append(f"Modelo primário {primario['estado']}" + (": as estimativas não merecem confiança." if "did" in primario else "."))
    if args.auditoria and h1 is None:
        avisos.append(f"Arquivo de auditoria não encontrado: {args.auditoria}")
    figs: dict[str, Optional[str]] = {}
    if F.disponivel():
        figs["celulas"] = tentar("Figura das células", lambda: F.celulas(taxas, pasta))
        figs["forest"] = tentar("Figura da DiD", lambda: F.forest(sens, tipo, sub, pasta))
    else:
        avisos.append("matplotlib não instalado: figuras não geradas (pip install matplotlib).")

    texto += R.secao_celulas(D.tabela_celulas(a), a.loc[a["variante"] == 1, "tipo"].value_counts(), a["deck_name"].value_counts())
    texto += R.secao_primaria(primario, classe or "", minimos, taxas, coef)
    if figs.get("celulas"):
        texto += [f"![Falha por estrato e braço]({figs['celulas']})", ""]
    if verdade is not None and "did" in primario:
        dentro = primario["did_lo"] <= verdade["did"] <= primario["did_hi"]
        texto += ["## Conferência com o efeito verdadeiro (só nos dados sintéticos)", "", f"DiD verdadeira {R.num(verdade['did'], 1, True)} pp (suspeitos {R.num(verdade['delta_susp'], 1, True)}, controles {R.num(verdade['delta_ctrl'], 1, True)}); estimada {R.num(primario['did'], 1, True)} pp; o IC 95% {'contém' if dentro else 'NÃO contém'} o valor verdadeiro.", ""]
    if escalas is not None:
        texto += R.secao_escalas(escalas)
    if sens is not None:
        texto += R.secao_sensibilidade(sens)
    if tipo is not None and sub is not None:
        texto += R.secao_exploratorias(tipo, dim, sub, dose)
    if figs.get("forest"):
        texto += [f"![DiD com IC 95%]({figs['forest']})", ""]
    if custo is not None:
        texto += R.secao_custo(custo)
    texto += R.secao_e3(e3_res, bool(getattr(args, "notas", None)))
    texto += R.secao_h1(h1)
    texto += R.secao_verificacoes(D.verificacoes(d, a, D.reproduzir_sorteios(d), D.reproduzir_variantes(d, args.banco) if getattr(args, "banco", None) else None))
    texto += R.secao_balanco(D.balanco(a))
    texto += R.secao_avisos(avisos)

    caminho = R.gravar(pasta, "relatorio.md", "\n".join(texto))
    for nome, t in (("fluxo", flx), ("taxas_celulas", taxas), ("escalas", escalas), ("sensibilidades", sens), ("por_tipo", tipo), ("por_dimensao", dim), ("por_subgrupo", sub), ("dose_resposta", dose[1] if dose else None), ("coeficientes_primario", coef)):
        if t is not None:
            R.gravar_tabela(pasta, nome, t)
    R.gravar_json(pasta, "resultados.json", {"modo": modo, "codigo": info_codigo(), "minimos": minimos, "primario": primario, "classe_8_1": classe, "custo": custo, "h1": h1, "e3": e3_res, "dose": dose[0] if dose else None, "verdade": verdade, "avisos": avisos})

    print(flx.to_string(index=False))
    if "did" in primario:
        print(f"\nDiD = {primario['did']:+.1f} pp (IC 95%: {primario['did_lo']:.1f} a {primario['did_hi']:.1f}); classe 8.1: {classe}")
        if primario["estado"] != "ok":
            print(f"ATENÇÃO: modelo primário {primario['estado']}")
        if verdade is not None:
            print(f"Verdade: {verdade['did']:+.1f} pp")
    else:
        print(f"\nDiD não estimada: {primario['estado']}")
    if modo == "cego":
        print("(teste cego: os números não dizem nada sobre o estudo)")
    for a_ in avisos:
        print("AVISO:", a_)
    print(f"Relatório: {caminho}")
    return 0


def rodar_final(args: argparse.Namespace) -> int:
    perfil = _perfil(args)
    df = D.ler_csv(args.csv)
    n_validos = len(D.validos(D.preparar(df, perfil, args.fuso)))
    try:
        olhada = checar_trava(n_validos, hoje(), args.olhada_intermediaria)
    except Recusa as e:
        print(str(e), file=sys.stderr)
        return 2
    if olhada:
        os.makedirs(args.saida, exist_ok=True)
        with open(os.path.join(args.saida, "olhadas.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\tcsv={os.path.basename(args.csv)} sha256={sha256_arquivo(args.csv)[:16]}\tvalidos={n_validos}\tmotivo={olhada}\n")
    return rodar_analise(args, "final", df, perfil, caminho_csv=args.csv, olhada=olhada)


def rodar_cego(args: argparse.Namespace) -> int:
    perfil = _perfil(args)
    return rodar_analise(args, "cego", D.ler_csv(args.csv), perfil, caminho_csv=args.csv)


def rodar_sintetico(args: argparse.Namespace) -> int:
    from . import synthetic as S

    df, verdade = S.simular(args.n, efeito_susp_pp=args.efeito_susp, efeito_ctrl_pp=args.efeito_ctrl, semente=args.semente)
    pasta = os.path.join(args.saida, "sintetico")
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, "eventos_sinteticos.csv")
    S.gravar_csv(df, caminho)
    args.auditoria = None
    args.notas = os.path.join(pasta, "notas_sinteticas.jsonl")
    S.gravar_notas(df, args.notas, args.semente)
    return rodar_analise(args, "sintetico", D.ler_csv(caminho), S.PERFIL_TESTE, caminho_csv=caminho, verdade=verdade)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dfc_analysis", description="Análise do estudo DFC (protocolo v1.7, seções 7 e 8).")
    sub = p.add_subparsers(dest="modo", required=True)

    def comum(sp: argparse.ArgumentParser, csv: bool = True) -> None:
        if csv:
            sp.add_argument("--csv", required=True, help="CSV de Ferramentas > DFC Probe > Exportar eventos")
            sp.add_argument("--perfil", help=f"nome do perfil de estudo (ou variável {P.PERFIL_ENV})")
            sp.add_argument("--banco", help="variant_bank.json: também refaz a variante sorteada de cada evento")
        sp.add_argument("--fuso", default=P.FUSO, help="fuso da data local da janela")
        sp.add_argument("--saida", default=os.path.join("data", "analise"))

    m = sub.add_parser("monitor", help="contagem, fluxo, integridade e ritmo; não calcula desfecho por braço")
    comum(m)
    c = sub.add_parser("cego", help="embaralha braço e tipo entre os eventos sorteados e roda a análise (teste do roteiro)")
    comum(c)
    c.add_argument("--auditoria", default=os.path.join("data", "audit_report.json"))
    c.add_argument("--notas", help="texto exportado das notas (1_notas_exportadas_*.jsonl): liga o E3")
    c.add_argument("--semente", type=int, default=1)
    c.add_argument("--bootstrap", type=int, default=200)
    f = sub.add_parser("final", help="análise pré-registrada; só roda no fim da coleta (22/11 ou ≈ 1000 eventos válidos)")
    comum(f)
    f.add_argument("--auditoria", default=os.path.join("data", "audit_report.json"))
    f.add_argument("--notas", help="texto exportado das notas (1_notas_exportadas_*.jsonl): liga o E3")
    f.add_argument("--semente", type=int, default=20261122)
    f.add_argument("--bootstrap", type=int, default=2000)
    f.add_argument("--olhada-intermediaria", metavar="MOTIVO", help="olhar o desfecho antes do fim da coleta (fica registrado em olhadas.log e no relatório)")
    s = sub.add_parser("sintetico", help="gera dados com efeito conhecido e confere o roteiro")
    comum(s, csv=False)
    s.add_argument("--n", type=int, default=1000)
    s.add_argument("--efeito-susp", type=float, default=15.0, help="efeito da variante nos suspeitos, em pp")
    s.add_argument("--efeito-ctrl", type=float, default=3.0, help="efeito da variante nos controles, em pp")
    s.add_argument("--semente", type=int, default=1)
    s.add_argument("--bootstrap", type=int, default=200)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    args = _parser().parse_args(argv)
    return {"monitor": rodar_monitor, "cego": rodar_cego, "final": rodar_final, "sintetico": rodar_sintetico}[args.modo](args)
