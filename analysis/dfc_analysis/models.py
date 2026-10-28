"""Modelos da análise pré-registrada (protocolo, seção 7).

Primária: logística `falha ~ variante x suspeito + log(intervalo) + log(dias desde a última revisão) + tipo + n_blanks + has_image`
com erro-padrão robusto agrupado por nota; a estimativa reportada é a DiD em pontos percentuais (efeitos marginais médios: para cada
estrato, a média sobre os eventos de p(variante) - p(original), com a variante na proporção de tipos sorteados) e o IC 95% sai do
método delta com a covariância robusta. As demais funções repetem a estimativa em outras escalas, subconjuntos e recortes.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from scipy.special import expit

from . import prereg as P

Z_IC = float(stats.norm.ppf(0.5 + P.NIVEL_IC / 2))
Z_PODER = float(stats.norm.ppf(P.PODER))
COV_BASE = ["log_ivl", "log_dias", "n_blanks", "has_image"]
COV_FALHA_ANTERIOR = ["n_falhas_prev3", "ult_falha"]


@dataclass
class Ajuste:
    params: pd.Series
    cov: pd.DataFrame
    convergiu: bool
    avisos: list[str]


def _ajustar(y: np.ndarray, X: pd.DataFrame, grupos: np.ndarray, familia: str = "logit", robusto: bool = True) -> Ajuste:
    """Logística (`logit`), Poisson com ligação log (`poisson`, razão de risco) ou mínimos quadrados (`ols`), com erro-padrão agrupado por nota."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        if familia == "ols":
            modelo = sm.OLS(y, X)
        else:
            modelo = sm.GLM(y, X, family={"logit": sm.families.Binomial(), "poisson": sm.families.Poisson()}[familia])
        res = modelo.fit(cov_type="cluster", cov_kwds={"groups": grupos}) if robusto else modelo.fit()
    avisos = sorted({f"{x.category.__name__}: {x.message}" for x in w if not issubclass(x.category, (FutureWarning, DeprecationWarning))})
    return Ajuste(res.params, res.cov_params(), bool(getattr(res, "converged", True)), avisos)


def montar_X(d: pd.DataFrame, mod: str, cov: Sequence[str], tipos: Sequence[str], v: Optional[np.ndarray] = None, tipo: Optional[str] = None) -> pd.DataFrame:
    """Matriz do modelo: constante, variante, modificador (estrato ou dose), interação, covariáveis e, se há mais de um tipo, o tipo de variante em codificação de desvio (soma zero), que fica em 0 no braço original. Com `v` e `tipo` monta o contrafactual."""
    n = len(d)
    v_ = d["variante"].to_numpy(float) if v is None else v
    m = d[mod].to_numpy(float)
    X: dict[str, np.ndarray] = {"const": np.ones(n), "variante": v_, mod: m, f"variante:{mod}": v_ * m}
    for c in cov:
        X[c] = d[c].to_numpy(float) - float(d[c].mean())  # covariáveis centradas: a constante fica no nível típico e o ajuste fica estável; os efeitos marginais não mudam
    if len(tipos) > 1:
        tp = np.where(v_ == 1, d["tipo"].to_numpy() if tipo is None else np.full(n, tipo), "original")
        for t in tipos[:-1]:
            X[f"tipo[{t}]"] = (tp == t).astype(float) - (tp == tipos[-1]).astype(float)
    return pd.DataFrame(X, index=d.index)


def independentes(d: pd.DataFrame, mod: str, cov: Sequence[str], tipos: Sequence[str]) -> tuple[list[str], list[str]]:
    """Separa as covariáveis que acrescentam informação das que são constantes ou combinação exata de colunas já no modelo (por exemplo, `ult_falha` igual a `n_falhas_prev3` numa amostra pequena), que deixariam a matriz singular."""
    base = montar_X(d, mod, [], tipos).to_numpy(float)
    posto = np.linalg.matrix_rank(base)
    ficam, saem = [], []
    for c in cov:
        col = d[c].to_numpy(float)
        if d[c].nunique() > 1:
            cand = np.column_stack([base, col - col.mean()])
            if np.linalg.matrix_rank(cand) > posto:
                base, posto = cand, posto + 1
                ficam.append(c)
                continue
        saem.append(c)
    return ficam, saem


