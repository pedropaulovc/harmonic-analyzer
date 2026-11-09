r"""Create the curated machinist drawing for MHA-SM-01, the gooseneck tube.

The SLDPRT remains authoritative.  This recipe supplies the views, places the
part's marked dimensions and links the notes; sheet/template and export
behaviour lives in ``_drawing_common``.

The gooseneck is a 1/2 in 4130-N tube bent R3.0, its arm end sawn and faced
to length after the bend (owner rulings 2026-10-27, #1951; 2026-11-08
(Pedro), #2315).  The end plug bonded into that end is its own part and sheet
(MHA-SM-05), and the leg carries no sleeve.  The sheet carries, at 1:3, the
ELEVATION (``*Front``): the leg length (foot to the bend's entry tangent) and
the reference arm straight (the bend's exit tangent to the faced arm end) on
the tube's axes, from the part's hidden ``StationReference``; the bend's
centreline radius; the tube's reference stock Ø with its wall; the overall
reach (faced arm end to the leg's outer side) and the reference overall
height, from the part's hidden ``OverallReference``.  The isometric is at
1:4.  The sheet prints decimal inch (#290, the registry row's drawing_unit).

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck.py sm-gooseneck
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sm_gooseneck_geom import (
    ARM_Y,
    LEG_BOTTOM,
    LEG_TOP,
    TUBE_DIA,
    TUBE_END_X,
)
from sm_gooseneck_spec import (
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TUBE_OD_REF_Y,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:3 whole sheet (~500 mm tall gooseneck)
VIEW_SCALE = (1, 3)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm

# A placed view centres its model bounding box: x from the faced arm end to
# the leg's far side, y from the leg's foot to the arm's top.
_TUBE_R = TUBE_DIA / 2.0
_BOX_MID_X = (TUBE_END_X + _TUBE_R) / 2.0
_BOX_MID_Y = (LEG_BOTTOM + ARM_Y + _TUBE_R) / 2.0

# Sheet layout (metres): the elevation with its dimensions on the leg's right
# left of centre, its foot clear of the title block's left edge (x 0.216) and
# above the notes, and the isometric right of centre over the title block, so
# the two views spread across the usable region (rule 15).
FRONT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.310, 0.165)


def _front_x(model_x: float) -> float:
    return FRONT_CENTER[0] + (model_x - _BOX_MID_X) * _S


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _BOX_MID_Y) * _S


LEG_AXIS_X = _front_x(0.0)
ARM_AXIS_Y = _front_y(ARM_Y)
ARM_END_X = _front_x(TUBE_END_X)
FOOT_Y = _front_y(LEG_BOTTOM)
BEND_TANGENT_Y = _front_y(LEG_TOP)

# The elevation's dimensions: both vertical runs on the leg's right, the leg
# length's text level with the tube's reference Ø, which crosses the leg on
# its left, level with the hidden reference line; the arm straight over the
# arm; the bend radius outside the bend, its block centred 25 mm right of the
# leg's axis so the 37.5-mm "TUBE CENTERLINE" row clears the bend's inner
# edge by 3.6 mm (farm run 20261107T102825912Z: "TO TUBE CENTERLINE" centred
# 19 mm right ran under the arc) and ends 8 mm short of the overall height's
# line, its bottom row over the leg length's upper extension line.
# The reference overall height (foot face to the arm's top) stands outermost
# on the leg's right, beyond the leg length (its text ended at x 0.310 in farm
# run 20261101T004958072Z) and short of the title block's left edge, so its
# foot extension line stays off the title block; its text at the view's
# mid-height, 21 mm below the leg length's.  The overall reach (faced arm end
# to the leg's outer side) runs over the arm straight.  Machinist review r5 of
# that run.  The arm straight's text stands outside its short span, left of
# the faced arm end: centred over the span it straddled the end's extension
# line, which the reach shares (text-on-line, farm run 20261101T022045634Z).
FRONT_KEEP = {
    "LegLength": (LEG_AXIS_X + 0.034, _front_y(TUBE_OD_REF_Y)),
    "TubeOdRef": (LEG_AXIS_X - 0.030, _front_y(TUBE_OD_REF_Y)),
    "ArmStraight": (ARM_END_X - 0.010, ARM_AXIS_Y + 0.014),
    "BendRadius": (LEG_AXIS_X + 0.025, ARM_AXIS_Y - 0.0176),
    "OverallHeight": (
        LEG_AXIS_X + 0.052,
        (FOOT_Y + _front_y(ARM_Y + _TUBE_R)) / 2.0,
    ),
    "OverallReach": (
        (ARM_END_X + _front_x(_TUBE_R)) / 2.0,
        ARM_AXIS_Y + 0.021,
    ),
}
if set(FRONT_KEEP) != {
    name for names in DRAWING_DIMENSIONS.values() for name in names
}:
    raise AssertionError("the gooseneck sheet does not place every marked dimension")

# The note sits in the bottom left, under the elevation's foot (y ~0.067) and
# left of the title block (x 0.216); the isometric's note sits under it.  The
# elevation is a projected principal view at the sheet's scale, so it carries
# no label (drawing-guidelines.md rule 9).
NOTES_XY = (0.016, 0.062)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, 0.085)


def _assert_part_callouts(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below its dimension's value; the
    import must carry each one unchanged (the drawing never writes them,
    #1942)."""
    # swDimensionTextCalloutBelow = 4.
    expected = {(4, name): text for name, text in DIMENSION_CALLOUTS_BY_NAME.items()}
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"gooseneck dimension callouts did not import: {found!r} != {expected!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
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
            0: "Gooseneck Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck; bent 4130 tube; spring post",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_callouts(adapter, annotations)

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Post Manufacturing Drawing",
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
