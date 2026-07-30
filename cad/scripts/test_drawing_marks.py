"""Focused contracts for drawing-dimension marking across feature trees."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

import _drawing_marks


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
