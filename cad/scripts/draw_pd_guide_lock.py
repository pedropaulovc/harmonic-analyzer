r"""Create the curated machinist drawing for the platen guide lock plate.

The SLDPRT remains authoritative.  This recipe supplies only the guide-lock
views, dimension layout and hole callout;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

The sheet runs at 4:1 in decimal inch (#290; the plate is .89 x .45, cut from
1/16 sheet whose thickness prints as a fraction REF, its four corners
rounded); the isometric carries an explicit 2:1 override so it stays
clear of the title block.  A flat plate needs only the face view (front), one
thickness view (right) and the iso.
No frames and no datums (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the screw holes locate by +/-
coordinates from the plate's corner, authored on the part.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_guide_lock.py pd-guide-lock
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
import _config
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _part_properties import part_drawing_unit
from _session import run_build
import _telemetry
from pd_guide_lock_spec import (
    DRAWING_PRECISION_BY_NAME,
    HOLE_LOCATION_PLACES,
    HOLE_SPEC,
    HOLE_XY,
    LOCK_HEIGHT,
    LOCK_STOCK_CALLOUT,
    LOCK_THICK,
    LOCK_WIDTH,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_guide_lock"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (4.0, 1.0)

# Sheet layout (meters).  The front view's model bbox is 22.6 x 11.4 (the plate
# face); at 4:1 the view is 90 x 45.7 mm, x 0.105..0.195, y 0.152..0.198.
# Third angle: the right view (the 1/16 sheet edge-on) sits to its right,
# past the hole callout; the isometric rides top-right.  The whole group sits
# centred between the border and the title block (it sat 25 mm low and 15 mm
# left under an empty upper field, machinist review of 40e51b9a7).
FRONT_CENTER = (0.150, 0.175)
RIGHT_CENTER = (0.280, 0.175)
ISO_CENTER = (0.355, 0.225)
ISO_NOTE_XY = (0.330, 0.185)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - LOCK_WIDTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - LOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


# Handy picks derived from the layout above.
LEFT_EDGE_X = _sheet_x(0.0)
RIGHT_EDGE_X = _sheet_x(LOCK_WIDTH)
BOTTOM_EDGE_Y = _sheet_y(0.0)
HOLE_R_SHEET = blind_cut_dia_mm(HOLE_SPEC) * SHEET_SCALE[0] / 2000.0
HOLE_Y_SHEET = _sheet_y(HOLE_XY[0][1])
HOLE_2_X_SHEET = _sheet_x(HOLE_XY[1][0])

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Width stacks below the front view under the two hole X
# coordinates, the 4.000's text outboard of the plate's left edge (between
# its extension lines the hole's own extension cut through it); the shared
# hole Y stands left of the plate, its text under the plate's bottom-left
# corner, and Height outboard of it (smaller dimension nearer the part), its
# value mid-way between the top and bottom extension lines and left of the
# hole Y dimension line, where the hole Y extension stops (inboard of it, the
# value sat on the top extension line, machinist review of 1c9f9b2a6); the 4X
# corner radius stands off the top-right corner, its leader landing on that
# arc clear of the Height's extension lines on the left and the hole callout
# below; the sheet thickness rides above the right view, its value outboard
# right of the view's extension lines (centred between them, the lines struck
# its digits, machinist review ENFORCE r1-r3) and its one-line as-supplied
# stock callout in the clear field above the value.
# The three hole coordinates carry three-row blocks (value plus the mate
# callout below it). SolidWorks centres a block on its text position and
# hangs the dimension's shelf from its last row, about 8.3 mm below that
# position, its first row's top about 7.3 mm above (layout audit of farm run
# 20261024T123122680Z). Kept at the one-row positions, the hole Y's line ran
# down through the 4.000 and the 4.000's line fell onto the 18.000's
# (machinist review r1-r3 of bef0d46b6). So the hole Y's line stands at
# 68 mm, its block left of it and below the Height's bottom arrow; the 4.000's
# block stands right of that line, its shelf (the 4.000's dimension line)
# 6 mm above the 18.000's and its top clear of the Height's extension line.
# The 18.000's text rises by the block's extra rows so its shelf keeps the
# one-row line's place; the block stands under the plate between hole 1's and
# hole 2's extension lines, right of where the 4.000's line ends.
# The blocks under the plate hang from its bottom edge, so they follow the
# plate's height (.45 since the .29 rails, owner ruling 2026-11-01).
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], BOTTOM_EDGE_Y - 0.0302),
    "Height": (0.057, FRONT_CENTER[1]),
    "Hole1X": (0.086, BOTTOM_EDGE_Y - 0.0104),
    "Hole2X": (0.142, BOTTOM_EDGE_Y - 0.0164),
    "Hole1Y": (0.068, BOTTOM_EDGE_Y - 0.0142),
    "CornerR": (0.215, 0.211),
}
RIGHT_KEEP = {"Depth": (RIGHT_CENTER[0] + 0.023, 0.209)}
# Both holes stand on the one Y coordinate the part prints (Hole1Y); the one
# printed fillet stands for all four equal corners (CornerR). A custom prefix
# replaces SolidWorks' own radius "R", so it carries it ("4X 1.8" printed
# without, farm run 20261012T061737079Z).
DIMENSION_PREFIXES = {"Hole1Y": "2X ", "CornerR": "4X R"}
DIMENSION_CALLOUTS = {"Depth": LOCK_STOCK_CALLOUT}
# The 1/16 sheet's thickness is stock: a fraction REF, the supplier's band
# governs it (#290).
THICKNESS_DIMENSION = "Depth"
THICKNESS_PREFIX = "1/16 ("
THICKNESS_SUFFIX = ")"
# The 1/8 drill's Ø prints .XXX, as every native Hole Wizard length.
HOLE_CALLOUT_PRECISION = {"hw-diam": HOLE_LOCATION_PLACES}
# The bent leader elbows at the text's LEFT end and enters hole 2 from its
# upper-right quadrant, crossing only the plate's right edge; the text stands
# between that edge and the right view.
HOLE_CALLOUT_XY = (0.230, 0.185)
HOLE_CALLOUT_PROCESS = "DRILL"
# The hole coordinates' ±.001 bands exist for the mate (rule 4): the
# pattern must land on the platen guide's #4-40 taps with the lock-screw
# shanks clear in their holes (pd_vn_guide_lock_screw_spec.LOCK_SET_OFFSET),
# so the callout names both.
# Rows stay at most 23 characters so the block keeps between the plate and
# the right view.
GUIDE_NUMBER = _config.parts("pd-platen-guide")["number"]
SCREW_NUMBER = _config.parts("pd-vn-guide-lock-screw")["number"]
HOLE_CALLOUT_BELOW = "\n".join(
    (
        f"MATCHES {GUIDE_NUMBER} TAPS,",
        "CLEARANCE FIT ON",
        f"{SCREW_NUMBER} SCREWS",
    )
)
# The coordinates baseline both holes from the plate's corner, so the 4.000,
# the 18.000 and the shared 2X Y are each the pattern: the holes' X's and
# their common line are what land on the guide's tap row (the R9-49 set
# window spends each coordinate's band, pd_vn_guide_lock_screw_spec
# .POSITION_RADIAL; ±0.065 is refused). Each carries the mate at its own
# value (machinist review ENFORCE at 2056e3344: the hole callout alone left
# the edge locations without one; at eecbf880d the 18.000 still lacked it).
# Two short rows keep each block inside its value's width, the hole Y's left
# of the 4.000 and the 4.000's left of the plate's left-edge extension line.
DIMENSION_CALLOUTS_BELOW = {
    "Hole1X": f"MATCHES\n{GUIDE_NUMBER}",
    "Hole2X": f"MATCHES\n{GUIDE_NUMBER}",
    "Hole1Y": f"MATCHES\n{GUIDE_NUMBER}",
}


def _set_dimension_prefixes(
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


def _thickness_reference(adapter: Any, annotations: list[Any]) -> None:
    """Print the 1/16 sheet's thickness as its stock fraction with the
    native value in parentheses, REF (the transgear arm's stock idiom)."""
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) != THICKNESS_DIMENSION:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        if abs(float(dimension.SystemValue) - LOCK_THICK / 1000.0) > 1e-9:
            raise RuntimeError(
                f"guide-lock thickness {float(dimension.SystemValue)!r} m "
                f"is not the sheet's {LOCK_THICK} mm"
            )
        display.SetText(1, THICKNESS_PREFIX)  # swDimensionTextPrefix
        display.SetText(2, THICKNESS_SUFFIX)  # swDimensionTextSuffix
        readback = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
        if readback != (THICKNESS_PREFIX, THICKNESS_SUFFIX):
            raise RuntimeError(
                f"guide-lock thickness text did not persist: {readback!r}"
            )
        return
    raise RuntimeError("guide-lock sheet thickness was not imported")


