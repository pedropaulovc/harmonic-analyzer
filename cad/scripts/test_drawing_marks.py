"""Focused contracts for drawing-dimension marking across feature trees."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

import _drawing_marks
from pinion_cam_pin_spec import PIN_DIA_BAND
from pinion_cam_spec import BORE_BAND as CAM_BORE_BAND
from pinion_handle_spec import ROD_HOLE_REAM_BAND, ROD_PRESS_BAND
from pinion_lever_spec import BORE_BAND as LEVER_BORE_BAND


class _Display:
    def __init__(self, name: str, owner: str) -> None:
        self.dimension = SimpleNamespace(Name=name, FullName=f"{name}@{owner}@Part")
        self.MarkedForDrawing = False

    def GetDimension2(self, _configuration: int) -> SimpleNamespace:
        return self.dimension


class _Feature:
    def __init__(
        self,
        name: str,
        *,
        displays: list[_Display] | None = None,
        children: list["_Feature"] | None = None,
    ) -> None:
        self.Name = name
        self._displays = displays or []
        self._children = children or []
        self._next_subfeature: _Feature | None = None
        for current, following in zip(
            self._children, self._children[1:], strict=False
        ):
            current._next_subfeature = following

    def GetFirstDisplayDimension(self) -> _Display | None:
        return self._displays[0] if self._displays else None

    def GetNextDisplayDimension(self, display: _Display) -> _Display | None:
        index = self._displays.index(display) + 1
        return self._displays[index] if index < len(self._displays) else None

    def GetFirstSubFeature(self) -> "_Feature | None":
        return self._children[0] if self._children else None

    def GetNextSubFeature(self) -> "_Feature | None":
        return self._next_subfeature


def test_marks_a_hole_wizard_placement_dimension_on_its_subfeature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    placement = _Display("PinchZ", "PlacementProfile")
    feature = _Feature(
        "PinchBore",
        children=[_Feature("PlacementProfile", displays=[placement])],
    )
    monkeypatch.setattr(_drawing_marks, "_feature_by_name", lambda *_args: feature)

    _drawing_marks.mark_dimensions_for_drawing(object(), "PinchBore", {"PinchZ"})

    assert placement.MarkedForDrawing is True


def test_rejects_ambiguous_dimension_names_below_one_feature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature = _Feature(
        "PinchBore",
        children=[
            _Feature("PlacementA", displays=[_Display("PinchZ", "PlacementA")]),
            _Feature("PlacementB", displays=[_Display("PinchZ", "PlacementB")]),
        ],
    )
    monkeypatch.setattr(_drawing_marks, "_feature_by_name", lambda *_args: feature)

    with pytest.raises(RuntimeError, match="drawing dimension 'PinchZ' is ambiguous"):
        _drawing_marks.mark_dimensions_for_drawing(
            object(), "PinchBore", {"PinchZ"}
        )


def test_angular_tolerance_helper_has_an_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    monkeypatch.setattr(_drawing_marks._telemetry, "span", capture_span)

    with pytest.raises(ValueError, match="angular tolerance must be positive"):
        _drawing_marks.set_dimension_symmetric_angular_tolerance(
            object(), "RodProfile", "GripAngle", 0.0
        )

    assert spans == [("dim.angular_tolerance", {"label": "GripAngle"})]


def test_dimension_prefix_helper_has_an_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    class PrefixDisplay:
        def __init__(self) -> None:
            self.prefix = ""

        def SetText(self, _part: int, prefix: str) -> bool:
            self.prefix = prefix
            return True

        def GetText(self, _part: int) -> str:
            return self.prefix

    display = PrefixDisplay()
    monkeypatch.setattr(_drawing_marks._telemetry, "span", capture_span)
    monkeypatch.setattr(
        _drawing_marks, "_named_dimension", lambda *_args: (display, object())
    )
    monkeypatch.setattr(_drawing_marks, "_early_bound", lambda value, _type: value)

    _drawing_marks.set_dimension_prefix(object(), "GripAngleDim", "GripAngle", "REF ")

    assert display.prefix == "REF "
    assert spans == [("dim.prefix", {"label": "GripAngle"})]


@pytest.mark.parametrize(
    ("band", "expected"),
    [
        (PIN_DIA_BAND, 3),
        (CAM_BORE_BAND, 3),
        (ROD_PRESS_BAND, 4),
        (ROD_HOLE_REAM_BAND, 3),
        (LEVER_BORE_BAND, 4),
    ],
)
def test_sub_hundredth_model_bands_get_exact_tolerance_precision(
    band: tuple[float, float], expected: int
) -> None:
    assert _drawing_marks._tolerance_precision_mm(*band) == expected


def test_bilateral_tolerance_sets_and_verifies_display_precision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Tolerance:
        Type = 0

        def __init__(self) -> None:
            self.minimum = 0.0
            self.maximum = 0.0

        def SetValues(self, minimum: float, maximum: float) -> bool:
            self.minimum = minimum
            self.maximum = maximum
            return True

        def GetMinValue(self) -> float:
            return self.minimum

        def GetMaxValue(self) -> float:
            return self.maximum

    class PrecisionDisplay:
        def __init__(self) -> None:
            self.tolerance_precision = -2
            self.calls: list[tuple[int, int, int, int]] = []

        def SetPrecision3(
            self, primary: int, dual: int, primary_tol: int, dual_tol: int
        ) -> int:
            self.calls.append((primary, dual, primary_tol, dual_tol))
            self.tolerance_precision = primary_tol
            return 0

        def GetPrimaryTolPrecision2(self) -> int:
            return self.tolerance_precision

    tolerance = Tolerance()
    display = PrecisionDisplay()
    dimension = SimpleNamespace(Tolerance=tolerance)
    monkeypatch.setattr(
        _drawing_marks,
        "_named_dimension",
        lambda *_args: (display, dimension),
    )
    monkeypatch.setattr(_drawing_marks, "_early_bound", lambda value, _type: value)

    _drawing_marks.set_dimension_bilateral_tolerance(
        object(), "RodProfile", "RodDia", -0.0025, 0.0025
    )

    assert tolerance.Type == 2
    assert display.calls == [(-1, -1, 4, -1)]


def test_tolerance_precision_rejects_silent_com_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    display = SimpleNamespace(
        SetPrecision3=lambda *_args: -1,
        GetPrimaryTolPrecision2=lambda: 2,
    )
    monkeypatch.setattr(_drawing_marks, "_early_bound", lambda value, _type: value)

    with pytest.raises(RuntimeError, match="requested 3 decimals.*reports 2"):
        _drawing_marks._set_tolerance_precision(
            display, (-0.004, 0.004), label="PinDia@PinProfile"
        )
