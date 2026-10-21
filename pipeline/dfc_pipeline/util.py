"""Utilitários compartilhados: JSONL, hash, tokenização."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable, Iterable, Iterator

WORD_RE = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text or "")]


def sha1_short(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "sim", "yes", "1", "s", "y")
    return bool(value)


def read_jsonl(path: str) -> Iterator[dict[str, Any]]:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: str, records: Iterable[dict[str, Any]]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def append_jsonl(path: str, record: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_parallel(items: Iterable[Any], fn: Callable[[Any], Any], workers: int, on_result: Callable[[Any, Any], None]) -> None:
    """Roda fn(item) em `workers` threads. on_result(item, resultado) roda sempre na thread principal, na ordem de
    conclusão, então pode gravar arquivo sem trava; só 2 x workers itens ficam em andamento (uma interrupção perde pouco)."""
    if workers <= 1:
        for item in items:
            on_result(item, fn(item))
        return
    source = iter(items)
    running: dict[Any, Any] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            while len(running) < workers * 2:
                try:
                    item = next(source)
                except StopIteration:
                    break
                running[pool.submit(fn, item)] = item
            if not running:
                return
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in finished:
                on_result(running.pop(future), future.result())
