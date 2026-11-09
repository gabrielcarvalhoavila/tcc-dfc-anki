"""Figuras do texto do TCC (repositório do Overleaf). Uso: python scripts/figuras_tcc.py <pasta de saída>

Os números da figura de validação vêm de docs/protocolo.md (seção 14) e do relatório da geração de 21/10; as telas são as do add-on 0.5.0
desenhadas com o Qt (PyQt6), sem abrir janelas. Precisa de matplotlib e, para as telas, PyQt6.
"""
import os
import sys
import types

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "figuras")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 9, "pdf.fonttype": 42})

BLUE, GREEN, ORANGE, GREY = "#dbe7f5", "#dff0d8", "#fbe5c8", "#eeeeee"
EDGE = "#444444"


def box(ax, x, y, w, h, text, color=BLUE, size=8.5, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=color, ec=EDGE, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, p, q, text=None, dy=0.12, ha="center"):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=EDGE, lw=0.9, shrinkA=0, shrinkB=0))
    if text:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, text, ha=ha, va="bottom", fontsize=7.5, style="italic")


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".pdf"), bbox_inches="tight")
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def fluxo_geral():
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.set_xlim(0, 10.4)
    ax.set_ylim(0, 5)
    ax.axis("off")
    ax.text(0.0, 4.75, "Antes da coleta (offline)", fontsize=9, fontweight="bold")
    xs = [0.0, 2.15, 4.3, 6.45, 8.6]
    labels = ["Notas elegíveis\ndo Anki", "Geração\n(LLM gerador)", "Validação\n(juiz e regras)", "Auditoria\nhumana (100)", "Banco de\nvariantes"]
    colors = [GREEN, BLUE, BLUE, BLUE, ORANGE]
    for x, t, c in zip(xs, labels, colors):
        box(ax, x, 3.35, 1.8, 0.95, t, c)
    for a, b in zip(xs[:-1], xs[1:]):
        arrow(ax, (a + 1.8, 3.82), (b, 3.82))
    ax.text(0.0, 2.2, "Durante a coleta (no Anki)", fontsize=9, fontweight="bold")
    ys = 0.75
    xs2 = [0.0, 2.15, 4.3, 6.45, 8.6]
    labels2 = ["Pergunta\nmostrada", "Add-on: elegível?\nsorteio 50/50", "Cartão original\nou variante", "Resposta\n(Again, Hard, ...)", "Evento\n(SQLite, CSV)"]
    colors2 = [GREEN, BLUE, BLUE, GREEN, ORANGE]
    for x, t, c in zip(xs2, labels2, colors2):
        box(ax, x, ys, 1.8, 0.95, t, c)
    for a, b in zip(xs2[:-1], xs2[1:]):
        arrow(ax, (a + 1.8, ys + 0.47), (b, ys + 0.47))
    ax.plot([9.5, 9.5, 3.05], [3.35, 2.85, 2.85], color=EDGE, lw=0.9)
    arrow(ax, (3.05, 2.85), (3.05, 1.7))
    ax.text(6.3, 2.9, "banco importado no add-on", ha="center", va="bottom", fontsize=7.5, style="italic")
    ax.text(5.0, 0.15, "Depois da coleta: eventos → análise (diferença de diferenças)", fontsize=8.5, ha="center", style="italic")
    save(fig, "fluxo-geral")


