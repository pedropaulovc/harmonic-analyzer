"""Focused contracts for drawing-dimension marking across feature trees."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

import _drawing_marks
import _dimension_prefix
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
        for current, following in zip(self._children, self._children[1:], strict=False):
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
        _drawing_marks.mark_dimensions_for_drawing(object(), "PinchBore", {"PinchZ"})


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

        def SetText(self, _part: int, prefix: str) -> None:
            self.prefix = prefix

        def GetText(self, _part: int) -> str:
            return self.prefix

    display = PrefixDisplay()
    monkeypatch.setattr(_dimension_prefix._telemetry, "span", capture_span)
    monkeypatch.setattr(
        _dimension_prefix, "_named_dimension", lambda *_args: (display, object())
    )
    monkeypatch.setattr(_dimension_prefix, "_early_bound", lambda value, _type: value)

    _dimension_prefix.set_dimension_prefix(object(), "GripAngleDim", "GripAngle", "REF ")

    assert display.prefix == "REF "
    assert spans == [("dim.prefix", {"label": "GripAngle"})]


@pytest.mark.parametrize("prefix", ["REF ", "", "2X "])
def test_dimension_prefix_accepts_void_setter_with_exact_readback(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    calls = []
    text = {}

    def set_text(part, value):
        calls.append(("set", part, value))
        text[part] = value

    def get_text(part):
        calls.append(("get", part))
        return text[part]

    display = SimpleNamespace(SetText=set_text, GetText=get_text)
    monkeypatch.setattr(
        _dimension_prefix, "_named_dimension", lambda *_args: (display, object())
    )
    monkeypatch.setattr(_dimension_prefix, "_early_bound", lambda value, _type: value)

    _dimension_prefix.set_dimension_prefix(object(), "GripAngleDim", "GripAngle", prefix)

    assert calls == [("set", 1, prefix), ("get", 1)]


@pytest.mark.parametrize(
    ("prefix", "observed"), [("REF ", "REF"), ("REF ", ""), ("", None)]
)
def test_dimension_prefix_rejects_mismatched_or_null_readback(
    monkeypatch: pytest.MonkeyPatch, prefix: str, observed: str | None
) -> None:
    calls = []
    display = SimpleNamespace(
        SetText=lambda part, value: calls.append((part, value)),
        GetText=lambda _part: observed,
    )
    monkeypatch.setattr(
        _dimension_prefix, "_named_dimension", lambda *_args: (display, object())
    )
    monkeypatch.setattr(_dimension_prefix, "_early_bound", lambda value, _type: value)

    with pytest.raises(
        RuntimeError, match="GripAngle@GripAngleDim: prefix did not persist"
    ):
        _dimension_prefix.set_dimension_prefix(
            object(), "GripAngleDim", "GripAngle", prefix
        )

    assert calls == [(1, prefix)]


@pytest.mark.parametrize("failure_stage", ["setter", "getter"])
@pytest.mark.parametrize("failure_type", ["runtime", "com"])
def test_dimension_prefix_propagates_native_exception_through_operation_span(
    monkeypatch: pytest.MonkeyPatch, failure_stage: str, failure_type: str
) -> None:
    failure = RuntimeError("COM call rejected")
    if failure_type == "com":
        # Construct only the native exception, never a COM adapter/server.
        failure = pytest.importorskip("pywintypes").com_error(
            -2147352567, "COM call rejected", None, None
        )
    calls, spans, caught_in_span = [], [], []

    def set_text(part, value):
        calls.append(("set", part, value))
        if failure_stage == "setter":
            raise failure

    def get_text(part):
        calls.append(("get", part))
        raise failure

    @contextmanager
    def capture_span(name, **attributes):
        spans.append((name, attributes))
        try:
            yield
        except Exception as error:
            caught_in_span.append(error)
            raise

    display = SimpleNamespace(SetText=set_text, GetText=get_text)
    monkeypatch.setattr(
        _dimension_prefix, "_named_dimension", lambda *_args: (display, object())
    )
    monkeypatch.setattr(_dimension_prefix, "_early_bound", lambda value, _type: value)
    monkeypatch.setattr(_dimension_prefix._telemetry, "span", capture_span)

    with pytest.raises(type(failure), match="COM call rejected") as caught:
        _dimension_prefix.set_dimension_prefix(
            object(), "GripAngleDim", "GripAngle", "REF "
        )

    assert caught.value is failure
    assert caught_in_span == [failure]
    assert spans == [("dim.prefix", {"label": "GripAngle"})]
    expected = [("set", 1, "REF ")]
    if failure_stage == "getter":
        expected.append(("get", 1))
    assert calls == expected


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


def test_tolerance_precision_has_dimension_labeled_operation_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spans: list[tuple[str, dict[str, Any]]] = []

    @contextmanager
    def capture_span(name: str, **attributes: Any):
        spans.append((name, attributes))
        yield

    display = SimpleNamespace(
        SetPrecision3=lambda *_args: 0,
        GetPrimaryTolPrecision2=lambda: 3,
    )
    monkeypatch.setattr(_drawing_marks._telemetry, "span", capture_span)
    monkeypatch.setattr(_drawing_marks, "_early_bound", lambda value, _type: value)

    assert (
        _drawing_marks._set_tolerance_precision(
            display, (-0.004, 0.004), label="PinDia@PinProfile"
        )
        == 3
    )
    assert spans == [("dim.tolerance_precision", {"label": "PinDia@PinProfile"})]