def jacobiano(f, beta: np.ndarray, h: float = 1e-5) -> np.ndarray:
    colunas = []
    for j in range(len(beta)):
        passo = np.zeros_like(beta)
        passo[j] = h * max(1.0, abs(beta[j]))
        colunas.append((f(beta + passo) - f(beta - passo)) / (2 * passo[j]))
    return np.column_stack(colunas)


class ModeloEfeito:
    """Logística com variante x modificador e efeitos marginais médios, em pontos percentuais, por grupo de eventos (`mascaras`)."""

    def __init__(self, d: pd.DataFrame, mod: str, cov: Sequence[str], mascaras: dict[str, np.ndarray], tipos: Any = "auto"):
        if not (d["variante"] == 1).any() or not (d["variante"] == 0).any():
            raise ValueError("falta um dos braços")
        self.mod, self.mascaras = mod, mascaras
        var = d["variante"].to_numpy() == 1
        if tipos == "nenhum":  # recortes pequenos: sem o tipo de variante no modelo
            self.tipos, self.pesos = ["*"], {"*": 1.0}
        else:
            self.tipos = sorted(d.loc[var, "tipo"].unique()) if tipos == "auto" else list(tipos)
            freq = d.loc[var, "tipo"].value_counts(normalize=True)
            self.pesos = {t: float(freq.get(t, 0.0)) for t in self.tipos}
        n = len(d)
        self.cov, self.cov_fora = independentes(d, mod, cov, self.tipos)  # covariável constante ou colinear no recorte deixaria a matriz singular
        self.X = montar_X(d, mod, self.cov, self.tipos)
        self.X0 = montar_X(d, mod, self.cov, self.tipos, v=np.zeros(n)).to_numpy(float)
        self.X1 = {t: montar_X(d, mod, self.cov, self.tipos, v=np.ones(n), tipo=t).to_numpy(float) for t in self.tipos}
        self.y = d["falha"].to_numpy(float)
        self.grupos = pd.factorize(d["nota"])[0]

    def ajustar(self, familia: str = "logit", robusto: bool = True) -> Ajuste:
        return _ajustar(self.y, self.X, self.grupos, familia, robusto)

    def beta(self, aj: Ajuste) -> np.ndarray:
        return aj.params[list(self.X.columns)].to_numpy(float)

    def efeitos(self, beta: np.ndarray) -> np.ndarray:
        p0 = expit(self.X0 @ beta)
        p1 = sum(w * expit(self.X1[t] @ beta) for t, w in self.pesos.items())
        dif = (p1 - p0) * 100.0
        return np.array([dif[m].mean() for m in self.mascaras.values()])

    def com_ep(self, aj: Ajuste) -> tuple[np.ndarray, np.ndarray]:
        """Efeitos marginais e a covariância deles (método delta, com a covariância robusta por nota)."""
        nomes = list(self.X.columns)
        beta = self.beta(aj)
        V = aj.cov.loc[nomes, nomes].to_numpy(float)
        J = jacobiano(self.efeitos, beta)
        return self.efeitos(beta), J @ V @ J.T


def _ic(est: float, ep: float) -> tuple[float, float]:
    return est - Z_IC * ep, est + Z_IC * ep


def _p_wald(est: float, ep: float) -> float:
    return float(2 * stats.norm.sf(abs(est / ep))) if ep and ep > 0 else float("nan")


def tabela_coef(aj: Ajuste, razao: bool = True) -> pd.DataFrame:
    ep = pd.Series(np.sqrt(np.clip(np.diag(aj.cov.to_numpy(float)), 0, None)), index=aj.cov.index)
    t = pd.DataFrame({"coef": aj.params, "ep": ep})
    t["lo"], t["hi"] = t["coef"] - Z_IC * t["ep"], t["coef"] + Z_IC * t["ep"]
    t["p"] = [_p_wald(c, e) for c, e in zip(t["coef"], t["ep"])]
    if razao:
        t["razao"], t["razao_lo"], t["razao_hi"] = np.exp(t["coef"]), np.exp(t["lo"]), np.exp(t["hi"])
    return t.reset_index(names="termo")


