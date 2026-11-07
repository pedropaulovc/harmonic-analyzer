r"""Create the manufacturing drawing for the oblique-trammel hub washer (MHA-CH-06-TL-52).

The face view carries the 13/64 drilled bore with its DRILL THRU callout; the
side view reads like the lathe (drawing-guidelines.md rule 11): both turned
diameters and both lengths from the seat face, with the flange's O.D. naming
the cutter its .XXX row clears (rule 3), the flange thickness carrying the
owner's edge break and the floored wall it leaves at the rims (machinist
exception RV-01), the spigot's band naming the strap hole it locates in
(rule 4), and the spigot length carrying its local edge limits.  Each
callout keeps to two lines of words (rule 7).  Places and bands are authored
on the part (``ch_rocker_arm_tl_oblique_hub_washer_spec``).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_hub_washer.py ch-rocker-arm-tl-oblique-hub-washer
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

import _telemetry
from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from ch_rocker_arm_spec import inch_text
from ch_rocker_arm_tl_oblique_hub_washer_spec import (
    BORE_DRILL,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_EDGE_BREAK_MAX,
    FLANGE_WALL_CALLOUT,
    JIG_NUMBER,
    OD,
    SPIGOT_LENGTH,
    SPIGOT_ROOT_RADIUS_MAX,
    STEM,
    STRAP_HOLE_LIMITS,
    STRAP_NUMBER,
    THICK,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_washer"]
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

# Drawing-owned callouts, so the wording stays off the part's cache key.
# Rule 7: at most two lines of words and at most one short reason; every
# mate by its drawing number (rule 4).  Rule 12: the bore says what to do;
# the title block's DRILLED HOLES row is its band.  The O.D.'s .XXX row names
# what it clears (rule 3), the 3/8 cutter on the jig; the holding proof and
# the jig's tooling-clearance check carry the 1.5 mm floor.  The flange
# thickness carries the owner's .005 break and the floored wall it leaves at
# the rims (machinist exception RV-01, owner ruling 2026-11-07, #2249; rule
# 20's plain fact).  The spigot's band names its mate, the strap hole's
# limits REF (the strap's sheet controls them).  The spigot length carries
# its two local edge limits, which override the title block's break and
# inside corner.
DIMENSION_CALLOUTS: dict[str, str] = {
    "WasherBore": f"{BORE_DRILL} DRILL THRU",
    "WasherOd": f"CLEARS 3/8 CUTTER\nON {JIG_NUMBER}",
    "WasherThickness": (
        f"BREAK EDGES {inch_text(FLANGE_EDGE_BREAK_MAX, 3)} MAX\n{FLANGE_WALL_CALLOUT}"
    ),
    "SpigotDia": (
        f"LOCATES IN STRAP {STRAP_NUMBER}\n"
        f"HUB HOLE ({inch_text(STRAP_HOLE_LIMITS[0], 4)}-"
        f"{inch_text(STRAP_HOLE_LIMITS[1], 4)} REF)"
    ),
    "SpigotLength": (
        f"END EDGE SHARP, NO BURR\nROOT R{inch_text(SPIGOT_ROOT_RADIUS_MAX, 3)} MAX"
    ),
}

# A Ø.433 x .074 top hat at 4:1 (44 mm across, 7.5 mm long): the face view,
# the side view and the isometric on one row midway between the top border
# and the title block (the mg-wheel-axle-spacer sheet's layout), no general
# note.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FRONT_CENTER = (0.090, 0.160)
RIGHT_CENTER = (0.215, 0.160)
ISO_CENTER = (0.345, 0.160)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# The side view (*Right) draws the Right-plane profile, sheet X = model -Z,
# centred on the part's z span -SPIGOT_LENGTH..THICK.
_U_MID = (SPIGOT_LENGTH - THICK) / 2.0


def _side_x(u_mm: float) -> float:
    """Sheet X of a profile station u = -z (mm) on the side view."""
    return RIGHT_CENTER[0] + (u_mm - _U_MID) * _S


HEAD_FACE_X = _side_x(-THICK)
SEAT_FACE_X = _side_x(0.0)
SPIGOT_END_X = _side_x(SPIGOT_LENGTH)
_OD_TOP_Y = RIGHT_CENTER[1] + OD / 2.0 * _S

# Face view: the bore alone, its callout up and left of the side view's
# flange-thickness rows.
FRONT_KEEP = {
    "WasherBore": (0.105, 0.225),
}
# Side view.  The profile's sketch corners lie on its +Y side, so both
# lengths chain on one row above the part, from the seat face: the
# thickness's text and its two callout rows well left of the head-side face,
# clear of its extension line and above the flange Ø's upper extension line;
# the spigot length's right of the spigot's end (each span is narrower than
# its text at 4:1), the length row high enough that every length row stays
# above the Ø extension lines.  The flange Ø stands left of the head-side
# face, where its extension lines leave the rims into open air and its rows
# sit between the face view and the part; the spigot Ø right
# of the spigot's end.  SolidWorks centres each Ø's whole text block (value
# and callout rows) on its requested point, so each block centres on the
# axis, midway between its arrows: set higher (run 9a1aa3a10e36) the Ø.433
# value sat on its upper extension line and the spigot's upper arrowhead
# struck its value.
_LENGTH_ROW_Y = _OD_TOP_Y + 0.030
RIGHT_KEEP = {
    "WasherOd": (HEAD_FACE_X - 0.035, RIGHT_CENTER[1]),
    "SpigotDia": (SPIGOT_END_X + 0.040, RIGHT_CENTER[1]),
    "WasherThickness": ((HEAD_FACE_X + SEAT_FACE_X) / 2.0, _LENGTH_ROW_Y),
    "SpigotLength": ((SEAT_FACE_X + SPIGOT_END_X) / 2.0, _LENGTH_ROW_Y),
}
LENGTH_TEXT_XY = {
    "WasherThickness": (HEAD_FACE_X - 0.040, _LENGTH_ROW_Y),
    "SpigotLength": (SPIGOT_END_X + 0.036, _LENGTH_ROW_Y),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub washer source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Oblique Trammel Hub Washer Manufacturing Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "hub clamp top-hat washer; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *right_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the spigot's band are authored on the part; the sheet only proves
    # the import kept the places.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    offset_dimension_text(adapter, right_annotations, LENGTH_TEXT_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Oblique Trammel Hub Washer Manufacturing Drawing",
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
