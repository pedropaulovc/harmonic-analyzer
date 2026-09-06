"""SF typography follows the drawing's dimension standard, not a fixed size."""

from types import SimpleNamespace
from copy import deepcopy
from unittest.mock import Mock, PropertyMock

import pytest

import _drawing_common as drawing


def context(monkeypatch, height=0.0035, font="Century Gothic"):
    text = SimpleNamespace(CharHeight=height, TypeFaceName=font, WidthFactor=1.0, Italic=False)
    model, symbol, annotation = Mock(), Mock(), Mock()
    model.Extension.GetUserPreferenceTextFormat.return_value = text
    symbol.GetAngle.return_value = 0.0
    annotation.GetTextFormat.return_value = text
    annotation.SetTextFormat.return_value = True
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _kind: value)
    return SimpleNamespace(currentModel=model), symbol, annotation, text


@pytest.mark.parametrize("height,font", [(0.0035, "Century Gothic"), (0.0025, "Arial")])
def test_surface_style_uses_actual_dimension_font_and_native_upright(monkeypatch, height, font):
    adapter, symbol, annotation, text = context(monkeypatch, height, font)
    drawing._style_surface_finish(adapter, symbol, annotation, label="bore")
    adapter.currentModel.Extension.GetUserPreferenceTextFormat.assert_called_once_with(1, 0)
    annotation.SetTextFormat.assert_called_once_with(0, False, text)
    assert symbol.Orientation == 1
    annotation.SetPosition2.assert_not_called()
    annotation.SetAttachedEntities.assert_not_called()
    symbol.SetText.assert_not_called()
    adapter.currentModel.Extension.SetUserPreferenceTextFormat.assert_not_called()
    adapter.currentModel.EditRebuild3.assert_not_called()


@pytest.mark.parametrize("failure", ["missing_standard", "height", "font", "rejected", "missing_readback", "changed_size", "changed_font", "orientation", "angle"])
def test_surface_style_rejects_missing_or_unapplied_native_style(monkeypatch, failure):
    adapter, symbol, annotation, text = context(monkeypatch)
    if failure == "missing_standard":
        adapter.currentModel.Extension.GetUserPreferenceTextFormat.return_value = None
    if failure == "height":
        text.CharHeight = float("nan")
    if failure == "font":
        text.TypeFaceName = ""
    if failure == "rejected":
        annotation.SetTextFormat.return_value = False
    if failure == "missing_readback":
        annotation.GetTextFormat.return_value = None
    if failure in {"changed_size", "changed_font"}:
        annotation.GetTextFormat.return_value = SimpleNamespace(
            CharHeight=0.00635 if failure == "changed_size" else text.CharHeight,
            TypeFaceName="Wrong" if failure == "changed_font" else text.TypeFaceName,
            WidthFactor=1.0, Italic=False,
        )
    if failure == "orientation":
        type(symbol).Orientation = PropertyMock(return_value=3)
    if failure == "angle":
        symbol.GetAngle.return_value = 1.0
    with pytest.raises(RuntimeError, match="bore"):
        drawing._style_surface_finish(adapter, symbol, annotation, label="bore")


@pytest.mark.parametrize("failure", [None, "font", "orientation", "position", "text", "glyph_height", "glyph_angle"])
def test_saved_surface_witness_requires_real_rendered_font_and_content(failure):
    from probe_drawing_annotation_layout import _validate_reopened_surface

    before = {"format": {"height_m": 0.0035, "font": "Century Gothic"},
              "orientation": 1, "angle": 0, "position": (0.2, 0.1, 0),
              "text": [{"value": "Ra 1.6", "height_m": 0.0035, "angle": 0}]}
    after = deepcopy(before)
    if failure == "font":
        after["format"]["height_m"] = 0.00635
    if failure == "orientation":
        after["orientation"] = 3
    if failure == "position":
        after["position"] = (0.2, 0.2, 0)
    if failure == "text":
        after["text"][0]["value"] = "Ra 9.9"
    if failure == "glyph_height":
        after["text"][0]["height_m"] = 0.00635
    if failure == "glyph_angle":
        after["text"][0]["angle"] = 0.8
    if failure is None:
        _validate_reopened_surface(before, after)
        return
    with pytest.raises(RuntimeError, match="saved SF"):
        _validate_reopened_surface(before, after)


