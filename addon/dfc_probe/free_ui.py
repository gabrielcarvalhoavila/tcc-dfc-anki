"""Telas do uso livre (v0.5.0): ajustes, geração em lote, banco pessoal e escolha das variantes de um cartão.

O Qt vem de `aqt.qt` e só é importado quando uma tela abre: um problema aqui nunca afeta o registro nem o sorteio do estudo.
"""
from __future__ import annotations

import dataclasses
import threading
from types import SimpleNamespace
from typing import Any, Callable, Optional
from urllib.parse import urlparse

try:
    from . import anki_adapter, batch, core, free, live
except ImportError:  # os testes carregam o módulo fora do pacote
    import anki_adapter  # type: ignore
    import batch  # type: ignore
    import core  # type: ignore
    import free  # type: ignore
    import live  # type: ignore

PREVIEW_CHARS = 110
_ui: Optional[SimpleNamespace] = None


def deck_choices(col: Any) -> list[tuple[int, str]]:
    """(id, nome) dos baralhos comuns, em ordem alfabética."""
    return sorted(((d.id, d.name) for d in col.decks.all_names_and_ids(skip_empty_default=True, include_filtered=False)), key=lambda item: item[1].lower())


def preview(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= PREVIEW_CHARS else flat[: PREVIEW_CHARS - 1].rstrip() + "…"


def _widgets() -> SimpleNamespace:
    global _ui
    if _ui is None:
        _ui = _build()
    return _ui


def _build() -> SimpleNamespace:
    from aqt.qt import (
        QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
        QPlainTextEdit, QProgressBar, QPushButton, QRadioButton, QSlider, QSpinBox, Qt, QVBoxLayout,
    )

    ok, cancel = QDialogButtonBox.StandardButton.Ok, QDialogButtonBox.StandardButton.Cancel

    def note(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        return label

    def type_group(selected: Any) -> tuple[QGroupBox, dict[str, QCheckBox]]:
        group = QGroupBox("Tipos de variante")
        grid = QGridLayout(group)
        checks: dict[str, QCheckBox] = {}
        for i, vtype in enumerate(free.ALL_TYPES):
            check = QCheckBox(free.TYPE_LABELS[vtype])
            check.setChecked(vtype in selected)
            grid.addWidget(check, i // 2, i % 2)
            checks[vtype] = check
        return group, checks

    def button_box(dialog: QDialog, ok_text: str) -> QDialogButtonBox:
        box = QDialogButtonBox(ok | cancel)
        box.button(ok).setText(ok_text)
        box.button(cancel).setText("Cancelar")
        box.accepted.connect(dialog.accept)
        box.rejected.connect(dialog.reject)
        return box

    class SettingsDialog(QDialog):
        def __init__(self, parent: Any, settings: free.Settings, decks: list[tuple[int, str]], status: str, on_generate: Callable[[], None], on_bank: Callable[[], None]):
            super().__init__(parent)
            self.setWindowTitle("DFC Probe: variantes nos meus cartões")
            self.setMinimumWidth(600)
            root = QVBoxLayout(self)
            root.addWidget(note("Com isto ligado, parte das suas revisões mostra uma variante do cartão (outro texto, a mesma resposta) no lugar do original, como no experimento. Nada é alterado nas suas notas."))
            self.enabled = QCheckBox("Mostrar variantes durante as revisões")
            self.enabled.setChecked(settings.enabled)
            root.addWidget(self.enabled)

            row = QHBoxLayout()
            row.addWidget(QLabel("Chance de aparecer uma variante em vez do original:"))
            self.slider = QSlider(Qt.Orientation.Horizontal)
            self.slider.setRange(0, 100)
            self.spin = QSpinBox()
            self.spin.setRange(0, 100)
            self.spin.setSuffix(" %")
            self.slider.valueChanged.connect(self.spin.setValue)
            self.spin.valueChanged.connect(self.slider.setValue)
            self.spin.setValue(settings.probability)
            row.addWidget(self.slider, 1)
            row.addWidget(self.spin)
            root.addLayout(row)

            group, self.type_boxes = type_group(settings.types)
            group.setTitle("Tipos de variante que podem aparecer")
            root.addWidget(group)

            decks_group = QGroupBox("Baralhos")
            decks_layout = QVBoxLayout(decks_group)
            self.all_decks = QRadioButton("Todos os baralhos")
            self.some_decks = QRadioButton("Só os selecionados (com os subbaralhos)")
            self.deck_list = QListWidget()
            self.deck_list.setMinimumHeight(90)
            chosen = set(settings.deck_ids or [])
            for deck_id, name in decks:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if deck_id in chosen else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, deck_id)
                self.deck_list.addItem(item)
            self.some_decks.toggled.connect(self.deck_list.setEnabled)
            (self.all_decks if settings.deck_ids is None else self.some_decks).setChecked(True)
            self.deck_list.setEnabled(settings.deck_ids is not None)
            for widget in (self.all_decks, self.some_decks, self.deck_list):
                decks_layout.addWidget(widget)
            root.addWidget(decks_group)

            cards_group = QGroupBox("Quais cartões")
            cards_layout = QVBoxLayout(cards_group)
            self.learning = QCheckBox("Incluir cartões em aprendizado e reaprendizado")
            self.suspects = QCheckBox("Só cartões que costumo acertar (5+ respostas, sem lapsos, última resposta Good ou Easy)")
            self.no_repeat = QCheckBox("Não repetir a mesma variante em sequência no mesmo cartão")
            self.no_same_day = QCheckBox("Não mostrar variante em cartão que já respondi hoje")
            self.badge = QCheckBox("Mostrar um selo \"variante\" no cartão (padrão: às cegas, como no estudo)")
            for check, value in ((self.learning, settings.include_learning), (self.suspects, settings.suspects_only), (self.no_repeat, settings.avoid_repeat), (self.no_same_day, settings.avoid_same_day), (self.badge, settings.badge)):
                check.setChecked(value)
                cards_layout.addWidget(check)
            root.addWidget(cards_group)

            self.status = note(status)
            root.addWidget(self.status)
            actions = QHBoxLayout()
            self.generate_button = QPushButton("Gerar variantes de um baralho...")
            self.bank_button = QPushButton("Banco pessoal...")
            self.generate_button.clicked.connect(lambda _checked=False: on_generate())
            self.bank_button.clicked.connect(lambda _checked=False: on_bank())
            actions.addWidget(self.generate_button)
            actions.addWidget(self.bank_button)
            actions.addStretch(1)
            root.addLayout(actions)
            root.addWidget(button_box(self, "Salvar"))

        def result_settings(self) -> free.Settings:
            chosen = [self.deck_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.deck_list.count()) if self.deck_list.item(i).checkState() == Qt.CheckState.Checked]
            return free.Settings(
                enabled=self.enabled.isChecked(), probability=self.spin.value(), types=[t for t in free.ALL_TYPES if self.type_boxes[t].isChecked()],
                deck_ids=None if self.all_decks.isChecked() else chosen, include_learning=self.learning.isChecked(), suspects_only=self.suspects.isChecked(),
                avoid_repeat=self.no_repeat.isChecked(), avoid_same_day=self.no_same_day.isChecked(), badge=self.badge.isChecked(),
            )

        def problem(self) -> Optional[str]:
            s = self.result_settings()
            if s.enabled and not s.types:
                return "Escolha ao menos um tipo de variante."
            if s.enabled and s.deck_ids is not None and not s.deck_ids:
                return "Escolha ao menos um baralho ou marque \"Todos os baralhos\"."
            return None

        def accept(self) -> None:
            from aqt.utils import showWarning

            message = self.problem()
            if message:
                showWarning(message, parent=self)
                return
            super().accept()

    class BatchDialog(QDialog):
        def __init__(self, parent: Any, decks: list[tuple[int, str]], deck_id: Optional[int], on_analyze: Callable[[dict[str, Any]], None], on_start: Callable[[dict[str, Any], batch.Plan], None]):
            super().__init__(parent)
            self.on_analyze, self.on_start = on_analyze, on_start
            self.plan: Optional[batch.Plan] = None
            self.setWindowTitle("DFC Probe: gerar variantes de um baralho")
            self.setMinimumWidth(600)
            root = QVBoxLayout(self)
            root.addWidget(note("A IA cria variantes de cada nota do baralho; só as aprovadas na validação do estudo vão para o seu banco pessoal. Primeiro você vê quantas notas e quanto deve custar, e só então confirma."))
            row = QHBoxLayout()
            row.addWidget(QLabel("Baralho:"))
            self.deck = QComboBox()
            for did, name in decks:
                self.deck.addItem(name, did)
            index = self.deck.findData(deck_id)
            if index >= 0:
                self.deck.setCurrentIndex(index)
            row.addWidget(self.deck, 1)
            root.addLayout(row)
            self.children_box = QCheckBox("Incluir os subbaralhos")
            self.skip_new = QCheckBox("Pular cartões novos (nunca estudados)")
            self.skip_suspended = QCheckBox("Pular cartões suspensos")
            for check in (self.children_box, self.skip_new, self.skip_suspended):
                check.setChecked(True)
                root.addWidget(check)
            group, self.type_boxes = type_group(free.ALL_TYPES)
            group.setTitle("Tipos de variante a gerar")
            root.addWidget(group)
            self.reprocess = QCheckBox("Refazer as notas que já têm variantes ou foram avaliadas sem variantes")
            root.addWidget(self.reprocess)
            limits = QHBoxLayout()
            self.max_notes = QSpinBox()
            self.max_notes.setRange(1, 5000)
            self.max_notes.setValue(batch.DEFAULT_MAX_NOTES)
            self.workers = QSpinBox()
            self.workers.setRange(1, 8)
            self.workers.setValue(batch.DEFAULT_WORKERS)
            limits.addWidget(QLabel("No máximo"))
            limits.addWidget(self.max_notes)
            limits.addWidget(QLabel("notas por vez; chamadas simultâneas:"))
            limits.addWidget(self.workers)
            limits.addStretch(1)
            root.addLayout(limits)
            self.report = QPlainTextEdit()
            self.report.setReadOnly(True)
            self.report.setMinimumHeight(130)
            self.report.setPlaceholderText("Clique em Analisar para ver quantas notas serão geradas e o custo aproximado.")
            root.addWidget(self.report)
            buttons = QHBoxLayout()
            self.analyze_button = QPushButton("Analisar")
            self.go = QPushButton("Gerar...")
            self.close_button = QPushButton("Fechar")
            self.go.setEnabled(False)
            self.analyze_button.clicked.connect(lambda _checked=False: self.analyze())
            self.go.clicked.connect(lambda _checked=False: self.start())
            self.close_button.clicked.connect(lambda _checked=False: self.reject())
            for button in (self.analyze_button, self.go):
                buttons.addWidget(button)
            buttons.addStretch(1)
            buttons.addWidget(self.close_button)
            root.addLayout(buttons)
            for check in (self.children_box, self.skip_new, self.skip_suspended, self.reprocess, *self.type_boxes.values()):
                check.toggled.connect(self.invalidate)
            for spin in (self.max_notes, self.workers):
                spin.valueChanged.connect(self.invalidate)
            self.deck.currentIndexChanged.connect(self.invalidate)

        def chosen_types(self) -> list[str]:
            return [t for t in free.ALL_TYPES if self.type_boxes[t].isChecked()]

        def params(self) -> dict[str, Any]:
            chosen = self.chosen_types()
            options = batch.Options(workers=self.workers.value(), max_notes=self.max_notes.value(), reprocess=self.reprocess.isChecked(), types=None if len(chosen) == len(free.ALL_TYPES) else chosen)
            return {"deck_id": self.deck.currentData(), "children": self.children_box.isChecked(), "skip_new": self.skip_new.isChecked(), "skip_suspended": self.skip_suspended.isChecked(), "options": options}

        def invalidate(self, *_args: Any) -> None:
            self.plan = None
            self.go.setEnabled(False)

        def analyze(self) -> None:
            if not self.chosen_types():
                self.show_error("Escolha ao menos um tipo de variante.")
                return
            self.invalidate()
            self.analyze_button.setEnabled(False)
            self.report.setPlainText("Analisando...")
            self.on_analyze(self.params())

        def show_plan(self, plan: batch.Plan) -> None:
            self.plan = plan
            self.analyze_button.setEnabled(True)
            self.report.setPlainText(batch.describe_plan(plan))
            self.go.setEnabled(bool(plan.todo))

        def show_error(self, message: str) -> None:
            self.analyze_button.setEnabled(True)
            self.report.setPlainText(message)

        def start(self) -> None:
            if self.plan is not None and self.plan.todo:
                self.on_start(self.params(), self.plan)

    class ProgressDialog(QDialog):
        def __init__(self, parent: Any, total: int, on_cancel: Callable[[], None]):
            super().__init__(parent)
            self.on_cancel, self.finished_ok = on_cancel, False
            self.setWindowTitle("DFC Probe: gerando variantes")
            self.setMinimumWidth(460)
            root = QVBoxLayout(self)
            self.bar = QProgressBar()
            self.bar.setRange(0, max(1, total))
            self.label = note(f"Começando: {total} notas...")
            self.cancel_button = QPushButton("Cancelar")
            self.cancel_button.clicked.connect(lambda _checked=False: self.request_cancel())
            root.addWidget(self.bar)
            root.addWidget(self.label)
            root.addWidget(note("Você pode continuar usando o Anki enquanto isso."))
            root.addWidget(self.cancel_button)

        def update_counts(self, s: batch.Summary) -> None:
            self.bar.setValue(s.done)
            text = f"{s.done} de {s.total} notas. Com variantes: {s.with_variants}."
            if s.errors:
                text += f" Falhas: {s.errors}."
            self.label.setText(text)

        def request_cancel(self) -> None:
            if self.cancel_button.isEnabled():
                self.cancel_button.setEnabled(False)
                self.label.setText("Cancelando: aguardando as chamadas em andamento...")
                self.on_cancel()

        def reject(self) -> None:
            if self.finished_ok:
                super().reject()
            else:
                self.request_cancel()  # fechar a janela só pede o cancelamento

        def finish(self) -> None:
            self.finished_ok = True
            super().accept()

    class BankDialog(QDialog):
        def __init__(self, parent: Any, describe: Callable[[], str], actions: list[tuple[str, Callable[[], None]]]):
            super().__init__(parent)
            self.describe = describe
            self.setWindowTitle("DFC Probe: banco pessoal de variantes")
            self.setMinimumWidth(560)
            root = QVBoxLayout(self)
            self.report = note("")
            self.report.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            root.addWidget(self.report)
            self.buttons: dict[str, QPushButton] = {}
            for label, fn in actions:
                button = QPushButton(label)
                button.clicked.connect(lambda _checked=False, fn=fn: (fn(), self.refresh()))
                root.addWidget(button)
                self.buttons[label] = button
            close = QPushButton("Fechar")
            close.clicked.connect(lambda _checked=False: self.accept())
            root.addWidget(close)
            self.refresh()

        def refresh(self) -> None:
            self.report.setText(self.describe())

    class SavePickerDialog(QDialog):
        def __init__(self, parent: Any, rows: list[tuple[str, str]]):
            super().__init__(parent)
            self.setWindowTitle("DFC Probe: guardar no banco pessoal")
            self.setMinimumWidth(620)
            root = QVBoxLayout(self)
            root.addWidget(note("Marque as variantes que podem aparecer nas suas revisões. Elas se somam às que a nota já tem no banco pessoal."))
            self.checks: dict[str, QCheckBox] = {}
            for variant_id, label in rows:
                check = QCheckBox(label)
                check.setChecked(True)
                root.addWidget(check)
                self.checks[variant_id] = check
            root.addWidget(button_box(self, "Guardar"))

        def selected_ids(self) -> list[str]:
            return [vid for vid, check in self.checks.items() if check.isChecked()]

    return SimpleNamespace(SettingsDialog=SettingsDialog, BatchDialog=BatchDialog, ProgressDialog=ProgressDialog, BankDialog=BankDialog, SavePickerDialog=SavePickerDialog)


def open_settings(mw: Any, fm: Any, on_generate: Callable[[], None], on_bank: Callable[[], None]) -> None:
    from aqt.utils import showInfo, tooltip

    if mw.col is None:
        showInfo("Abra um perfil antes de configurar.")
        return
    dialog = _widgets().SettingsDialog(mw, fm.settings(), deck_choices(mw.col), fm.status_line(), on_generate, on_bank)
    accepted = dialog.exec()
    dialog.deleteLater()
    if accepted:
        fm.save_settings(dialog.result_settings())
        tooltip("DFC Probe: ajustes das variantes salvos.")


def open_batch(mw: Any, fm: Any, cfg: dict[str, Any], official_ids: Callable[[], Any], deck_id: Optional[int] = None) -> None:
    from aqt.operations import QueryOp
    from aqt.utils import askUser, showInfo

    if mw.col is None:
        showInfo("Abra um perfil antes de gerar variantes.")
        return
    if not cfg.get("live_enabled", False):
        showInfo("Gerar variantes usa a IA: ligue `live_enabled` e preencha a chave em Ferramentas > Complementos > DFC Probe > Config.")
        return
    try:
        gen, judge = live.build_clients(cfg, batch=True)
    except Exception as e:
        showInfo(f"Não foi possível preparar a geração: {e}.\n\nConfira live_api_key, live_base_url e os modelos em Ferramentas > Complementos > DFC Probe > Config.")
        return
    bank = fm.bank()
    host = urlparse(str(cfg.get("live_base_url") or "")).netloc or "o provedor configurado"
    dialog: Any = None

    def analyze(params: dict[str, Any]) -> None:
        def work(col: Any) -> batch.Plan:
            records = anki_adapter.collect_records(col, params["deck_id"], core.note_to_record, children=params["children"], skip_new=params["skip_new"], skip_suspended=params["skip_suspended"])
            return batch.make_plan(records, bank, official_ids(), params["options"])

        op = QueryOp(parent=dialog, op=work, success=dialog.show_plan)
        op.failure(lambda e: dialog.show_error(f"Falha ao analisar o baralho: {e}")).with_progress("DFC Probe: analisando o baralho...").run_in_background()

    def start(params: dict[str, Any], plan: batch.Plan) -> None:
        text = f"{batch.describe_plan(plan)}\n\nO texto dessas notas será enviado a {host}, com a sua chave. Continuar?"
        if askUser(text, parent=dialog, title="DFC Probe: gerar variantes"):
            dialog.accept()
            run_batch(mw, bank, gen, judge, plan, params["options"])

    dialog = _widgets().BatchDialog(mw, deck_choices(mw.col), deck_id if deck_id is not None else mw.col.decks.get_current_id(), analyze, start)
    dialog.exec()
    dialog.deleteLater()


def run_batch(mw: Any, bank: free.FreeBank, gen: Any, judge: Any, plan: batch.Plan, options: batch.Options) -> None:
    """Gera em segundo plano, com janela de progresso (sem travar o Anki) e botão de cancelar."""
    from aqt.operations import QueryOp
    from aqt.utils import showInfo, showText

    cancel = threading.Event()
    progress = _widgets().ProgressDialog(mw, len(plan.todo), cancel.set)

    def on_progress(summary: batch.Summary) -> None:
        snapshot = dataclasses.replace(summary)
        mw.taskman.run_on_main(lambda: progress.update_counts(snapshot))

    def work(_col: Any) -> batch.Summary:
        return batch.run(plan.todo, gen, judge, bank, options, on_progress=on_progress, cancelled=cancel.is_set)

    def done(summary: batch.Summary) -> None:
        progress.finish()
        progress.deleteLater()
        showText(batch.format_summary(summary), parent=mw, title="DFC Probe: variantes geradas", minWidth=520, minHeight=260)

    def failed(exc: Exception) -> None:
        progress.finish()
        progress.deleteLater()
        bank.save()
        showInfo(f"A geração parou: {exc}")

    progress.show()
    QueryOp(parent=mw, op=work, success=done).failure(failed).without_collection().run_in_background()


def open_bank(mw: Any, fm: Any) -> None:
    from aqt.qt import QFileDialog
    from aqt.utils import askUser, showInfo, showWarning, tooltip

    bank = fm.bank()
    if bank is None:
        showInfo("Abra um perfil antes de abrir o banco pessoal.")
        return
    dialog: Any = None

    def export() -> None:
        path, _filter = QFileDialog.getSaveFileName(mw, "Exportar o banco pessoal", "banco_pessoal.json", "JSON (*.json)")
        if path:
            bank.export_to(path)
            tooltip("Banco pessoal exportado.")

    def import_() -> None:
        path, _filter = QFileDialog.getOpenFileName(mw, "Importar variantes para o banco pessoal", "", "JSON (*.json)")
        if not path:
            return
        try:
            n = bank.merge_from(path)
        except (OSError, ValueError) as e:
            showWarning(f"Não foi possível importar: {e}", parent=dialog)
            return
        bank.save()
        tooltip(f"{n} notas importadas.")

    def forget() -> None:
        n = bank.forget_skipped()
        bank.save()
        tooltip(f"{n} notas serão avaliadas de novo na próxima geração.")

    def wipe() -> None:
        if askUser("Apagar todas as variantes do banco pessoal? Os cartões e as notas do Anki não são afetados.", parent=dialog, defaultno=True):
            bank.clear()
            bank.save()

    dialog = _widgets().BankDialog(mw, lambda: free.describe_bank(bank), [("Exportar...", export), ("Importar...", import_), ("Esquecer as notas avaliadas sem variantes", forget), ("Apagar o banco pessoal", wipe)])
    dialog.exec()
    dialog.deleteLater()


def open_save_picker(mw: Any, fm: Any, result: dict[str, Any]) -> None:
    """Guarda no banco pessoal as variantes que a pessoa marcar, entre as aprovadas na geração de um cartão."""
    from aqt.utils import showInfo, tooltip

    bank = fm.bank()
    if bank is None:
        showInfo("Abra um perfil antes de guardar variantes.")
        return
    rows = [(v["id"], f"{live.TYPE_LABELS.get(v['type'], v['type'])}: {preview(v['text'])}") for v in result["variants"] if v["valid"]]
    if rows and result["entry"]["kind"] == "cloze" and result["entry"]["images_html"]:
        rows.append((f"{result['note_id']}-sem_imagem", "Sem imagem: o mesmo cartão, sem a imagem"))
    if not rows:
        showInfo("Não há variante aprovada para guardar.")
        return
    dialog = _widgets().SavePickerDialog(mw, rows)
    accepted = dialog.exec()
    dialog.deleteLater()
    if not accepted:
        return
    ids = dialog.selected_ids()
    new = free.entry_from_result(result, only_ids=ids) if ids else None
    if new is None:
        return
    nid = result["note_id"]
    bank.unban(v["id"] for v in new["variants"])  # guardar de propósito vale mais do que um "ruim" antigo
    if not bank.set_entry(nid, free.merge_entries(bank.entry(nid), new), result["models"]["gen"], result["models"]["judge"]):
        showInfo("Não foi possível guardar estas variantes.")
        return
    bank.save()
    on = fm.settings().enabled
    tooltip(f"{len(new['variants'])} variantes guardadas no banco pessoal." + ("" if on else " As variantes só aparecem nas revisões depois de ligar o modo em Variantes nos meus cartões > Configurar."))
