"""DFC Probe v0: registra as revisões (e o tempo até revelar) para o estudo de dependência da forma do cartão.

Esta versão só registra; não altera nenhum cartão. Ver docs/protocolo.md no repositório do projeto.
"""
import os
import time
import traceback

from aqt import gui_hooks, mw
from aqt.qt import QAction, QFileDialog, QInputDialog
from aqt.utils import showInfo, tooltip

from . import core
from .anki_adapter import anki_version, make_snapshot_fn, scheduler_name

ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
USER_FILES = os.environ.get("DFC_PROBE_USER_FILES") or os.path.join(ADDON_DIR, "user_files")
DB_PATH = os.path.join(USER_FILES, "dfc_events.sqlite3")
ERR_LOG = os.path.join(USER_FILES, "dfc_errors.log")
SALT_PATH = os.path.join(USER_FILES, "salt.txt")


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


gui_hooks.reviewer_did_show_question.append(_on_question)
gui_hooks.reviewer_did_show_answer.append(_on_answer_shown)
gui_hooks.reviewer_did_answer_card.append(_on_answered)


@_safe
def _toggle(checked) -> None:
    cfg = _config()
    cfg["enabled"] = bool(checked)
    mw.addonManager.writeConfig(__name__, cfg)
    tooltip("DFC Probe: registro " + ("ligado" if checked else "desligado"))


@_safe
def _status() -> None:
    n = _store.count() if _store else 0
    sched = scheduler_name(mw.col) if mw.col is not None else None
    showInfo(
        f"DFC Probe {core.ADDON_VERSION}\n\nEventos registrados: {n}\nBanco: {DB_PATH}\n"
        f"Registro: {'ligado' if _enabled() else 'desligado'}\nAgendador: {sched or 'desconhecido'}\nErros: {ERR_LOG}"
    )


@_safe
def _export_events() -> None:
    path, _ = QFileDialog.getSaveFileName(mw, "Exportar eventos", "dfc_eventos.csv", "CSV (*.csv)")
    if not path:
        return
    anonymize = bool(_config().get("anonymize_export", False))
    salt = core.get_salt(SALT_PATH) if anonymize else b""
    n = core.export_csv(_store, path, anonymize=anonymize, salt=salt)
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
    for label, fn in (
        ("Status", _status),
        ("Exportar eventos (CSV)...", _export_events),
        ("Exportar notas para variantes (JSONL)...", _export_notes),
    ):
        action = QAction(label, mw)
        action.triggered.connect(lambda _checked=False, f=fn: f())
        menu.addAction(action)


_safe(_setup_menu)()
