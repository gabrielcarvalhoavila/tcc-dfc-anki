"""Figuras do relatório (matplotlib, opcional): falha por estrato e braço, DiD com as sensibilidades e os recortes, e ritmo da coleta."""
from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np
import pandas as pd

from . import prereg as P

COR_ORIGINAL, COR_VARIANTE, COR_REF = "#4d4d4d", "#d95f02", "#b2182b"


def disponivel() -> bool:
    try:
        import matplotlib  # noqa: F401

        return True
    except ImportError:
        return False


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    return plt


def _salvar(fig, pasta: str, nome: str) -> str:
    os.makedirs(os.path.join(pasta, "figuras"), exist_ok=True)
    caminho = os.path.join(pasta, "figuras", nome)
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return f"figuras/{nome}"


def celulas(taxas: pd.DataFrame, pasta: str) -> str:
    """Falha por estrato e braço com IC 95% de Wilson: a inclinação de cada linha é o efeito da variante e a diferença entre as inclinações, a DiD."""
    plt = _plt()
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    x = {"controle": 0, "suspeito": 1}
    for braco, cor, desl in (("original", COR_ORIGINAL, -0.04), ("variante", COR_VARIANTE, 0.04)):
        t = taxas[taxas["braco"] == braco].set_index("estrato").loc[["controle", "suspeito"]]
        xs = np.array([x[e] for e in t.index]) + desl
        y = 100 * t["taxa"].to_numpy(float)
        ax.errorbar(xs, y, yerr=[y - 100 * t["lo"].to_numpy(float), 100 * t["hi"].to_numpy(float) - y], fmt="o", color=cor, capsize=3, label=braco)
        for xi, yi, n in zip(xs, y, t["n"]):
            ax.annotate(f"n = {int(n)}", (xi, yi), textcoords="offset points", xytext=(8 if braco == "variante" else -8, -3), ha="left" if braco == "variante" else "right", fontsize=7, color=cor)
    for estrato, xi in x.items():
        t = taxas[taxas["estrato"] == estrato].set_index("braco")
        ax.plot([xi - 0.04, xi + 0.04], [100 * t.loc["original", "taxa"], 100 * t.loc["variante", "taxa"]], color="#999999", lw=1, zorder=0)
    ax.set_xticks([0, 1], ["Controles", "Suspeitos"])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Falha ('Again'), %")
    ax.set_title("Falha por estrato e braço (IC 95% de Wilson)")
    ax.legend(frameon=False, loc="upper left")
    return _salvar(fig, pasta, "celulas.png")


def forest(sens: Optional[pd.DataFrame], tipo: Optional[pd.DataFrame], sub: Optional[pd.DataFrame], pasta: str) -> Optional[str]:
    """DiD em pp (IC 95%) da análise principal, das sensibilidades e dos recortes exploratórios, com a linha de 0 e a de 10 pp (limiar de relevância)."""
    linhas: list[tuple[str, float, float, float, str]] = []
    for nome, df, grupo in (("sens", sens, "Principal e sensibilidades"), ("tipo", tipo, "Por tipo (exploratória)"), ("sub", sub, "Por lacunas e imagem (exploratória)")):
        if df is None or not len(df) or "did" not in df.columns:
            continue
        for _, r in df.iterrows():
            if pd.notna(r.get("did")) and pd.notna(r.get("did_lo")) and pd.notna(r.get("did_hi")):
                rot = str(r["rotulo"]).replace("`", "")
                linhas.append((rot if len(rot) < 62 else rot[:59] + "...", float(r["did"]), float(r["did_lo"]), float(r["did_hi"]), grupo))
    if not linhas:
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.4, 0.32 * len(linhas) + 2.2))
    y = 0
    ticks, rotulos, anteriores = [], [], None
    for rot, est, lo, hi, grupo in linhas:
        if grupo != anteriores:
            y += 1.0 if anteriores is not None else 0.0
            ax.annotate(grupo, xy=(0.0, -y + 0.75), xycoords=("axes fraction", "data"), ha="left", va="center", fontsize=8, fontweight="bold", color="#333333")
            y += 0.2
        anteriores = grupo
        ax.errorbar(est, -y, xerr=[[est - lo], [hi - est]], fmt="o", color=COR_VARIANTE if grupo.startswith("Principal") else COR_ORIGINAL, capsize=2.5, ms=4)
        ticks.append(-y)
        rotulos.append(rot)
        y += 1
    ax.set_ylim(-y + 0.3, 1.3)
    ax.axvline(0, color="#999999", lw=1)
    ax.axvline(P.LIMIAR_PP, color=COR_REF, lw=1, ls="--")
    ax.text(P.LIMIAR_PP, 0.6, f" {P.LIMIAR_PP:.0f} pp (relevante)", color=COR_REF, fontsize=7, va="bottom")
    ax.set_yticks(ticks, rotulos)
    ax.set_xlabel("DiD (pontos percentuais): efeito da variante nos suspeitos menos nos controles")
    ax.set_title("DiD com IC 95%")
    return _salvar(fig, pasta, "did_forest.png")


def ritmo(por_dia: pd.DataFrame, pasta: str) -> Optional[str]:
    """Eventos válidos por dia (barras) e acumulados (linha) contra o alvo de parada."""
    if not len(por_dia):
        return None
    plt = _plt()
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    dias = pd.to_datetime(por_dia["data_local"])
    ax.bar(dias, por_dia["validos"], color="#9ecae1", width=0.8, label="válidos por dia")
    ax.set_ylabel("eventos válidos por dia")
    ax2 = ax.twinx()
    ax2.plot(dias, por_dia["acumulado"], color=COR_VARIANTE, marker="o", ms=3, label="acumulados")
    ax2.axhline(P.ALVO_EVENTOS, color=COR_REF, ls="--", lw=1)
    ax2.text(dias.iloc[0], P.ALVO_EVENTOS, f"alvo {P.ALVO_EVENTOS}", color=COR_REF, fontsize=7, va="bottom")
    ax2.set_ylabel("acumulados")
    ax2.spines["right"].set_visible(True)
    ax.set_xlim(pd.Timestamp(P.JANELA_INICIO) - pd.Timedelta(days=1), pd.Timestamp(P.JANELA_FIM) + pd.Timedelta(days=1))
    fig.autofmt_xdate()
    ax.set_title("Eventos válidos ao longo da janela")
    return _salvar(fig, pasta, "ritmo.png")
