"""Shelve native supplier reference text clear of its own witness lines.

On a small purchased part a reference's text is wider than its span, so
centred on its dimension line it prints across its extension lines (rule 14).
Offset-text mode moves the text alone onto a shelf past the outer witness on
the named side; the native arrows, witnesses and dimension line stay where the
import put them, and the settled check proves they did. This is the measured
method of the supplier_top screw shelves
(``_supplier_screw_dimensions._shelf_supplier_top_text``) for any named
reference, so the per-part sheet chooses the shelves, not the screw family's
fixed name table.
"""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any, Literal

from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _supplier_screw_dimensions import _assert_supplier_top_stations, _supplier_top_record
from _supplier_screw_layout import supplier_top_text_geometry

# name -> (dimension line is horizontal, shelf side past the outer witness)
Shelves = Mapping[str, tuple[bool, Literal["left", "right"]]]


def _measure(adapter: Any, display: Any, horizontal: bool) -> dict[str, Any]:
    return supplier_top_text_geometry(
        _supplier_top_record(adapter, display), horizontal=horizontal
    )


def _gap(actual: Mapping[str, Any], side: str) -> float:
    text = actual["text"]
    return actual["left"] - text.xmax if side == "left" else text.xmin - actual["right"]


def shelve_supplier_text(
    adapter: Any, displays: Mapping[str, Any], shelves: Shelves
) -> dict[str, dict[str, Any]]:
    """Move each named text onto its shelf; return the measured native stations."""
    if not shelves or set(shelves) - set(displays):
        raise ValueError("supplier text shelves must name imported references")
    for name in shelves:
        # A model annotation may inherit offset mode; measure the imported line.
        _early_bound(displays[name], "IDisplayDimension").OffsetText = False
    rebuild_drawing(adapter, label="supplier references settled before shelving")
    before: dict[str, dict[str, Any]] = {}
    heights: dict[str, float] = {}
    anchors: dict[str, tuple[float, float]] = {}
    for name, (horizontal, _side) in shelves.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3 or not all(map(isfinite, position)):
            raise RuntimeError(f"{name}: supplier reference has no native position")
        actual = _measure(adapter, display, horizontal)
        before[name] = actual
        # The shelf keeps the text's original height on the sheet.
        heights[name] = position[1]
        # OffsetText makes the old annotation anchor the physical line station.
        # Seed it from the measured arrow tips first, as on the screw shelves.
        normal = 1 if horizontal else 0
        anchor = list(position[:2])
        anchor[normal] = sum(tip[normal] for tip in actual["tips"]) / 2.0
        anchors[name] = (anchor[0], anchor[1])
        if not annotation.SetPosition2(*anchors[name], 0.0):
            raise RuntimeError(f"{name}: failed to prepare supplier offset anchor")
    rebuild_drawing(adapter, label="supplier measured pre-offset anchors")
    for name, anchor in anchors.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        display.OffsetText = True
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: failed to enable supplier text offset")
    rebuild_drawing(adapter, label="supplier native offset-text mode")
    for name, (horizontal, side) in shelves.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = _measure(adapter, display, horizontal)
        _assert_supplier_top_stations(name, before[name], actual)
        text = actual["text"]
        gap = CLEAR_GAP_M + PLACE_SETTLE_M
        current = tuple(float(value) for value in annotation.GetPosition())
        dx = (
            actual["left"] - gap - text.xmax if side == "left"
            else actual["right"] + gap - text.xmin
        )
        target = (current[0] + dx, heights[name])
        if not annotation.SetPosition2(*target, 0.0):
            raise RuntimeError(f"{name}: failed to place supplier text shelf")
    rebuild_drawing(adapter, label="supplier text shelves settled")
    assert_supplier_shelves(adapter, displays, shelves, before)
    return before


def assert_supplier_shelves(
    adapter: Any,
    displays: Mapping[str, Any],
    shelves: Shelves,
    stations: Mapping[str, Mapping[str, Any]],
) -> None:
    """Read settled shelves: text clear of its witnesses, stations unmoved."""
    if set(stations) != set(shelves) or set(shelves) - set(displays):
        raise RuntimeError("supplier text shelves have no retained native stations")
    for name, (horizontal, side) in shelves.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        actual = _measure(adapter, display, horizontal)
        if display.OffsetText is not True or _gap(actual, side) < CLEAR_GAP_M:
            raise RuntimeError(f"{name}: supplier text shelf is not clear")
        _assert_supplier_top_stations(name, stations[name], actual)
