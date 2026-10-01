r"""Create the manufacturing drawing for the latch-hook bracket (MHA-170).

Third-angle, all at 4:1:

* the elevation is ``*Bottom`` (looking +Y, X right, Z up): the L's section
  with the base on the bar underneath and the flap rising at the right; it
  carries the base length and the flap height;
* the plan above it is ``*Front`` (looking -Z onto the base, X right, Y up):
  the two screw holes, located from the flap's outer face and the low-Y
  edge, and the banded width;
* the side view to the elevation's right is ``*Right`` (looking -X onto the
  flap's outer face) turned a quarter turn so Z runs up: the two rivet
  holes, sized only -- they are drilled at assembly through the hook, so
  the sheet gives no location for them.

The bend and drilling instructions ride the part's Manufacturing Notes.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from latch_hook_bracket_geometry import (
    BASE_LENGTH,
    FLAP_HEIGHT,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    WIDTH,
)
from latch_hook_bracket_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_CALLOUT,
    PAIR_CALLOUT,
    RIVET_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["latch_hook_bracket"]
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

# A 17 x 8 x 19 bracket: 4:1 keeps the Ø1.6 rivet holes and their .XXX
# positions legible; the three orthographic views fit the landscape sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
ELEVATION_CENTER = (0.170, 0.100)
PLAN_CENTER = (ELEVATION_CENTER[0], 0.200)
SIDE_CENTER = (0.275, ELEVATION_CENTER[1])
ISO_CENTER = (0.360, 0.205)
NOTES_XY = (0.020, 0.060)
# The *Right view turned so model +Z runs up the sheet (and +Y to the right).
SIDE_VIEW_ANGLE = -math.pi / 2.0


def _elevation(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (X, Z) on the elevation (bbox-centred)."""
    return (
        ELEVATION_CENTER[0] + (x_mm + BASE_LENGTH / 2.0) * _S,
        ELEVATION_CENTER[1] + (z_mm - FLAP_HEIGHT / 2.0) * _S,
    )


def _plan(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (X, Y) on the plan (bbox-centred)."""
    return (
        PLAN_CENTER[0] + (x_mm + BASE_LENGTH / 2.0) * _S,
        PLAN_CENTER[1] + (y_mm - WIDTH / 2.0) * _S,
    )


def _side(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (Y, Z) on the turned side view (bbox-centred)."""
    return (
        SIDE_CENTER[0] + (y_mm - WIDTH / 2.0) * _S,
        SIDE_CENTER[1] + (z_mm - FLAP_HEIGHT / 2.0) * _S,
    )


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The elevation's base length runs under it and the flap height
# to its right.  On the plan the two screw-hole X chains stack above the
# view, the hole Y and the width stand to its left, and the hole size sits
# below the near hole.  On the side view the rivet-hole size leads to the
# upper modelled hole from above-left.
ELEVATION_KEEP = {
    "BaseLength": (
        _elevation(-BASE_LENGTH / 2.0, 0.0)[0],
        _elevation(0.0, 0.0)[1] - 0.014,
    ),
    "FlapHeight": (_elevation(0.0, 0.0)[0] + 0.014, ELEVATION_CENTER[1]),
}
PLAN_KEEP = {
    "ScrewX2": (_plan(SCREW_HOLE_X[1] / 2.0, 0.0)[0], _plan(0.0, WIDTH)[1] + 0.010),
    "ScrewX1": (_plan(SCREW_HOLE_X[0] / 2.0, 0.0)[0], _plan(0.0, WIDTH)[1] + 0.020),
    "ScrewY": (_plan(-BASE_LENGTH, 0.0)[0] - 0.012, _plan(0.0, SCREW_HOLE_Y / 2.0)[1]),
    "Width": (_plan(-BASE_LENGTH, 0.0)[0] - 0.026, PLAN_CENTER[1]),
    "ScrewDia": (_plan(SCREW_HOLE_X[1], 0.0)[0] + 0.012, _plan(0.0, 0.0)[1] - 0.012),
}
SIDE_KEEP = {
    "RivetDia": (_side(0.0, 0.0)[0] - 0.014, _side(0.0, FLAP_HEIGHT)[1] + 0.008),
}
CALLOUTS_ABOVE = {"ScrewDia": PAIR_CALLOUT, "RivetDia": PAIR_CALLOUT}
CALLOUTS_BELOW = {"ScrewDia": HOLE_CALLOUT, "RivetDia": RIVET_HOLE_CALLOUT}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open latch-hook-bracket source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Latch Hook Bracket Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "latch hook bracket; bent steel sheet",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    elevation = place_view(
        adapter, str(SOURCE), "*Bottom", *ELEVATION_CENTER, scale=VIEW_SCALE
    )
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if (
        abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi))
        > 1e-9
    ):
        raise RuntimeError("failed to stand the bracket's flap view upright")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (elevation, plan, side, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            elevation,
            keep=ELEVATION_KEEP,
            view_label="elevation",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            plan,
            keep=PLAN_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            side,
            keep=SIDE_KEEP,
            view_label="flap",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # and the hole, position and width bands are authored on the part; the
    # sheet only proves the import kept the places.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    for view, label in ((plan, "screw holes"), (side, "rivet holes")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label}")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0], 0.160)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Latch Hook Bracket Manufacturing Drawing",
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
