"""Carrega os módulos puros do add-on (sem Anki) como um pacote falso, para os imports relativos funcionarem nos testes."""
import importlib
import os
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ADDON = os.path.join(ROOT, "addon", "dfc_probe")
PIPELINE = os.path.join(ROOT, "pipeline")
PKG = "dfc_probe_pure"

if PIPELINE not in sys.path:
    sys.path.insert(0, PIPELINE)  # `live` cai para `dfc_pipeline` quando a cópia dentro do add-on não existe (repositório)


def load(name: str):
    if PKG not in sys.modules:
        pkg = types.ModuleType(PKG)
        pkg.__path__ = [ADDON]
        sys.modules[PKG] = pkg
    return importlib.import_module(f"{PKG}.{name}")
