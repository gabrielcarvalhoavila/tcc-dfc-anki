"""Roteiro de verificação dentro do Anki real, usado só por scripts/anki_teste.ps1 -Auto no Anki isolado de teste.

NÃO faz parte do DFC Probe e nunca é instalado no Anki de estudo. Roda quando o perfil abre, confere os menus, os ganchos, as telas, a geração em lote
(com LLM falso ou, com DFC_SELFTEST_LIVE=1, com a chave configurada) e a troca de variante na tela de revisão de verdade; grava o resultado em
DFC_SELFTEST_OUT (JSON) e fecha o Anki.
"""
import json
import os
import re
import sys
import time
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QApplication, QTimer

OUT = os.environ.get("DFC_SELFTEST_OUT", "")
SHOTS = os.path.join(os.path.dirname(OUT), "telas") if OUT else ""
LIVE = os.environ.get("DFC_SELFTEST_LIVE") == "1"
DECK = "Biologia (teste)"
results = {"live": LIVE}


def save() -> None:
    if OUT:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1, default=str)


def step(name, fn):
    try:
        results[name] = fn()
    except Exception:
        results[name] = {"ERRO": traceback.format_exc()}
    save()


def addon():
    return sys.modules["dfc_probe"]


def shot(widget, name) -> str:
    os.makedirs(SHOTS, exist_ok=True)
    QApplication.processEvents()
    path = os.path.join(SHOTS, name + ".png")
    widget.grab().save(path)
    return path


def check_menus_and_hooks():
    menu = next(a.menu() for a in mw.form.menuTools.actions() if a.menu() and a.menu().title() == "DFC Probe")
    sub = next(a.menu() for a in menu.actions() if a.menu())
    free_hooks = [h.__name__ for h in gui_hooks.card_will_show._hooks]
    return {
        "versao": addon().core.ADDON_VERSION,
        "itens": [a.text() for a in menu.actions() if a.text()],
        "submenu": sub.title(),
        "submenu_itens": [a.text() for a in sub.actions()],
        "card_will_show": free_hooks,
        "gancho_do_baralho": any(getattr(h, "__module__", "") == "dfc_probe" for h in gui_hooks.deck_browser_will_show_options_menu._hooks),
        "usolivre_carregado": addon()._free is not None,
        "erros_log": os.path.exists(addon().ERR_LOG),
    }


def check_deck_menu():
    """A engrenagem do baralho na tela inicial: o gancho real, com um QMenu real."""
    from aqt.qt import QMenu

    menu = QMenu(mw)
    gui_hooks.deck_browser_will_show_options_menu(menu, mw.col.decks.id(DECK))
    return [a.text() for a in menu.actions()]


def check_dialogs():
    from dfc_probe import batch, free, free_ui

    ui = free_ui._widgets()
    fm = addon()._free
    out = {}
    d = ui.SettingsDialog(mw, free.Settings(enabled=True, probability=40, deck_ids=[mw.col.decks.id(DECK)]), free_ui.deck_choices(mw.col), fm.status_line(), lambda: None, lambda: None)
    d.show()
    out["configurar"] = shot(d, "configurar")
    d.close()
    b = ui.BatchDialog(mw, free_ui.deck_choices(mw.col), mw.col.decks.id(DECK), lambda p: None, lambda p, plan: None)
    b.show()
    b.show_plan(batch.Plan(todo=[{"note_id": 1}] * 12, examined=18, ineligible=2, already=4))
    out["lote"] = shot(b, "lote")
    b.close()
    return out