def _instavel(aj: Ajuste) -> Optional[str]:
    """Sinais de ajuste que não merece confiança: sem convergência, coeficiente enorme (separação quase completa, comum com poucas falhas) ou variância negativa."""
    if not aj.convergiu:
        return "sem convergência"
    if (np.abs(aj.params.to_numpy(float)) > 10).any():
        return "coeficiente com módulo acima de 10 (possível separação)"
    if (np.diag(aj.cov.to_numpy(float)) < 0).any():
        return "variância negativa"
    return None


def classificar_h2(did: float, lo: float, hi: float, limiar: float = P.LIMIAR_PP) -> str:
    """Tabela da seção 8.1. Estimativa negativa com IC que exclui 0 cai em "efeito pequeno" pela tabela, e vem rotulada com a direção oposta."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "indeterminada"
    if lo > 0:
        return "apoiada" if did >= limiar else "efeito pequeno"
    if hi < 0:
        return "efeito pequeno (direção oposta à hipótese)"
    return "relevante descartado" if hi < limiar else "inconclusivo"


TEXTO_H2 = {
    "apoiada": "H2 apoiada: penalidade relevante maior nos suspeitos (estimativa >= 10 pp e IC 95% exclui 0).",
    "efeito pequeno": "Efeito pequeno: o IC 95% exclui 0, com estimativa abaixo de 10 pp.",
    "efeito pequeno (direção oposta à hipótese)": "Efeito pequeno, mas na direção oposta à hipótese: a variante custa mais aos controles do que aos suspeitos (IC 95% exclui 0).",
    "relevante descartado": "Relevante descartado: o IC 95% inclui 0 e o limite superior fica abaixo de 10 pp (dependência de forma desprezível nesta amostra).",
    "inconclusivo": "Inconclusivo: o IC 95% inclui 0 e o limite superior chega a 10 pp ou mais.",
    "indeterminada": "Indeterminada: o ajuste do modelo está instável e não há IC confiável.",
}


def menor_efeito_detectavel(ep: float) -> float:
    """Menor DiD que a amostra distingue de 0 com α = 0,05 (bilateral) e poder de 80%, dado o erro-padrão observado."""
    return (Z_IC + Z_PODER) * ep


def checar_minimos(a: pd.DataFrame, suspeito: str = "suspeito") -> dict[str, Any]:
    """Seção 8, linha 4: ao menos 300 eventos válidos e 100 por estrato para analisar H2."""
    ns, nc = int((a[suspeito] == 1).sum()), int((a[suspeito] == 0).sum())
    return {"n": int(len(a)), "suspeitos": ns, "controles": nc, "ok": len(a) >= P.MIN_EVENTOS and ns >= P.MIN_POR_ESTRATO and nc >= P.MIN_POR_ESTRATO}


def _contagens(d: pd.DataFrame, s: np.ndarray) -> dict[str, int]:
    v = d["variante"].to_numpy() == 1
    return {"n_susp_orig": int((s & ~v).sum()), "n_susp_var": int((s & v).sum()), "n_ctrl_orig": int((~s & ~v).sum()), "n_ctrl_var": int((~s & v).sum())}


def estimar_did(d: pd.DataFrame, *, rotulo: str, suspeito: str = "suspeito", cov: Optional[Sequence[str]] = None, tipos: Any = "auto", n_boot: int = 0, semente: int = 1) -> tuple[dict[str, Any], Optional[pd.DataFrame]]:
    """DiD em pontos percentuais (logística, efeitos marginais, IC 95% pelo método delta com erro-padrão robusto por nota). Devolve a linha de resultado e a tabela de coeficientes."""
    cov = list(COV_BASE if cov is None else cov)
    d = d.dropna(subset=["falha", suspeito, *cov]).reset_index(drop=True)
    s = d[suspeito].to_numpy() == 1
    linha: dict[str, Any] = {"rotulo": rotulo, "n": int(len(d)), "n_notas": int(d["nota"].nunique()), **_contagens(d, s), "estado": "ok"}
    if min(linha[k] for k in ("n_susp_orig", "n_susp_var", "n_ctrl_orig", "n_ctrl_var")) < P.MIN_CELULA:
        linha["estado"] = f"células com menos de {P.MIN_CELULA} eventos: não estimado"
        return linha, None
    try:
        m = ModeloEfeito(d, suspeito, cov, {"susp": s, "ctrl": ~s, "todos": np.ones(len(d), bool)}, tipos)
        aj = m.ajustar()
        est, V = m.com_ep(aj)
    except (ValueError, np.linalg.LinAlgError) as e:
        linha["estado"] = f"falhou: {e}"
        return linha, None
    did, var_did = est[0] - est[1], V[0, 0] + V[1, 1] - 2 * V[0, 1]
    ep = {"delta_susp": math.sqrt(max(V[0, 0], 0)), "delta_ctrl": math.sqrt(max(V[1, 1], 0)), "did": math.sqrt(max(var_did, 0)), "delta_todos": math.sqrt(max(V[2, 2], 0))}
    for nome, valor in (("delta_susp", est[0]), ("delta_ctrl", est[1]), ("did", did), ("delta_todos", est[2])):
        lo, hi = _ic(valor, ep[nome])
        linha.update({nome: float(valor), f"{nome}_ep": ep[nome], f"{nome}_lo": lo, f"{nome}_hi": hi})
    nome_int = f"variante:{suspeito}"
    coef = tabela_coef(aj)
    c = coef.set_index("termo").loc[nome_int]
    linha.update(or_inter=float(c["razao"]), or_lo=float(c["razao_lo"]), or_hi=float(c["razao_hi"]), p_inter=float(c["p"]))
    linha["convergiu"] = aj.convergiu
    instavel = _instavel(aj)
    if instavel:
        linha["estado"] = f"instável: {instavel}"
        for k in list(linha):
            if k.endswith(("_ep", "_lo", "_hi")):
                linha[k] = float("nan")  # sem confiança no ajuste, não há intervalo
    linha["avisos"] = "; ".join(aj.avisos + ([f"covariável removida (constante ou colinear no recorte): {', '.join(m.cov_fora)}"] if m.cov_fora else []))
    if n_boot:
        bs, falhas = bootstrap_did(d, suspeito, cov, m.tipos, n_boot, semente)
        if len(bs) >= 50:
            linha["did_boot_lo"], linha["did_boot_hi"] = (float(x) for x in np.percentile(bs[:, 2], [100 * (1 - P.NIVEL_IC) / 2, 100 * (1 + P.NIVEL_IC) / 2]))
            linha["did_boot_ep"] = float(np.std(bs[:, 2], ddof=1))
        linha["boot_validas"], linha["boot_falhas"] = int(len(bs)), int(falhas)
    return linha, coef


def bootstrap_did(d: pd.DataFrame, suspeito: str, cov: Sequence[str], tipos: Sequence[str], n_boot: int, semente: int) -> tuple[np.ndarray, int]:
    """Bootstrap por nota (sorteia notas com reposição e reajusta): confere o IC pelo método delta. Devolve [delta_susp, delta_ctrl, DiD] de cada réplica."""
    rng = np.random.default_rng(semente)
    cod, uniq = pd.factorize(d["nota"])
    ordem = np.argsort(cod, kind="stable")
    lim = np.searchsorted(cod[ordem], np.arange(len(uniq) + 1))
    idx = [ordem[lim[g] : lim[g + 1]] for g in range(len(uniq))]
    out, falhas = [], 0
    for _ in range(n_boot):
        ix = np.concatenate([idx[g] for g in rng.integers(0, len(uniq), len(uniq))])
        db = d.iloc[ix].reset_index(drop=True)
        try:
            s = db[suspeito].to_numpy() == 1
            m = ModeloEfeito(db, suspeito, cov, {"susp": s, "ctrl": ~s}, list(tipos))
            aj = m.ajustar(robusto=False)
            if _instavel(aj):
                raise ValueError("ajuste instável")
            e = m.efeitos(m.beta(aj))
            if not np.all(np.isfinite(e)):
                raise ValueError("efeito não finito")
            out.append([e[0], e[1], e[0] - e[1]])
        except (ValueError, np.linalg.LinAlgError, KeyError):
            falhas += 1
    return (np.array(out) if out else np.empty((0, 3))), falhas


def _interacao(d: pd.DataFrame, suspeito: str, cov: Sequence[str], familia: str) -> Optional[tuple[float, float, Optional[str]]]:
    d = d.dropna(subset=["falha", suspeito, *cov]).reset_index(drop=True)
    tipos = sorted(d.loc[d["variante"] == 1, "tipo"].unique())
    cov, _ = independentes(d, suspeito, cov, tipos)
    X = montar_X(d, suspeito, cov, tipos)
    try:
        aj = _ajustar(d["falha"].to_numpy(float), X, pd.factorize(d["nota"])[0], familia)
    except (ValueError, np.linalg.LinAlgError):
        return None
    nome = f"variante:{suspeito}"
    return float(aj.params[nome]), float(math.sqrt(max(aj.cov.loc[nome, nome], 0))), _instavel(aj)


def _leitura(lo: float, hi: float, nulo: float) -> str:
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "sem IC"
    if lo > nulo:
        return "maior nos suspeitos"
    if hi < nulo:
        return "maior nos controles"
    return "IC inclui o nulo"


def escalas(d: pd.DataFrame, *, suspeito: str = "suspeito") -> pd.DataFrame:
    """Seção 7, efeito de escala: a mesma interação em pontos percentuais (efeitos marginais da logística), em razão de chances (logística), em razão de risco (Poisson com erro-padrão robusto) e em diferença de probabilidades (modelo linear), com e sem a falha anterior do cartão."""
    linhas = []
    for nome_cov, cov in (("covariáveis do protocolo", COV_BASE), ("com falha anterior (`last_ease`, `prev_eases`)", COV_BASE + COV_FALHA_ANTERIOR)):
        est, _ = estimar_did(d, rotulo="pp", suspeito=suspeito, cov=cov)
        if "did" in est:
            linhas.append({"escala": "diferença de diferenças, pp (logística)", "covariaveis": nome_cov, "estimativa": est["did"], "lo": est["did_lo"], "hi": est["did_hi"], "nulo": 0.0, "leitura": _leitura(est["did_lo"], est["did_hi"], 0.0), "estado": est["estado"]})
        for rotulo, familia, expo in (("razão de chances da interação (logística)", "logit", True), ("razão de riscos da interação (Poisson robusto)", "poisson", True), ("diferença de diferenças, pp (modelo linear)", "ols", False)):
            r = _interacao(d, suspeito, cov, familia)
            if r is None:
                continue
            b, ep, instavel = r
            lo, hi = b - Z_IC * ep, b + Z_IC * ep
            if instavel:
                lo = hi = float("nan")
            k = (math.exp, 1.0) if expo else (lambda x: 100 * x, 0.0)
            linhas.append({"escala": rotulo, "covariaveis": nome_cov, "estimativa": k[0](b), "lo": k[0](lo), "hi": k[0](hi), "nulo": k[1], "leitura": _leitura(k[0](lo), k[0](hi), k[1]), "estado": f"instável: {instavel}" if instavel else "ok"})
    return pd.DataFrame(linhas)


def _sem_eventos(a: pd.DataFrame, prefixos: Sequence[str]) -> pd.Series:
    saem = pd.Series(False, index=a.index)
    for p in prefixos:
        saem |= a["event_id"].str.startswith(p)
    return saem


def sensibilidades(d: pd.DataFrame, a: pd.DataFrame, mascara_fn, *, n_boot: int = 0, semente: int = 1) -> pd.DataFrame:
    """Seção 7 (sensibilidade) e as três acrescentadas antes do fim da coleta (desvios.md). `d` é o CSV preparado, `a` o conjunto principal e `mascara_fn(d, **kw)` o filtro de evento válido."""
    def com(kw):  # conjunto de eventos com outro filtro de validade
        m = mascara_fn(d, **kw) & d["completo"]
        return d[m]

    casos = [
        ("Principal", a, {}),
        ("Incluir eventos de variante ruim", com({"incluir_ruins": True}), {}),
        ("Incluir respostas desfeitas sem substituta (`revlog_match` = 0)", com({"incluir_desfeitas": True}), {}),
        ("Suspeito com `reps` >= 4", a, {"suspeito": "suspeito_reps4"}),
        ("Suspeito com `n_reviews` >= 5 (em vez de `reps`)", a[a["suspeito_nrev5"].notna()], {"suspeito": "suspeito_nrev5"}),
        ("Só modo regular", a[a["mode"] == "regular"], {}),
        ("Sem as respostas refeitas depois de Ctrl+Z (`after_undo`)", a[a["after_undo"] != 1], {}),
        ("Só `reps` >= 5", a[a["reps"] >= P.SUSPEITO_REPS], {}),
        ("Sem o evento da nota editada (desvios.md, entrada 4)", a[~_sem_eventos(a, list(P.EVENTOS_SENSIBILIDADE))], {}),
    ]
    linhas = []
    for rotulo, dados, kw in casos:
        linha, _ = estimar_did(dados, rotulo=rotulo, n_boot=n_boot, semente=semente, **kw)
        if "did" in linha:
            linha["classe"] = classificar_h2(linha["did"], linha["did_lo"], linha["did_hi"])
        linhas.append(linha)
    return pd.DataFrame(linhas)


def por_tipo(a: pd.DataFrame) -> pd.DataFrame:
    """Exploratória: DiD de cada tipo de variante contra os mesmos eventos originais (que são comuns a todos os tipos, então as linhas não são independentes)."""
    linhas = []
    for t in sorted(a.loc[a["variante"] == 1, "tipo"].unique()):
        linha, _ = estimar_did(a[(a["tipo"] == t) | (a["variante"] == 0)], rotulo=t, tipos=[t])
        linha["dimensao"] = P.DIMENSAO.get(t, t)
        linhas.append(linha)
    return pd.DataFrame(linhas)


def por_dimensao(a: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Só existe se alguma dimensão reúne mais de um tipo (no Cloze, cada tipo é uma dimensão)."""
    tipos = sorted(a.loc[a["variante"] == 1, "tipo"].unique())
    if len({P.DIMENSAO.get(t, t) for t in tipos}) == len(tipos):
        return None
    b = a.copy()
    b["tipo"] = np.where(b["variante"] == 1, b["dimensao"], "original")
    linhas = []
    for t in sorted(b.loc[b["variante"] == 1, "tipo"].unique()):
        linha, _ = estimar_did(b[(b["tipo"] == t) | (b["variante"] == 0)], rotulo=t, tipos=[t])
        linhas.append(linha)
    return pd.DataFrame(linhas)


