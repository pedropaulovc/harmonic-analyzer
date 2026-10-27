"""Projected-zone and axis lines authored in a drawing view's sketch, shared
by the transgear arm (MHA-PD-18) and its plate (MHA-PD-19).

Each caller projects its own model points onto the sheet and keeps its own
caption semantics, rebuild timing and settled checks; this module owns the
common core: sheet points through the view's sketch transform, black lines
of one font created together straight to the database (an inferred endpoint
would snap onto a hole wall or a face), their fonts and endpoints read back,
and a line's length dimensioned with no Modify dialog.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import view_name

from _com import _early_bound
from _drawing_sections import _assert_section_line_placed

CHAIN_LINE_STYLE = 3  # swLineStyles_e.swLineCHAIN
CHAIN_LINE_WEIGHT = 2  # swLineWeights_e.swLW_THICK: Y14.5's heavy chain line
CENTER_LINE_STYLE = 4  # swLineStyles_e.swLineCENTER
CENTER_LINE_WEIGHT = 0  # swLineWeights_e.swLW_THIN
_SW_INPUT_DIM_VAL_ON_CREATE = 10  # swUserPreferenceToggle_e.swInputDimValOnCreate


@dataclass(frozen=True)
class SketchedLine:
    """A created line: its segment and line interfaces and its authored
    ends in the view sketch's space (m)."""

    segment: Any
    line: Any
    ends: tuple[tuple[float, ...], tuple[float, ...]]


def sheet_to_sketch(
    adapter: Any, view: Any, sheet_points: list[tuple[float, float]]
) -> list[tuple[float, ...]]:
    """Sheet points (m) in ``view``'s sketch space, through one transform read."""
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    return points


def sketch_lines(
    adapter: Any,
    view: Any,
    sheet_ends: Mapping[str, tuple[tuple[float, float], tuple[float, float]]],
    *,
    style: int,
    width: int,
    label: str,
) -> dict[str, SketchedLine]:
    """One black line of ``style``/``width`` per entry, between its two sheet
    points, in ``view``'s sketch, all created direct to the database. No
    rebuild: the caller rebuilds when it is ready and then calls
    ``require_placed``."""
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for {label}")
    model.ClearSelection2(True)
    keys = list(sheet_ends)
    mapped = sheet_to_sketch(
        adapter, view, [point for key in keys for point in sheet_ends[key]]
    )
    manager = _early_bound(model.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    created: dict[str, tuple[Any, tuple[tuple[float, ...], tuple[float, ...]]]] = {}
    try:
        for index, key in enumerate(keys):
            ends = (mapped[2 * index], mapped[2 * index + 1])
            line = manager.CreateLine(*ends[0], *ends[1])
            if line is None:
                raise RuntimeError(f"failed to sketch the {label} line {key!r}")
            created[key] = (line, ends)
    finally:
        manager.AddToDB = previous
    sketched = {}
    for key, (line, ends) in created.items():
        segment = _early_bound(line, "ISketchSegment")
        # COLORREF black: a view sketch line otherwise prints in the sketch's
        # grey or under-defined blue, which reads as a hidden line.
        segment.Color = 0
        segment.Style = style
        segment.Width = width
        sketched[key] = SketchedLine(segment, _early_bound(line, "ISketchLine"), ends)
    model.ClearSelection2(True)
    return sketched


def require_placed(
    adapter: Any,
    sketched: Mapping[str, SketchedLine],
    *,
    style: int,
    width: int,
    label: str,
    stage: str,
    ends: Mapping[str, tuple[tuple[float, ...], tuple[float, ...]]] | None = None,
) -> None:
    """Each line still prints black in its font, and its ends sit exactly at
    ``ends`` (sketch space; default: where they were authored)."""
    for key, line in sketched.items():
        font = (int(line.segment.Color), int(line.segment.Style), int(line.segment.Width))
        if font != (0, style, width):
            raise RuntimeError(
                f"{label} {key!r} ({stage}): font reads {font!r}, not {(0, style, width)!r}"
            )
        want = line.ends if ends is None else ends[key]
        _assert_section_line_placed(
            adapter, line.line, list(want), label=f"{label} {key!r} ({stage})"
        )


@contextmanager
def dimension_input_suppressed(adapter: Any) -> Iterator[None]:
    """No Modify dialog while a dimension lands on a fresh sketch line:
    SolidWorks resets swInputDimValOnCreate on entering a sketch, so the
    adapter's connect-time suppression does not cover it (codjiflo on
    #2015). The seat's own setting comes back afterwards."""
    app = adapter.swApp
    previous = bool(app.GetUserPreferenceToggle(_SW_INPUT_DIM_VAL_ON_CREATE))
    app.SetUserPreferenceToggle(_SW_INPUT_DIM_VAL_ON_CREATE, False)
    try:
        if bool(app.GetUserPreferenceToggle(_SW_INPUT_DIM_VAL_ON_CREATE)):
            raise RuntimeError("swInputDimValOnCreate stayed on")
        yield
    finally:
        app.SetUserPreferenceToggle(_SW_INPUT_DIM_VAL_ON_CREATE, previous)


def dimension_line(
    adapter: Any,
    view: Any,
    segment: Any,
    *,
    vertical: bool,
    at: tuple[float, float],
    label: str,
) -> Any:
    """The line's length as a vertical or horizontal dimension with its text
    at ``at`` (sheet m); returns the ``IDisplayDimension``. Call it inside
    ``dimension_input_suppressed``."""
    model = adapter.currentModel
    drawing = _early_bound(model, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view to dimension {label}")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
    selection.View = view
    if not segment.Select4(False, selection):
        raise RuntimeError(f"failed to select the {label} line")
    add = model.AddVerticalDimension2 if vertical else model.AddHorizontalDimension2
    display = add(at[0], at[1], 0.0)
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to dimension the {label} line")
    return _early_bound(display, "IDisplayDimension")
