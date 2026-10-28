"""Relatório em Markdown e tabelas em CSV e JSON."""
from __future__ import annotations

import json
import math
import os
from typing import Any, Callable, Optional, Sequence

import numpy as np
import pandas as pd

from . import prereg as P
from . import models as M


def num(x: Any, casas: int = 1, sinal: bool = False) -> str:
    if x is None or (isinstance(x, (float, np.floating)) and not math.isfinite(float(x))):
        return "-"
    return (f"{x:+.{casas}f}" if sinal else f"{x:.{casas}f}").replace(".", ",")


def pct(x: Any, casas: int = 1) -> str:
    return "-" if x is None or not math.isfinite(float(x)) else num(100 * float(x), casas) + "%"


def ic(lo: Any, hi: Any, casas: int = 1) -> str:
    return f"{num(lo, casas)} a {num(hi, casas)}"


def tabela(df: pd.DataFrame, colunas: Sequence[tuple[str, str, Callable[[Any], str]]]) -> list[str]:
    """Tabela Markdown: `colunas` = (coluna do DataFrame, cabeçalho, formatador)."""
    linhas = ["| " + " | ".join(c[1] for c in colunas) + " |", "|" + "|".join("---" for _ in colunas) + "|"]
    for _, r in df.iterrows():
        linhas.append("| " + " | ".join(fmt(r[col]) if col in r.index else "-" for col, _, fmt in colunas) + " |")
    return linhas + [""]


def _txt(x: Any) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else str(x)


def _int(x: Any) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else str(int(x))


def cabecalho(modo: str, info: dict[str, Any]) -> list[str]:
    titulo = {"monitor": "monitoramento", "cego": "teste cego (rótulos embaralhados)", "final": "análise final", "sintetico": "teste com dados sintéticos"}[modo]
    out = [f"# Análise DFC: {titulo}", ""]
    avisos = {
        "monitor": "Monitoramento (protocolo 6.8 e 8, linha 5): só contagem e qualidade. Nenhum desfecho por braço é calculado.",
        "cego": "**TESTE CEGO.** Os rótulos de braço e de tipo foram embaralhados ao acaso entre os eventos sorteados. Todo número de efeito abaixo vem de dados com o efeito destruído e serve só para provar que o roteiro roda; não diz nada sobre o estudo.",
        "final": "Análise pré-registrada (protocolo 7 e 8).",
        "sintetico": "**DADOS SINTÉTICOS** com efeito conhecido: teste do roteiro, sem relação com o estudo.",
    }
    out += [avisos[modo], ""]
    if info.get("olhada"):
        out += [f"> **OLHADA INTERMEDIÁRIA, não é a análise pré-registrada.** Motivo informado: {info['olhada']}. Registrada em `olhadas.log` (anotar também em `docs/desvios.md`).", ""]
    out += ["| Item | Valor |", "|---|---|"]
    for k, v in info.get("meta", {}).items():
        out.append(f"| {k} | {v} |")
    return out + [""]


def secao_fluxo(flx: pd.DataFrame) -> list[str]:
    return ["## Fluxo dos eventos", "", "Cada passo vale para o que sobrou do anterior (protocolo, seções 5 e 8).", ""] + tabela(flx, [("passo", "Passo", _txt), ("restam", "Restam", _int), ("saem", "Saem", _int)])


def secao_celulas(cel: pd.DataFrame, por_tipo: pd.Series, por_baralho: pd.Series) -> list[str]:
    out = ["## Eventos da análise por célula", ""]
    t = cel.reset_index().rename(columns={cel.index.name or "index": "estrato"})
    t.columns = ["estrato", "original", "variante", "total"]
    out += tabela(t, [("estrato", "Estrato", _txt), ("original", "Original", _int), ("variante", "Variante", _int), ("total", "Total", _int)])
    out += ["Variantes por tipo: " + (", ".join(f"{k} {v}" for k, v in por_tipo.items()) or "nenhuma"), ""]
    out += ["Eventos por baralho: " + (", ".join(f"{k} {v}" for k, v in por_baralho.items()) or "nenhum"), ""]
    return out


def secao_verificacoes(v: list[dict[str, str]]) -> list[str]:
    return ["## Qualidade e integridade", ""] + tabela(pd.DataFrame(v), [("item", "Conferência", _txt), ("status", "Resultado", _txt), ("detalhe", "Detalhe", _txt)])


