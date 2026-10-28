"""Dados sintéticos com efeito conhecido, no formato do CSV do add-on.

Servem para testar o roteiro inteiro (leitura, filtros, modelo, relatório) antes de qualquer olhada nos dados reais e para conferir, nos testes, que a estimativa recupera o efeito e que o IC 95% cobre o valor verdadeiro.
O efeito é dado em pontos percentuais por estrato (média sobre os tipos de variante) e calibrado pela população de referência; `verdade` devolve os efeitos com que os dados foram gerados.
"""
from __future__ import annotations

import datetime
import json
import random
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

from . import prereg as P
from .data import OBRIGATORIAS

TIPOS = ("paraphrase", "reorder", "cue_swap", "pergunta", "sem_imagem")
DESVIO_TIPO = {"paraphrase": 0.0, "reorder": 0.3, "cue_swap": 0.5, "pergunta": -0.3, "sem_imagem": -0.5}  # variação do efeito entre tipos (logit, soma zero)
SD_NOTA = 0.5  # efeito aleatório da nota (correlação entre eventos da mesma nota)
B0, B_SUSP, B_IVL, B_DIAS, B_LAC, B_IMG = -1.9, -1.5, 0.15, 0.10, 0.10, -0.10
PERFIL_TESTE = "perfil-teste"


def _covariaveis(rng: np.random.Generator, n: int, p_susp: float, n_notas: int) -> dict[str, np.ndarray]:
    nota_ix = rng.integers(0, n_notas, n)
    lac_nota = rng.choice([1, 2, 3], n_notas, p=[0.10, 0.50, 0.40])
    img_nota = (rng.random(n_notas) < 0.88).astype(int)
    u_nota = rng.normal(0, SD_NOTA, n_notas)
    log_ivl = np.clip(rng.normal(5.0, 0.9, n), 0.0, 7.0)
    log_dias = np.maximum(log_ivl + rng.normal(0.15, 0.35, n), np.log(0.5))
    suspeito = (rng.random(n) < p_susp).astype(int)
    return {"nota": nota_ix, "n_blanks": lac_nota[nota_ix], "has_image": img_nota[nota_ix], "u": u_nota[nota_ix], "log_ivl": log_ivl, "log_dias": log_dias, "suspeito": suspeito}


def _eta(c: dict[str, np.ndarray]) -> np.ndarray:
    """Preditor linear sem o efeito da variante (logit da probabilidade de falha no original)."""
    return B0 + B_SUSP * c["suspeito"] + B_IVL * (c["log_ivl"] - 5.0) + B_DIAS * (c["log_dias"] - 5.15) + B_LAC * (c["n_blanks"] - 2) + B_IMG * (c["has_image"] - 1) + c["u"]


def _efeito_pp(eta: np.ndarray, tau: float) -> float:
    return float(np.mean([np.mean(expit(eta + tau + g) - expit(eta)) for g in DESVIO_TIPO.values()]) * 100)


def _calibrar(eta: np.ndarray, alvo_pp: float) -> float:
    return float(brentq(lambda tau: _efeito_pp(eta, tau) - alvo_pp, -8.0, 8.0))


@lru_cache(maxsize=None)
def _calibracao(efeito_susp_pp: float, efeito_ctrl_pp: float, p_susp: float) -> tuple[float, float, dict[str, float]]:
    """Desvios (logit) da variante em suspeitos e controles que dão os efeitos pedidos numa população grande de referência, e os efeitos verdadeiros."""
    ref = _covariaveis(np.random.default_rng(12345), 100_000, p_susp, 30_000)
    eta_ref = _eta(ref)
    tau_s = _calibrar(eta_ref[ref["suspeito"] == 1], efeito_susp_pp)
    tau_c = _calibrar(eta_ref[ref["suspeito"] == 0], efeito_ctrl_pp)
    verdade = {"delta_susp": _efeito_pp(eta_ref[ref["suspeito"] == 1], tau_s), "delta_ctrl": _efeito_pp(eta_ref[ref["suspeito"] == 0], tau_c)}
    verdade["did"] = verdade["delta_susp"] - verdade["delta_ctrl"]
    return tau_s, tau_c, verdade


