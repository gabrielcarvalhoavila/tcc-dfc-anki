"""DFC Probe: registra as revisões e, na janela do estudo, sorteia original ou variante (dependência da forma do cartão).

Nada é gravado nas notas: a variante só existe na tela, naquela exibição. Ver docs/protocolo.md no repositório do projeto.
"""
import datetime
import os
import shutil
import time
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QAction, QFileDialog, QInputDialog
from aqt.utils import showInfo, tooltip

from . import core, variants
from .anki_adapter import anki_version, make_revlog_matcher, make_snapshot_fn, render_pair, scheduler_name

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILES = os.environ.get("DFC_PROBE_USER_FILES") or os.path.join(ADDON_DIR, "user_files")
DB_PATH = os.path.join(USER_FILES, "dfc_events.sqlite3")
ERR_LOG = os.path.join(USER_FILES, "dfc_errors.log")
SALT_PATH = os.path.join(USER_FILES, "salt.txt")
BANK_PATH = os.path.join(USER_FILES, "variant_bank.json")


def _log_error() -> None:
    try:
        os.makedirs(USER_FILES, exist_ok=True)
        with open(ERR_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + traceback.format_exc() + "\n")
    except Exception:
        pass


def _safe(fn):
    """Nenhum erro do add-on pode atrapalhar a revisão."""

    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            _log_error()
            return None

    return wrapper


def _config() -> dict:
    return mw.addonManager.getConfig(__name__) or {}


def _enabled() -> bool:
    return bool(_config().get("enabled", True))


_store = None
_tracker = None
try:
    _store = core.EventStore(DB_PATH)
    _tracker = core.EventTracker(_store, make_snapshot_fn(mw), anki_version())
except Exception:
    _log_error()

_bank = None
try:
    if os.path.exists(BANK_PATH):
        _bank = variants.Bank.load(BANK_PATH)
except Exception:
    _log_error()


def _draw_enabled() -> bool:
    return bool(_config().get("draw_enabled", True))


def _window_ok() -> bool:
    cfg = _config()
    return variants.in_window(datetime.date.today(), str(cfg.get("draw_start", "2026-11-02")), str(cfg.get("draw_end", "2026-11-22")))


# Teclas globais do Anki (setupKeys, aqt/main.py): valem em todas as telas e, repetidas, anulam o atalho do add-on.
ANKI_GLOBAL_KEYS = {"d", "s", "a", "b", "t", "y", "shift+t", "ctrl+:"}
FALLBACK_KEY = "x"
_warned_key = []


def _bad_key(shortcuts=()):
    """(tecla a usar, tecla configurada que conflita ou None). Conflito: usa `x`; se ele também estiver ocupado, nenhuma."""
    key = str(_config().get("bad_shortcut", FALLBACK_KEY) or "").strip()
    taken = ANKI_GLOBAL_KEYS | {item[0].lower() for item in shortcuts if isinstance(item[0], str)}
    if key and key.lower() in taken:
        return (FALLBACK_KEY if FALLBACK_KEY not in taken else ""), key
    return key, None


@_safe
def _on_question(card) -> None:
    if _tracker is not None and _enabled():
        _tracker.question_shown(card)


@_safe
def _on_answer_shown(card) -> None:
    if _tracker is not None and _enabled():
        _tracker.answer_shown(card)


@_safe
def _on_answered(reviewer, card, ease) -> None:
    if _tracker is not None and _enabled():
        _tracker.answered(card, ease)


def _prepare_exposure(p: dict, card) -> None:
    """Decide o braço da exposição e prepara pergunta e resposta com a variante (uma vez por exposição)."""
    extra, snap = p["extra"], p["snap"]
    entry = _bank.entry(card.nid) if _bank is not None else None
    note = mw.col.get_note(card.nid) if entry is not None else None
    d = variants.decide(
        entry,
        card_ord=card.ord,
        fields_hash_now=variants.fields_hash(note.fields) if note is not None else "",
        reps=snap.get("reps"),
        same_day=snap.get("same_day"),
        draw_on=_draw_enabled(),
        window_ok=_window_ok(),
        last_shown=_store.shown_variants(card.id) if entry is not None else [],
        event_id=p["event_id"],
        salt=core.get_salt(SALT_PATH),
        bank_ok=_bank is None or not _bank.is_fake or bool(_config().get("allow_fake_bank", False)),
    )
    prior = p.get("inherit")
    if d.arm is not None and prior and prior.get("arm") is not None:
        # Ctrl+Z: o cartão volta no mesmo estado (mesmo reps), então é a mesma exposição: mantém braço, variante e semente
        again = next((v for v in entry["variants"] if v["id"] == prior.get("variant_id")), None)
        if prior["arm"] == "original" or again is not None:
            d = variants.Decision(prior["arm"], "undo_redo", again, prior.get("draw_seed"))
    extra.update(arm=d.arm, draw_note=d.reason, draw_seed=d.seed, bank_hash=_bank.hash if _bank is not None else None)
    if d.arm is None:
        return
    extra["shown_ok"] = 1
    if d.arm == "variant":
        extra.update(variant_id=d.variant["id"], variant_type=d.variant["type"])
        try:
            value, needles = variants.field_value(entry, d.variant)
            orig_q, orig_a = render_pair(mw.col, card)
            var_q, var_a = render_pair(mw.col, card, entry["q_field"], value)
            if var_q != orig_q and all(n in var_q for n in needles):
                p["render"] = {"orig_q": orig_q, "var_q": var_q, "orig_a": orig_a, "var_a": var_a}
            else:
                extra.update(shown_ok=0, draw_note="render_failed")
        except Exception:
            _log_error()
            extra.update(shown_ok=0, draw_note="render_error")