def secao_balanco(b: pd.DataFrame) -> list[str]:
    out = ["## Equilíbrio das covariáveis entre os braços", "", "Só covariáveis (nunca o desfecho). O sorteio é 50/50 por exposição, então as diferenças padronizadas devem ficar perto de 0. O limite é o tamanho que o acaso produz em 95% dos sorteios com estes números de eventos; com seis covariáveis, uma ou outra passar do limite é esperada.", ""]
    b = b.copy()
    b["fora"] = np.where(b["dif_padronizada"].abs() > b["limite"], "acima do limite", "dentro")
    return out + tabela(b, [("covariavel", "Covariável", _txt), ("media_original", "Média no original", lambda x: num(x, 2)), ("media_variante", "Média na variante", lambda x: num(x, 2)), ("dif_padronizada", "Dif. padronizada", lambda x: num(x, 2, True)), ("limite", "Limite (95%)", lambda x: num(x, 2)), ("fora", "Situação", _txt)])


def secao_ritmo(por_dia: pd.DataFrame, info: dict[str, Any], prec: list[dict[str, Any]], taxa: Optional[float]) -> list[str]:
    out = ["## Ritmo e projeção", ""]
    out.append(f"Eventos válidos: **{info['n']}** em {info['dias_com_evento']} dia(s) com revisão (alvo de parada: {P.ALVO_EVENTOS} ou 22/11, o que vier primeiro).")
    if "ritmo_7d" in info:
        out.append(f"Ritmo dos últimos 7 dias do calendário: {num(info['ritmo_7d'], 1)} eventos por dia; projeção para 22/11: ≈ {info['projecao_fim']}.")
        if info.get("dias_ate_alvo") is not None:
            out.append(f"No ritmo atual, o alvo de {P.ALVO_EVENTOS} chega em ≈ {info['dias_ate_alvo']} dia(s) ({info.get('data_alvo', '-')}); ritmo de uma amostra curta varia muito (o Enem é em 8 e 15/11).")
    out.append("")
    if len(por_dia):
        t = por_dia.copy()
        t["dia"] = t["data_local"].dt.strftime("%d/%m")
        out += tabela(t, [("dia", "Dia", _txt), ("validos", "Válidos", _int), ("acumulado", "Acumulado", _int)])
    if prec:
        out += [f"Precisão prevista da DiD, só com os tamanhos das células e a taxa global de falha ({pct(taxa)} em todos os eventos, sem separar por braço; sem agrupamento, então o real é um pouco pior):", ""]
        out += tabela(pd.DataFrame(prec), [("rotulo", "Cenário", _txt), ("n", "Eventos", _int), ("ep_pp", "Erro-padrão (pp)", lambda x: num(x, 1)), ("mde_pp", "Menor efeito detectável (pp)", lambda x: num(x, 1))])
    return out


