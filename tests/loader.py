"""Loads scripts/build-episodes.py (hyphenated, so not importable) as `be`."""
import importlib.util
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "cloudcasts.json")


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_episodes", os.path.join(ROOT, "scripts", "build-episodes.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


be = _load()


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)
