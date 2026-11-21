r"""Create the manufacturing drawing for the wheel-axle spacer (MHA-MG-11).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_axle_spacer.py mg-wheel-axle-spacer
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
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
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from mg_wheel_axle_spacer_spec import (
    BORE_CALLOUT,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LENGTH,
    LENGTH_CALLOUT,
    LENGTH_LIMITS,
    OD,
    UNIT,
    WALL_WORST,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["mg_wheel_axle_spacer"]
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

# A Ø.44 sleeve, its length set by the pen line (about .73), at 3:1: the face
# view, the side view and the isometric on one row midway between the top
# border and the title block (the mg-wheel-drum sheet's layout), with no
# general note (drawing-guidelines.md rule 7 (notes: few, flagged, never a
# method)).
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.090, 0.155)
RIGHT_CENTER = (0.215, 0.155)
ISO_CENTER = (0.345, 0.155)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Both diameters import on the face view, where every diameter line runs
# through the centre: two would cross there.  The bore keeps the face view,
# its one-line callout up and right of it; the O.D. is a donor there and
# moves onto the side view, right of the sleeve (drawing-guidelines.md rule
# 11 (turned parts read like the lathe)).  The length and its two-line
# callout hang under the side view, centred between its extension lines;
# each callout line stays narrower than that span (spec LENGTH_CALLOUT).
FRONT_KEEP = {
    "SpacerOd": (0.050, 0.100),
    "SpacerBore": (0.130, 0.205),
}
RIGHT_KEEP = {
    "SpacerLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - OD / 2.0 * _S - 0.022),
}
OD_ON_SIDE = (RIGHT_CENTER[0] + LENGTH / 2.0 * _S + 0.030, RIGHT_CENTER[1])
# The bore is a drilled clearance (rule 12 (hole and slot callouts say what to
# do)); the length's band names the stack it sets (rule 4 (tighten only for
# function, and name the mate)).
DIMENSION_CALLOUTS = {
    "SpacerBore": BORE_CALLOUT,
    "SpacerLength": LENGTH_CALLOUT,
}


# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_mg_wheel_axle_spacer: axis +Z through the origin, the bar-side face
# at z = 0, the datum end the length runs from; the washer face at z =
# LENGTH). The length carries its model band (LENGTH_LIMITS); the O.D. the
# title block's .XX row; the bore the DRILLED HOLES row. Each ``span`` is a
# diameter's model-Z extent. The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_mg_wheel_axle_spacer"
part_metadata(
    model_sources=("LENGTH", "OD", "BORE_DIA"),
    precision_sources=("DRAWING_PRECISION", (_SELF, "DRAWING_PRECISION_BY_NAME")),
)
requirement(
    "datum_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("LENGTH",)),
        "outward": ([0.0, 0.0, -1.0], ("LENGTH",)),
    },
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), LENGTH),),
    requirements=("length",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 0.0, 1.0], ("LENGTH",)),
        "length": (
            list(LENGTH_LIMITS),
            ("LENGTH_LIMITS", "LENGTH_BAND", (_SELF, "RIGHT_KEEP")),
        ),
        "length_nominal": (LENGTH, ("LENGTH",)),
        "length_from": ("datum_end", ((_SELF, "RIGHT_KEEP"),)),
        "callout": (LENGTH_CALLOUT, ("LENGTH_CALLOUT",)),
    },
    precision={"length": _P["SpacerLength"]},
)
requirement(
    "outer",
    kind="diameter",
    faces=(CylinderFace(OD),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("OD",)),
        "at": ([0.0, 0.0, 0.0], ("OD",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            limits(OD, _P["SpacerOd"], unit=UNIT),
            ("OD", "UNIT", (_SELF, "OD_ON_SIDE")),
        ),
        "dia_nominal": (OD, ("OD",)),
    },
    precision={"dia": _P["SpacerOd"]},
)
requirement(
    "bore",
    kind="hole",
    faces=(CylinderFace(BORE_DIA),),
    requirements=("dia", "thru"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("BORE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("BORE_DIA",)),
        "span": ([0.0, LENGTH], ("LENGTH",)),
        "dia": (
            drilled_limits(BORE_DIA, _P["SpacerBore"], unit=UNIT),
            ("BORE_DIA", "UNIT", (_SELF, "FRONT_KEEP")),
        ),
        "nominal_dia": (BORE_DIA, ("BORE_DIA",)),
        "thru": (True, ("BORE_CALLOUT",)),
        "process": ("drill", ("BORE_CALLOUT",)),
        "wall_min": (WALL_WORST, ("WALL_WORST",)),
        "callout": (BORE_CALLOUT, ("BORE_CALLOUT",)),
    },
    precision={"dia": _P["SpacerBore"]},
)


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle spacer source", adapter.open_model(str(SOURCE)))
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
        required=("Number", "Material Specification", "Finish", "Quantity"),
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
            0: "Wheel Axle Spacer Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel axle spacer; turned brass",
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
    od_donors = [
        a for a in front_annotations if dimension_name(adapter, a) == "SpacerOd"
    ]
    if len(od_donors) != 1:
        raise RuntimeError("expected one spacer O.D. donor dimension")
    moved_od = move_model_dimension(
        adapter, od_donors[0], right, OD_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "SpacerOd"),
        *right_annotations,
        moved_od,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Axle Spacer Manufacturing Drawing",
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
