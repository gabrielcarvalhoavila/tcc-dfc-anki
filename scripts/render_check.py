"""Confere, numa cópia da coleção real, se a troca de variante funciona em todas as notas de um banco.

Usa o motor do Anki (pacote `anki`, sem interface) e as mesmas funções do add-on; nada é gravado na coleção original.
Uso: .venv\\Scripts\\python scripts\\render_check.py --bank data\\bank\\variant_bank.json [--profile "Usuário 1"]
"""
import argparse
import collections
import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def load(name, *relpath):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *relpath))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def find_profile(anki_dir, wanted):
    if wanted:
        return wanted
    found = [d for d in os.listdir(anki_dir) if os.path.exists(os.path.join(anki_dir, d, "collection.anki2"))]
    if len(found) != 1:
        raise SystemExit(f"Informe --profile (perfis encontrados: {found})")
    return found[0]


def copy_collection(profile_dir, tmp):
    dst = os.path.join(tmp, "collection.anki2")
    for suffix in ("", "-wal"):  # com o Anki aberto, as últimas gravações podem estar no -wal
        src = os.path.join(profile_dir, "collection.anki2" + suffix)
        if os.path.exists(src):
            shutil.copyfile(src, dst + suffix)
    return dst


def check_note(col, adapter, variants, note_id, entry, count, fail):
    note = col.get_note(note_id)
    kind_model = (entry["kind"], note.note_type()["name"])
    if variants.fields_hash(note.fields) != entry["fields_hash"]:
        return fail(kind_model, "nota_editada", note_id)
    card = next((c for c in note.cards() if c.ord in entry["ords"]), None)
    if card is None:
        return fail(kind_model, "ord_ausente", note_id)
    orig_q, orig_a = adapter.render_pair(col, card)
    reviewer_q, reviewer_a = card.question(), card.answer()  # o que o gancho do Reviewer recebe
    if orig_q not in reviewer_q:
        return fail(kind_model, "template_mismatch", note_id)
    if orig_a not in reviewer_a:
        return fail(kind_model, "answer_mismatch", note_id)
    for variant in entry["variants"]:
        value, needles = variants.field_value(entry, variant)
        try:
            var_q, var_a = adapter.render_pair(col, card, entry["q_field"], value)
        except Exception as e:  # noqa: BLE001
            fail(kind_model, "render_error:" + type(e).__name__, note_id)
            continue
        if var_q == orig_q or not all(n in var_q for n in needles):
            fail(kind_model, "render_failed", note_id)
        elif var_q not in reviewer_q.replace(orig_q, var_q, 1) or var_a not in reviewer_a.replace(orig_a, var_a, 1):
            fail(kind_model, "swap_failed", note_id)
        else:
            count(kind_model)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bank", default=os.path.join(ROOT, "data", "bank", "variant_bank.json"))
    parser.add_argument("--anki-dir", default=os.path.join(os.environ.get("APPDATA", ""), "Anki2"))
    parser.add_argument("--profile")
    args = parser.parse_args()

    try:
        from anki.collection import Collection
    except ImportError:
        raise SystemExit("Falta o pacote anki: .venv\\Scripts\\python -m pip install anki==26.5")
    adapter = load("dfc_adapter_check", "addon", "dfc_probe", "anki_adapter.py")
    variants = load("dfc_variants_check", "addon", "dfc_probe", "variants.py")

    bank = variants.Bank.load(args.bank)
    print(f"banco: {len(bank.notes)} notas, {bank.n_variants} variantes (hash {bank.hash}, falso={bank.is_fake})")
    profile_dir = os.path.join(args.anki_dir, find_profile(args.anki_dir, args.profile))

    ok = collections.Counter()
    failures = collections.defaultdict(list)

    def count(kind_model):
        ok[kind_model] += 1

    def fail(kind_model, reason, note_id):
        failures[(kind_model, reason)].append(note_id)

    with tempfile.TemporaryDirectory() as tmp:
        col = Collection(copy_collection(profile_dir, tmp))
        try:
            for note_id, entry in bank.notes.items():
                try:
                    check_note(col, adapter, variants, note_id, entry, count, fail)
                except Exception as e:  # noqa: BLE001
                    fail((entry["kind"], "?"), "nota_ausente_ou_erro:" + type(e).__name__, note_id)
        finally:
            col.close()

    for kind_model, n in sorted(ok.items()):
        print(f"ok      {kind_model[0]:6} {kind_model[1]}: {n} variantes")
    for (kind_model, reason), ids in sorted(failures.items()):
        notes = sorted(set(ids))
        print(f"FALHA   {kind_model[0]:6} {kind_model[1]}: {reason} em {len(ids)} variantes de {len(notes)} notas (exemplos: {notes[:5]})")
    total_ok, total_fail = sum(ok.values()), sum(len(v) for v in failures.values())
    print(f"total: {total_ok} ok, {total_fail} falhas")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
