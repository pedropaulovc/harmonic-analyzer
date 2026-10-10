"""Stock-fastener thread declaration and local recipe contracts (SolidWorks-free)."""

from __future__ import annotations

import ast
import asyncio
import importlib
import re
from functools import wraps
from pathlib import Path
from types import SimpleNamespace

import pytest

import _stock_fastener
from _buildgraph import module_deps_of
from _stock_fastener import THREAD_FEATURE
from _stock_recipe import recipe_declaration, stock_recipe
from _test_stock_recipes import discovered_recipes

SCRIPTS = Path(__file__).resolve().parent
DIAGNOSTICS = SCRIPTS / "diagnostics"
_RECIPE_IMPORT = re.compile(r"^from diagnostics\.(diag_\w+) import", re.MULTILINE)


def _cuts_thread(module: str) -> bool:
    """Whether a recipe (or a family helper it imports) names the thread cut."""
    source = (DIAGNOSTICS / f"{module}.py").read_text(encoding="utf-8")
    helpers = set(_RECIPE_IMPORT.findall(source)) - {"diag_mcmaster_lib"}
    return f'"{THREAD_FEATURE}"' in source or any(_cuts_thread(name) for name in helpers)


def test_every_recipe_declares_the_thread_it_cuts() -> None:
    recipes = discovered_recipes()
    declared = {sku: metadata.threaded for sku, metadata in recipes.items()}
    scanned = {
        sku: _cuts_thread(metadata.module.removeprefix("diagnostics."))
        for sku, metadata in recipes.items()
    }
    # Anchors: a scan that found nothing (or everything) must not pass.
    assert scanned["91375A106"] and scanned["90280A194"] and not scanned["98381A473"]
    # The partial-thread SHCS cuts its groove in the shared socket-head helper.
    assert scanned["91251A157"] and scanned["91251A108"]
    assert declared == scanned


def _part(groove: bool) -> SimpleNamespace:
    features = {THREAD_FEATURE: object()} if groove else {}
    return SimpleNamespace(currentModel=SimpleNamespace(FeatureByName=features.get))


@pytest.fixture
def saves(monkeypatch) -> SimpleNamespace:
    def record(kind: str):
        async def save(*_args, **_kwargs) -> str:
            return kind

        return save

    simplified = record("simplified")
    monkeypatch.setattr(_stock_fastener, "save_part_and_images", record("plain"))
    return SimpleNamespace(simplified=simplified)


@pytest.mark.parametrize(("threaded", "saved"), [(True, "simplified"), (False, "plain")])
def test_a_stock_part_saves_with_its_declared_thread(threaded, saved, saves) -> None:
    result = _stock_fastener._save_stock_part(
        _part(threaded),
        "screw",
        threaded=threaded,
        save_threaded_part=saves.simplified if threaded else None,
    )
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
        asyncio.run(
            _stock_fastener._save_stock_part(_part(groove), "screw", threaded=threaded)
        )


@pytest.mark.parametrize("saver", [None, False, "save_simplified_part"])
def test_threaded_stock_requires_an_explicit_callable_saver(saver) -> None:
    with pytest.raises(TypeError, match="requires a callable simplified saver"):
        asyncio.run(
            _stock_fastener._save_stock_part(
                _part(True), "screw", threaded=True, save_threaded_part=saver
            )
        )


def test_threaded_save_receives_the_declared_suppression_feature() -> None:
    adapter = _part(True)
    saved = {"part": "screw.SLDPRT"}

    async def save(actual_adapter, name, features):
        assert actual_adapter is adapter
        assert name == "screw"
        assert features == (THREAD_FEATURE,)
        return saved

    assert (
        asyncio.run(
            _stock_fastener._save_stock_part(
                adapter, "screw", threaded=True, save_threaded_part=save
            )
        )
        is saved
    )


def test_unthreaded_save_never_calls_part_simplification(saves) -> None:
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("unthreaded part reached simplification")

    assert (
        asyncio.run(
            _stock_fastener._save_stock_part(
                _part(False), "washer", threaded=False, save_threaded_part=forbidden
            )
        )
        == "plain"
    )