def _on_card_will_show(text, card, kind):
    """Troca a pergunta (e depois a resposta) pela variante sorteada. Em qualquer falha, devolve o texto original."""
    try:
        if kind not in ("reviewQuestion", "reviewAnswer") or _tracker is None or _store is None or not _enabled():
            return text
        if kind == "reviewQuestion":
            p = _tracker.begin_exposure(card)
            if "arm" not in p["extra"]:
                _prepare_exposure(p, card)
        else:
            p = _tracker.pending
            if not p or p["card_id"] != card.id:
                return text
        out = text
        r = p["render"]
        if r is not None and (kind == "reviewQuestion" or p["extra"].get("shown_ok") == 1):
            old, new = (r["orig_q"], r["var_q"]) if kind == "reviewQuestion" else (r["orig_a"], r["var_a"])
            if old in text:
                out = text.replace(old, new, 1)
            else:
                p["extra"].update(shown_ok=0, draw_note="template_mismatch" if kind == "reviewQuestion" else "answer_mismatch")
        if kind == "reviewQuestion" and p["extra"].get("arm") is not None:
            p["extra"]["shown_hash"] = variants.sha1_short(out)
        return out
    except Exception:
        _log_error()
        return text


@_safe
def _mark_bad_current() -> None:
    p = _tracker.pending if _tracker is not None else None
    if not p or p["extra"].get("arm") != "variant":
        tooltip("DFC Probe: esta exibição não mostra uma variante.")
        return
    p["extra"]["flag_bad"] = 1
    tooltip("DFC Probe: variante marcada como ruim.")


@_safe
def _mark_bad_last() -> None:
    row = _store.last_event() if _store is not None else None
    if not row or row.get("arm") != "variant":
        tooltip("DFC Probe: a última resposta não foi de uma variante.")
        return
    _store.mark_bad(row["event_id"])
    tooltip("DFC Probe: última variante marcada como ruim.")


@_safe
def _on_shortcuts(state, shortcuts) -> None:
    if state != "review":
        return
    key, conflict = _bad_key(shortcuts)
    if conflict and conflict not in _warned_key:
        _warned_key.append(conflict)
        tooltip(f"DFC Probe: '{conflict}' já é tecla do Anki; variante ruim em '{key}'." if key else f"DFC Probe: '{conflict}' já é tecla do Anki; troque bad_shortcut.")
    if key:
        shortcuts.append((key, _mark_bad_current))


@_safe
def _on_context_menu(reviewer, menu) -> None:
    action = menu.addAction("Variante ruim (DFC Probe)")
    action.triggered.connect(lambda _checked=False: _mark_bad_current())


gui_hooks.reviewer_did_show_question.append(_on_question)
gui_hooks.reviewer_did_show_answer.append(_on_answer_shown)
gui_hooks.reviewer_did_answer_card.append(_on_answered)
gui_hooks.card_will_show.append(_on_card_will_show)
gui_hooks.state_shortcuts_will_change.append(_on_shortcuts)
gui_hooks.reviewer_will_show_context_menu.append(_on_context_menu)


@_safe
def _toggle(checked) -> None:
    cfg = _config()
    cfg["enabled"] = bool(checked)
    mw.addonManager.writeConfig(__name__, cfg)
    tooltip("DFC Probe: registro " + ("ligado" if checked else "desligado"))


@_safe
def _toggle_draw(checked) -> None:
    cfg = _config()
    cfg["draw_enabled"] = bool(checked)
    mw.addonManager.writeConfig(__name__, cfg)
    tooltip("DFC Probe: sorteio " + ("ligado" if checked else "desligado"))


