"""Sheet steps the two column-clamp arc drawings share.

``draw_sh_column_clamp_front`` and ``draw_sh_column_clamp_back`` print the
same split-face view of the shared semi-arc (``_clamp_arc``): both mark the
ear pair's imported dimensions ``2X``, both draw the bore axis the ear
stations measure from, and both name the other arc's ear holes once, under
their native hole callout.  Drawing-only: no part recipe imports this module.
"""

from __future__ import annotations

from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, view_name

import _telemetry
from _com import _early_bound


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


# swDimensionText_e: the writable callout-below part and the definitions
# (prefix, suffix, callout above, callout below) it pairs with.
_CALLOUT_BELOW = 4
_DEFINITIONS = (5, 6, 7, 8)
_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}


def _definitions(display: Any) -> dict[int, str]:
    return {part: str(display.GetText(part) or "") for part in _DEFINITIONS}


def set_hole_callout_below(display: Any, text: str, *, label: str) -> None:
    """Write ``text`` under a native hole callout and read it back.

    Only the callout-below definition changes; the prefix, size and depth
    definitions stay untouched, so the Hole Wizard variables stay associative
    (draw_pd_guide_lock._set_hole_callout_below).
    """
    display = _early_bound(display, "IDisplayDimension")
    before = _definitions(display)
    # SolidWorks may store CRLF row breaks; compare both sides without CR.
    below = before[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(_CALLOUT_BELOW, updated)
    after = _definitions(display)
    if after[8].replace("\r", "") != updated or any(
        after[part] != before[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            f"{label}: hole callout mate or native definitions did not persist: "
            f"{after!r}"
        )


def drill_thru_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Swap a plain through hole's one native extent for ``DRILL THRU``.

    The installed calloutformat.txt formats a plain through hole as
    ``<MOD-DIAM> <hw-diam> <hw-thru>``, so the size reads first, then the
    process and the depth (drawing-guidelines.md rules 12 and 26;
    draw_fr_top_frame._hanger_hole_callout_definitions).  Any other hole
    type's tokens mean the wrong feature.
    """
    native = "\n".join(definitions.values())
    if (
        set(definitions) != set(_DEFINITIONS)
        or native.count("<hw-diam>") != 1
        or native.count("<hw-thru>") != 1
        or any(
            token in native
            for token in (
                "<hw-thruholedia>",
                "<hw-cbdia>",
                "<hw-cbdepth>",
                "<HOLE-SPOT>",
                "<HOLE-SINK>",
            )
        )
    ):
        raise RuntimeError(f"unexpected native through-hole callout: {definitions!r}")
    return {
        part: text.replace("<hw-thru>", "DRILL THRU")
        for part, text in definitions.items()
    }


def set_drill_thru(display: Any, *, label: str) -> None:
    """Print a plain through hole as ``nX Ø.nnn DRILL THRU``, natively."""
    display = _early_bound(display, "IDisplayDimension")
    before = _definitions(display)
    updated = drill_thru_definitions(before)
    for part, text in updated.items():
        if text != before[part]:
            display.SetText(_WRITABLE[part], text)
    after = _definitions(display)
    resolved = "\n".join(str(display.GetText(part) or "") for part in (1, 2, 3, 4))
    if after != updated or resolved.count("DRILL THRU") != 1:
        raise RuntimeError(
            f"{label}: DRILL THRU did not persist: {after!r}, resolved {resolved!r}"
        )


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