@_telemetry.traced("drawing.hole_callout_below")
def _set_hole_callout_below(display: Any, text: str) -> None:
    """Write ``text`` under the native hole callout and read it back.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_ch_channel_lever._name_hole_mate)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    # SolidWorks may store CRLF row breaks; compare both sides without CR.
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            "guide-lock hole callout mate or native definitions did not persist: "
            f"{[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open guide-lock source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Guide Lock Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "guide lock; manufacturing drawing; 1/8 drill screw holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    # The through holes are fully defined by their callout; the strip seen
    # edge-on needs no hidden bores.
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    # Seen edge-on, the corner fillets' tangent edges drew as two solid lines
    # across the sheet's thickness that read as steps (machinist review
    # ENFORCE r1); the plain plate needs none of them.
    right.SetDisplayTangentEdges2(0)  # swTangentEdgesHidden
    if int(right.GetDisplayTangentEdges2()) != 0:
        raise RuntimeError("failed to hide the right view's tangent edges")
    right.UpdateViewDisplayGeometry()

    # The places and the hole coordinates' explicit bands are authored on the
    # part (the paper-drive lock-station sweep and the screw set window read
    # the same spec); the sheet only proves the import kept the places. The
    # sheet thickness prints as its stock fraction, REF. The hole size ships
    # as a native wizard callout below.
    annotations = [
        *curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front"),
        *curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right"),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)
    _thickness_reference(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="above")
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_BELOW, location="below"
    )

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    hole_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            HOLE_2_X_SHEET + 0.6 * HOLE_R_SHEET,
            HOLE_Y_SHEET + 0.8 * HOLE_R_SHEET,
        ),
        callout_xy=HOLE_CALLOUT_XY,
        label="guide-lock screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        hole_callout, HOLE_CALLOUT_PRECISION, label="guide-lock screw holes"
    )
    _set_hole_callout_below(hole_callout, HOLE_CALLOUT_BELOW)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Guide Lock Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
