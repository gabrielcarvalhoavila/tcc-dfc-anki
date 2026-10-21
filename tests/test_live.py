"""Testes da variante sob demanda do add-on (sem Anki e sem rede)."""
import ast
import importlib
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from dfc_pipeline.llm import ConfigError, FakeLLM, LLMError  # noqa: E402

LIVE_PATH = os.path.join(ROOT, "addon", "dfc_probe", "live.py")
VENDOR_PS1 = os.path.join(ROOT, "scripts", "vendor_pipeline.ps1")


def load_live():
    spec = importlib.util.spec_from_file_location("dfc_live", LIVE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dfc_live"] = mod
    spec.loader.exec_module(mod)
    return mod


L = load_live()


def basic_record(question="Qual organela produz ATP na célula eucarionte?", answer="Mitocôndria", model="Basic"):
    return {"note_id": 7, "guid": "g", "model": model, "fields": {"Front": question, "Back": answer}, "tags": [], "decks": ["D"]}


def cloze_record(text="A {{c1::mitose}} ocorre em células somáticas e a {{c1::meiose}} forma os gametas nos seres vivos."):
    return {"note_id": 8, "guid": "g", "model": "Cloze", "fields": {"Text": text, "Extra": ""}, "tags": [], "decks": ["D"]}


def failing(*_args):
    raise LLMError("sem crédito")


class GenerateVariantsTest(unittest.TestCase):
    def test_basic_card_gets_four_validated_variants(self):
        gen, judge = FakeLLM(), FakeLLM()
        result = L.generate_variants(basic_record(), gen, judge)
        self.assertEqual(sorted(v["type"] for v in result["variants"]), ["cue_swap", "paraphrase", "reformat", "reorder"])
        self.assertTrue(all(v["valid"] and not v["reasons"] for v in result["variants"]), result["variants"])
        self.assertEqual((len(gen.calls), len(judge.calls)), (1, 4))
        self.assertEqual((result["answers"], result["conceptual"], result["error"]), ([("", "Mitocôndria")], True, None))
        self.assertEqual(result["models"]["gen_prompt"], "gen-v4")

    def test_cloze_card_keeps_one_answer_per_marker(self):
        result = L.generate_variants(cloze_record(), FakeLLM(), FakeLLM())
        self.assertEqual(result["answers"], [("[...1]", "mitose"), ("[...2]", "meiose")])
        self.assertEqual(sorted(v["type"] for v in result["variants"]), ["cue_swap", "paraphrase", "pergunta", "reorder"])
        self.assertTrue(all(v["valid"] for v in result["variants"]), result["variants"])

    def test_ineligible_cards_never_reach_the_llm(self):
        cases = [
            (basic_record(model="Image Occlusion Enhanced"), 0, "model_not_supported"),
            (basic_record(answer="1500"), 0, "numeric_answer"),
            (cloze_record("A {{c1::mitose}} divide."), 0, "short_text"),
            (basic_record(), 1, "other_card_of_note"),
        ]
        for record, card_ord, reason in cases:
            gen, judge = FakeLLM(), FakeLLM()
            result = L.generate_variants(record, gen, judge, card_ord=card_ord)
            self.assertIn(reason, result["reasons"])
            self.assertEqual((result["variants"], gen.calls, judge.calls), ([], [], []), reason)

    def test_non_conceptual_card_has_no_variants_and_no_judge_calls(self):
        gen, judge = FakeLLM(lambda m: '{"conceptual": false, "reason": "vocabulário", "variants": []}'), FakeLLM()
        result = L.generate_variants(basic_record(), gen, judge)
        self.assertEqual((result["conceptual"], result["reason"], result["variants"], result["error"]), (False, "vocabulário", [], None))
        self.assertEqual(judge.calls, [])

    def test_generation_error_is_reported(self):
        result = L.generate_variants(basic_record(), FakeLLM(failing), FakeLLM())
        self.assertIn("sem crédito", result["error"])
        self.assertEqual(result["variants"], [])

    def test_judge_failure_rejects_the_variant_but_keeps_it_visible(self):
        result = L.generate_variants(basic_record(), FakeLLM(), FakeLLM(failing))
        self.assertEqual(len(result["variants"]), 4)
        self.assertTrue(all(not v["valid"] and "judge_error" in v["reasons"] for v in result["variants"]))


class RenderTest(unittest.TestCase):
    def result(self, **over):
        base = {
            "text": "Pergunta <b>x</b>?",
            "answers": [("", "Resposta & cia")],
            "images": 0,
            "reasons": [],
            "conceptual": True,
            "reason": "",
            "error": None,
            "variants": [
                {"type": "paraphrase", "text": "<script>alert(1)</script>", "valid": True, "reasons": []},
                {"type": "reorder", "text": "Outra ordem", "valid": False, "reasons": ["too_similar", "motivo_novo"]},
            ],
            "models": {"gen": "g<1>", "judge": "j", "gen_prompt": "gen-v4", "judge_prompt": "judge-v4"},
        }
        base.update(over)
        return base

    def test_text_from_the_card_and_the_llm_is_escaped(self):
        out = L.render_html(self.result())
        self.assertNotIn("<script>", out)
        self.assertNotIn("<b>x</b>", out)
        self.assertIn("&lt;script&gt;", out)
        self.assertIn("Resposta &amp; cia", out)
        self.assertIn("g&lt;1&gt;", out)

    def test_verdicts_and_reasons_are_labelled(self):
        out = L.render_html(self.result())
        self.assertIn("aprovada", out)
        self.assertIn("reprovada: parecida demais com o original; motivo_novo", out)
        self.assertIn("Paráfrase", out)
        self.assertIn("Nada foi gravado", out)

    def test_cards_without_variants_say_why(self):
        self.assertIn("texto visível curto demais", L.render_html(self.result(reasons=["short_text"], variants=[])))
        self.assertIn("não conceitual: vocabulário", L.render_html(self.result(conceptual=False, reason="vocabulário", variants=[])))
        self.assertIn("Falha na geração: HTTP 429", L.render_html(self.result(error="HTTP 429", variants=[])))

    def test_image_note_is_shown_for_cloze_with_images(self):
        self.assertIn("2 imagem(ns)", L.render_html(self.result(images=2)))


class ConfigTest(unittest.TestCase):
    def test_load_env_merges_the_file_with_ambient_dfc_variables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w", encoding="utf-8") as f:
                f.write("DFC_GEN_MODEL=g\nDFC_LLM_API_KEY=do-arquivo\n")
            env = L.load_env(path, {"DFC_LLM_API_KEY": "do-ambiente", "PATH": "x"})
            self.assertEqual(env, {"DFC_GEN_MODEL": "g", "DFC_LLM_API_KEY": "do-ambiente"})
            with self.assertRaises(FileNotFoundError):
                L.load_env(os.path.join(tmp, "nao-existe.env"), {})
        self.assertEqual(L.load_env("", {"DFC_X": "1", "OUTRA": "2"}), {"DFC_X": "1"})

    def test_clients_wait_less_than_in_the_batch_run(self):
        env = {"DFC_LLM_BASE_URL": "https://exemplo.test/v1", "DFC_LLM_API_KEY": "k", "DFC_GEN_MODEL": "g", "DFC_JUDGE_MODEL": "j"}
        gen, judge = L.build_clients(env)
        self.assertEqual([(c.max_retries, c.timeout) for c in (gen, judge)], [(1, 60), (1, 60)])
        self.assertEqual((gen.model, judge.model), ("g", "j"))
        with self.assertRaises(ConfigError):
            L.build_clients({})


class VendoredPipelineTest(unittest.TestCase):
    """O add-on instalado leva uma cópia dos módulos do pipeline (scripts/vendor_pipeline.ps1)."""

    pkg = os.path.join(ROOT, "pipeline", "dfc_pipeline")

    def listed(self):
        with open(VENDOR_PS1, encoding="utf-8") as f:
            return set(re.findall(r'"(\w+\.py)"', f.read()))

    def sibling_imports(self, name):
        with open(os.path.join(self.pkg, name), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                found.update([node.module + ".py"] if node.module else [a.name + ".py" for a in node.names])
        return found

    def test_the_list_covers_everything_live_imports_transitively(self):
        with open(LIVE_PATH, encoding="utf-8") as f:
            needed = {m + ".py" for m in re.findall(r"from \.dfc_pipeline\.(\w+) import", f.read())}
        self.assertTrue(needed)
        todo = list(needed)
        while todo:
            for dep in self.sibling_imports(todo.pop()):
                if dep not in needed:
                    needed.add(dep)
                    todo.append(dep)
        self.assertEqual(needed | {"__init__.py"}, self.listed())

    def test_install_and_package_scripts_copy_the_modules(self):
        for name in ("install_addon.ps1", "package_addon.ps1"):
            with open(os.path.join(ROOT, "scripts", name), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("vendor_pipeline.ps1", text, name)
            self.assertIn("Copy-PipelineInto", text, name)

    def test_installed_layout_runs_end_to_end_with_the_copied_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "dfc_probe_installed")
            os.makedirs(os.path.join(pkg, "dfc_pipeline"))
            open(os.path.join(pkg, "__init__.py"), "w").close()
            shutil.copy(LIVE_PATH, pkg)
            for name in self.listed():
                shutil.copy(os.path.join(self.pkg, name), os.path.join(pkg, "dfc_pipeline", name))
            sys.path.insert(0, tmp)
            try:
                mod = importlib.import_module("dfc_probe_installed.live")
                self.assertEqual(mod.parse_note.__module__, "dfc_probe_installed.dfc_pipeline.cards")
                result = mod.generate_variants(basic_record(), FakeLLM(), FakeLLM())
                self.assertEqual(len(result["variants"]), 4)
            finally:
                sys.path.remove(tmp)
                for name in [m for m in sys.modules if m == "dfc_probe_installed" or m.startswith("dfc_probe_installed.")]:
                    del sys.modules[name]


if __name__ == "__main__":
    unittest.main()