def secao_primaria(res: dict[str, Any], classe: str, minimos: dict[str, Any], taxas: pd.DataFrame, coef: Optional[pd.DataFrame]) -> list[str]:
    out = ["## H2: diferença de diferenças (análise primária)", ""]
    if "did" not in res:
        return out + [f"Não estimada: {res['estado']}.", ""]
    if res["estado"] != "ok":
        out += [f"> **ATENÇÃO: ajuste {res['estado']}.** As estimativas abaixo não merecem confiança; ver Avisos.", ""]
    out.append(f"Eventos válidos na análise: **{res['n']}** em {res['n_notas']} notas ({minimos['suspeitos']} de suspeitos e {minimos['controles']} de controles).")
    if not minimos["ok"]:
        out.append(f"**Abaixo do mínimo pré-registrado** (300 eventos e 100 por estrato, seção 8, linha 4): o que segue é descritivo e a tabela 8.1 não se aplica (seção 12).")
    out += ["", f"**DiD = {num(res['did'], 1, True)} pp** (IC 95%: {ic(res['did_lo'], res['did_hi'])}); erro-padrão {num(res['did_ep'], 2)} pp. Limiar de relevância: {num(P.LIMIAR_PP, 0)} pp.", ""]
    if minimos["ok"]:
        out += [f"**Conclusão (seção 8.1): {classe}.** {M.TEXTO_H2[classe]}", ""]
    mde = M.menor_efeito_detectavel(res["did_ep"])
    out += [f"Menor DiD detectável com esta amostra (α = 0,05 bilateral, poder 80%): {num(mde, 1)} pp.", ""]
    est = pd.DataFrame([
        {"estrato": "suspeito", "n_original": res["n_susp_orig"], "n_variante": res["n_susp_var"], "efeito": res["delta_susp"], "lo": res["delta_susp_lo"], "hi": res["delta_susp_hi"]},
        {"estrato": "controle", "n_original": res["n_ctrl_orig"], "n_variante": res["n_ctrl_var"], "efeito": res["delta_ctrl"], "lo": res["delta_ctrl_lo"], "hi": res["delta_ctrl_hi"]},
    ])
    t = est.merge(taxas.pivot(index="estrato", columns="braco", values="taxa").reset_index(), on="estrato")
    out += ["Efeito da variante (queda de acerto = aumento de falha, em pp; efeito marginal médio do modelo) e falha observada em cada célula:", ""]
    out += tabela(t, [("estrato", "Estrato", _txt), ("n_original", "N original", _int), ("n_variante", "N variante", _int), ("original", "Falha no original", pct), ("variante", "Falha na variante", pct), ("efeito", "Efeito da variante (pp)", lambda x: num(x, 1, True)), ("lo", "IC 95% inf.", lambda x: num(x, 1)), ("hi", "IC 95% sup.", lambda x: num(x, 1))])
    if "did_boot_lo" in res:
        cb = M.classificar_h2(res["did"], res["did_boot_lo"], res["did_boot_hi"])
        out += [f"Conferência por bootstrap de notas ({res['boot_validas']} réplicas válidas, {res['boot_falhas']} descartadas): IC 95% {ic(res['did_boot_lo'], res['did_boot_hi'])}; classe 8.1 com este IC: {cb}" + (" (igual à do método delta)." if cb == classe else " (**difere** da do método delta)."), ""]
    out += [f"Razão de chances da interação variante × suspeito: {num(res['or_inter'], 2)} (IC 95%: {ic(res['or_lo'], res['or_hi'], 2)}; p = {num(res['p_inter'], 3)}).", ""]
    if res.get("avisos"):
        out += [f"Avisos do ajuste: {res['avisos']}", ""]
    if coef is not None:
        out += ["<details><summary>Coeficientes do modelo (logit; erro-padrão robusto por nota)</summary>", ""]
        out += tabela(coef, [("termo", "Termo", _txt), ("coef", "Coef.", lambda x: num(x, 3)), ("ep", "EP", lambda x: num(x, 3)), ("razao", "Razão de chances", lambda x: num(x, 2)), ("p", "p", lambda x: num(x, 3))])
        out += ["</details>", ""]
    return out


def secao_escalas(df: pd.DataFrame) -> list[str]:
    out = ["## Efeito de escala (seção 7)", "", "A mesma interação variante × suspeito em outras escalas e com a falha anterior do cartão (`last_ease`, `prev_eases`) como covariável. Se a variante é mais fácil (ou mais difícil) para todos, a DiD em pp deixa de ser 0 sem dependência da forma; por isso a conclusão precisa sobreviver às outras escalas.", ""]
    if not len(df):
        return out + ["Não estimado.", ""]
    out += tabela(df, [("escala", "Escala", _txt), ("covariaveis", "Covariáveis", _txt), ("estimativa", "Estimativa", lambda x: num(x, 2)), ("lo", "IC 95% inf.", lambda x: num(x, 2)), ("hi", "IC 95% sup.", lambda x: num(x, 2)), ("leitura", "Leitura", _txt), ("estado", "Estado", _txt)])
    leituras = set(df.loc[df["leitura"] != "sem IC", "leitura"])
    if len(leituras) <= 1:
        out += ["A leitura é a mesma em todas as escalas com IC." if leituras else "Nenhuma escala teve IC confiável.", ""]
    else:
        out += ["**A leitura muda de uma escala para outra** (ver a coluna Leitura): a conclusão de H2 depende da escala e deve ser relatada assim.", ""]
    return out


def secao_sensibilidade(df: pd.DataFrame) -> list[str]:
    out = ["## Sensibilidades", "", "DiD em pp refeita com cada alteração. A coluna Classe aplica a tabela 8.1 ao IC de cada linha, só para comparar com a principal.", ""]
    return out + tabela(df, [("rotulo", "Análise", _txt), ("n", "Eventos", _int), ("did", "DiD (pp)", lambda x: num(x, 1, True)), ("did_lo", "IC 95% inf.", lambda x: num(x, 1)), ("did_hi", "IC 95% sup.", lambda x: num(x, 1)), ("classe", "Classe", _txt), ("estado", "Estado", _txt)])


