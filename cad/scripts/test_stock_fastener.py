"""Stock-fastener thread declaration (SolidWorks-free)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _stock_fastener
from _stock_fastener import STOCK_RECIPES, THREAD_FEATURE

DIAGNOSTICS = Path(__file__).resolve().parent / "diagnostics"
_RECIPE_IMPORT = re.compile(r"^from diagnostics\.(diag_\w+) import", re.MULTILINE)


def _cuts_thread(module: str) -> bool:
    """Whether a recipe (or a family helper it imports) names the thread cut."""
    source = (DIAGNOSTICS / f"{module}.py").read_text(encoding="utf-8")
    helpers = set(_RECIPE_IMPORT.findall(source)) - {"diag_mcmaster_lib"}
    return f'"{THREAD_FEATURE}"' in source or any(_cuts_thread(name) for name in helpers)


def test_every_recipe_declares_the_thread_it_cuts() -> None:
    declared = {sku: metadata.threaded for sku, metadata in STOCK_RECIPES.items()}
    scanned = {
        sku: _cuts_thread(metadata.module.removeprefix("diagnostics."))
        for sku, metadata in STOCK_RECIPES.items()
    }
    # Anchors: a scan that found nothing (or everything) must not pass.
    assert scanned["91375A106"] and scanned["90280A194"] and not scanned["90126A211"]
    assert declared == scanned


def _part(groove: bool) -> SimpleNamespace:
    features = {THREAD_FEATURE: object()} if groove else {}
    return SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))


@pytest.fixture
def saves(monkeypatch) -> None:
    def record(kind: str):
        async def save(*_args, **_kwargs) -> str:
            return kind

        return save

    monkeypatch.setattr(_stock_fastener, "save_simplified_part", record("simplified"))
    monkeypatch.setattr(_stock_fastener, "save_part_and_images", record("plain"))


@pytest.mark.usefixtures("saves")
@pytest.mark.parametrize(("threaded", "saved"), [(True, "simplified"), (False, "plain")])
def test_a_stock_part_saves_with_its_declared_thread(threaded, saved) -> None:
    result = _stock_fastener._save_stock_part(_part(threaded), "screw", threaded=threaded)
    assert asyncio.run(result) == saved


@pytest.mark.usefixtures("saves")
@pytest.mark.parametrize(
    ("threaded", "groove", "message"),
    [
        # A renamed (or never cut) groove would save without simplified views.
        (True, False, "declare it threaded but it has no 'ThreadGroove'"),
        (False, True, "declare it unthreaded but it has 'ThreadGroove'"),
    ],
)
def test_a_stock_part_contradicting_its_recipe_is_refused(threaded, groove, message) -> None:
    with pytest.raises(RuntimeError, match=message):
        asyncio.run(_stock_fastener._save_stock_part(_part(groove), "screw", threaded=threaded))