def por_subgrupo(a: pd.DataFrame) -> pd.DataFrame:
    """Exploratória: DiD por número de lacunas e por presença de imagem (o modelo do recorte não leva a própria covariável)."""
    linhas = []
    for col, nome in (("n_blanks", "lacunas"), ("has_image", "imagem")):
        for nivel in sorted(a[col].dropna().unique()):
            sub = a[a[col] == nivel]
            linha, _ = estimar_did(sub, rotulo=f"{nome} = {int(nivel)}", cov=[c for c in COV_BASE if c != col], tipos="nenhum")
            linhas.append(linha)
    return pd.DataFrame(linhas)


def dose_resposta(a: pd.DataFrame, suspeito: str = "suspeito") -> tuple[dict[str, Any], pd.DataFrame]:
    """Exploratória: o efeito da variante muda com `reps`? Interação variante x log(reps) (razão de chances por dobro de `reps`) e efeito marginal por faixa de `reps`."""
    d = a.dropna(subset=["falha", "log_reps", *COV_BASE]).reset_index(drop=True)
    d["lr"] = d["log_reps"] - d["log_reps"].mean()
    faixa = pd.qcut(d["reps"], P.DOSE_FAIXAS, labels=False, duplicates="drop").to_numpy()
    mascaras = {}
    for i in sorted(np.unique(faixa)):
        r = d.loc[faixa == i, "reps"]
        mascaras[f"{int(r.min())} a {int(r.max())}"] = faixa == i
    m = ModeloEfeito(d, "lr", COV_BASE + [suspeito], mascaras)
    aj = m.ajustar()
    est, V = m.com_ep(aj)
    c = tabela_coef(aj).set_index("termo").loc["variante:lr"]
    por_dobro = {"razao": math.exp(c["coef"] * math.log(2)), "lo": math.exp(c["lo"] * math.log(2)), "hi": math.exp(c["hi"] * math.log(2)), "p": float(c["p"]), "convergiu": aj.convergiu}
    linhas = []
    for i, (nome, masc) in enumerate(mascaras.items()):
        ep = math.sqrt(max(V[i, i], 0))
        v = d["variante"].to_numpy() == 1
        lo, hi = _ic(est[i], ep)
        linhas.append({"faixa_reps": nome, "n": int(masc.sum()), "n_variante": int((masc & v).sum()), "n_original": int((masc & ~v).sum()), "efeito_pp": float(est[i]), "lo": lo, "hi": hi})
    return por_dobro, pd.DataFrame(linhas)


