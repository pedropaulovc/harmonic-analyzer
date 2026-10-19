r"""Create the drawing for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_oblique_pivot_pin_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_oblique_pivot_pin_spec import (
    BEARING_LENGTH,
    CARRIER_STATION,
    COLLAR_DIA,
    COLLAR_HEIGHT,
    COLLAR_STATION,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OVERALL_LENGTH,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_pivot_pin"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 37 mm pin: 4:1 keeps the collar, the chamfers and the shoulder radii
# legible on the one turned profile.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
# One turned profile (*Right: model +Z runs to sheet -X, so the top end,
# faced in the turning chucking, is on the left) carries every size. The
# profile sketch lies on the upper half, so its length and chamfer extension
# lines rise from the upper outline: the length baseline from the top end
# and both chamfers go above the view (the hub pin's layout). The diameters
# and the two shoulder radii go below, where nothing but their own leaders
# reaches. Farm run 20261017T015225029Z had the lengths below, and both
# radius shoulders crossed the extension lines rising at the shoulders.
PROFILE_CENTER = (0.200, 0.160)
# The isometric moves 10 mm right of run 20261017T015225029Z's, clear of the
# bottom chamfer's callout; the note keeps its 45 mm over the view centre.
ISO_CENTER = (0.370, 0.200)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.340, 0.245)
_COLLAR_HALF = COLLAR_DIA / 2.0 * _S
_ABOVE = PROFILE_CENTER[1] + _COLLAR_HALF
_BELOW = PROFILE_CENTER[1] - _COLLAR_HALF


def _x(z_mm: float) -> float:
    """Sheet X of a model station (the view centres on the model box)."""
    return PROFILE_CENTER[0] - (z_mm - OVERALL_LENGTH / 2.0) * _S


# Rows of the top-end baseline, nearest first. A chamfer's extension lines
# end about 4.6 mm under its text position, so the chamfers stand under the
# first row and no row's dimension line crosses them.
ROW_Y = (_ABOVE + 0.019, _ABOVE + 0.032, _ABOVE + 0.045)
CHAMFER_Y = _ABOVE + 0.009
# The callout text (value over "X 45° LEAD CHAMFER", about 48 mm wide) is
# centred on its position; each block ends 8 mm outboard of its end face.
CHAMFER_OUTBOARD = 0.032
# Below the view, as run 20261017T022004769Z printed them (sheet mm):
# * a radius text is centred on its position with its shoulder 2.8 under
#   it; the knee is 13.7 from the position on the corner's side.
# * a diameter's dimension line stands at its position's x and runs from
#   its callout block's bottom up through the part. The block starts at
#   that line and runs right by its widest line; four lines span +-12.85
#   about the position's y, the bare Ø12.70 sits 2.8 above its shoulder.
# So each block must stay out of every other diameter's line, and every
# deeper block's line out of the shallower blocks. Run 20261017T022004769Z
# stacked the 65 mm wide carrier block over the collar's Ø12.5 (now Ø12.70).
FILLET_Y = _BELOW - 0.003
# The seat radius's knee 2.8 mm toward the collar from its corner, so its
# leader passes left of where the bearing diameter's extension line starts
# at the collar face (run 20261017T022004769Z's one advisory crossing).
SEAT_FILLET_X = _x(COLLAR_STATION) + 0.0117
CARRIER_FILLET_X = _x(CARRIER_STATION) - 0.016
# Nearest the part: the collar's one line between the two radius knees,
# under the radius shoulders.
COLLAR_DIA_XY = (_x(COLLAR_STATION + COLLAR_HEIGHT / 2.0), _BELOW - 0.011)
# The bearing block right of the seat radius's text, on its section.
BEARING_DIA_XY = (_x(BEARING_LENGTH / 2.0), _BELOW - 0.017)
# The carrier block deepest, its line 6 mm in from the top end and left of
# the carrier radius's shoulder; the block runs under the collar's Ø12.70
# and stops left of the bearing's line.
CARRIER_DIA_XY = (_x(OVERALL_LENGTH) + 0.006, _BELOW - 0.031)


def _span_mid(station_mm: float) -> float:
    """Sheet X of the middle of a top-end-to-station span."""
    return (_x(OVERALL_LENGTH) + _x(station_mm)) / 2.0


PROFILE_KEEP = {
    # Shortest span nearest the part so no extension line crosses a row.
    "CarrierLength": (_span_mid(CARRIER_STATION), ROW_Y[0]),
    "CollarSeatStation": (_span_mid(COLLAR_STATION), ROW_Y[1]),
    "PinLength": (_span_mid(0.0), ROW_Y[2]),
    "TopChamfer": (_x(OVERALL_LENGTH) - CHAMFER_OUTBOARD, CHAMFER_Y),
    "BottomChamfer": (_x(0.0) + CHAMFER_OUTBOARD, CHAMFER_Y),
    "BearingDia": BEARING_DIA_XY,
    "CarrierDia": CARRIER_DIA_XY,
    "CollarDia": COLLAR_DIA_XY,
    "CarrierFilletR": (CARRIER_FILLET_X, FILLET_Y),
    "SeatFilletR": (SEAT_FILLET_X, FILLET_Y),
}
# The axis pick sits on the collar face just off the axis.
CENTERLINE_PICK = (_x(COLLAR_STATION + COLLAR_HEIGHT / 2.0), PROFILE_CENTER[1] + 0.003)


_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_FROM_TOP = ("top_face", (("draw_ch_rocker_arm_tl_oblique_pivot_pin", "build"),))


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement(
    "top_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.OVERALL_LENGTH),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
    },
)

requirement(
    "collar_top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.CARRIER_STATION),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.CARRIER_STATION},
            ("CARRIER_STATION",),
        ),
        "station": (
            limits(part_spec.CARRIER_LENGTH, part_spec.LENGTH_PLACES),
            ("CARRIER_LENGTH",),
        ),
        "station_nominal": (part_spec.CARRIER_LENGTH, ("CARRIER_LENGTH",)),
        "height_from": _FROM_TOP,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "collar_seat",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part_spec.COLLAR_STATION),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.COLLAR_STATION},
            ("COLLAR_STATION",),
        ),
        "station": (
            limits(part_spec.TOP_TO_COLLAR_SEAT, part_spec.LENGTH_PLACES),
            ("TOP_TO_COLLAR_SEAT",),
        ),
        "station_nominal": (part_spec.TOP_TO_COLLAR_SEAT, ("TOP_TO_COLLAR_SEAT",)),
        "height_from": _FROM_TOP,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("station",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "station": (
            limits(part_spec.OVERALL_LENGTH, part_spec.LENGTH_PLACES),
            ("OVERALL_LENGTH",),
        ),
        "station_nominal": (part_spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "height_from": _FROM_TOP,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "collar",
    kind="boss",
    faces=(CylinderFace(part_spec.COLLAR_DIA),),
    requirements=("dia",),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.COLLAR_DIA, part_spec.COLLAR_PLACES),
            ("COLLAR_DIA",),
        ),
        "dia_nominal": (part_spec.COLLAR_DIA, ("COLLAR_DIA",)),
    },
    precision={"dia": part_spec.COLLAR_PLACES},
)

# Rule 4: the k5 press seat in both 6200-2RS inner races.
requirement(
    "bearing_section",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.BEARING_DIA, contains_z_mm=part_spec.BEARING_LENGTH / 2.0
        ),
    ),
    requirements=("dia", "note"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(
                part_spec.BEARING_DIA,
                part_spec.FIT_PLACES,
                part_spec.BEARING_PRINT_BAND,
            ),
            ("BEARING_DIA", "BEARING_PRINT_BAND"),
        ),
        "dia_nominal": (part_spec.BEARING_DIA, ("BEARING_DIA",)),
        "note": (part_spec.BEARING_NOTE, ("BEARING_NOTE", "RACE_BORE_BAND")),
    },
    precision={"dia": part_spec.FIT_PLACES},
)

# Rule 4: the h6 locating section in the carrier's Ø10 H7 pin holes.
requirement(
    "carrier_section",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.FIT_DIA,
            contains_z_mm=part_spec.CARRIER_STATION + part_spec.CARRIER_LENGTH / 2.0,
        ),
    ),
    requirements=("dia", "note"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.FIT_DIA, part_spec.FIT_PLACES, part_spec.CARRIER_BAND),
            ("FIT_DIA", "CARRIER_BAND"),
        ),
        "dia_nominal": (part_spec.FIT_DIA, ("FIT_DIA",)),
        "note": (part_spec.CARRIER_NOTE, ("CARRIER_NOTE", "PIN_HOLE_BAND")),
    },
    precision={"dia": part_spec.FIT_PLACES},
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-pin source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Oblique Trammel Pivot Pin Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker oblique trammel pivot pin; 1144 stress-proof; MHA-CH-06-TL-23",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(
        adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each fit band) are authored on the part; the sheet only
    # proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # drawing-guidelines.md rule 4: each fit band names its mate and its fit.
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, location="below")
    add_view_centerline(
        adapter, profile, face_xy=CENTERLINE_PICK, label="pivot pin axis"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Oblique Trammel Pivot Pin Drawing",
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
