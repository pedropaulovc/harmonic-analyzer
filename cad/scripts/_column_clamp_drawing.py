"""Sheet steps the two column-clamp arc drawings share.

``draw_sh_column_clamp_front`` and ``draw_sh_column_clamp_back`` print the
same split-face view of the shared semi-arc (``_clamp_arc``): both mark the
ear pair's imported dimensions ``2X``, both draw the bore axis the ear
stations measure from, and both print the bore-axis-to-side-face AnchorZ as a
plain linear reference.  Drawing-only: no part recipe imports this module.
"""

from __future__ import annotations

from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

import _telemetry
from _com import _early_bound
from _drawing_dimensions import set_reference_dimension


def set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


def set_linear_reference_dimensions(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Parenthesize named LINEAR dimensions as references, "(.945)".

    ``_drawing_dimensions.set_reference_dimensions`` writes "(<MOD-DIAM>" on
    every name, which printed the AnchorZ distance as "(Ø.945)" (farm
    20261101T002109868Z); the singular helper writes a plain "(" and reads
    both parts back."""
    remaining = set(names)
    for raw in annotations:
        name = dimension_name(adapter, _early_bound(raw, "IAnnotation"))
        if name not in remaining:
            continue
        set_reference_dimension(adapter, raw, label=f"{name} reference")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"linear references not applied: {sorted(remaining)}")


@_telemetry.traced("drawing.column_clamp.bore_axis_centerline")
def add_bore_axis_centerline(
    adapter: Any, face: Any, edges_xy: list[tuple[float, float]]
) -> None:
    """Draw the bore axis midway between the relief's two split-face edges.

    Round 2 (farm 20261015T010255283Z): ``InsertCenterLine2`` on the
    half-cylinder relief face returned None on both arcs; an edge pair is
    draw_dt_crank_arm's working recipe, and the edges sit symmetric about
    the axis.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, face)):
        raise RuntimeError("failed to activate the split-face view for the bore axis")
    _early_bound(face, "IView").UpdateViewDisplayGeometry()
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate(edges_xy):
        if not draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError("failed to select a relief edge for the bore axis")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError("failed to draw the bore axis between the relief edges")
    count = int(_early_bound(face, "IView").GetCenterLineCount())
    if count != 1:
        raise RuntimeError(f"split-face view carries {count} centerlines, expected 1")