@pytest.mark.parametrize("names", [[], ["SF1"], ["SF1", "SF1"], ["SF1", "SF2", "SF2"], ["SF1", "Extra"]])
def test_reopened_surface_inventory_rejects_missing_extra_or_duplicate_symbols(names):
    from probe_drawing_annotation_layout import _validate_surface_inventory

    before = [{"name": "SF1"}, {"name": "SF2"}]
    after = [{"name": name} for name in names]
    with pytest.raises(RuntimeError, match="SF inventory"):
        _validate_surface_inventory(before, after)


def test_surface_inventory_reordering_is_valid_but_ambiguous_baseline_is_not():
    from probe_drawing_annotation_layout import _validate_surface_inventory

    before = [{"name": "SF1"}, {"name": "SF2"}]
    _validate_surface_inventory(before, before[::-1])
    with pytest.raises(RuntimeError, match="SF inventory"):
        _validate_surface_inventory([{"name": "SF1"}, {"name": "SF1"}], [{"name": "SF1"}, {"name": "SF1"}])


@pytest.mark.parametrize("reopened_names", [[], ["SF1"], ["SF1", "SF1"], ["SF1", "SF2", "SF2"], ["SF2", "SF1"]])
def test_probe_worker_validates_inventory_before_reporting_passed(monkeypatch, tmp_path, reopened_names):
    import asyncio
    import json
    import sys
    from pathlib import Path

    import probe_drawing_annotation_layout as probe

    source, part = tmp_path / "source.SLDDRW", tmp_path / "source.SLDPRT"
    source.write_bytes(b"original drawing")
    part.write_bytes(b"original part")
    model, view = Mock(), Mock()
    view.ReferencedDocument.GetPathName.return_value = str(part)
    model.GetViews.return_value = [[object(), view]]
    adapter = SimpleNamespace(currentModel=None, swApp=Mock())
    adapter.swApp.IsSame.return_value = 1
    entity = object()

    def annotation(name):
        value = Mock()
        value.GetName.return_value = name
        value.GetPosition.return_value = (0.2, 0.1, 0)
        value.GetAttachedEntities3.return_value = (entity,)
        value.GetAttachedEntityTypes.return_value = (1,)
        value.SetTextFormat.return_value = True
        value.Owner = view
        return value

    original, explicit = annotation("SF1"), annotation("SF2")
    phases = iter(([original], [annotation(name) for name in reopened_names]))

    async def open_model(path):
        adapter.currentModel = model
        model.GetPathName.return_value = path
        view.GetAnnotationsByType.return_value = next(phases)
        return None

    async def close_model(*, save):
        assert save is False
        adapter.currentModel = None
        return None

    def surface(value):
        return {"name": value.GetName(), "position": (0.2, 0.1, 0),
                "format": {"height_m": 0.0035, "font": "Arial"}, "orientation": 1, "angle": 0,
                "text": [{"value": "Ra 1.6", "height_m": 0.0035, "angle": 0}]}

    adapter.open_model, adapter.close_model = open_model, close_model
    monkeypatch.setattr(probe, "CAD_ROOT", tmp_path)
    monkeypatch.setattr(probe, "_early_bound", lambda value, _kind: value)
    monkeypatch.setattr(probe, "_surface", surface)
    monkeypatch.setattr(probe, "_document_formats", lambda _extension: {})
    monkeypatch.setattr(probe, "_attachment_geometry", lambda _annotation: [{"radius": 0.01}])
    monkeypatch.setattr(probe, "check", lambda *_args: None)
    monkeypatch.setattr(probe, "add_surface_finish", lambda *_args, **_kwargs: SimpleNamespace(GetAnnotation=lambda: explicit))
    monkeypatch.setattr(probe._drawing_common, "_style_surface_finish", Mock())
    monkeypatch.setattr(probe, "save_drawing", lambda *_args, **_kwargs: {"drawing": "copy", "pdf": "copy.pdf"})
    monkeypatch.setattr(probe, "render_pdf_png", Mock())
    monkeypatch.setattr(probe, "run_build", lambda operation: asyncio.run(operation(adapter)))
    monkeypatch.setattr(probe._telemetry, "set_service", Mock())
    monkeypatch.setattr(sys, "argv", [str(Path(probe.__file__)), str(source), "--worker"])
    monkeypatch.setenv("HARMONIC_COM_SEAT", "mocked-no-com")
    if reopened_names == ["SF2", "SF1"]:
        probe.main()
    else:
        with pytest.raises(RuntimeError, match="SF inventory"):
            probe.main()
    report_path, = (tmp_path / "out/reports").glob("annotation-layout-*/layout.json")
    report = json.loads(report_path.read_text())
    assert (report["stage"] == "passed") == (reopened_names == ["SF2", "SF1"])
    assert all(report["source_unchanged"].values())