def _author(sku: str = "TEST123"):
    async def author(_adapter, _truth=None):
        return None

    author.__name__ = f"build_{sku}"
    author.__module__ = f"diagnostics.diag_build_{sku}"
    return author


def test_local_declaration_preserves_the_author_and_stock_rework_wrapper() -> None:
    author = _author()
    decorated = stock_recipe("TEST123", threaded=True)(author)
    assert decorated is author
    declaration = recipe_declaration("TEST123", author)
    assert declaration.sku == "TEST123"
    assert declaration.module == "diagnostics.diag_build_TEST123"
    assert declaration.callable_name == "build_TEST123"
    assert declaration.threaded is True

    @wraps(author)
    async def reworked(*args, **kwargs):
        return await author(*args, **kwargs)

    assert recipe_declaration("TEST123", reworked) is declaration


@pytest.mark.parametrize("author", [None, False, object()])
def test_noncallable_stock_recipe_authors_are_refused(author) -> None:
    with pytest.raises(TypeError, match="recipe author is not callable"):
        recipe_declaration("TEST123", author)


def test_undeclared_stock_recipe_is_unknown() -> None:
    with pytest.raises(KeyError, match="unknown stock fastener SKU"):
        recipe_declaration("TEST123", _author())


def test_stock_recipe_sku_must_match_its_local_declaration() -> None:
    author = stock_recipe("TEST123", threaded=False)(_author())
    with pytest.raises(ValueError, match="requires its own recipe.*TEST123"):
        recipe_declaration("OTHER456", author)


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        ("__name__", "other_author", "requires recipe 'build_TEST123'"),
        ("__module__", "other.module", "requires recipe module"),
    ],
)
def test_stock_recipe_author_identity_is_checked_again_at_use(attribute, value, message):
    author = stock_recipe("TEST123", threaded=False)(_author())
    setattr(author, attribute, value)
    with pytest.raises(ValueError, match=message):
        recipe_declaration("TEST123", author)


def test_local_declaration_rejects_the_wrong_callable_name() -> None:
    with pytest.raises(ValueError, match="requires recipe 'build_OTHER456'"):
        stock_recipe("OTHER456", threaded=False)(_author())


def test_stock_builder_closures_track_local_metadata_and_threaded_saves(monkeypatch):
    """The callback is a real static dependency only for builders that need it."""
    shared = {Path(path).stem for path in module_deps_of(SCRIPTS / "_stock_fastener.py")}
    assert "_stock_recipe" in shared
    assert "_simplified_part" not in shared
    checked_threaded = checked_unthreaded = 0
    declared_modules = {
        metadata.module.rsplit(".", 1)[1]
        for metadata in discovered_recipes().values()
    }
    for path in sorted(SCRIPTS.glob("build_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if not any(
            isinstance(node, ast.ImportFrom)
            and node.module == "_stock_fastener"
            and any(alias.name == "build_stock_fastener" for alias in node.names)
            for node in ast.walk(tree)
        ):
            continue
        builder = importlib.import_module(path.stem)
        captured = {}

        async def capture(_adapter, **kwargs):
            captured.update(kwargs)
            return {}

        monkeypatch.setattr(builder, "build_stock_fastener", capture)
        asyncio.run(builder.build(object()))
        declarations = [
            recipe_declaration(component.sku, component.author)
            for component in captured["components"]
        ]
        assert declarations, path.name
        threaded = any(declaration.threaded for declaration in declarations)
        closure = {Path(dependency).stem for dependency in module_deps_of(path)}
        assert "_stock_recipe" in closure, path.name
        own_modules = {
            declaration.module.rsplit(".", 1)[1] for declaration in declarations
        }
        assert closure & declared_modules == own_modules, path.name
        if threaded:
            assert callable(captured.get("save_threaded_part")), path.name
            assert "_simplified_part" in closure, path.name
            checked_threaded += 1
        else:
            assert captured.get("save_threaded_part") is None, path.name
            assert "_simplified_part" not in closure, path.name
            checked_unthreaded += 1
    assert checked_threaded and checked_unthreaded