@_safe
def _import_bank() -> None:
    global _bank
    path, _ = QFileDialog.getOpenFileName(mw, "Importar banco de variantes", "", "JSON (*.json)")
    if not path:
        return
    try:
        bank = variants.Bank.load(path)
    except (OSError, ValueError) as e:
        showInfo(f"Não foi possível importar: {e}")
        return
    os.makedirs(USER_FILES, exist_ok=True)
    shutil.copyfile(path, BANK_PATH)
    _bank = bank
    skipped = f"\n{bank.skipped} entradas ignoradas por formato inválido." if bank.skipped else ""
    showInfo(f"Banco importado: {len(bank.notes)} notas, {bank.n_variants} variantes (hash {bank.hash}).{skipped}")


@_safe
def _status() -> None:
    n = _store.count() if _store else 0
    sched = scheduler_name(mw.col) if mw.col is not None else None
    cfg = _config()
    bank = f"{len(_bank.notes)} notas, {_bank.n_variants} variantes (hash {_bank.hash})" if _bank is not None else "nenhum (importe pelo menu)"
    key, conflict = _bad_key()
    key_text = (key or "nenhum") + (f" ('{conflict}' configurada conflita com o Anki)" if conflict else "")
    if _bank is not None and _bank.is_fake:
        bank += " — BANCO DE TESTE, variantes falsas: " + ("permitido por allow_fake_bank" if cfg.get("allow_fake_bank") else "não sorteia")
    showInfo(
        f"DFC Probe {core.ADDON_VERSION}\n\nEventos registrados: {n}\nBanco de eventos: {DB_PATH}\n"
        f"Registro: {'ligado' if _enabled() else 'desligado'}\nAgendador: {sched or 'desconhecido'}\n"
        f"Banco de variantes: {bank}\n"
        f"Sorteio: {'ligado' if _draw_enabled() else 'desligado'} (janela {cfg.get('draw_start')} a {cfg.get('draw_end')}; hoje {'dentro' if _window_ok() else 'fora'})\n"
        f"Atalho de variante ruim: {key_text}\nErros: {ERR_LOG}"
    )


@_safe
def _export_events() -> None:
    path, _ = QFileDialog.getSaveFileName(mw, "Exportar eventos", "dfc_eventos.csv", "CSV (*.csv)")
    if not path:
        return
    anonymize = bool(_config().get("anonymize_export", False))
    salt = core.get_salt(SALT_PATH) if anonymize else b""
    matcher = make_revlog_matcher(mw) if mw.col is not None else None
    n = core.export_csv(_store, path, anonymize=anonymize, salt=salt, revlog_match=matcher)
    tooltip(f"{n} eventos exportados" + (" (IDs anonimizados)" if anonymize else ""))


@_safe
def _export_notes() -> None:
    if mw.col is None:
        showInfo("Abra um perfil antes de exportar.")
        return
    query, ok = QInputDialog.getText(mw, "DFC Probe", "Busca do Anki (vazio = todas as notas):")
    if not ok:
        return
    path, _ = QFileDialog.getSaveFileName(mw, "Exportar notas", "dfc_notas.jsonl", "JSONL (*.jsonl)")
    if not path:
        return
    records = []
    for nid in mw.col.find_notes(query.strip()):
        note = mw.col.get_note(nid)
        decks = [mw.col.decks.name(c.odid or c.did) for c in note.cards()]
        records.append(core.note_to_record(nid, note.guid, note.note_type()["name"], note.items(), note.tags, decks))
    n = core.write_jsonl(path, records)
    tooltip(f"{n} notas exportadas")


def _setup_menu() -> None:
    menu = mw.form.menuTools.addMenu("DFC Probe")
    toggle = QAction("Registro ativo", mw)
    toggle.setCheckable(True)
    toggle.setChecked(_enabled())
    toggle.toggled.connect(_toggle)
    menu.addAction(toggle)
    draw = QAction("Sorteio ativo", mw)
    draw.setCheckable(True)
    draw.setChecked(_draw_enabled())
    draw.toggled.connect(_toggle_draw)
    menu.addAction(draw)
    for label, fn in (
        ("Status", _status),
        ("Importar banco de variantes...", _import_bank),
        ("Marcar a última resposta como variante ruim", _mark_bad_last),
        ("Exportar eventos (CSV)...", _export_events),
        ("Exportar notas para variantes (JSONL)...", _export_notes),
    ):
        action = QAction(label, mw)
        action.triggered.connect(lambda _checked=False, f=fn: f())
        menu.addAction(action)


_safe(_setup_menu)()