def fluxo_exposicao():
    fig, ax = plt.subplots(figsize=(6.2, 4.9))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.3, 8.6)
    ax.axis("off")
    box(ax, 3.2, 7.7, 3.6, 0.7, "Pergunta mostrada (revisão)", GREEN)
    box(ax, 2.3, 6.2, 4.4, 0.95, "Nota no banco, mesmo cartão e texto\nnão editado, reps ≥ 1, dentro da janela?", BLUE, size=8)
    box(ax, 2.3, 4.6, 4.4, 0.95, "A revisão anterior foi\nem outro dia do Anki?", BLUE)
    box(ax, 2.3, 3.0, 4.4, 0.95, "Sorteio 50/50\n(semente do evento)", BLUE)
    box(ax, 0.2, 1.1, 3.2, 0.95, "Original", ORANGE)
    box(ax, 6.6, 1.1, 3.2, 0.95, "Variante nova\n(ainda não mostrada)", ORANGE)
    box(ax, 7.6, 6.2, 2.3, 0.95, "Original,\nsem sorteio", GREY)
    box(ax, 7.6, 4.6, 2.3, 0.95, "Original,\nsame_day = 1", GREY)
    arrow(ax, (4.5, 7.7), (4.5, 7.15))
    arrow(ax, (4.5, 6.2), (4.5, 5.55), "sim", dy=0.05, ha="left")
    arrow(ax, (6.7, 6.67), (7.6, 6.67), "não", dy=0.04)
    arrow(ax, (4.5, 4.6), (4.5, 3.95), "sim", dy=0.05, ha="left")
    arrow(ax, (6.7, 5.07), (7.6, 5.07), "não", dy=0.04)
    arrow(ax, (3.8, 3.0), (1.8, 2.05))
    arrow(ax, (5.2, 3.0), (8.2, 2.05))
    box(ax, 2.3, 0.0, 4.4, 0.6, "Registro do evento", GREEN)
    arrow(ax, (1.8, 1.1), (3.4, 0.6))
    arrow(ax, (8.2, 1.1), (5.6, 0.6))
    save(fig, "fluxo-exposicao")


def did():
    fig, ax = plt.subplots(figsize=(4.6, 3.1))
    xs = [0, 1]
    ax.plot(xs, [4, 18], "-o", color="#b03a2e", label="Suspeitos")
    ax.plot(xs, [11, 14], "-o", color="#2e6da4", label="Controles")
    ax.plot(xs, [4, 7], ":", color="#b03a2e", lw=1)
    ax.annotate("", xy=(1.06, 18), xytext=(1.06, 7), arrowprops=dict(arrowstyle="<->", color="#444444", lw=0.9))
    ax.text(1.1, 12.5, "DiD\n= 11 pp", fontsize=8, va="center")
    ax.text(0.5, 4.4, "sem efeito extra\nnos suspeitos", fontsize=7, ha="center", va="top", color="#b03a2e")
    ax.set_xticks(xs)
    ax.set_xticklabels(["Original", "Variante"])
    ax.set_xlim(-0.2, 1.4)
    ax.set_ylim(0, 24)
    ax.set_ylabel("Falhas (%), valores ilustrativos")
    ax.legend(frameon=False, loc="upper left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    save(fig, "did-ilustracao")


def wrap(ax, x, y, lines, size=7.6):
    ax.text(x, y, "\n".join(lines), ha="left", va="top", fontsize=size, linespacing=1.35)


def cartoes():
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.4))
    fichas = [
        ("Original", "Revolução Industrial", ["País de origem: [...]", "Fonte de energia: [...]", "Setor pioneiro: [...]"], True),
        ("paraphrase", None, ["A Revolução Industrial começou na [...],", "movida a [...], e o primeiro setor a se", "industrializar foi o [...]."], True),
        ("reorder", "Revolução Industrial", ["Setor pioneiro: [...]", "País de origem: [...]", "Fonte de energia: [...]"], True),
        ("cue_swap", "Industrialização moderna", ["Onde começou: [...]", "Combustível: [...]", "Ramo que saiu na frente: [...]"], True),
        ("pergunta", None, ["Em que país começou a Revolução", "Industrial? [...]", "Que fonte de energia a impulsionou? [...]", "Qual setor foi o pioneiro? [...]"], True),
        ("sem_imagem", "Revolução Industrial", ["País de origem: [...]", "Fonte de energia: [...]", "Setor pioneiro: [...]"], False),
    ]
    for ax, (nome, titulo, linhas, imagem) in zip(axes.flat, fichas):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0.2, 0.2), 9.6, 9.0, boxstyle="round,pad=0.02,rounding_size=0.3", fc="white", ec=EDGE, lw=0.8))
        ax.text(5, 9.9, nome if nome != "Original" else "Cartão original", ha="center", va="bottom", fontsize=8.5, fontweight="bold", family="monospace" if nome != "Original" else None)
        y = 8.6
        if titulo:
            ax.text(5, y, titulo, ha="center", va="top", fontsize=8.5, fontweight="bold", color="#555555")
            y -= 1.5
        if imagem:
            ax.add_patch(Rectangle((3.2, y - 2.0), 3.6, 2.0, fc="#d9e2ec", ec="#8a9bab", lw=0.6))
            ax.text(5, y - 1.0, "imagem", ha="center", va="center", fontsize=7, color="#5a6b7b")
            y -= 2.5
        wrap(ax, 0.8, y, linhas)
    fig.tight_layout(h_pad=1.0, w_pad=0.5)
    save(fig, "variantes-exemplo")


