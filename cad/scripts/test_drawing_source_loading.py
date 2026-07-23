"""Contracts for lazy drawing-source loading through the first placed view."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import _drawing_common


SCRIPTS = Path(__file__).resolve().parent


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def test_every_recipe_validates_properties_through_its_first_view():
    recipes = sorted(SCRIPTS.glob("draw_*.py"))
    assert len(recipes) == 93
    delegated: list[Path] = []
    for recipe in recipes:
        tree = ast.parse(recipe.read_text(encoding="utf-8"), filename=str(recipe))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert not [call for call in calls if _call_name(call) == "open_model"], recipe

        delegates = [
            call for call in calls if _call_name(call) == "build_fastener_sheet"
        ]
        if delegates:
            assert len(delegates) == 1, recipe
            delegated.append(recipe)
            continue

        placed_views = [call for call in calls if _call_name(call) == "place_view"]
        assert placed_views, recipe
        first_view = min(placed_views, key=lambda call: call.lineno)
        validations = [
            call
            for call in calls
            if _call_name(call) == "read_required_view_properties"
        ]
        assert len(validations) == 1, recipe
        assert first_view.lineno < validations[0].lineno, recipe

    assert len(delegated) == 6
    helper = SCRIPTS / "_fastener_drawing.py"
    tree = ast.parse(helper.read_text(encoding="utf-8"), filename=str(helper))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert not [call for call in calls if _call_name(call) == "open_model"]
    first_view = min(
        (call for call in calls if _call_name(call) == "place_view"),
        key=lambda call: call.lineno,
    )
    validations = [
        call for call in calls if _call_name(call) == "read_required_view_properties"
    ]
    assert len(validations) == 1
    assert first_view.lineno < validations[0].lineno


def test_view_property_reader_uses_referenced_document(monkeypatch):
    class Model:
        def GetCustomInfoValue(self, _configuration, name):
            return {"Number": "MHA-002", "Finish": "AS MACHINED"}.get(name, "")

    model = Model()
    view = SimpleNamespace(ReferencedDocument=model)
    adapter = SimpleNamespace(
        _get_attr_or_call=lambda owner, name: getattr(owner, name)
    )
    monkeypatch.setattr(
        _drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda owner, *_args: owner,
    )

    properties = _drawing_common.read_required_view_properties(
        adapter,
        view,
        ("Number", "Finish"),
        required=("Number", "Finish"),
    )
    assert properties == {"Number": "MHA-002", "Finish": "AS MACHINED"}


def test_view_property_reader_fails_without_referenced_document(monkeypatch):
    view = SimpleNamespace(ReferencedDocument=None)
    adapter = SimpleNamespace(
        _get_attr_or_call=lambda owner, name: getattr(owner, name)
    )
    monkeypatch.setattr(
        _drawing_common._sw_type_info,
        "early_bound_or_flag",
        lambda owner, *_args: owner,
    )

    with pytest.raises(RuntimeError, match="no referenced source document"):
        _drawing_common.read_required_view_properties(
            adapter, view, ("Number",), required=("Number",)
        )
