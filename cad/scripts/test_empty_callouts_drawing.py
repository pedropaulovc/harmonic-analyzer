"""Empty manufacturing callout maps must not touch the COM seat."""

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import _drawing_common as drawing


@pytest.mark.parametrize("location", ["above", "below"])
def test_empty_map_does_not_scan_annotations_or_rebuild(location):
    def annotations():
        raise AssertionError("empty map must not enumerate drawing annotations")
        yield

    drawing.set_dimension_callouts(object(), annotations(), {}, location=location)


def test_empty_map_still_rejects_invalid_location():
    with pytest.raises(KeyError):
        drawing.set_dimension_callouts(object(), (), {}, location="invalid")


@pytest.mark.parametrize("location,slot", [("above", 3), ("below", 4)])
def test_nonempty_map_preserves_exact_named_setter_and_single_rebuild(
    monkeypatch, location, slot
):
    display = NS(SetText=Mock())
    annotation = NS(GetSpecificAnnotation=lambda: display)
    adapter = NS(_attempt=lambda callback: callback(), currentModel=NS(EditRebuild3=Mock()))
    monkeypatch.setattr(drawing._sw_type_info, "early_bound_or_flag", lambda obj, *_: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda *_: "Bore")
    drawing.set_dimension_callouts(adapter, (annotation,), {"Bore": "REAM"}, location=location)
    display.SetText.assert_called_once_with(slot, "REAM")
    adapter.currentModel.EditRebuild3.assert_called_once_with()


def test_missing_nonempty_map_still_rejects_before_rebuild():
    adapter = NS(currentModel=NS(EditRebuild3=Mock()))
    with pytest.raises(RuntimeError, match="callouts not applied"):
        drawing.set_dimension_callouts(adapter, (), {"Bore": "REAM"})
    adapter.currentModel.EditRebuild3.assert_not_called()