def validacao():
    tipos = ["cue_swap", "paraphrase", "pergunta", "reorder", "sem_imagem"]
    auto = [1941 / 2273 * 100, 2095 / 2308 * 100, 2097 / 2312 * 100, 2098 / 2178 * 100, None]
    aud = [17 / 20 * 100, 100, 100, 17 / 20 * 100, 100]
    fig, ax = plt.subplots(figsize=(6.2, 3.2))
    w = 0.38
    for i, (a, b) in enumerate(zip(auto, aud)):
        if a is not None:
            ax.bar(i - w / 2, a, w, color="#9fb8d6", ec=EDGE, lw=0.6, label="Validação automática" if i == 0 else None)
            ax.text(i - w / 2, a + 1, f"{a:.1f}".replace(".", ",") + "%", ha="center", fontsize=7.5)
        ax.bar(i + (w / 2 if a is not None else 0), b, w, color="#f0b27a", ec=EDGE, lw=0.6, label="Auditoria humana (20 por tipo)" if i == 0 else None)
        ax.text(i + (w / 2 if a is not None else 0), b + 1, f"{b:.0f}%", ha="center", fontsize=7.5)
    ax.axhline(94, color="#444444", lw=0.8, ls="--")
    ax.text(4.55, 94.8, "auditoria, total: 94% (IC 95%: 87,5 a 97,2%)", ha="right", fontsize=7.5)
    ax.axhline(70, color="#888888", lw=0.8, ls=":")
    ax.text(4.55, 70.8, "limiar por tipo (70%)", ha="right", fontsize=7.5, color="#666666")
    ax.set_xticks(range(5))
    ax.set_xticklabels(tipos)
    ax.set_ylim(50, 110)
    ax.set_yticks([50, 60, 70, 80, 90, 100])
    ax.set_ylabel("Variantes válidas (%)")
    ax.legend(frameon=False, loc="upper left", fontsize=7.5, ncol=2, bbox_to_anchor=(0, 1.12))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    save(fig, "validacao-tipos")


def telas():
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
    except ImportError:
        print("PyQt6 ausente: telas não geradas")
        return
    os.environ.pop("QT_QPA_PLATFORM", None)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    qt = types.ModuleType("aqt.qt")
    for mod in (QtCore, QtGui, QtWidgets):
        for name in dir(mod):
            setattr(qt, name, getattr(mod, name))
    sys.modules.update({"aqt": types.ModuleType("aqt"), "aqt.qt": qt})
    sys.path[:0] = [os.path.join(ROOT, "tests"), os.path.join(ROOT, "pipeline")]
    import addon_pure

    free, batch, free_ui = addon_pure.load("free"), addon_pure.load("batch"), addon_pure.load("free_ui")
    ui = free_ui._widgets()
    decks = [(1, "Biologia"), (2, "Biologia::Genética"), (3, "História"), (4, "Química")]
    settings = free.Settings(enabled=True, probability=40, deck_ids=[1, 2])
    dialog = ui.SettingsDialog(None, settings, decks, "ligado (40% das revisões elegíveis); banco pessoal: 120 notas, 480 variantes", lambda: None, lambda: None)
    dialog.adjustSize()
    dialog.grab().save(os.path.join(OUT, "tela-configurar.png"))
    dlg = ui.BatchDialog(None, decks, 2, lambda p: None, lambda p, plan: None)
    plan = batch.Plan(todo=[{"note_id": i} for i in range(180)], examined=412, ineligible=96, already=40, dismissed=12, truncated=84)
    plan.reasons.update({"short_text": 50, "empty_answer": 30, "media_or_latex": 16})
    dlg.show_plan(plan)
    dlg.adjustSize()
    dlg.grab().save(os.path.join(OUT, "tela-lote.png"))


if __name__ == "__main__":
    fluxo_geral()
    fluxo_exposicao()
    did()
    cartoes()
    validacao()
    telas()
    print("ok:", sorted(os.listdir(OUT)))