def secao_exploratorias(tipo: pd.DataFrame, dim: Optional[pd.DataFrame], sub: pd.DataFrame, dose: Optional[tuple[dict[str, Any], pd.DataFrame]]) -> list[str]:
    out = ["## Análises exploratórias", "", "Rotuladas como exploratórias (seção 7, multiplicidade): com ≈ 100 eventos de variante por tipo só aparecem efeitos grandes, e a estimativa primária é a média sobre os tipos. As linhas por tipo usam os mesmos eventos originais e não são independentes.", ""]
    cols = [("rotulo", "Recorte", _txt), ("n", "Eventos", _int), ("n_susp_var", "Variantes em suspeitos", _int), ("n_ctrl_var", "Variantes em controles", _int), ("did", "DiD (pp)", lambda x: num(x, 1, True)), ("did_lo", "IC 95% inf.", lambda x: num(x, 1)), ("did_hi", "IC 95% sup.", lambda x: num(x, 1)), ("estado", "Estado", _txt)]
    out += ["### Por tipo de variante", ""] + tabela(tipo, [("dimensao", "Dimensão", _txt)] + cols)
    if dim is not None:
        out += ["### Por dimensão", ""] + tabela(dim, cols)
    else:
        out += ["Cada dimensão tem um só tipo neste banco: a tabela por dimensão repete a anterior (palavras = `paraphrase`, ordem = `reorder`, palavras iniciais = `cue_swap`, formato = `pergunta`, imagem = `sem_imagem`).", ""]
    out += ["### Por número de lacunas e por imagem", ""] + tabela(sub, cols)
    if dose is not None:
        por_dobro, faixas = dose
        out += ["### Dose-resposta: variante × `reps`", "", f"Razão de chances da interação variante × log(`reps`) por dobro de `reps`: {num(por_dobro['razao'], 2)} (IC 95%: {ic(por_dobro['lo'], por_dobro['hi'], 2)}; p = {num(por_dobro['p'], 3)}). Acima de 1: a variante pesa mais em cartões com mais repetições.", ""]
        out += tabela(faixas, [("faixa_reps", "`reps`", _txt), ("n", "Eventos", _int), ("n_variante", "Variante", _int), ("n_original", "Original", _int), ("efeito_pp", "Efeito da variante (pp)", lambda x: num(x, 1, True)), ("lo", "IC 95% inf.", lambda x: num(x, 1)), ("hi", "IC 95% sup.", lambda x: num(x, 1))])
    return out


def secao_custo(c: dict[str, Any]) -> list[str]:
    out = ["## Custo (H5, descritivo)", "", "Sem decisão confirmatória (seção 8, linha 7)."]
    out.append("")
    if "falha_controle_pp" in c:
        lo, hi = c["falha_controle_ic"]
        out.append(f"- Falha nas variantes dos controles acima do original: {num(c['falha_controle_pp'], 1, True)} pp (IC 95%: {ic(lo, hi)}); referência: até {num(P.H5_FALHA_CONTROLE_PP, 0)} pp ({'dentro' if c['falha_controle_ok'] else 'fora'}).")
        lo, hi = c["falhas_extras_ic"]
        out.append(f"- Falhas extras por 100 exposições a variantes (todos os eventos): {num(c['falhas_extras_por_100_variantes'], 1, True)} (IC 95%: {ic(lo, hi)}).")
    if c["variantes_exibidas"]:
        out.append(f"- Variantes marcadas como ruins: {c['variante_ruim']} de {c['variantes_exibidas']} exibidas ({pct(c['variante_ruim_pct'])}); referência: até {pct(P.H5_VARIANTE_RUIM, 0)} ({'dentro' if c['variante_ruim_ok'] else 'fora'}).")
    if "tempo_extra_s" in c:
        lo, hi = c["tempo_extra_ic"]
        out.append(f"- Tempo total por exposição (truncado no percentil {P.TEMPO_PERCENTIL}, {num(c['tempo_teto_s'], 0)} s): mediana {num(c['tempo_mediana_original_s'], 1)} s no original e {num(c['tempo_mediana_variante_s'], 1)} s na variante; diferença ajustada {num(c['tempo_extra_s'], 1, True)} s (IC 95%: {ic(lo, hi)}), ≈ {num(c['tempo_extra_total_min'], 0)} min a mais no total das {int(c['variantes_exibidas'])} exposições a variantes.")
    return out + [""]


