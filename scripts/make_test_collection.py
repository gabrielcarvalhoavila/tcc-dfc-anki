"""Cria a pasta-base de um Anki de teste isolado: prefs21.db (perfil "Teste", sem sincronização nem verificação de atualizações)
e uma coleção com cartões INVENTADOS, já estudados, para testar o add-on sem tocar no Anki de estudo.

Uso: python scripts/make_test_collection.py BASE [--perfil Teste] [--recriar]
Precisa do pacote `anki` (o mesmo do .venv do repositório). Só escreve dentro de BASE e recusa a pasta do Anki de estudo.
"""
import argparse
import os
import pickle
import random
import shutil
import sqlite3
import struct
import sys
import time
import zlib

DAY_MS = 86_400_000

# (baralho, tipo, campos, situação). Situações: suspeito (reps 6, sem lapsos, última resposta Good), controle (poucas respostas
# ou um lapso), hoje (respondido há minutos), novo (nunca estudado), suspenso.
BIO, HIS = "Biologia (teste)", "Historia (teste)"
NOTES = [
    (BIO, "Basic", {"Front": "Qual organela celular é responsável pela produção de ATP na respiração celular aeróbia?", "Back": "Mitocôndria"}, "suspeito"),
    (BIO, "Basic", {"Front": "Que processo transforma a energia luminosa em energia química nas plantas?", "Back": "Fotossíntese"}, "suspeito"),
    (BIO, "Basic", {"Front": "Qual estrutura da célula vegetal garante rigidez e proteção externa à célula?", "Back": "Parede celular"}, "controle"),
    (BIO, "Basic", {"Front": "Qual molécula carrega a informação genética nos seres vivos?", "Back": "DNA (ácido desoxirribonucleico)"}, "suspeito"),
    (BIO, "Basic", {"Front": "Em qual fase da mitose os cromossomos se alinham no centro da célula?", "Back": "Metáfase"}, "controle"),
    (BIO, "Basic", {"Front": "Que tipo de transporte move substâncias a favor do gradiente sem gastar energia?", "Back": "Transporte passivo (difusão)"}, "suspeito"),
    (BIO, "Cloze", {"Text": "A {{c1::meiose}} reduz o número de cromossomos à metade e forma os {{c1::gametas}} nos animais.", "Back Extra": ""}, "suspeito"),
    (BIO, "Cloze", {"Text": "Na fotossíntese, a {{c1::clorofila}} absorve a luz e o gás {{c1::carbônico}} é fixado no ciclo de Calvin.", "Back Extra": ""}, "suspeito"),
    (BIO, "Cloze", {"Text": 'Célula animal<br><div><img src="dfc_teste_celula.png"></div><br>Controla a entrada e a saída: {{c1::membrana plasmática}}<br>Guarda o material genético: {{c1::núcleo}}', "Back Extra": ""}, "suspeito"),
    (BIO, "Cloze", {"Text": "O {{c1::ribossomo}} é a organela onde ocorre a síntese de proteínas, e o {{c1::lisossomo}} realiza a digestão intracelular.", "Back Extra": ""}, "controle"),
    (HIS, "Basic", {"Front": "Qual evento marcou o início da Revolução Francesa em 14 de julho de 1789?", "Back": "A Queda da Bastilha"}, "suspeito"),
    (HIS, "Basic", {"Front": "Qual documento de 1215 limitou os poderes do rei da Inglaterra?", "Back": "A Magna Carta"}, "suspeito"),
    (HIS, "Basic", {"Front": "Qual tratado encerrou a Primeira Guerra Mundial para a Alemanha em 1919?", "Back": "O Tratado de Versalhes"}, "controle"),
    (HIS, "Cloze", {"Text": "A {{c1::Revolução Industrial}} começou na {{c1::Inglaterra}} no século XVIII e transformou a produção com o uso de máquinas.", "Back Extra": ""}, "suspeito"),
    (HIS, "Cloze", {"Text": 'Governo Mussolini<br><div><img src="dfc_teste_celula.png"></div><br>Antecedentes: {{c1::Questão Romana}}<br>Consiste: {{c1::reconhecimento do Vaticano}}<br>Ano: {{c1::1929}}', "Back Extra": "Tratado de Latrão"}, "suspeito"),
    (HIS, "Cloze", {"Text": "A {{c1::Guerra Fria}} opôs os Estados Unidos e a {{c1::União Soviética}} sem confronto militar direto entre as duas potências.", "Back Extra": ""}, "hoje"),
    (HIS, "Basic", {"Front": "Que império foi governado por Carlos Magno e teve Aachen como capital?", "Back": "Império Carolíngio"}, "novo"),
    (HIS, "Basic", {"Front": "Qual rei francês ficou conhecido como o Rei Sol e construiu o Palácio de Versalhes?", "Back": "Luís XIV"}, "suspenso"),
]


