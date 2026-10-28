"""Leitura do CSV do add-on, filtros do protocolo (seções 5 e 8) e covariáveis da análise (seção 7)."""
from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from . import prereg as P

NUMERICAS = (
    "seq", "answered_at", "reps", "lapses", "ivl", "days_since_last_review", "same_day", "n_reviews", "last_ease", "ease",
    "t_reveal_ms", "t_total_ms", "n_blanks", "has_image", "shown_ok", "flag_bad", "revlog_match", "superseded", "after_undo",
)
TEXTO = (
    "event_id", "session_id", "profile", "anki_version", "addon_version", "note_id", "card_id", "deck_name", "mode", "scheduler",
    "arm", "variant_id", "variant_type", "note_kind", "draw_seed", "draw_note", "bank_hash", "prev_eases",
)
OBRIGATORIAS = TEXTO + NUMERICAS
BRACOS = ("original", "variant")


def ler_csv(path: str) -> pd.DataFrame:
    """CSV exportado pelo add-on (Ferramentas > DFC Probe > Exportar eventos). Tudo entra como texto e as colunas numéricas são convertidas aqui: `draw_seed` é hexadecimal e não pode virar número."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    faltam = [c for c in OBRIGATORIAS if c not in df.columns]
    if faltam:
        raise ValueError("CSV sem as colunas: " + ", ".join(faltam))
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _contar_falhas(texto: Any) -> float:
    try:
        v = json.loads(texto) if isinstance(texto, str) and texto.strip() else []
        return float(sum(1 for e in v if e == 1))
    except (ValueError, TypeError):
        return float("nan")


def braco_da_semente(seed_hex: str) -> str:
    """Refaz o sorteio 50/50 do add-on (`variants.decide`): a semente de cada evento fica gravada em `draw_seed`."""
    return "variant" if random.Random(int(seed_hex, 16)).random() < 0.5 else "original"


def preparar(df: pd.DataFrame, perfil: str, fuso: str = P.FUSO, embaralhar: Optional[int] = None) -> pd.DataFrame:
    """Acrescenta ao CSV as marcas de cada filtro (uma coluna `f_*` por passo do fluxo), a data local e as covariáveis.

    `embaralhar` (semente) troca ao acaso `arm`, `variant_id` e `variant_type` entre os eventos sorteados do perfil de estudo na janela: modo cego, que testa o roteiro sem revelar o efeito.
    """
    d = df.copy()
    ts = pd.to_datetime(d["answered_at"], unit="s", utc=True).dt.tz_convert(fuso)
    d["data_local"] = ts.dt.tz_localize(None).dt.normalize()
    d["f_perfil"] = d["profile"] == perfil
    d["f_janela"] = (d["data_local"] >= pd.Timestamp(P.JANELA_INICIO)) & (d["data_local"] <= pd.Timestamp(P.JANELA_FIM))
    d["f_banco"] = d["bank_hash"] == P.BANCO_HASH
    d["f_anki"] = d["anki_version"] == P.ANKI_VERSAO
    d["f_sorteado"] = d["arm"].isin(BRACOS)

    if embaralhar is not None:
        alvo = d.index[d["f_perfil"] & d["f_janela"] & d["f_sorteado"]]
        perm = np.random.default_rng(embaralhar).permutation(len(alvo))
        for c in ("arm", "variant_id", "variant_type"):
            d.loc[alvo, c] = d.loc[alvo, c].to_numpy()[perm]

    d["f_outro_dia"] = d["same_day"] == 0
    d["f_exibido"] = d["shown_ok"] == 1
    d["f_sem_marca"] = d["flag_bad"] != 1
    d["f_par"] = d["revlog_match"] == 1
    d["f_nao_subst"] = d["superseded"] != 1

    n_blanks = d["n_blanks"].where(d["note_kind"] != "basic", 0.0)  # seção 7: vale 0 no Básico
    d["n_blanks"] = n_blanks
    d["falha"] = (d["ease"] == 1).astype(float).where(d["ease"].notna())
    d["variante"] = (d["arm"] == "variant").astype(float)
    d["tipo"] = np.where(d["arm"] == "variant", d["variant_type"], "original")
    d["dimensao"] = d["tipo"].map(lambda t: P.DIMENSAO.get(t, t))
    d["log_ivl"] = np.log(np.maximum(d["ivl"], 1.0))
    d["log_dias"] = np.log(np.maximum(d["days_since_last_review"], 0.5))
    d["log_reps"] = np.log(np.maximum(d["reps"], 1.0))
    base = (d["lapses"] == 0) & (d["last_ease"] >= P.SUSPEITO_ULTIMA_RESPOSTA)
    d["suspeito"] = ((d["reps"] >= P.SUSPEITO_REPS) & base).astype(float)
    d["suspeito_reps4"] = ((d["reps"] >= P.SUSPEITO_REPS_SENS) & base).astype(float)
    d["suspeito_nrev5"] = ((d["n_reviews"] >= P.SUSPEITO_NREV_SENS) & base).astype(float).where(d["n_reviews"].notna())
    d["ult_falha"] = (d["last_ease"] == 1).astype(float).where(d["last_ease"].notna(), 0.0)
    d["n_falhas_prev3"] = d["prev_eases"].map(_contar_falhas)
    d["t_total_s"] = d["t_total_ms"] / 1000.0
    d["nota"] = d["note_id"]
    d["completo"] = d[["falha", "ivl", "days_since_last_review", "reps", "lapses", "n_blanks", "has_image"]].notna().all(axis=1)
    return d


def mascara(d: pd.DataFrame, *, incluir_ruins: bool = False, incluir_desfeitas: bool = False) -> pd.Series:
    """Evento válido (seções 5 e 8). As variantes servem para as sensibilidades: `incluir_ruins` aceita a marca "variante ruim"; `incluir_desfeitas` aceita a resposta sem par no histórico do Anki desde que nenhuma outra a tenha substituído."""
    m = d["f_perfil"] & d["f_janela"] & d["f_banco"] & d["f_anki"] & d["f_sorteado"] & d["f_outro_dia"] & d["f_exibido"]
    if not incluir_ruins:
        m &= d["f_sem_marca"]
    m &= d["f_nao_subst"]
    m &= d["revlog_match"].notna() if incluir_desfeitas else d["f_par"]
    return m


def validos(d: pd.DataFrame, **kw: bool) -> pd.DataFrame:
    return d[mascara(d, **kw)]


def analise(d: pd.DataFrame, **kw: bool) -> pd.DataFrame:
    """Eventos válidos com todas as covariáveis do modelo primário."""
    m = mascara(d, **kw) & d["completo"]
    return d[m]


def fluxo(d: pd.DataFrame) -> pd.DataFrame:
    """Funil, passo a passo: quantas linhas do CSV chegam a evento da análise."""
    passos = [
        ("Todas as revisões do CSV (todos os perfis e datas)", None),
        ("Perfil de estudo", "f_perfil"),
        ("Data local de 28/10 a 22/11", "f_janela"),
        ("Banco oficial (`bank_hash`)", "f_banco"),
        ("Anki 26.05", "f_anki"),
        ("Exposição sorteada (braço registrado)", "f_sorteado"),
        ("Última revisão em outro dia do Anki", "f_outro_dia"),
        ("Exibida como sorteada (`shown_ok` = 1)", "f_exibido"),
        ("Sem marca de variante ruim", "f_sem_marca"),
        ("Com par no histórico de revisões do Anki", "f_par"),
        ("Não substituída por outra do mesmo cartão e `reps`", "f_nao_subst"),
        ("Covariáveis completas (evento da análise)", "completo"),
    ]
    vivo = pd.Series(True, index=d.index)
    linhas = []
    anterior = len(d)
    for nome, col in passos:
        if col is not None:
            vivo &= d[col]
        n = int(vivo.sum())
        linhas.append({"passo": nome, "restam": n, "saem": anterior - n if col is not None else 0})
        anterior = n
    return pd.DataFrame(linhas)


def tabela_celulas(a: pd.DataFrame) -> pd.DataFrame:
    """Eventos por estrato e braço (só contagem)."""
    t = pd.crosstab(a["suspeito"].map({1.0: "suspeito", 0.0: "controle"}), a["arm"].map({"original": "original", "variant": "variante"}))
    for c in ("original", "variante"):
        if c not in t.columns:
            t[c] = 0
    t = t[["original", "variante"]]
    t["total"] = t.sum(axis=1)
    return t


def reproduzir_sorteios(d: pd.DataFrame) -> dict[str, Any]:
    """Refaz o braço de cada exposição sorteada do perfil de estudo a partir de `draw_seed` e lista as divergências."""
    s = d[d["f_perfil"] & d["f_sorteado"] & (d["draw_seed"] != "")]
    div = []
    for r in s.itertuples():
        try:
            if braco_da_semente(r.draw_seed) != r.arm:
                div.append(r.event_id[:8])
        except ValueError:
            div.append(r.event_id[:8])
    return {"testados": int(len(s)), "divergentes": div, "sem_semente": int((d["f_perfil"] & d["f_sorteado"] & (d["draw_seed"] == "")).sum())}


def _carregar_variants() -> Any:
    """Módulo `variants` do add-on, carregado pelo caminho (o pacote do add-on importa o Anki e não pode ser importado aqui)."""
    caminho = Path(__file__).resolve().parents[2] / "addon" / "dfc_probe" / "variants.py"
    spec = importlib.util.spec_from_file_location("dfc_variants", caminho)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dfc_variants"] = mod  # o @dataclass do módulo procura a si mesmo em sys.modules
    spec.loader.exec_module(mod)
    return mod


def reproduzir_variantes(d: pd.DataFrame, banco: str) -> dict[str, Any]:
    """Refaz a variante sorteada (`pick_variant`) com o banco e o histórico do próprio cartão no CSV. Só `draw_note = ok`: em `undo_redo` a variante é herdada."""
    variants = _carregar_variants()
    bank = variants.Bank.load(banco)
    historico: dict[str, list[str]] = defaultdict(list)
    testados, div = 0, []
    ordem = d.sort_values(["answered_at", "seq"], kind="stable")
    for r in ordem.itertuples():
        if r.f_perfil and r.f_sorteado and r.draw_note == "ok" and r.draw_seed != "" and r.arm == "variant" and r.bank_hash == bank.hash:  # os ensaios com banco falso ficam só no histórico
            entry = bank.entry(r.note_id)
            if entry is not None:
                rng = random.Random(int(r.draw_seed, 16))
                rng.random()
                testados += 1
                if variants.pick_variant(entry, historico[r.card_id], rng)["id"] != r.variant_id:
                    div.append(r.event_id[:8])
        if r.arm == "variant" and r.shown_ok == 1 and r.variant_id:
            historico[r.card_id].insert(0, r.variant_id)
    return {"testados": testados, "divergentes": div, "banco_hash": bank.hash}


def balanco(a: pd.DataFrame) -> pd.DataFrame:
    """Diferença padronizada das covariáveis entre os braços (só covariáveis, nunca o desfecho): o sorteio deve equilibrá-las. `limite` é o que o acaso produz em 95% dos sorteios com esses tamanhos (≈ 1,96 √(1/n₁ + 1/n₂))."""
    linhas = []
    o, v = a[a["variante"] == 0], a[a["variante"] == 1]
    limite = 1.96 * math.sqrt(1 / len(o) + 1 / len(v)) if len(o) and len(v) else float("nan")
    for c, nome in (("log_ivl", "log(intervalo)"), ("log_dias", "log(dias desde a última revisão)"), ("log_reps", "log(reps)"), ("n_blanks", "lacunas"), ("has_image", "tem imagem"), ("suspeito", "suspeito")):
        dp = np.sqrt((o[c].var(ddof=1) + v[c].var(ddof=1)) / 2) if len(o) > 1 and len(v) > 1 else np.nan
        smd = (v[c].mean() - o[c].mean()) / dp if dp and dp > 0 else np.nan
        linhas.append({"covariavel": nome, "media_original": o[c].mean(), "media_variante": v[c].mean(), "dif_padronizada": smd, "limite": limite})
    return pd.DataFrame(linhas)


def verificacoes(d: pd.DataFrame, a: pd.DataFrame, sorteios: dict[str, Any], variantes: Optional[dict[str, Any]] = None) -> list[dict[str, str]]:
    """Conferência de integridade do CSV (protocolo 6.8, "Conferência"): só contagem e qualidade, nunca o desfecho por braço."""
    out: list[dict[str, str]] = []

    def add(item: str, ok: Optional[bool], detalhe: str = "") -> None:
        out.append({"item": item, "status": "info" if ok is None else ("ok" if ok else "ATENÇÃO"), "detalhe": detalhe})

    est = d[d["f_perfil"] & d["f_janela"]]
    sort = est[est["f_sorteado"]]
    add("Identificadores de evento únicos", bool(d["event_id"].is_unique), f"{len(d)} linhas")
    lacunas = 0
    for _, g in d.sort_values("answered_at", kind="stable").groupby("session_id"):
        if not np.array_equal(g["seq"].to_numpy(), np.arange(1, len(g) + 1)):
            lacunas += 1
    add("`seq` contínuo dentro de cada sessão (CSV completo, sem filtro de perfil)", lacunas == 0, f"{lacunas} sessão(ões) com salto ou repetição")
    add("Sorteio refeito pela semente `draw_seed`", len(sorteios["divergentes"]) == 0 and sorteios["testados"] > 0, f"{sorteios['testados'] - len(sorteios['divergentes'])} de {sorteios['testados']} iguais; {sorteios['sem_semente']} sem semente" + (f"; divergentes: {', '.join(sorteios['divergentes'][:5])}" if sorteios["divergentes"] else ""))
    if variantes is not None:
        add("Variante refeita pelo banco e pelo histórico do cartão", len(variantes["divergentes"]) == 0, f"{variantes['testados'] - len(variantes['divergentes'])} de {variantes['testados']} iguais (banco {variantes['banco_hash']})")
    ruins = sort[sort["shown_ok"] != 1]
    add("Exposição sorteada exibida como sorteada (`shown_ok` = 1)", len(ruins) == 0, f"{len(ruins)} com falha" + (": " + ", ".join(f"{k} {v}" for k, v in ruins["draw_note"].value_counts().items()) if len(ruins) else ""))
    fora = est[~est["f_banco"] | ~est["f_anki"]]
    add("Eventos do perfil de estudo na janela são do banco oficial e do Anki 26.05", len(fora) == 0, f"{len(fora)} fora")
    versoes = est["addon_version"].value_counts()
    add("Uma só versão do add-on na janela", len(versoes) <= 1, ", ".join(f"{k}: {v}" for k, v in versoes.items()) or "nenhum evento")
    for col, rot in (("mode", "Modo de revisão"), ("scheduler", "Agendador")):
        vc = est[col].value_counts()
        add(f"{rot} (perfil de estudo, janela)", len(vc) <= 1, ", ".join(f"{k or '(vazio)'}: {v}" for k, v in vc.items()) or "nenhum evento")
    add("`revlog_match` preenchido em todo evento sorteado", int(sort["revlog_match"].isna().sum()) == 0, f"{int(sort['revlog_match'].isna().sum())} vazios")
    add("Respostas sem par no histórico do Anki (desfeitas)", None, f"{int((sort['revlog_match'] == 0).sum())} sem par; {int((sort['superseded'] == 1).sum())} substituídas; {int((sort['after_undo'] == 1).sum())} refeitas depois de Ctrl+Z")
    v = sort[sort["arm"] == "variant"]
    add("Variantes marcadas como ruins", None, f"{int((v['flag_bad'] == 1).sum())} de {len(v)} exibidas")
    add("Exposições sorteadas por motivo (`draw_note`) no perfil de estudo", None, ", ".join(f"{k or '(vazio)'}: {x}" for k, x in est["draw_note"].value_counts().items()))
    sem_cov = d[mascara(d) & ~d["completo"]]
    add("Eventos válidos sem as covariáveis do modelo", len(sem_cov) == 0, f"{len(sem_cov)} (saem da análise)")
    sem_ult = a[a["last_ease"].isna()]
    add("`last_ease` preenchido nos eventos da análise (vazio conta como controle)", len(sem_ult) == 0, f"{len(sem_ult)} vazios")
    add("`ease` de 1 a 4 nas exposições sorteadas", bool(sort["ease"].isin([1, 2, 3, 4]).all()), f"{int((~sort['ease'].isin([1, 2, 3, 4])).sum())} fora")
    sem_tempo = sort[sort["t_reveal_ms"].isna() | sort["t_total_ms"].isna()]
    add("Tempos registrados (E3 e custo)", len(sem_tempo) == 0, f"{len(sem_tempo)} sem tempo")
    if len(a):
        n_v = int(a["variante"].sum())
        p = stats_binom(n_v, len(a))
        add("Proporção de variantes entre os eventos válidos perto de 50%", p > 0.01, f"{n_v} de {len(a)} ({100 * n_v / len(a):.1f}%; teste binomial p = {p:.3f})".replace(".", ","))
    return out


def stats_binom(k: int, n: int) -> float:
    """p bilateral do teste binomial contra 50% (aproximação normal com correção de continuidade; só um alerta de integridade)."""
    if n == 0:
        return 1.0
    z = (abs(k - n / 2) - 0.5) / math.sqrt(n / 4)
    return math.erfc(max(z, 0) / math.sqrt(2))


def ritmo(v: pd.DataFrame, hoje: Optional[Any] = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Eventos válidos por dia e projeção do alvo de 1000 pelo ritmo dos últimos 7 dias do calendário."""
    por_dia = v.groupby("data_local").size().rename("validos").reset_index()
    por_dia["acumulado"] = por_dia["validos"].cumsum()
    info: dict[str, Any] = {"n": int(len(v)), "dias_com_evento": int(len(por_dia))}
    if not len(por_dia):
        return por_dia, info
    primeiro, ultimo = por_dia["data_local"].min(), por_dia["data_local"].max()
    dias = min(7, (ultimo - primeiro).days + 1)
    info["ritmo_7d"] = float((v["data_local"] > ultimo - pd.Timedelta(days=dias)).sum()) / dias
    hoje = pd.Timestamp(hoje) if hoje is not None else ultimo
    restam_dias = max(0, (pd.Timestamp(P.JANELA_FIM) - max(hoje, ultimo)).days)
    info["projecao_fim"] = int(round(len(v) + info["ritmo_7d"] * restam_dias))
    falta = max(0, P.ALVO_EVENTOS - len(v))
    info["dias_ate_alvo"] = None if falta and info["ritmo_7d"] <= 0 else (0 if not falta else math.ceil(falta / info["ritmo_7d"]))
    if info["dias_ate_alvo"] is not None:
        info["data_alvo"] = (max(hoje, ultimo) + pd.Timedelta(days=info["dias_ate_alvo"])).date().isoformat()
    return por_dia, info


def precisao_prevista(celulas: dict[str, int], taxa: float, n_alvo: int) -> dict[str, float]:
    """Erro-padrão e menor efeito detectável da DiD se as quatro células crescerem na mesma proporção até `n_alvo` eventos, com a taxa de falha global em todas (só tamanhos de célula; sem agrupamento, então o real é maior)."""
    total = sum(celulas.values())
    if total == 0 or min(celulas.values()) == 0:
        return {"n": n_alvo, "ep_pp": float("nan"), "mde_pp": float("nan")}
    esc = n_alvo / total
    ep = math.sqrt(taxa * (1 - taxa) * sum(1.0 / (n * esc) for n in celulas.values())) * 100
    return {"n": n_alvo, "ep_pp": ep, "mde_pp": (1.959964 + 0.841621) * ep}