def taxas_celulas(a: pd.DataFrame, suspeito: str = "suspeito") -> pd.DataFrame:
    """Falhas por estrato e braço, com IC de Wilson. Descritiva, só no relatório final (desfecho por braço)."""
    linhas = []
    for estrato, nome_e in ((1.0, "suspeito"), (0.0, "controle")):
        for bra, nome_b in ((0.0, "original"), (1.0, "variante")):
            x = a[(a[suspeito] == estrato) & (a["variante"] == bra)]["falha"]
            n, k = int(len(x)), int(x.sum())
            lo, hi = _wilson(k, n)
            linhas.append({"estrato": nome_e, "braco": nome_b, "n": n, "falhas": k, "taxa": k / n if n else float("nan"), "lo": lo, "hi": hi})
    return pd.DataFrame(linhas)


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + Z_IC**2 / n
    centro = (p + Z_IC**2 / (2 * n)) / den
    meia = Z_IC * math.sqrt(p * (1 - p) / n + Z_IC**2 / (4 * n**2)) / den
    return centro - meia, centro + meia


def custo(a_com_ruins: pd.DataFrame, a: pd.DataFrame, primario: dict[str, Any]) -> dict[str, Any]:
    """H5, descritivo (seção 8, linha 7): falha extra nas variantes dos controles, % de "variante ruim", falhas extras no conjunto e tempo extra por exposição."""
    var = a_com_ruins[a_com_ruins["variante"] == 1]
    n_ruim = int((var["flag_bad"] == 1).sum())
    out: dict[str, Any] = {"variantes_exibidas": int(len(var)), "variante_ruim": n_ruim, "variante_ruim_pct": n_ruim / len(var) if len(var) else float("nan")}
    out["variante_ruim_ok"] = bool(out["variante_ruim_pct"] <= P.H5_VARIANTE_RUIM) if len(var) else None
    if "delta_ctrl" in primario:
        out["falha_controle_pp"] = primario["delta_ctrl"]
        out["falha_controle_ic"] = [primario["delta_ctrl_lo"], primario["delta_ctrl_hi"]]
        out["falha_controle_ok"] = bool(primario["delta_ctrl"] <= P.H5_FALHA_CONTROLE_PP)
        out["falhas_extras_por_100_variantes"] = primario["delta_todos"]
        out["falhas_extras_ic"] = [primario["delta_todos_lo"], primario["delta_todos_hi"]]
    d = a.dropna(subset=["t_total_s", *COV_BASE]).reset_index(drop=True)
    if len(d) > 30 and (d["variante"] == 1).any() and (d["variante"] == 0).any():
        teto = float(np.percentile(d["t_total_s"], P.TEMPO_PERCENTIL))
        d["t"] = d["t_total_s"].clip(upper=teto)
        d["sc"] = d["suspeito"] - d["suspeito"].mean()  # modificador centrado: o coeficiente da variante é o efeito médio
        tipos = sorted(d.loc[d["variante"] == 1, "tipo"].unique())
        X = montar_X(d, "sc", COV_BASE, tipos)
        aj = _ajustar(d["t"].to_numpy(float), X, pd.factorize(d["nota"])[0], "ols")
        b, ep = float(aj.params["variante"]), float(math.sqrt(aj.cov.loc["variante", "variante"]))
        out.update(tempo_teto_s=teto, tempo_mediana_original_s=float(d.loc[d["variante"] == 0, "t"].median()), tempo_mediana_variante_s=float(d.loc[d["variante"] == 1, "t"].median()),
                   tempo_extra_s=b, tempo_extra_ic=[b - Z_IC * ep, b + Z_IC * ep], tempo_extra_total_min=b * float((d["variante"] == 1).sum()) / 60)
    return out