def png_bytes(width: int = 160, height: int = 100) -> bytes:
    """Uma figura simples (célula com núcleo) em PNG, feita à mão para não depender de nenhuma biblioteca de imagens."""

    def pixel(x: int, y: int) -> tuple[int, int, int]:
        dx, dy = x - width // 2, y - height // 2
        if dx * dx + dy * dy < 12 * 12:
            return (200, 70, 70)
        if (dx / 70) ** 2 + (dy / 40) ** 2 < 1:
            return (120, 190, 140)
        return (235, 240, 245)

    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def write_prefs(base: str, profile: str) -> None:
    """prefs21.db como o Anki grava (perfis em pickles); assim o Anki abre direto no perfil de teste, sem escolher idioma nem criar perfil."""
    path = os.path.join(base, "prefs21.db")
    now = int(time.time())
    meta = dict(
        ver=0, updates=False, created=now, id=random.randrange(0, 2**63), lastMsg=0, suppressUpdate=True, firstRun=False, defaultLang="en_US",
        last_loaded_profile_name=profile, check_for_updates=False, check_for_addon_updates=False,
    )
    prof = dict(
        mainWindowGeom=None, mainWindowState=None, numBackups=5, lastOptimize=now, searchHistory=[], syncKey=None, syncMedia=False, autoSync=False,
        allowHTML=False, importMode=1, lastColour="#00f", stripHTML=True, deleteMedia=False,
    )
    con = sqlite3.connect(path)
    with con:
        con.execute("create table if not exists profiles (name text primary key collate nocase, data blob not null)")
        con.execute("insert or replace into profiles values ('_global', ?)", (pickle.dumps(meta, protocol=4),))
        con.execute("insert or replace into profiles values (?, ?)", (profile, pickle.dumps(prof, protocol=4)))
    con.close()


def add_revlog(col, card_id: int, when_ms: int, kind: int, ease: int, ivl: int) -> None:
    col.db.execute("insert into revlog (id, cid, usn, ease, ivl, lastIvl, factor, time, type) values (?, ?, -1, ?, ?, ?, 2500, 6000, ?)", when_ms, card_id, ease, ivl, max(1, ivl // 2), kind)


def history(col, card, scenario: str, now_ms: int, salt: int) -> tuple[int, int]:
    """Grava o histórico no revlog e devolve (reps, lapses). Cada resposta tem id único (o id do revlog é o horário em ms)."""
    if scenario == "controle" and salt % 2:
        steps = [(130, 0, 3), (100, 1, 3), (70, 1, 1), (45, 1, 3), (20, 1, 3)]  # um lapso no meio
        lapses = 1
    elif scenario == "controle":
        steps = [(60, 0, 3), (30, 1, 3), (10, 1, 3)]  # poucas respostas
        lapses = 0
    else:
        steps = [(130, 0, 3), (100, 1, 3), (70, 1, 3), (45, 1, 3), (25, 1, 3), (10, 1, 3)]
        lapses = 0
    for i, (days_ago, kind, ease) in enumerate(steps):
        add_revlog(col, card.id, now_ms - days_ago * DAY_MS + salt * 1000 + i, kind, ease, 3 * (i + 1))
    if scenario == "hoje":
        add_revlog(col, card.id, now_ms - 5 * 60_000 + salt, 1, 3, 30)
    return len(steps) + (scenario == "hoje"), lapses


def build_collection(path: str, media_name: str = "dfc_teste_celula.png") -> int:
    from anki.collection import Collection

    col = Collection(path)
    try:
        col.media.write_data(media_name, png_bytes())
        today, now_ms = col.sched.today, int(time.time() * 1000)
        suspended = []
        for salt, (deck, model, fields, scenario) in enumerate(NOTES, start=1):
            note = col.new_note(col.models.by_name(model))
            for name, value in fields.items():
                note[name] = value
            col.add_note(note, col.decks.id(deck))
            if scenario == "novo":
                continue
            card = note.cards()[0]
            reps, lapses = history(col, card, scenario, now_ms, salt)
            card.type, card.queue, card.ivl, card.factor = 2, 2, 30, 2500
            card.reps, card.lapses = reps, lapses
            card.due = today
            col.update_card(card)
            if scenario == "suspenso":
                suspended.append(card.id)
        if suspended:
            col.sched.suspend_cards(suspended)
        return col.note_count()
    finally:
        col.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base")
    parser.add_argument("--perfil", default="Teste")
    parser.add_argument("--recriar", action="store_true", help="apaga o perfil de teste e cria de novo")
    args = parser.parse_args()
    base = os.path.abspath(args.base)
    study = os.path.abspath(os.path.join(os.environ.get("APPDATA", ""), "Anki2"))
    if os.path.normcase(base) == os.path.normcase(study) or os.path.normcase(base).startswith(os.path.normcase(study) + os.sep):
        print(f"Recusado: {base} é a pasta do seu Anki de estudo.", file=sys.stderr)
        return 2
    folder = os.path.join(base, args.perfil)
    if args.recriar and os.path.isdir(folder):
        shutil.rmtree(folder)
        for leftover in ("prefs21.db",):
            if os.path.exists(os.path.join(base, leftover)):
                os.remove(os.path.join(base, leftover))
    os.makedirs(os.path.join(base, "addons21"), exist_ok=True)
    os.makedirs(folder, exist_ok=True)
    if not os.path.exists(os.path.join(base, "prefs21.db")):
        write_prefs(base, args.perfil)
    collection = os.path.join(folder, "collection.anki2")
    if os.path.exists(collection):
        print(f"A coleção de teste já existe em {collection} (use --recriar para refazer).")
        return 0
    n = build_collection(collection)
    print(f"Coleção de teste criada: {n} notas em {collection}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