def run_batch_then(next_step):
    from dfc_probe import anki_adapter, batch, core, free_ui, live
    import aqt.utils

    fm = addon()._free
    bank = fm.bank()
    records = anki_adapter.collect_records(mw.col, mw.col.decks.id(DECK), core.note_to_record)
    options = batch.Options(workers=2, max_notes=50)
    plan = batch.make_plan(records, bank, set(), options)
    results["lote_plano"] = {"notas": len(records), "para_gerar": len(plan.todo), "inelegiveis": plan.ineligible, "motivos": dict(plan.reasons)}
    if LIVE:
        gen, judge = live.build_clients(addon()._config(), batch=True)
    else:
        from dfc_probe.dfc_pipeline.llm import FakeLLM

        gen, judge = FakeLLM(), FakeLLM()
    shown = []
    original = aqt.utils.showText
    aqt.utils.showText = lambda text, **kw: shown.append(text)  # o resumo final abriria uma janela modal
    started = time.time()

    def poll():
        if shown or time.time() - started > 240:
            aqt.utils.showText = original
            results["lote_resumo"] = shown[0] if shown else "TEMPO ESGOTADO"
            results["lote_banco"] = bank.stats()
            results["lote_segundos"] = round(time.time() - started, 1)
            save()
            next_step()
        else:
            QTimer.singleShot(500, poll)

    free_ui.run_batch(mw, bank, gen, judge, plan, options)
    QTimer.singleShot(500, poll)


def review_cards(count, done):
    from dfc_probe import free

    fm = addon()._free
    bank = fm.bank()
    fm.save_settings(free.Settings(enabled=True, probability=100, badge=False))
    mw.col.decks.set_current(mw.col.decks.id(DECK))
    mw.moveToState("review")
    seen = []
    marked = []

    def norm(text):
        return re.sub(r"\[\.\.\.\d*\]", "[...]", text or "")

    def prefix(text):
        """Começo do texto da variante até a primeira lacuna: é o que aparece igual na pergunta e na resposta (a resposta troca as lacunas pelas respostas)."""
        return norm(text).split("[...]")[0].strip()[:30]

    def read(js, cb):
        mw.reviewer.web.evalWithCallback(js, cb)

    def next_card():
        if len(seen) >= count or mw.reviewer.card is None:
            results["revisao"] = seen
            results["tecla_x"] = marked
            save()
            done()
            return
        card = mw.reviewer.card
        entry = bank.entry(card.nid)
        texts = [prefix(v.get("text")) for v in (entry or {}).get("variants", []) if v.get("text")]

        def got_question(q):
            shown_variant = next((t for t in texts if t and t in norm(q)), None)
            if shown_variant and not marked:
                before = len(bank.banned)
                addon()._mark_bad_current()  # o mesmo que a tecla x
                marked.append({"banidas_antes": before, "banidas_depois": len(bank.banned)})

            def got_answer(a):
                row = {"nid": card.nid, "tem_banco": bool(entry), "variante_na_pergunta": bool(shown_variant), "variante_na_resposta": bool(shown_variant and shown_variant in norm(a)),
                       "pergunta": (q or "")[:140], "reps": card.reps}
                seen.append(row)
                if len(seen) == 1:
                    row["tela"] = shot(mw, "revisao_resposta")
                mw.reviewer._answerCard(3)
                QTimer.singleShot(1500, next_card)

            mw.reviewer._showAnswer()
            QTimer.singleShot(1200, lambda: read("document.getElementById('qa').innerText", got_answer))
            if len(seen) == 0:
                results["tela_pergunta"] = shot(mw, "revisao_pergunta")

        read("document.getElementById('qa').innerText", got_question)

    QTimer.singleShot(2500, next_card)


def finish():
    ev = addon()._store.rows() if addon()._store else []
    results["eventos"] = [{"draw_note": r.get("draw_note"), "arm": r.get("arm"), "reps": r.get("reps")} for r in ev]
    results["erros_log"] = os.path.exists(addon().ERR_LOG)
    results["terminou"] = True
    save()
    QTimer.singleShot(800, mw.close)


def on_profile_open():
    def go():
        step("menus_e_ganchos", check_menus_and_hooks)
        step("menu_do_baralho", check_deck_menu)
        step("telas", check_dialogs)
        run_batch_then(lambda: review_cards(6, finish))

    QTimer.singleShot(2500, go)


gui_hooks.profile_did_open.append(on_profile_open)