def simular(n: int = 1000, *, efeito_susp_pp: float = 15.0, efeito_ctrl_pp: float = 3.0, p_susp: float = 0.55, semente: int = 1, perfil: str = PERFIL_TESTE,
            efeito_tempo: float = 1.15, p_ruim: float = 0.0) -> tuple[pd.DataFrame, dict[str, float]]:
    """Gera `n` eventos válidos com o efeito da variante (pontos percentuais, média sobre os tipos) nos suspeitos e nos controles."""
    n_notas = max(int(0.85 * n), 5)
    tau_s, tau_c, verdade = _calibracao(float(efeito_susp_pp), float(efeito_ctrl_pp), float(p_susp))
    verdade = dict(verdade)

    rng = np.random.default_rng(semente)
    py = random.Random(semente)
    c = _covariaveis(rng, n, p_susp, n_notas)
    eta = _eta(c)
    variante = rng.random(n) < 0.5
    tipo = np.where(variante, rng.choice(TIPOS, n), "")
    tau = np.where(c["suspeito"] == 1, tau_s, tau_c)
    g = np.array([DESVIO_TIPO.get(t, 0.0) for t in tipo])
    p = expit(eta + np.where(variante, tau + g, 0.0))
    falha = rng.random(n) < p

    susp = c["suspeito"] == 1
    reps = np.where(susp, 5 + rng.poisson(3, n), 5 + rng.poisson(3, n))
    lapses = np.zeros(n, int)
    last_ease = np.where(susp, rng.choice([3, 4], n), 3)
    tipo_ctrl = rng.choice(["a", "b", "c"], n, p=[0.4, 0.4, 0.2])
    a_, b_, c_ = (~susp) & (tipo_ctrl == "a"), (~susp) & (tipo_ctrl == "b"), (~susp) & (tipo_ctrl == "c")
    reps = np.where(a_, rng.integers(1, 5, n), reps)
    lapses = np.where(b_, 1 + rng.poisson(0.5, n), lapses)
    last_ease = np.where(b_, rng.choice([1, 3], n, p=[0.3, 0.7]), last_ease)
    last_ease = np.where(c_, rng.choice([1, 2], n), last_ease)
    n_reviews = np.maximum(1, reps - rng.integers(0, 3, n))

    dia = rng.integers(0, (P.JANELA_FIM - P.JANELA_INICIO).days + 1, n)
    seg = rng.integers(9 * 3600, 21 * 3600, n)
    fuso = datetime.timezone(datetime.timedelta(hours=-3))  # o Brasil não tem horário de verão desde 2019
    base = datetime.datetime(P.JANELA_INICIO.year, P.JANELA_INICIO.month, P.JANELA_INICIO.day, tzinfo=fuso)
    respondida = np.array([(base + datetime.timedelta(days=int(a), seconds=int(b))).timestamp() for a, b in zip(dia, seg)])

    seeds = []
    for v in variante:
        while True:
            s = py.getrandbits(64)
            if (random.Random(s).random() < 0.5) == bool(v):
                break
        seeds.append(f"{s:016x}")

    tempo = np.exp(rng.normal(np.log(24_000), 0.5, n)) * np.where(variante, efeito_tempo, 1.0)
    ruim = variante & (rng.random(n) < p_ruim)
    ordem = np.argsort(respondida)
    df = pd.DataFrame({
        "event_id": [f"{py.getrandbits(128):032x}" for _ in range(n)],
        "session_id": [f"s{int(d_):02d}" for d_ in dia],
        "seq": 0,
        "addon_version": "0.4.0",
        "anki_version": P.ANKI_VERSAO,
        "profile": perfil,
        "answered_at": respondida,
        "note_id": [str(1_600_000_000_000 + int(k)) for k in c["nota"]],
        "card_id": [str(1_700_000_000_000 + int(k)) for k in c["nota"]],
        "deck_name": "baralho-teste",
        "mode": "regular",
        "scheduler": "sm2",
        "reps": reps,
        "lapses": lapses,
        "ivl": np.maximum(1, np.round(np.exp(c["log_ivl"]))).astype(int),
        "days_since_last_review": np.round(np.exp(c["log_dias"]), 3),
        "same_day": 0,
        "n_reviews": n_reviews,
        "last_ease": last_ease,
        "prev_eases": [json.dumps([int(e), 3, 3]) for e in last_ease],
        "ease": np.where(falha, 1, 3),
        "t_reveal_ms": (tempo * 0.6).astype(int),
        "t_total_ms": tempo.astype(int),
        "arm": np.where(variante, "variant", "original"),
        "variant_id": [f"{k}-{t}" if t else "" for k, t in zip(c["nota"], tipo)],
        "variant_type": tipo,
        "note_kind": "cloze",
        "n_blanks": c["n_blanks"],
        "has_image": c["has_image"],
        "shown_ok": 1,
        "draw_seed": seeds,
        "draw_note": "ok",
        "bank_hash": P.BANCO_HASH,
        "flag_bad": ruim.astype(int),
        "revlog_match": 1,
        "superseded": 0,
        "after_undo": 0,
    })
    df = df.iloc[ordem].reset_index(drop=True)
    df["session_id"] = df["session_id"].astype(str)
    df["seq"] = df.groupby("session_id").cumcount() + 1
    faltam = [c_ for c_ in OBRIGATORIAS if c_ not in df.columns]
    assert not faltam, faltam
    return df, verdade


def gravar_csv(df: pd.DataFrame, caminho: str) -> None:
    df.to_csv(caminho, index=False, encoding="utf-8")


def gravar_notas(df: pd.DataFrame, caminho: str, semente: int = 1) -> None:
    """Texto inventado das notas do CSV (e de outras 200), no formato de `1_notas_exportadas_*.jsonl`, para exercitar o E3."""
    rng = np.random.default_rng(semente)
    vocab = [f"palavra{i}" for i in range(60)]
    ids = sorted(set(df["note_id"].astype(str)) | {str(2_000_000_000_000 + i) for i in range(200)})
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        for nid in ids:
            palavras = list(rng.choice(vocab, int(rng.integers(8, 25))))
            palavras.insert(int(rng.integers(1, len(palavras))), "[...]")
            f.write(json.dumps({"note_id": int(nid), "question_text": " ".join(palavras)}) + "\n")
