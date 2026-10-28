"""Testes da análise (analysis/dfc_analysis): trava do pré-registro, filtros, estimador, relatório e monitor.

Precisam de numpy, pandas, scipy e statsmodels (analysis/requirements.txt); sem eles, são pulados.
Os dados são sintéticos (com efeito conhecido) e o nome do perfil é fictício.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))
HAS_STATS = all(importlib.util.find_spec(m) is not None for m in ("numpy", "pandas", "scipy", "statsmodels"))

if HAS_STATS:
    import numpy as np
    import pandas as pd

    from dfc_analysis import cli, data as D, e3 as E, figuras as F, models as M, prereg as P, report as R, synthetic as S

SKIP = unittest.skipUnless(HAS_STATS, "faltam numpy, pandas, scipy ou statsmodels (pip install -r analysis/requirements.txt)")
BRT = datetime.timezone(datetime.timedelta(hours=-3))


def epoch(y, m, d, hh=12, mm=0, ss=0):
    return datetime.datetime(y, m, d, hh, mm, ss, tzinfo=BRT).timestamp()


def preparado(n=600, semente=1, **kw):
    df, verdade = S.simular(n, semente=semente, **kw)
    d = D.preparar(df, S.PERFIL_TESTE)
    return d, D.analise(d), verdade


def rodar_cli(argv):
    buf, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
        rc = cli.main(argv)
    return rc, buf.getvalue() + err.getvalue()


def csv_sintetico(pasta, n=600, semente=1, perfil=S.PERFIL_TESTE if HAS_STATS else "p", **kw):
    df, verdade = S.simular(n, semente=semente, perfil=perfil, **kw)
    caminho = os.path.join(pasta, "eventos.csv")
    S.gravar_csv(df, caminho)
    return caminho, df, verdade


@SKIP
class TestTrava(unittest.TestCase):
    def test_recusa_antes_do_fim(self):
        with self.assertRaises(cli.Recusa):
            cli.checar_trava(500, datetime.date(2026, 11, 10), None)

    def test_recusa_no_ultimo_dia_com_poucos_eventos(self):
        with self.assertRaises(cli.Recusa):
            cli.checar_trava(999, datetime.date(2026, 11, 22), None)

    def test_libera_depois_de_22_11(self):
        self.assertIsNone(cli.checar_trava(200, datetime.date(2026, 11, 23), None))

    def test_libera_no_alvo_de_eventos(self):
        self.assertIsNone(cli.checar_trava(1000, datetime.date(2026, 11, 10), None))

    def test_olhada_exige_motivo(self):
        self.assertEqual(cli.checar_trava(200, datetime.date(2026, 11, 10), " testar o roteiro "), "testar o roteiro")
        for vazio in ("", "   ", None):
            with self.assertRaises(cli.Recusa):
                cli.checar_trava(200, datetime.date(2026, 11, 10), vazio)


@SKIP
class TestDados(unittest.TestCase):
    def test_cada_filtro_exclui_so_a_sua_linha(self):
        df, _ = S.simular(40, semente=3)
        df.loc[0, "profile"] = "outro perfil"
        df.loc[1, "bank_hash"] = "000000000000"
        df.loc[2, "anki_version"] = "26.09"
        df.loc[3, "arm"] = ""
        df.loc[4, "same_day"] = 1
        df.loc[5, "shown_ok"] = 0
        df.loc[6, "flag_bad"] = 1
        df.loc[7, "revlog_match"] = 0
        df.loc[8, "superseded"] = 1
        df.loc[9, "answered_at"] = epoch(2026, 10, 27, 23, 59, 59)
        df.loc[10, "answered_at"] = epoch(2026, 11, 23, 0, 0, 0)
        df.loc[11, "answered_at"] = epoch(2026, 10, 28, 0, 0, 0)  # primeiro instante da janela: entra
        df.loc[12, "answered_at"] = epoch(2026, 11, 22, 23, 59, 59)  # último instante: entra
        d = D.preparar(df, S.PERFIL_TESTE)
        self.assertEqual(set(D.validos(d).index), set(range(11, 40)))
        flx = D.fluxo(d)
        self.assertEqual(int(flx["restam"].iloc[0]), 40)
        self.assertEqual(int(flx["restam"].iloc[-1]), 29)
        self.assertEqual(int(flx["saem"].sum()), 11)

    def test_variacoes_de_validade_para_as_sensibilidades(self):
        df, _ = S.simular(30, semente=4)
        df.loc[0, "flag_bad"] = 1
        df.loc[1, ["revlog_match", "superseded"]] = [0, 0]  # desfeita sem substituta
        df.loc[2, ["revlog_match", "superseded"]] = [0, 1]  # desfeita e substituída
        d = D.preparar(df, S.PERFIL_TESTE)
        self.assertEqual(len(D.validos(d)), 27)
        self.assertEqual(set(D.validos(d, incluir_ruins=True).index) - set(D.validos(d).index), {0})
        self.assertEqual(set(D.validos(d, incluir_desfeitas=True).index) - set(D.validos(d).index), {1})

    def test_suspeito_nos_limites(self):
        df, _ = S.simular(8, semente=1)
        casos = [(5, 0, 3, True), (4, 0, 3, False), (5, 1, 3, False), (5, 0, 2, False), (30, 0, 4, True), (1, 0, 3, False), (5, 0, 1, False), (6, 0, 3, True)]
        for i, (reps, lapses, ult, _) in enumerate(casos):
            df.loc[i, ["reps", "lapses", "last_ease"]] = [reps, lapses, ult]
        d = D.preparar(df, S.PERFIL_TESTE)
        self.assertEqual(d["suspeito"].astype(bool).tolist(), [c[3] for c in casos])
        self.assertEqual(d["suspeito_reps4"].astype(bool).tolist(), [True, True, False, False, True, False, False, True])

    def test_perfil_so_conta_o_informado(self):
        df, _ = S.simular(20, semente=2)
        df.loc[:4, "profile"] = "perfil-do-autor"
        d = D.preparar(df, S.PERFIL_TESTE)
        self.assertEqual(len(D.validos(d)), 15)

    def test_csv_exige_as_colunas_e_nao_converte_a_semente(self):
        with tempfile.TemporaryDirectory() as t:
            df, _ = S.simular(10, semente=1)
            df.loc[0, "draw_seed"] = "1e12345678901234"  # parece notação científica
            caminho = os.path.join(t, "a.csv")
            S.gravar_csv(df, caminho)
            lido = D.ler_csv(caminho)
            self.assertEqual(lido.loc[0, "draw_seed"], "1e12345678901234")
            S.gravar_csv(df.drop(columns=["shown_ok"]), caminho)
            with self.assertRaises(ValueError):
                D.ler_csv(caminho)

    def test_embaralhar_preserva_contagens_e_so_mexe_nos_sorteados(self):
        df, _ = S.simular(300, semente=2)
        df.loc[:9, "profile"] = "perfil-do-autor"
        antes = D.preparar(df, S.PERFIL_TESTE)
        depois = D.preparar(df, S.PERFIL_TESTE, embaralhar=5)
        est = antes["f_perfil"] & antes["f_janela"] & antes["f_sorteado"]
        self.assertEqual(sorted(antes.loc[est, "variant_type"]), sorted(depois.loc[est, "variant_type"]))
        self.assertEqual(int((antes.loc[est, "arm"] == "variant").sum()), int((depois.loc[est, "arm"] == "variant").sum()))
        self.assertFalse((antes.loc[est, "arm"].to_numpy() == depois.loc[est, "arm"].to_numpy()).all())
        self.assertTrue((antes.loc[~est, "arm"].to_numpy() == depois.loc[~est, "arm"].to_numpy()).all())
        # o tipo acompanha o braço: só variante tem tipo
        self.assertTrue(((depois["arm"] == "variant") == (depois["variant_type"] != "")).all())


def _variants_do_addon():
    spec = importlib.util.spec_from_file_location("dfc_variants_teste", ROOT / "addon" / "dfc_probe" / "variants.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dfc_variants_teste"] = mod
    spec.loader.exec_module(mod)
    return mod


@SKIP
class TestSorteio(unittest.TestCase):
    def test_braco_da_semente_igual_ao_do_addon(self):
        v = _variants_do_addon()
        entry = {"kind": "cloze", "ords": [0], "fields_hash": "h", "q_field": 0, "answers_html": ["r"], "images_html": [],
                 "variants": [{"id": "x1", "type": "paraphrase", "text": "a [...]"}, {"id": "x2", "type": "reorder", "text": "b [...]"}]}
        for i in range(300):
            dec = v.decide(entry, card_ord=0, fields_hash_now="h", reps=5, same_day=0, draw_on=True, window_ok=True, last_shown=[], event_id=f"evento-{i}", salt=b"sal")
            self.assertEqual(D.braco_da_semente(dec.seed), dec.arm)

    def test_adulteracao_do_braco_e_detectada(self):
        df, _ = S.simular(30, semente=5)
        antes = D.reproduzir_sorteios(D.preparar(df, S.PERFIL_TESTE))
        self.assertEqual((antes["testados"], antes["divergentes"]), (30, []))
        df.loc[3, "arm"] = "variant" if df.loc[3, "arm"] == "original" else "original"
        depois = D.reproduzir_sorteios(D.preparar(df, S.PERFIL_TESTE))
        self.assertEqual(depois["divergentes"], [df.loc[3, "event_id"][:8]])

    def test_variante_refeita_com_o_banco_e_o_historico_do_cartao(self):
        v = _variants_do_addon()
        notas = {}
        for k in range(3):
            notas[str(1_600_000_000_000 + k)] = {"kind": "cloze", "ords": [0], "q_field": 0, "fields_hash": f"h{k}", "answers_html": ["r"], "images_html": [],
                                                  "variants": [{"id": f"{k}-{t}", "type": t, "text": "x [...]"} for t in ("paraphrase", "reorder", "cue_swap")]}
        with tempfile.TemporaryDirectory() as t:
            banco = os.path.join(t, "banco.json")
            with open(banco, "w", encoding="utf-8") as f:
                json.dump({"schema": 3, "generated_at": "t", "generator_models": ["m"], "judge_models": ["j"], "excluded_types": [], "notes": notas}, f)
            bank = v.Bank.load(banco)
            df, _ = S.simular(60, semente=8)
            hist = {}
            for i in df.index:
                k = i % 3
                nid = 1_600_000_000_000 + k
                dec = v.decide(bank.entry(nid), card_ord=0, fields_hash_now=f"h{k}", reps=5, same_day=0, draw_on=True, window_ok=True, last_shown=hist.get(k, []), event_id=df.loc[i, "event_id"], salt=b"sal")
                df.loc[i, ["note_id", "card_id", "arm", "draw_seed", "draw_note", "bank_hash", "shown_ok"]] = [str(nid), str(1_700_000_000_000 + k), dec.arm, dec.seed, "ok", bank.hash, 1]
                df.loc[i, ["variant_id", "variant_type"]] = [dec.variant["id"], dec.variant["type"]] if dec.variant else ["", ""]
                if dec.variant:
                    hist.setdefault(k, []).insert(0, dec.variant["id"])
            ok = D.reproduzir_variantes(D.preparar(df, S.PERFIL_TESTE), banco)
            self.assertEqual(ok["divergentes"], [])
            self.assertEqual(ok["testados"], int((df["arm"] == "variant").sum()))
            i = int(df.index[df["arm"] == "variant"][-1])
            trocada = [x["id"] for x in notas[df.loc[i, "note_id"]]["variants"] if x["id"] != df.loc[i, "variant_id"]][0]
            df.loc[i, "variant_id"] = trocada
            ruim = D.reproduzir_variantes(D.preparar(df, S.PERFIL_TESTE), banco)
            self.assertEqual(ruim["divergentes"], [df.loc[i, "event_id"][:8]])


@SKIP
class TestEstimador(unittest.TestCase):
    def test_recupera_o_efeito_conhecido(self):
        d, a, verdade = preparado(2000, semente=11)
        linha, coef = M.estimar_did(a, rotulo="x")
        self.assertEqual(linha["estado"], "ok")
        self.assertAlmostEqual(verdade["did"], 12.0, places=1)
        for nome, ref in (("did", verdade["did"]), ("delta_susp", verdade["delta_susp"]), ("delta_ctrl", verdade["delta_ctrl"])):
            self.assertLessEqual(linha[f"{nome}_lo"], ref, nome)
            self.assertGreaterEqual(linha[f"{nome}_hi"], ref, nome)
        self.assertIn("variante:suspeito", set(coef["termo"]))

    def test_vies_e_cobertura_do_ic(self):
        est, cobre = [], []
        for s in range(100, 180):
            _, a, v = preparado(800, semente=s)
            linha, _ = M.estimar_did(a, rotulo="x")
            est.append(linha["did"])
            cobre.append(linha["did_lo"] <= v["did"] <= linha["did_hi"])
        self.assertLess(abs(np.mean(est) - v["did"]), 1.5)
        self.assertGreaterEqual(np.mean(cobre), 0.87)

    def test_sem_efeito_quase_nunca_apoia_h2(self):
        classes, est = [], []
        for s in range(200, 280):
            _, a, v = preparado(1000, semente=s, efeito_susp_pp=0.0, efeito_ctrl_pp=0.0)
            linha, _ = M.estimar_did(a, rotulo="x")
            est.append(linha["did"])
            classes.append(M.classificar_h2(linha["did"], linha["did_lo"], linha["did_hi"]))
        self.assertAlmostEqual(v["did"], 0.0, places=1)
        self.assertLess(abs(np.mean(est)), 1.5)
        self.assertLessEqual(classes.count("apoiada") / len(classes), 0.05)

    def test_efeito_marginal_igual_ao_da_formula_do_statsmodels(self):
        import statsmodels.api as sm
        import statsmodels.formula.api as smf
        from patsy import dmatrix
        from scipy.special import expit

        _, a, _ = preparado(700, semente=5)
        a = a.reset_index(drop=True)
        s = a["suspeito"].to_numpy() == 1
        m = M.ModeloEfeito(a, "suspeito", M.COV_BASE, {"susp": s, "ctrl": ~s}, "nenhum")
        est, V = m.com_ep(m.ajustar())
        rhs = "variante * suspeito + log_ivl + log_dias + n_blanks + has_image"
        res = smf.glm("falha ~ " + rhs, a, family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(a["nota"])[0]})

        def matriz(v):
            novo = a.copy()
            novo["variante"] = v
            return dmatrix(rhs, novo, return_type="dataframe")[list(res.params.index)].to_numpy()

        X1, X0 = matriz(1.0), matriz(0.0)

        def f(beta):
            dif = (expit(X1 @ beta) - expit(X0 @ beta)) * 100
            return np.array([dif[s].mean(), dif[~s].mean()])

        beta = res.params.to_numpy()
        np.testing.assert_allclose(est[:2], f(beta), atol=1e-3)
        J = np.column_stack([(f(beta + h) - f(beta - h)) / 2e-5 for h in np.eye(len(beta)) * 1e-5])
        cov_ref = J @ res.cov_params().to_numpy() @ J.T
        np.testing.assert_allclose(np.sqrt(np.diag(V)[:2]), np.sqrt(np.diag(cov_ref)), rtol=2e-2)

    def test_resultado_nao_depende_da_codificacao_nem_da_escala(self):
        _, a, _ = preparado(700, semente=6)
        a = a.reset_index(drop=True)
        s = a["suspeito"].to_numpy() == 1
        tipos = sorted(a.loc[a["variante"] == 1, "tipo"].unique())
        m1 = M.ModeloEfeito(a, "suspeito", M.COV_BASE, {"susp": s, "ctrl": ~s}, tipos)
        m2 = M.ModeloEfeito(a, "suspeito", M.COV_BASE, {"susp": s, "ctrl": ~s}, list(reversed(tipos)))
        e1, e2 = m1.efeitos(m1.beta(m1.ajustar())), m2.efeitos(m2.beta(m2.ajustar()))
        np.testing.assert_allclose(e1, e2, atol=1e-4)
        b = a.copy()
        b["log_dias"] = b["log_dias"] * 3 + 7
        m3 = M.ModeloEfeito(b, "suspeito", M.COV_BASE, {"susp": s, "ctrl": ~s}, tipos)
        np.testing.assert_allclose(e1, m3.efeitos(m3.beta(m3.ajustar())), atol=1e-4)

    def test_metodo_delta_e_bootstrap_concordam(self):
        _, a, _ = preparado(800, semente=9)
        linha, _ = M.estimar_did(a, rotulo="x", n_boot=300, semente=3)
        self.assertGreaterEqual(linha["boot_validas"], 290)
        razao = linha["did_boot_ep"] / linha["did_ep"]
        self.assertTrue(0.7 < razao < 1.4, razao)

    def test_tabela_8_1(self):
        c = M.classificar_h2
        self.assertEqual(c(10.0, 2.0, 18.0), "apoiada")
        self.assertEqual(c(9.9, 2.0, 18.0), "efeito pequeno")
        self.assertEqual(c(12.0, -1.0, 25.0), "inconclusivo")
        self.assertEqual(c(1.0, -6.0, 9.9), "relevante descartado")
        self.assertEqual(c(1.0, -6.0, 10.0), "inconclusivo")
        self.assertEqual(c(-8.0, -14.0, -2.0), "efeito pequeno (direção oposta à hipótese)")
        self.assertEqual(c(5.0, float("nan"), float("nan")), "indeterminada")
        self.assertEqual(set(M.TEXTO_H2), {"apoiada", "efeito pequeno", "efeito pequeno (direção oposta à hipótese)", "relevante descartado", "inconclusivo", "indeterminada"})

    def test_minimos_do_protocolo(self):
        _, a, _ = preparado(600, semente=1)
        self.assertTrue(M.checar_minimos(a)["ok"])
        self.assertFalse(M.checar_minimos(a.iloc[:250])["ok"])  # menos de 300 eventos
        raros = a[(a["suspeito"] == 0)].iloc[:60]
        self.assertFalse(M.checar_minimos(pd.concat([a[a["suspeito"] == 1].iloc[:300], raros]))["ok"])  # menos de 100 controles

    def test_celulas_pequenas_nao_sao_estimadas(self):
        _, a, _ = preparado(600, semente=1)
        poucos = pd.concat([a[(a["suspeito"] == 1)], a[(a["suspeito"] == 0) & (a["variante"] == 0)], a[(a["suspeito"] == 0) & (a["variante"] == 1)].iloc[:5]])
        linha, coef = M.estimar_did(poucos, rotulo="x")
        self.assertTrue(linha["estado"].startswith("células"))
        self.assertIsNone(coef)

    def test_separacao_e_marcada_como_instavel_e_sem_ic(self):
        _, a, _ = preparado(600, semente=1)
        a = a.copy()
        a["falha"] = 0.0
        a.loc[(a["suspeito"] == 1) & (a["variante"] == 1), "falha"] = 1.0  # todas as falhas numa só célula
        linha, _ = M.estimar_did(a, rotulo="x")
        self.assertTrue(linha["estado"].startswith("instável"), linha["estado"])
        self.assertTrue(np.isnan(linha["did_lo"]) and np.isnan(linha["did_hi"]))
        self.assertEqual(M.classificar_h2(linha["did"], linha["did_lo"], linha["did_hi"]), "indeterminada")

    def test_escalas_concordam_com_efeito_forte(self):
        _, a, _ = preparado(1500, semente=3, efeito_susp_pp=30.0, efeito_ctrl_pp=0.0)
        tab = M.escalas(a)
        self.assertEqual(len(tab), 8)
        self.assertEqual(set(tab["leitura"]), {"maior nos suspeitos"})
        self.assertEqual(set(tab["estado"]), {"ok"})

    def test_sensibilidades_e_secundarias_rodam(self):
        d, a, _ = preparado(900, semente=12)
        sens = M.sensibilidades(d, a, D.mascara)
        self.assertEqual(len(sens), 9)
        self.assertTrue(sens["did"].notna().all())
        self.assertEqual(int(sens.loc[0, "n"]), len(a))
        self.assertEqual(int(sens.loc[sens["rotulo"].str.startswith("Só `reps`"), "n"].iloc[0]), int((a["reps"] >= 5).sum()))
        tipo = M.por_tipo(a)
        self.assertEqual(sorted(tipo["rotulo"]), sorted(S.TIPOS))
        self.assertIsNone(M.por_dimensao(a))
        sub = M.por_subgrupo(a)
        self.assertEqual(len(sub), 5)
        por_dobro, faixas = M.dose_resposta(a)
        self.assertEqual(len(faixas), P.DOSE_FAIXAS)
        self.assertEqual(int(faixas["n"].sum()), len(a))
        self.assertTrue(por_dobro["lo"] < por_dobro["razao"] < por_dobro["hi"])
        c = M.custo(D.analise(d, incluir_ruins=True), a, M.estimar_did(a, rotulo="x")[0])
        self.assertEqual(c["variante_ruim"], 0)
        self.assertGreater(c["tempo_extra_s"], 0)  # as variantes sintéticas demoram 15% mais

    def test_sensibilidades_mexem_so_no_que_dizem(self):
        df, _ = S.simular(500, semente=13, p_ruim=0.1)
        df.loc[7, "event_id"] = "3ceb41c0" + df.loc[7, "event_id"][8:]
        d = D.preparar(df, S.PERFIL_TESTE)
        a = D.analise(d)
        n_ruins = int(((d["arm"] == "variant") & (d["flag_bad"] == 1)).sum())
        self.assertGreater(n_ruins, 10)
        sens = M.sensibilidades(d, a, D.mascara).set_index("rotulo")
        self.assertEqual(int(sens.loc["Principal", "n"]), 500 - n_ruins)
        self.assertEqual(int(sens.loc["Incluir eventos de variante ruim", "n"]), 500)
        excluido = int(sens.loc["Sem o evento da nota editada (desvios.md, entrada 4)", "n"])
        self.assertEqual(excluido, len(a) - (1 if df.loc[7, "flag_bad"] != 1 else 0))

    def test_precisao_e_ritmo(self):
        p = D.precisao_prevista({"a": 250, "b": 250, "c": 250, "d": 250}, 0.1, 1000)
        self.assertAlmostEqual(p["ep_pp"], 3.795, places=2)
        self.assertAlmostEqual(p["mde_pp"], 10.63, places=1)
        self.assertAlmostEqual(D.precisao_prevista({"a": 125, "b": 125, "c": 125, "d": 125}, 0.1, 1000)["ep_pp"], p["ep_pp"], places=6)  # só importa a proporção das células
        df, _ = S.simular(200, semente=2)
        d = D.preparar(df, S.PERFIL_TESTE)
        por_dia, info = D.ritmo(D.validos(d), datetime.date(2026, 11, 1))
        self.assertEqual(int(por_dia["validos"].sum()), 200)
        self.assertEqual(info["n"], 200)
        self.assertGreater(info["ritmo_7d"], 0)


@SKIP
class TestE3(unittest.TestCase):
    def test_prefixo_minimo_identificador(self):
        palavras = [("a", "b", "c"), ("a", "b", "d"), ("a", "x"), ("z",), ("a", "b", "c"), ()]
        # 0 e 4 são iguais (vale o tamanho); 1 se separa de 0 só na 3ª palavra; 2 na 2ª; 3 na 1ª; vazio vale 0
        self.assertEqual(E.prefixo_minimo(palavras), [3, 3, 2, 1, 3, 0])
        self.assertEqual(E.prefixo_minimo([("a", "b"), ("a", "b", "c")]), [2, 3])  # prefixo de outro enunciado não se distingue: vale o tamanho

    def test_texto_visivel_sem_marcadores_e_tamanho(self):
        self.assertEqual(E.texto_visivel("Tecido [...1] é  [...2] e mais"), "Tecido é e mais")
        with tempfile.TemporaryDirectory() as t:
            caminho = os.path.join(t, "notas.jsonl")
            with open(caminho, "w", encoding="utf-8") as f:
                for i, q in enumerate(["Tecido [...1] é [...2] e mais", "Tecido após [...]", "Outro assunto [...]"]):
                    f.write(json.dumps({"note_id": 100 + i, "question_text": q}) + "\n")
            n = E.ler_notas(caminho)
        self.assertEqual(n.loc["100", "chars"], len("Tecido é e mais"))
        self.assertEqual(list(n["pmi"]), [2, 2, 1])  # "tecido é" / "tecido após" / "outro"

    def test_auc(self):
        self.assertAlmostEqual(E.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.4, 0.35, 0.8])), 0.75)
        self.assertAlmostEqual(E.auc(np.array([0, 1, 0, 1]), np.array([1.0, 1.0, 1.0, 1.0])), 0.5)
        self.assertTrue(np.isnan(E.auc(np.array([1, 1]), np.array([0.2, 0.9]))))

    def _dados(self, n=500, forca=1.5, semente=1):
        rng = np.random.default_rng(semente)
        z = rng.normal(size=n)
        v = pd.DataFrame({"nota": rng.integers(0, n // 2, n).astype(str), "log_reps": rng.normal(size=n), "z_tempo": z, "log_pmi": rng.normal(size=n), "n_blanks": rng.integers(1, 4, n).astype(float)})
        v["falha"] = (rng.random(n) < 1 / (1 + np.exp(-(-1.8 + forca * z)))).astype(float)
        return v

    def test_validacao_cruzada_acha_o_sinal_que_existe(self):
        v = self._dados(forca=1.5)
        y = v["falha"].to_numpy()
        escore = E.auc(y, E.previsao_cv(v, ["log_reps", "z_tempo", "log_pmi", "n_blanks"], repeticoes=5, semente=2))
        base = E.auc(y, E.previsao_cv(v, ["log_reps"], repeticoes=5, semente=2))
        self.assertGreater(escore, 0.70)
        self.assertLess(base, 0.60)

    def test_validacao_cruzada_nao_inventa_sinal(self):
        v = self._dados(forca=0.0)
        y = v["falha"].to_numpy()
        escore = E.auc(y, E.previsao_cv(v, ["log_reps", "z_tempo", "log_pmi", "n_blanks"], repeticoes=5, semente=2))
        self.assertLess(escore, 0.60)

    def test_a_mesma_nota_nunca_esta_no_treino_e_no_teste(self):
        rng = np.random.default_rng(3)
        notas = rng.integers(0, 120, 700).astype(str)
        bloco = E.blocos_por_nota(notas, 5, rng)
        for n in np.unique(notas):
            self.assertEqual(len(set(bloco[notas == n])), 1)  # todos os eventos da nota no mesmo bloco
        por_bloco = [len(set(notas[bloco == b])) for b in range(5)]
        self.assertLessEqual(max(por_bloco) - min(por_bloco), 1)
        self.assertEqual(sum(por_bloco), len(np.unique(notas)))

    def test_ponta_a_ponta_com_texto_sintetico(self):
        d, a, _ = preparado(900, semente=21)
        with tempfile.TemporaryDirectory() as t:
            caminho = os.path.join(t, "notas.jsonl")
            df, _ = S.simular(900, semente=21)
            S.gravar_notas(df, caminho, 21)
            r = E.e3(d, a, E.ler_notas(caminho), n_boot=100, repeticoes=3)
        self.assertEqual(r["estado"], "ok")
        self.assertEqual(r["sem_texto_ou_tempo"], 0)
        self.assertEqual(len(r["sinais"]), len(E.SINAIS))
        for k in ("auc_escore", "auc_baseline"):
            self.assertTrue(0.0 <= r[k] <= 1.0)
        self.assertLess(r["auc_escore_ic"][0], r["auc_escore"] + 0.2)

    def test_poucas_falhas_nao_estimam(self):
        d, a, _ = preparado(300, semente=2)
        a = a.copy()
        a["falha"] = 0.0
        with tempfile.TemporaryDirectory() as t:
            caminho = os.path.join(t, "notas.jsonl")
            df, _ = S.simular(300, semente=2)
            S.gravar_notas(df, caminho, 2)
            r = E.e3(d, a, E.ler_notas(caminho), n_boot=50, repeticoes=2)
        self.assertTrue(r["estado"].startswith("insuficiente"))


@SKIP
class TestLinhaDeComando(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.saida = os.path.join(self.tmp.name, "saida")
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop(P.PERFIL_ENV, None)
        self.addCleanup(self.env.stop)

    def pasta_unica(self):
        pastas = [p for p in Path(self.saida).iterdir() if p.is_dir()]
        self.assertEqual(len(pastas), 1)
        return pastas[0]

    def test_monitor_so_conta_e_nao_olha_o_desfecho(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 600, semente=2, efeito_susp_pp=30.0, efeito_ctrl_pp=0.0)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 3)):
            rc, _ = rodar_cli(["monitor", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida])
        self.assertEqual(rc, 0)
        pasta = self.pasta_unica()
        texto = (pasta / "relatorio.md").read_text(encoding="utf-8")
        titulos = [l for l in texto.splitlines() if l.startswith("## ")]
        self.assertEqual(titulos, ["## Fluxo dos eventos", "## Eventos da análise por célula", "## Equilíbrio das covariáveis entre os braços", "## Qualidade e integridade", "## Ritmo e projeção"])
        for proibido in ("DiD =", "Falha no original", "Efeito da variante", "Conclusão", "razão de chances", "Razão de chances"):
            self.assertNotIn(proibido, texto)
        dados = json.loads((pasta / "monitor.json").read_text(encoding="utf-8"))
        self.assertEqual(set(dados), {"fluxo", "verificacoes", "ritmo", "sorteios", "variantes", "precisao"})
        self.assertFalse((pasta / "tabelas" / "taxas_celulas.csv").exists())
        if F.disponivel():
            self.assertTrue((pasta / "figuras" / "ritmo.png").exists())
            self.assertFalse((pasta / "figuras" / "celulas.png").exists())  # a figura das células mostra o desfecho por braço

    def test_final_recusa_antes_do_fim(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 300)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 10)):
            rc, _ = rodar_cli(["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0"])
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(self.saida))

    def test_final_com_olhada_registra_no_log_e_marca_o_relatorio(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 400)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 10)):
            rc, _ = rodar_cli(["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0", "--olhada-intermediaria", "ver se o roteiro roda"])
        self.assertEqual(rc, 0)
        log = Path(self.saida, "olhadas.log").read_text(encoding="utf-8")
        self.assertIn("ver se o roteiro roda", log)
        self.assertIn("validos=400", log)
        pasta = [p for p in Path(self.saida).iterdir() if p.is_dir()][0]
        self.assertIn("OLHADA INTERMEDIÁRIA", (pasta / "relatorio.md").read_text(encoding="utf-8"))

    def test_final_depois_do_fim_roda_sem_marca(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 600, semente=4)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 23)):
            rc, _ = rodar_cli(["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "60", "--auditoria", os.path.join(self.tmp.name, "nao_existe.json")])
        self.assertEqual(rc, 0)
        pasta = self.pasta_unica()
        texto = (pasta / "relatorio.md").read_text(encoding="utf-8")
        self.assertNotIn("OLHADA INTERMEDIÁRIA", texto)
        self.assertIn("Conclusão (seção 8.1)", texto)
        self.assertIn("Conferência por bootstrap", texto)
        r = json.loads((pasta / "resultados.json").read_text(encoding="utf-8"))
        self.assertIn(r["classe_8_1"], M.TEXTO_H2)
        self.assertTrue(r["minimos"]["ok"])
        self.assertFalse(Path(self.saida, "olhadas.log").exists())
        self.assertTrue((pasta / "tabelas" / "sensibilidades.csv").exists())

    def test_final_roda_uma_vez_e_a_segunda_exige_motivo(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 400, semente=7)
        base = ["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0"]
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 23)):
            self.assertEqual(rodar_cli(base)[0], 0)
            pastas = [p for p in Path(self.saida).iterdir() if p.is_dir()]
            self.assertEqual(rodar_cli(base)[0], 2)  # segunda rodada sem motivo
            self.assertEqual([p for p in Path(self.saida).iterdir() if p.is_dir()], pastas)
            self.assertEqual(rodar_cli(base + ["--refazer", "   "])[0], 2)  # motivo vazio não vale
            self.assertEqual(rodar_cli(base + ["--refazer", "corrigi um erro de leitura"])[0], 0)
        linhas = Path(self.saida, "finais.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(linhas), 2)
        self.assertIn("primeira rodada", linhas[0])
        self.assertIn("corrigi um erro de leitura", linhas[1])
        self.assertIn("validos=400", linhas[0])

    def test_olhada_nao_conta_como_rodada_final(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 400, semente=8)
        base = ["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0"]
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 10)):
            self.assertEqual(rodar_cli(base + ["--olhada-intermediaria", "teste"])[0], 0)
        self.assertFalse(Path(self.saida, "finais.log").exists())
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 23)):
            self.assertEqual(rodar_cli(base)[0], 0)
        self.assertEqual(len(Path(self.saida, "finais.log").read_text(encoding="utf-8").splitlines()), 1)

    def test_final_no_alvo_de_eventos_nao_precisa_de_motivo(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 1000, semente=5)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 10)):
            rc, _ = rodar_cli(["final", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0"])
        self.assertEqual(rc, 0)

    def test_cego_marca_o_relatorio_e_nao_acha_o_efeito(self):
        caminho, _, verdade = csv_sintetico(self.tmp.name, 1500, semente=6, efeito_susp_pp=25.0, efeito_ctrl_pp=0.0)
        rc, _ = rodar_cli(["cego", "--csv", caminho, "--perfil", S.PERFIL_TESTE, "--saida", self.saida, "--bootstrap", "0", "--semente", "3"])
        self.assertEqual(rc, 0)
        pasta = self.pasta_unica()
        self.assertTrue(pasta.name.endswith("_cego"))
        texto = (pasta / "relatorio.md").read_text(encoding="utf-8")
        self.assertIn("TESTE CEGO", texto)
        r = json.loads((pasta / "resultados.json").read_text(encoding="utf-8"))
        self.assertLess(abs(r["primario"]["did"]), 10.0)  # o efeito de 25 pp foi destruído pelo embaralhamento
        self.assertLessEqual(r["primario"]["did_lo"], 0.0)
        self.assertGreaterEqual(r["primario"]["did_hi"], 0.0)

    def test_sintetico_confere_com_o_efeito_verdadeiro(self):
        rc, _ = rodar_cli(["sintetico", "--saida", self.saida, "--n", "800", "--bootstrap", "0"])
        self.assertEqual(rc, 0)
        pasta = [p for p in Path(self.saida).iterdir() if p.is_dir() and p.name.endswith("_sintetico")][0]
        r = json.loads((pasta / "resultados.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(r["verdade"]["did"], 12.0, places=1)
        self.assertEqual(r["e3"]["estado"], "ok")
        self.assertIn("E3: sinais de candidato", (pasta / "relatorio.md").read_text(encoding="utf-8"))
        if F.disponivel():
            self.assertTrue((pasta / "figuras" / "celulas.png").stat().st_size > 1000)
            self.assertTrue((pasta / "figuras" / "did_forest.png").stat().st_size > 1000)
            self.assertIn("](figuras/celulas.png)", (pasta / "relatorio.md").read_text(encoding="utf-8"))
        self.assertIn("Conferência com o efeito verdadeiro", (pasta / "relatorio.md").read_text(encoding="utf-8"))

    def test_perfil_e_obrigatorio_e_pode_vir_do_ambiente(self):
        caminho, _, _ = csv_sintetico(self.tmp.name, 300)
        with self.assertRaises(SystemExit):
            rodar_cli(["monitor", "--csv", caminho, "--saida", self.saida])
        with mock.patch.dict(os.environ, {P.PERFIL_ENV: S.PERFIL_TESTE}), mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 3)):
            rc, _ = rodar_cli(["monitor", "--csv", caminho, "--saida", self.saida])
        self.assertEqual(rc, 0)

    def test_nome_do_perfil_nao_vai_para_os_arquivos_de_saida(self):
        segredo = "perfil-secreto-xyz"
        caminho, _, _ = csv_sintetico(self.tmp.name, 500, perfil=segredo)
        with mock.patch.object(cli, "hoje", return_value=datetime.date(2026, 11, 23)):
            self.assertEqual(rodar_cli(["monitor", "--csv", caminho, "--perfil", segredo, "--saida", self.saida])[0], 0)
            self.assertEqual(rodar_cli(["final", "--csv", caminho, "--perfil", segredo, "--saida", self.saida, "--bootstrap", "0"])[0], 0)
        achados = 0
        for raiz, _, arquivos in os.walk(self.saida):
            for nome in arquivos:
                achados += segredo.encode("utf-8") in Path(raiz, nome).read_bytes()
                achados += segredo in nome
        self.assertEqual(achados, 0)

    def test_codigo_tem_hash_estavel(self):
        a, b = cli.info_codigo(), cli.info_codigo()
        self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual(a["versao"], P.VERSAO_ANALISE)


@SKIP
class TestConstantesDoProtocolo(unittest.TestCase):
    """As constantes de prereg.py precisam bater com o protocolo e com o que o add-on grava."""

    def test_valores_do_protocolo(self):
        protocolo = (ROOT / "docs" / "protocolo.md").read_text(encoding="utf-8")
        self.assertIn(P.BANCO_HASH, protocolo)
        self.assertIn("28/10", protocolo)
        self.assertIn("22/11", protocolo)
        self.assertEqual((P.JANELA_INICIO, P.JANELA_FIM), (datetime.date(2026, 10, 28), datetime.date(2026, 11, 22)))
        self.assertEqual((P.SUSPEITO_REPS, P.SUSPEITO_ULTIMA_RESPOSTA, P.LIMIAR_PP, P.MIN_EVENTOS, P.MIN_POR_ESTRATO, P.ALVO_EVENTOS), (5, 3, 10.0, 300, 100, 1000))

    def test_colunas_lidas_existem_no_csv_do_addon(self):
        spec = importlib.util.spec_from_file_location("dfc_core_teste", ROOT / "addon" / "dfc_probe" / "core.py")
        core = importlib.util.module_from_spec(spec)
        sys.modules["dfc_core_teste"] = core
        spec.loader.exec_module(core)
        exportadas = set(core.COLUMN_NAMES) | set(core.EXPORT_EXTRA)
        self.assertEqual(set(D.OBRIGATORIAS) - exportadas, set())

    def test_prob_de_variante_igual_a_do_addon(self):
        self.assertEqual(_variants_do_addon().VARIANT_PROBABILITY, 0.5)


if __name__ == "__main__":
    unittest.main()
