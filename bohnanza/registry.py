"""Discovers Bot subclasses in the bots/ directory.

Key = class attribute `key` if set, else the module filename (if it defines one bot),
else the snake_case class name.
"""
import importlib.util
import inspect
import re
import sys
from pathlib import Path

from .bot import Bot

DEFAULT_BOTS_DIR = Path(__file__).resolve().parent.parent / "bots"
_cache: dict[str, dict[str, type[Bot]]] = {}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def discover(bots_dir: "str | Path | None" = None) -> dict[str, type[Bot]]:
    d = Path(bots_dir or DEFAULT_BOTS_DIR).resolve()
    if str(d) in _cache:
        return _cache[str(d)]
    found: dict[str, type[Bot]] = {}
    for path in sorted(d.glob("*.py")):
        if path.name.startswith("_"):
            continue
        mod_name = f"bohnanza_userbots.{path.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
        classes = [c for _, c in inspect.getmembers(mod, inspect.isclass)
                   if issubclass(c, Bot) and c is not Bot and c.__module__ == mod_name]
        for c in classes:
            key = c.__dict__.get("key") or (path.stem if len(classes) == 1 else _snake(c.__name__))
            if key in found:
                raise ValueError(f"duplicate bot key {key!r} ({path})")
            found[key] = c
    _cache[str(d)] = found
    return found


def make_bot(key: str, bots_dir=None) -> Bot:
    bots = discover(bots_dir)
    if key not in bots:
        raise KeyError(f"unknown bot {key!r}. Available: {', '.join(sorted(bots))}")
    b = bots[key]()
    b._registry_key = key
    return b
