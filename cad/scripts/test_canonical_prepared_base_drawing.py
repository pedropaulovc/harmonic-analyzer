"""Canonical cache identity and per-instance native scale; COM-free doubles."""

import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_build as factory
import _drawing_prepared_template as prepared
import _drawing_sheet_setup as setup
from test_prepared_template_drawing import cache as cache, access
from test_template_preparation_dependencies_drawing import registered_specs


def test_all_fifteen_requested_specs_use_one_truthful_base_per_precision(cache):
    specs = registered_specs()
    assert len(specs) == 15
    entries = [access(cache, decimals=spec.decimals) for spec in specs]
    assert len({entry.key for entry in entries}) == 1
    assert len(cache.calls) == 1
    assert all(entry.spec == prepared.TemplateSpec() for entry in entries)
    precision = access(cache, decimals=3)
    assert precision.spec == prepared.TemplateSpec(decimals=3)
    assert precision.key != entries[0].key
    assert len(cache.calls) == 2
    for spec in specs:
        assert prepared.canonical_spec(spec) == entries[0].spec


def test_preparer_does_not_accept_a_requested_scale_as_an_artifact_spec(cache):
    with pytest.raises(TypeError, match="scale"):
        access(cache, scale=(2, 1))
    assert cache.calls == []


@pytest.fixture
def blank(monkeypatch):
    monkeypatch.setenv("HARMONIC_COM_SEAT", "offline-test")
    events = []
    properties = [0, 0, 1.0, 1.0, 0, setup.ASME_B_WIDTH_M, setup.ASME_B_HEIGHT_M, 0]

    def set_scale(numerator, denominator, positions, text_height):
        events.append(("scale", numerator, denominator, positions, text_height))
        properties[2:4] = [numerator, denominator]
        return True

    sheet = NS(
        GetProperties2=lambda: list(properties), SetScale=Mock(side_effect=set_scale)
    )
    draw = NS(
        EditSheet=lambda: events.append("edit"),
        GetCurrentSheet=lambda: sheet,
        GetViews=lambda: ((object(),),),
        GetType=lambda: 3,
        GetPathName=lambda: "",
        ViewZoomtofit2=lambda: events.append("fit"),
    )
    app = NS(ActiveDoc=draw, IsSame=lambda a, b: int(a is b))
    adapter = NS(
        currentModel=draw,
        swApp=app,
        _get_attr_or_call=lambda obj, name: getattr(obj, name)(),
    )
    monkeypatch.setattr(prepared, "_early_bound", lambda obj, _: obj)
    monkeypatch.setattr(prepared, "preparation_inputs", lambda *_: {})
    read = Mock(return_value=Path("prepared.DRWDOT"))
    monkeypatch.setattr(prepared, "_read_entry", read)
    create = Mock(return_value=draw)
    monkeypatch.setattr(setup, "new_drawing", create)
    entry = prepared.PreparedTemplate(Path("cache"), "key", prepared.TemplateSpec())
    return NS(
        adapter=adapter,
        draw=draw,
        sheet=sheet,
        entry=entry,
        properties=properties,
        events=events,
        create=create,
        read=read,
    )


@pytest.mark.parametrize("spec", registered_specs())
def test_every_requested_scale_is_applied_to_owned_empty_instance(blank, spec):
    created = factory.prepared_drawing_factory(blank.adapter, blank.entry, spec=spec)
    assert created.spec == spec
    assert created(blank.adapter, scale=spec.scale, decimals=spec.decimals) == (
        blank.draw,
        blank.sheet,
    )
    blank.sheet.SetScale.assert_called_once_with(*spec.scale, True, False)
    assert blank.entry.spec.scale == (1.0, 1.0)
    assert blank.properties[2:4] == list(spec.scale)
    assert blank.events == ["edit", ("scale", *spec.scale, True, False), "fit"]
    created.require_used()


@pytest.mark.parametrize(
    "damage",
    [
        "base_scale",
        "model_view",
        "second_sheet",
        "null_view",
        "saved",
        "wrong_active",
        "wrong_current",
    ],
)
def test_unproved_empty_base_or_wrong_owned_context_rejects_before_scale(blank, damage):
    if damage == "base_scale":
        blank.properties[2:4] = [4, 1]
    if damage == "model_view":
        blank.draw.GetViews = lambda: ((object(), object()),)
    if damage == "second_sheet":
        blank.draw.GetViews = lambda: ((object(),), (object(),))
    if damage == "null_view":
        blank.draw.GetViews = lambda: ((None,),)
    if damage == "saved":
        blank.draw.GetPathName = lambda: "foreign.SLDDRW"
    if damage == "wrong_active":
        blank.adapter.swApp.ActiveDoc = object()
    if damage == "wrong_current":
        blank.adapter.currentModel = object()
    with pytest.raises(RuntimeError):
        prepared.inherited_drawing(
            blank.adapter, blank.entry, spec=prepared.TemplateSpec((2, 1))
        )
    blank.sheet.SetScale.assert_not_called()


@pytest.mark.parametrize("damage", ["false", "clamped"])
def test_native_scale_rejection_or_incorrect_readback_is_fatal(blank, damage):
    blank.sheet.SetScale.side_effect = None
    blank.sheet.SetScale.return_value = damage != "false"
    with pytest.raises(RuntimeError, match="scale|sheet"):
        prepared.inherited_drawing(
            blank.adapter, blank.entry, spec=prepared.TemplateSpec((2, 1))
        )
    assert "fit" not in blank.events


def test_precision_mismatch_and_noncanonical_entry_fail_before_creation(blank):
    with pytest.raises(RuntimeError, match="canonical"):
        factory.prepared_drawing_factory(
            blank.adapter, blank.entry, spec=prepared.TemplateSpec(decimals=3)
        )
    wrong = prepared.PreparedTemplate(
        Path("cache"), "wrong", prepared.TemplateSpec((2, 1))
    )
    with pytest.raises(RuntimeError, match="canonical"):
        factory.prepared_drawing_factory(
            blank.adapter, wrong, spec=prepared.TemplateSpec((2, 1))
        )
    blank.create.assert_not_called()


def test_production_preparation_binds_requested_spec_not_entry_scale(monkeypatch):
    spec = prepared.TemplateSpec((1, 8))
    entry = prepared.PreparedTemplate(Path("cache"), "key", prepared.TemplateSpec())

    async def prepare(adapter, *, decimals):
        assert decimals == 2
        return entry

    monkeypatch.setattr(prepared, "prepare_project_drawing_template", prepare)
    actual = asyncio.run(factory.prepare_drawing_factory(object(), spec))
    assert actual.spec == spec and entry.spec == prepared.TemplateSpec()