def secao_e3(res: Optional[dict[str, Any]], pedida: bool) -> list[str]:
    out = ["## E3: sinais de candidato (exploratória)", ""]
    if not pedida:
        return out + ["Não rodada: informe o texto exportado das notas com `--notas` (protocolo 6.3.1).", ""]
    if res is None:
        return out + ["Falhou (ver Avisos).", ""]
    if res.get("estado") != "ok":
        return out + [f"Não estimada: {res.get('estado')}.", ""]
    out.append(f"Eventos do braço variante com texto e tempo: **{res['n']}** ({res['falhas']} falhas; {res.get('sem_texto_ou_tempo', 0)} ficaram de fora por falta de texto ou de tempo). Tempo até revelar padronizado por {res['referencia_tempo']} exposições do original ou sem sorteio.")
    out += ["", f"AUC por validação cruzada em blocos de notas (média de repetições; IC 95% por bootstrap de notas, {res['boot_validas']} réplicas):", ""]
    out += [f"- Escore com todos os sinais: **{num(res['auc_escore'], 2)}** (IC {ic(*res['auc_escore_ic'], casas=2)}).",
            f"- Baseline só com `reps`: {num(res['auc_baseline'], 2)} (IC {ic(*res['auc_baseline_ic'], casas=2)}).",
            f"- Diferença (escore - baseline): {num(res['dif'], 2, True)} (IC {ic(*res['dif_ic'], casas=2)}).", ""]
    out += ["AUC de cada sinal sozinho (sem ajuste; abaixo de 0,5 quer dizer que valores maiores acompanham mais acerto):", ""]
    out += tabela(res["sinais"], [("sinal", "Sinal", _txt), ("auc", "AUC", lambda x: num(x, 2)), ("lo", "IC 95% inf.", lambda x: num(x, 2)), ("hi", "IC 95% sup.", lambda x: num(x, 2))])
    out += ["Associação exploratória, sem limiar de decisão: o tempo até revelar é da mesma exposição da resposta, e com poucas falhas só aparecem sinais grandes (protocolo 6.3.1).", ""]
    return out


def secao_h1(a: Optional[dict[str, Any]]) -> list[str]:
    out = ["## H1: validade das variantes (auditoria do autor)", ""]
    if a is None:
        return out + ["`audit_report.json` não informado.", ""]
    lo, hi = a["ic95_wilson"]
    out.append(f"{a['validas']} de {a['auditadas']} variantes auditadas válidas ({pct(a['taxa'])}; IC 95% de Wilson {pct(lo)} a {pct(hi)}); limiar {pct(a['h1_limiar'], 0)}: {'atendido' if a.get('h1_ok') else 'não atendido'}.")
    if isinstance(a.get("por_tipo"), dict):
        out += ["", "Por tipo: " + ", ".join(f"{k} {v.get('validas', '?')}/{v.get('auditadas', v.get('n', '?'))}" if isinstance(v, dict) else f"{k} {v}" for k, v in a["por_tipo"].items())]
    return out + [""]


def secao_avisos(avisos: list[str]) -> list[str]:
    return ["## Avisos", ""] + ([f"- {a}" for a in avisos] if avisos else ["Nenhum."]) + [""]


def json_seguro(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): json_seguro(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_seguro(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, pd.DataFrame):
        return json_seguro(x.to_dict(orient="records"))
    if isinstance(x, pd.Timestamp):
        return x.date().isoformat()
    return x


def gravar(pasta: str, nome: str, texto: str) -> str:
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return caminho


def gravar_tabela(pasta: str, nome: str, df: pd.DataFrame) -> None:
    os.makedirs(os.path.join(pasta, "tabelas"), exist_ok=True)
    df.to_csv(os.path.join(pasta, "tabelas", nome + ".csv"), index=False, encoding="utf-8")


def gravar_json(pasta: str, nome: str, obj: Any) -> None:
    gravar(pasta, nome, json.dumps(json_seguro(obj), ensure_ascii=False, indent=2))
