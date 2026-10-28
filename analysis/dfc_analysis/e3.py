"""E3, exploratória (protocolo 3 e 6.3.1): sinais baratos de candidato, lidos antes da resposta, prevêem a falha da variante?

Nos eventos do braço variante, compara por validação cruzada agrupada por nota a AUC de um escore (regressão logística com todos os sinais)
com a de um baseline que só usa `reps`. Sem limiar de decisão e só como associação: o tempo até revelar é da mesma exposição da resposta.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional, Sequence

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import rankdata

from . import prereg as P

BLANK_RE = re.compile(r"\[\.\.\.\d*\]")
PALAVRA_RE = re.compile(r"\w+", re.UNICODE)
SINAIS = {
    "log_reps": "`reps` (log)",
    "log_lapses": "`lapses` (log(1 + x))",
    "n_falhas_prev3": "falhas entre as 3 últimas respostas",
    "z_tempo": "tempo até revelar por caractere (padronizado)",
    "log_pmi": "prefixo mínimo identificador (log(1 + palavras))",
    "n_blanks": "lacunas",
    "has_image": "tem imagem",
}
BASELINE = ["log_reps"]


def texto_visivel(question_text: str) -> str:
    """Texto visível do cartão original: sem lacunas, marcadores nem imagens (o export já tira o HTML e as imagens)."""
    return re.sub(r"\s+", " ", BLANK_RE.sub("", question_text or "")).strip()


def prefixo_minimo(palavras: Sequence[tuple[str, ...]]) -> list[int]:
    """PMI: o menor número de palavras iniciais do enunciado que o distingue de todos os outros. Notas vizinhas na ordenação têm o maior prefixo comum, então basta olhar os dois vizinhos; se nenhuma quantidade distingue (enunciado repetido ou prefixo de outro), vale o tamanho do enunciado."""
    def lcp(a: tuple[str, ...], b: tuple[str, ...]) -> int:
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        return n

    ordem = sorted(range(len(palavras)), key=lambda i: palavras[i])
    out = [0] * len(palavras)
    for pos, i in enumerate(ordem):
        m = 0
        if pos > 0:
            m = max(m, lcp(palavras[i], palavras[ordem[pos - 1]]))
        if pos < len(ordem) - 1:
            m = max(m, lcp(palavras[i], palavras[ordem[pos + 1]]))
        out[i] = min(len(palavras[i]), m + 1)
    return out


def ler_notas(caminho: str) -> pd.DataFrame:
    """Texto exportado das notas (`1_notas_exportadas_*.jsonl`): tamanho do enunciado e PMI de cada nota, calculado contra todas as notas do arquivo."""
    ids, chars, toks = [], [], []
    with open(caminho, encoding="utf-8") as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            v = texto_visivel(r.get("question_text", ""))
            ids.append(str(r["note_id"]))
            chars.append(len(v))
            toks.append(tuple(PALAVRA_RE.findall(v.lower())))
    return pd.DataFrame({"chars": chars, "n_palavras": [len(t) for t in toks], "pmi": prefixo_minimo(toks)}, index=pd.Index(ids, name="note_id"))


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """Área sob a curva ROC (probabilidade de uma falha ter escore maior que um acerto; empates valem 1/2)."""
    y = np.asarray(y, bool)
    n1, n0 = int(y.sum()), int((~y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(s)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def sinais(d: pd.DataFrame, a: pd.DataFrame, notas: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Sinais de cada evento do braço variante da análise. O tempo por caractere é padronizado pela própria pessoa nas exposições do original e nas sem sorteio (notas do texto exportado), com o tempo truncado no percentil 99."""
    v = a[a["variante"] == 1].copy()
    ref = d[d["f_perfil"] & d["f_janela"] & (d["arm"] != "variant") & d["note_id"].isin(notas.index) & (d["t_reveal_ms"] > 0)]
    ref = ref[ref["note_id"].map(notas["chars"]) > 0]
    info: dict[str, Any] = {"eventos_variante": int(len(v)), "referencia_tempo": int(len(ref))}
    if len(ref) < 30:
        info["estado"] = "poucas exposições de referência para padronizar o tempo"
        return v.iloc[0:0], info
    teto = float(np.percentile(ref["t_reveal_ms"], P.TEMPO_PERCENTIL))
    x_ref = np.log(np.minimum(ref["t_reveal_ms"], teto) / ref["note_id"].map(notas["chars"]))
    mu, dp = float(x_ref.mean()), float(x_ref.std(ddof=1))
    v = v[v["note_id"].isin(notas.index) & (v["t_reveal_ms"] > 0)]
    v = v[v["note_id"].map(notas["chars"]) > 0].copy()
    info["sem_texto_ou_tempo"] = info["eventos_variante"] - int(len(v))
    v["z_tempo"] = (np.log(np.minimum(v["t_reveal_ms"], teto) / v["note_id"].map(notas["chars"])) - mu) / dp
    v["log_pmi"] = np.log1p(v["note_id"].map(notas["pmi"]))
    v["log_lapses"] = np.log1p(v["lapses"])
    info["estado"] = "ok"
    return v, info


