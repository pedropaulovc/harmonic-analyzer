r"""Create the curated machinist drawing for the bought, cross-drilled crank taper pin."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import drilled_limits, limits
from _drawing_centerline import add_view_centerline
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_leader_notes import add_leader_note
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _drawing_view_display import set_hidden_lines_removed
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_pin_notes import (
    RING_HOLE_CALLOUTS,
    SHEET_NOTES,
    TAPER_CALLOUT,
)
from dt_crank_pin_spec import (
    BIG_END_DIA,
    BIG_END_DIA_BAND,
    CROSS_HOLE_WEB_MIN,
    DESIGNATION,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PIN_LENGTH,
    RING_HOLE_DIA,
    RING_HOLE_X,
    SKU,
    SMALL_END_DIA,
    STANDARD,
    UNIT,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pin"]
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

# Every orthographic view prints at the sheet scale: the end view is the
# projected right-side view, so it needs no label (drawing-guidelines.md
# rule 9); at 4:1 it read as an unlabelled enlarged view.
SHEET_SCALE = (2.0, 1.0)
FRONT_CENTER = (0.110, 0.195)
RIGHT_CENTER = (
    FRONT_CENTER[0] + PIN_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.080,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.340, 0.205)

# Side-view landmarks (sheet meters): the pin is centred on its bounding box,
# big end (model x=0) to the left, small end (x=PIN_LENGTH) to the right.
_HALF_LENGTH = PIN_LENGTH * SHEET_SCALE[0] / 2000.0
BIG_END_EDGE = (FRONT_CENTER[0] - _HALF_LENGTH, FRONT_CENTER[1])
# The upper taper outline at model x = TAPER_PICK_X, where the pin's radius
# is interpolated between its end diameters: the taper note's leader tip.
TAPER_PICK_X = PIN_LENGTH * 0.45
_TAPER_PICK_R = (BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * TAPER_PICK_X / PIN_LENGTH) / 2.0
TAPER_SILHOUETTE_PICK = (
    BIG_END_EDGE[0] + TAPER_PICK_X * SHEET_SCALE[0] / 1000.0,
    FRONT_CENTER[1] + _TAPER_PICK_R * SHEET_SCALE[0] / 1000.0,
)
# The fit callout's top-left corner: above the pin and just right of the
# leader tip, so the leader leaves the start of the first line down-left,
# outside the text block (round 2 had it run back through all four lines).
TAPER_NOTE_XY = (TAPER_SILHOUETTE_PICK[0] + 0.006, FRONT_CENTER[1] + 0.063)
# The numbered notes: under the side view, left of the title block (x 0.218).
NOTES_XY = (0.020, 0.120)

# The ring cross-hole, seen end-on as a circle on the axis.
RING_HOLE_CENTER = (
    BIG_END_EDGE[0] + RING_HOLE_X * SHEET_SCALE[0] / 1000.0,
    FRONT_CENTER[1],
)
# A point on the conical face, clear of the cross-hole, for the axis.
AXIS_FACE_PICK = (FRONT_CENTER[0] + 0.020, FRONT_CENTER[1] + 0.002)

# The .15 station's text cannot fit between its extension lines, 7.62 mm
# apart at 2:1 (its test still budgets the 9.05 mm the template's "3.70"
# measured). Put the text outboard right, clear of the outside arrow's
# 6.35-mm tail and left of the taper-note leader.
# Below the hole: its Ø callout, its widest row (the keeper-ring row) wholly
# right of the hole so the leader leaves the shoulder's left end and climbs to
# the hole without striking a letter, and its top row clear of the pin's
# lower outline (machinist review of b8fab08f4e: the leader crossed the
# row's F).  The bought pin's length and ends are reference (note 1), so
# nothing else is dimensioned.
FRONT_KEEP = {
    "RingHoleX": (
        RING_HOLE_CENTER[0] + 0.014,
        FRONT_CENTER[1] + 0.016,
    ),
    "RingHoleDia": (RING_HOLE_CENTER[0] + 0.039, FRONT_CENTER[1] - 0.019),
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (build_dt_crank_pin: the pin is a
# Front-plane revolve about model X, its flat big-end rim plane at X = 0 and
# the small end at X = PIN_LENGTH; the ring hole is a Front-plane circle at
# (RING_HOLE_X, 0) cut through both ways, so it runs along model Z).  The pin
# is bought, its length and end diameters reference (note 1): only the cross
# hole is made.  The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_dt_crank_pin"
_SPEC = "dt_crank_pin_spec"
_BUILD = "build_dt_crank_pin"
_FRAME = (_BUILD, "__frame__")
_TAPER_HALF_ANGLE_DEG = math.degrees(
    math.atan((BIG_END_DIA - SMALL_END_DIA) / 2.0 / PIN_LENGTH)
)
# The pin's surface where the hole enters it, on the +Z side at nominal.
_RING_HOLE_ENTRY_Z = (
    BIG_END_DIA - (BIG_END_DIA - SMALL_END_DIA) * RING_HOLE_X / PIN_LENGTH
) / 2.0


def _plane(value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": "x", "value": value}


part_metadata(
    model_sources=(_FRAME, "PIN_LENGTH", "BIG_END_DIA", "SMALL_END_DIA"),
    precision_sources=("DRAWING_PRECISION", (_SELF, "DRAWING_PRECISION_BY_NAME")),
)
# The as-bought big end's rim plane: the ring hole's station runs from it.
requirement(
    "big_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane(0.0), (_FRAME, (_SELF, "BIG_END_EDGE")))},
)
requirement(
    "small_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), PIN_LENGTH),),
    requirements=("plane",),
    fields={"plane": (_plane(PIN_LENGTH), (_FRAME, "PIN_LENGTH"))},
)
# The bought No. 3 taper pin, left as supplied: its ends are reference (note
# 1), its big end held by ASME B18.8.2's commercial band, not a printed one.
requirement(
    "taper",
    kind="outside_cone",
    faces=(ConeFace(_TAPER_HALF_ANGLE_DEG),),
    requirements=("stock",),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": ([1.0, 0.0, 0.0], (_FRAME,)),
        "stock": (f"McMASTER-CARR {SKU} {DESIGNATION}", ("SKU", "DESIGNATION")),
        "standard": (STANDARD, ("STANDARD",)),
        "dia_ref": (BIG_END_DIA, ("BIG_END_DIA",)),
        "dia": (
            [BIG_END_DIA + BIG_END_DIA_BAND[1], BIG_END_DIA + BIG_END_DIA_BAND[0]],
            ("BIG_END_DIA", "BIG_END_DIA_BAND"),
        ),
        "small_dia_ref": (SMALL_END_DIA, ("SMALL_END_DIA",)),
        "length_ref": (PIN_LENGTH, ("PIN_LENGTH",)),
        "taper_per_diameter": (1.0 / 48.0, ((_SPEC, "SMALL_END_DIA"),)),
    },
)
# The keeper-ring cross hole: #45 drill through (FRONT_KEEP "RingHoleDia",
# DRILLED HOLES row, with its web limit under it), .15 from the big end's
# rim (FRONT_KEEP "RingHoleX", .XX row).
requirement(
    "ring_hole",
    kind="hole",
    faces=(CylinderFace(RING_HOLE_DIA),),
    requirements=("dia", "thru", "station", "web_min"),
    fields={
        "at": ([RING_HOLE_X, 0.0, _RING_HOLE_ENTRY_Z], (_FRAME, "RING_HOLE_X")),
        "axis": ([0.0, 0.0, -1.0], (_FRAME,)),
        "dia": (
            drilled_limits(RING_HOLE_DIA, _P["RingHoleDia"], unit=UNIT),
            ("RING_HOLE_DIA", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (RING_HOLE_DIA, ("RING_HOLE_DIA",)),
        "thru": (True, ("DIMENSION_CALLOUTS",)),
        "process": ("drill", ("DIMENSION_CALLOUTS",)),
        "callout": (
            DIMENSION_CALLOUTS["RingHoleDia"],
            ("DIMENSION_CALLOUTS", (_SELF, "FRONT_KEEP")),
        ),
        "station": (
            limits(RING_HOLE_X, _P["RingHoleX"], unit=UNIT),
            ("RING_HOLE_X", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "station_nominal": (RING_HOLE_X, ("RING_HOLE_X",)),
        "station_from": ("big_end", ((_SELF, "FRONT_KEEP"),)),
        "web_min": (CROSS_HOLE_WEB_MIN, ("CROSS_HOLE_WEB_MIN",)),
    },
    precision={"dia": _P["RingHoleDia"], "station": _P["RingHoleX"]},
)


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pin source", adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Crank Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pin; purchased No. 3 taper pin; cross-drilled",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    # Descriptive text only; the hole's size and station are the model's.
    set_dimension_callouts(adapter, front_annotations, RING_HOLE_CALLOUTS)
    # The axis shows the cross-hole goes through the centre.
    add_view_centerline(
        adapter, front, face_xy=AXIS_FACE_PICK, label="crank pin axis centerline"
    )
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")

    # The fit callout (DRIVE FIT, SEE NOTE 2) is flagged on the taper it
    # governs: its leader tip lands on the cone's upper outline, mid-taper and
    # clear of the ring cross-hole.  Note 1 names the bought pin, note 2
    # states the matched fit.
    add_leader_note(
        adapter,
        TAPER_CALLOUT,
        text_xy=TAPER_NOTE_XY,
        attach_xy=TAPER_SILHOUETTE_PICK,
        label="taper fit callout",
        view=front,
    )
    if add_note(adapter, SHEET_NOTES, *NOTES_XY) is None:
        raise RuntimeError("failed to add the crank pin's numbered notes")

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pin Manufacturing Drawing",
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