def _ridge_logit(X: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    """Logística com penalidade L2 em todos os coeficientes menos a constante (Newton-Raphson); `X` já tem a constante na primeira coluna."""
    pen = np.eye(X.shape[1]) * lam
    pen[0, 0] = 0.0
    beta = np.zeros(X.shape[1])
    for _ in range(100):
        p = expit(X @ beta)
        grad = X.T @ (y - p) - pen @ beta
        hess = X.T @ (X * (p * (1 - p))[:, None]) + pen + 1e-10 * np.eye(X.shape[1])
        passo = np.linalg.solve(hess, grad)
        beta += passo
        if np.max(np.abs(passo)) < 1e-8:
            break
    return beta


def blocos_por_nota(notas: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    """Bloco (0 a k-1) de cada evento: todos os eventos de uma nota ficam no mesmo bloco, e os blocos têm quase o mesmo número de notas."""
    cod = pd.factorize(notas)[0]
    return rng.permutation(np.arange(cod.max() + 1) % k)[cod]


def previsao_cv(v: pd.DataFrame, feats: Sequence[str], *, k: int = P.E3_BLOCOS, repeticoes: int = 20, semente: int = 1, lam: float = P.E3_RIDGE) -> np.ndarray:
    """Probabilidade prevista fora da amostra: validação cruzada em `k` blocos de notas (a mesma nota nunca está no treino e no teste), repetida com sorteios diferentes de blocos e com a média das previsões."""
    y = v["falha"].to_numpy(float)
    X0 = v[list(feats)].to_numpy(float)
    rng = np.random.default_rng(semente)
    soma = np.zeros(len(v))
    for _ in range(repeticoes):
        bloco = blocos_por_nota(v["nota"].to_numpy(), k, rng)
        for b in range(k):
            tr, te = bloco != b, bloco == b
            mu, dp = X0[tr].mean(axis=0), X0[tr].std(axis=0)
            dp[dp == 0] = 1.0
            Z = (X0 - mu) / dp
            beta = _ridge_logit(np.column_stack([np.ones(tr.sum()), Z[tr]]), y[tr], lam)
            soma[te] += expit(np.column_stack([np.ones(te.sum()), Z[te]]) @ beta)
    return soma / repeticoes


def _bootstrap(y: np.ndarray, colunas: dict[str, np.ndarray], grupos: np.ndarray, n_boot: int, semente: int) -> dict[str, np.ndarray]:
    """AUC de cada coluna de escore e a diferença entre as duas primeiras, em réplicas com notas sorteadas com reposição."""
    rng = np.random.default_rng(semente)
    cod = pd.factorize(grupos)[0]
    ordem = np.argsort(cod, kind="stable")
    lim = np.searchsorted(cod[ordem], np.arange(cod.max() + 2))
    idx = [ordem[lim[g] : lim[g + 1]] for g in range(cod.max() + 1)]
    nomes = list(colunas)
    out = {n: [] for n in nomes + ["dif"]}
    for _ in range(n_boot):
        ix = np.concatenate([idx[g] for g in rng.integers(0, len(idx), len(idx))])
        yb = y[ix]
        if yb.sum() == 0 or yb.sum() == len(yb):
            continue
        aucs = {n: auc(yb, colunas[n][ix]) for n in nomes}
        for n in nomes:
            out[n].append(aucs[n])
        out["dif"].append(aucs[nomes[0]] - aucs[nomes[1]])
    return {n: np.array(x) for n, x in out.items()}


def _ic(x: np.ndarray) -> list[float]:
    return [float(np.percentile(x, 100 * (1 - P.NIVEL_IC) / 2)), float(np.percentile(x, 100 * (1 + P.NIVEL_IC) / 2))] if len(x) >= 50 else [float("nan")] * 2


def e3(d: pd.DataFrame, a: pd.DataFrame, notas: pd.DataFrame, *, semente: int = 1, n_boot: int = 1000, repeticoes: int = 20) -> dict[str, Any]:
    v, info = sinais(d, a, notas)
    res: dict[str, Any] = {**info, "n": int(len(v)), "falhas": int(v["falha"].sum()) if len(v) else 0}
    if info["estado"] != "ok":
        return res
    if res["falhas"] < 10 or res["n"] - res["falhas"] < 10:
        res["estado"] = f"insuficiente: {res['falhas']} falhas em {res['n']} eventos de variante (mínimo de 10 de cada classe)"
        return res
    feats = [f for f in SINAIS if v[f].nunique() > 1]
    y = v["falha"].to_numpy(float)
    p_escore = previsao_cv(v, feats, repeticoes=repeticoes, semente=semente)
    p_base = previsao_cv(v, BASELINE, repeticoes=repeticoes, semente=semente)
    colunas = {"escore": p_escore, "baseline": p_base, **{f: v[f].to_numpy(float) for f in feats}}
    bs = _bootstrap(y, colunas, v["nota"].to_numpy(), n_boot, semente)
    res.update(sinais_usados=feats, auc_escore=auc(y, p_escore), auc_escore_ic=_ic(bs["escore"]), auc_baseline=auc(y, p_base), auc_baseline_ic=_ic(bs["baseline"]),
               dif=auc(y, p_escore) - auc(y, p_base), dif_ic=_ic(bs["dif"]), boot_validas=int(len(bs["dif"])))
    linhas = []
    for f in feats:
        lo, hi = _ic(bs[f])
        linhas.append({"sinal": SINAIS[f], "auc": auc(y, v[f].to_numpy(float)), "lo": lo, "hi": hi})
    res["sinais"] = pd.DataFrame(linhas)
    return res
