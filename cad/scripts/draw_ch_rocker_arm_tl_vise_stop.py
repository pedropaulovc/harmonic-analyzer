r"""Create the drawing for the rocker arm's vise blank-end stop (MHA-CH-006-TL-01).

Third-angle at 1:1, laid out for a Z-up part:

* the elevation is ``*Bottom`` (looking +Y, X right, Z up): the lug at the
  seat face, the arm over the step and the taller finger at its left end; it
  carries the axial sizes and the step's height, all from the seat face and
  the lug's bottom face (the seat face is the one clamped to the magnetic
  base);
* the plan above it is ``*Front`` (looking -Z, X right, Y up): the L itself,
  the finger reaching across the blank end;
* the side view to the elevation's right is ``*Right`` (looking -X onto the
  seat face) turned a quarter turn so Z runs up: the finger section, the lug
  section and both drilled holes, every size and position from the shared
  rear and bottom faces.

The bonding and mounting instructions ride the part's Manufacturing Notes.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import ch_rocker_arm_tl_vise_stop_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_vise_stop_spec import (
    ARM_INNER_Y,
    ARM_TOP_Z,
    BACK_X,
    BOTTOM_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FINGER_END_Y,
    FINGER_FRONT_X,
    FINGER_TOP_Z,
    NOSE_PIN_CALLOUT,
    NOSE_Y,
    NOSE_Z,
    NOTCH_TOP_Z,
    REAR_Y,
    SCREW_GRIP,
    SCREW_HOLE_CALLOUT,
    SCREW_Y,
    SCREW_Z,
    SEAT_X,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vise_stop"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 68 x 59 x 36 L: 1:1 stacks the plan over the elevation above the notes,
# with the side view and its dimensions to the elevation's right.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
ELEVATION_CENTER = (0.115, 0.115)
PLAN_CENTER = (ELEVATION_CENTER[0], 0.210)
SIDE_CENTER = (0.270, ELEVATION_CENTER[1])
ISO_CENTER = (0.378, 0.238)
NOTES_XY = (0.020, 0.050)
ISO_NOTE_XY = (0.345, 0.208)
# The *Right view turned so model +Z runs up the sheet (and +Y to the right).
SIDE_VIEW_ANGLE = -math.pi / 2.0

# Bounding-box centres: each view centres the part's box on its placement.
_XC = (SEAT_X + BACK_X) / 2.0
_YC = (REAR_Y + FINGER_END_Y) / 2.0
_ZC = (BOTTOM_Z + FINGER_TOP_Z) / 2.0


def _elevation(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (X, Z) on the elevation."""
    return (
        ELEVATION_CENTER[0] + (x_mm - _XC) * _S,
        ELEVATION_CENTER[1] + (z_mm - _ZC) * _S,
    )


def _side(y_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a model (Y, Z) on the turned side view."""
    return (
        SIDE_CENTER[0] + (y_mm - _YC) * _S,
        SIDE_CENTER[1] + (z_mm - _ZC) * _S,
    )


_ELEVATION_LEFT, _ELEVATION_BOTTOM = _elevation(BACK_X, BOTTOM_Z)
_ELEVATION_TOP = _elevation(0.0, FINGER_TOP_Z)[1]
_SIDE_LEFT, _SIDE_BOTTOM = _side(FINGER_END_Y, BOTTOM_Z)
_SIDE_RIGHT, _SIDE_TOP = _side(REAR_Y, FINGER_TOP_Z)

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position. Both axial sizes stack above the elevation, from the seat face;
# the step's length (the screw grip) stands below it and its height to its
# left, both from the lug's seat-bottom corner.
# On the side view the Y runs stand below (finger, nose) and above (arm,
# screw) the section, the heights to its left (finger, nose) and right
# (arm, screw), each hole size beside its own hole.
ELEVATION_KEEP = {
    "FingerFront": (_elevation((SEAT_X + FINGER_FRONT_X) / 2.0, 0.0)[0], _ELEVATION_TOP + 0.010),
    "OverallLength": (_elevation(_XC, 0.0)[0], _ELEVATION_TOP + 0.022),
    "ScrewGrip": (_elevation(SEAT_X - SCREW_GRIP / 2.0, 0.0)[0], _ELEVATION_BOTTOM - 0.010),
    "NotchHeight": (_ELEVATION_LEFT - 0.012, _elevation(0.0, (BOTTOM_Z + NOTCH_TOP_Z) / 2.0)[1]),
}


_PLUS_X = ([1.0, 0.0, 0.0], ("__frame__",))


def _sized_face(
    normal: tuple[float, float, float], axis: str, value: float, field: str, size: float,
    size_name: str, reference: str, contains_x: float | None = None,
) -> dict:
    """A planar face whose printed one-place size from ``reference`` is ``size``."""
    offset = value if sum(normal) > 0.0 else -value
    return {
        'kind': "face",
        'faces': (PlanarFace(normal, offset, contains_x_mm=contains_x),),
        'requirements': (field,),
        'fields': {
            "normal": (list(normal), ("__frame__",)),
            "plane": ({"frame": "model", "axis": axis, "value": value}, (size_name,)),
            field: (limits(size, 1), (size_name,)),
            f"{field}_nominal": (size, (size_name,)),
            **(
                {"height_from": (reference, (("draw_ch_rocker_arm_tl_vise_stop", "build"),))}
                if field == "height"
                else {"note": (f"{field} from {reference}", (size_name, ("draw_ch_rocker_arm_tl_vise_stop", "build")))}
            ),
        },
        'precision': {field: 1},
    }


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement("seat_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.SEAT_X),),
    requirements=("length",),
    fields={
        "normal": _PLUS_X,
        "plane": ({"frame": "model", "axis": "x", "value": part_spec.SEAT_X}, ("SEAT_X", "BASE_DEPTH")),
        "length": (limits(part_spec.OVERALL_LENGTH, 1), ("OVERALL_LENGTH",)),
        "length_nominal": (part_spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
        "note": (
            "clamped to the tapped face of a Kanetec MB-PM magnetic base "
            "(40 x 40 x 40, M6 x 6 tap) by one M6 x 16 SHCS",
            ("SCREW_HOLE_CALLOUT", "BASE_SKU", "BASE_SIZE", "BASE_TAP_DEPTH", "SCREW_THREAD", "SCREW_LENGTH"),
        ),
    },
    precision={"length": 1},
)

requirement("finger_front",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.FINGER_FRONT_X),),
    requirements=("length",),
    fields={
        "normal": _PLUS_X,
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.FINGER_FRONT_X},
            ("FINGER_FRONT_X", "NOSE_FACE_X", "NOSE_PIN_LENGTH", "FINGER_THICK"),
        ),
        "length": (limits(part_spec.FINGER_FRONT, 1), ("FINGER_FRONT",)),
        "length_nominal": (part_spec.FINGER_FRONT, ("FINGER_FRONT",)),
        "note": ("length from seat_face", (("draw_ch_rocker_arm_tl_vise_stop", "build"),)),
    },
    precision={"length": 1},
)

# The lug's head-bearing face: its printed three-place distance from the
# seat face (the screw grip) sets the screw's engagement and tip clearance.
requirement("screw_seat",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), -part_spec.GRIP_FACE_X),),
    requirements=("length",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.GRIP_FACE_X},
            ("GRIP_FACE_X", "SEAT_X", "SCREW_GRIP"),
        ),
        "length": (limits(part_spec.SCREW_GRIP, 3), ("SCREW_GRIP", "DRAWING_PRECISION")),
        "length_nominal": (part_spec.SCREW_GRIP, ("SCREW_GRIP",)),
        "note": (
            "lug face under the M6 SHCS head; length is the grip from the seat face",
            ("SCREW_GRIP", "SEAT_X", ("draw_ch_rocker_arm_tl_vise_stop", "build")),
        ),
    },
    precision={"length": 3},
)

# The printed heights and widths' reference faces: the lug's bottom and
# the shared rear face.
requirement("bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part_spec.BOTTOM_Z),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": part_spec.BOTTOM_Z}, ("BOTTOM_Z", "NOSE_HEIGHT")),
    },
)

# The step's ceiling under the arm (station inside the arm span, should
# the finger's underside bind as a separate coplanar face).
requirement("notch_ceiling", **_sized_face(
    (0.0, 0.0, -1.0), "z", part_spec.NOTCH_TOP_Z, "height", part_spec.NOTCH_HEIGHT, "NOTCH_HEIGHT", "bottom_face",
    contains_x=(part_spec.GRIP_FACE_X + part_spec.FINGER_FRONT_X) / 2.0,
))

SIDE_KEEP = {
    "FingerLength": (SIDE_CENTER[0], _SIDE_BOTTOM - 0.012),
    "NoseFromRear": (_side((NOSE_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_BOTTOM - 0.023),
    "ScrewFromRear": (_side((SCREW_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_TOP + 0.010),
    "ArmWidth": (_side((ARM_INNER_Y + REAR_Y) / 2.0, 0.0)[0], _SIDE_TOP + 0.021),
    "FingerHeight": (_SIDE_LEFT - 0.012, SIDE_CENTER[1]),
    "NoseHeight": (_SIDE_LEFT - 0.024, _side(0.0, (BOTTOM_Z + NOSE_Z) / 2.0)[1]),
    "ScrewHeight": (_SIDE_RIGHT + 0.012, _side(0.0, (BOTTOM_Z + SCREW_Z) / 2.0)[1]),
    "ArmHeight": (_SIDE_RIGHT + 0.024, _side(0.0, (BOTTOM_Z + ARM_TOP_Z) / 2.0)[1]),
    "NoseHoleDia": (_side(NOSE_Y, 0.0)[0] - 0.011, _SIDE_TOP + 0.034),
    "ScrewHoleDia": (_SIDE_RIGHT + 0.058, _SIDE_TOP + 0.036),
}


requirement("rear_face",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part_spec.REAR_Y),),
    requirements=(),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "y", "value": part_spec.REAR_Y}, ("REAR_Y", "SCREW_FROM_REAR")),
    },
)

requirement("finger_top", **_sized_face(
    (0.0, 0.0, 1.0), "z", part_spec.FINGER_TOP_Z, "height", part_spec.FINGER_HEIGHT, "FINGER_HEIGHT", "bottom_face"
))

requirement("finger_end", **_sized_face(
    (0.0, -1.0, 0.0), "y", part_spec.FINGER_END_Y, "length", part_spec.FINGER_LENGTH, "FINGER_LENGTH", "rear_face"
))

requirement("arm_top", **_sized_face((0.0, 0.0, 1.0), "z", part_spec.ARM_TOP_Z, "height", part_spec.ARM_HEIGHT, "ARM_HEIGHT", "bottom_face"))

requirement("arm_inner_face", **_sized_face(
    (0.0, -1.0, 0.0), "y", part_spec.ARM_INNER_Y, "width", part_spec.ARM_WIDTH, "ARM_WIDTH", "rear_face"
))

# The drilling and the bought nose pin it takes read under the hole's size,
# standing high enough above the section for the three callout lines.
CALLOUTS_BELOW = {
    "NoseHoleDia": f"DRILL THRU\n{NOSE_PIN_CALLOUT}",
    "ScrewHoleDia": SCREW_HOLE_CALLOUT,
}


requirement("nose_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.NOSE_HOLE_DIA),),
    requirements=("dia", "at", "end", "station", "height"),
    fields={
        "at": ([part_spec.FINGER_FRONT_X, part_spec.NOSE_Y, part_spec.NOSE_Z], ("FINGER_FRONT_X", "NOSE_Y", "NOSE_Z")),
        "axis": _PLUS_X,
        "dia": (limits(part_spec.NOSE_HOLE_DIA, 2, part_spec.DRILLED_BAND), ("NOSE_HOLE_DIA", "DRILLED_BAND")),
        "dia_nominal": (part_spec.NOSE_HOLE_DIA, ("NOSE_HOLE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm_tl_vise_stop", "CALLOUTS_BELOW"),)),
        # Printed NoseFromRear / NoseHeight, from the rear and bottom faces
        # (the schema's only reference field is height_from; the note
        # names the station's).
        "station": (limits(part_spec.NOSE_FROM_REAR, 1), ("NOSE_FROM_REAR", "REAR_Y", "NOSE_Y")),
        "station_nominal": (part_spec.NOSE_FROM_REAR, ("NOSE_FROM_REAR",)),
        "height": (limits(part_spec.NOSE_HEIGHT, 1), ("NOSE_HEIGHT",)),
        "height_nominal": (part_spec.NOSE_HEIGHT, ("NOSE_HEIGHT",)),
        "height_from": ("bottom_face", (("draw_ch_rocker_arm_tl_vise_stop", "build"),)),
        "process": ("drill", (("draw_ch_rocker_arm_tl_vise_stop", "CALLOUTS_BELOW"),)),
        # The stop contact: the fixed pin's end, on the blank's raw left
        # end (nominal; X zero is edge-found on the part afterwards).
        "end": (
            [part_spec.NOSE_FACE_X, part_spec.NOSE_Y, part_spec.NOSE_Z],
            ("NOSE_FACE_X", "BLANK_END_X_SETUP", "JAW_HALF_WIDTH", ("ch_rocker_arm_spec", "ROD_TIP_X")),
        ),
        "supply_length": (part_spec.NOSE_PIN_LENGTH, ("NOSE_PIN_LENGTH",)),
        "note": (
            "bought hardened 6 x 8 dowel pin fixed immovable, flush with the back face; "
            "its end is the blank-end stop; station from rear_face, height from bottom_face",
            ("DRAWING_NOTES", "NOSE_PIN_CALLOUT", "NOSE_PIN_DIA", "NOSE_PIN_LENGTH", "BOND_GAP_MAX", ("draw_ch_rocker_arm_tl_vise_stop", "build")),
        ),
    },
    precision={"dia": 2, "station": 1, "height": 1},
)

requirement("screw_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.SCREW_HOLE_DIA),),
    requirements=("dia", "at", "station", "height"),
    fields={
        "at": ([part_spec.SEAT_X, part_spec.SCREW_Y, part_spec.SCREW_Z], ("SEAT_X", "SCREW_Y", "SCREW_Z")),
        "axis": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "dia": (limits(part_spec.SCREW_HOLE_DIA, 2, part_spec.DRILLED_BAND), ("SCREW_HOLE_DIA", "DRILLED_BAND")),
        "dia_nominal": (part_spec.SCREW_HOLE_DIA, ("SCREW_HOLE_DIA",)),
        "thru": (True, ("SCREW_HOLE_CALLOUT",)),
        # Printed ScrewFromRear / ScrewHeight, from the rear and bottom faces.
        "station": (limits(part_spec.SCREW_FROM_REAR, 1), ("SCREW_FROM_REAR",)),
        "station_nominal": (part_spec.SCREW_FROM_REAR, ("SCREW_FROM_REAR",)),
        "height": (limits(part_spec.SCREW_HEIGHT, 1), ("SCREW_HEIGHT",)),
        "height_nominal": (part_spec.SCREW_HEIGHT, ("SCREW_HEIGHT",)),
        "height_from": ("bottom_face", (("draw_ch_rocker_arm_tl_vise_stop", "build"),)),
        "process": ("drill", ("SCREW_HOLE_CALLOUT",)),
        "note": (
            f"drilled clearance through the lug for one M6 x {part_spec.SCREW_LENGTH:g} SHCS (ISO 4762) "
            f"into the M6 x {part_spec.BASE_TAP_DEPTH:g} deep tap of a Kanetec MB-PM base; head on "
            f"the lug face (screw_seat, {part_spec.SCREW_GRIP:.3f} +-{part_spec.LINEAR_3PL:g} from the seat); "
            f"full-thread engagement {part_spec.SCREW_ENGAGEMENT_PRINTED:.1f} min "
            f"({part_spec.SCREW_ENGAGEMENT_PRINTED_D:.2f}D); tip {part_spec.SCREW_TIP_CLEARANCE_PRINTED:.1f} min "
            "clear of the tap bottom; hand-seating load only; station from rear_face, "
            "height from bottom_face",
            (
                "SCREW_HOLE_CALLOUT",
                "SCREW_THREAD",
                "SCREW_LENGTH",
                "SCREW_LENGTH_BAND",
                "BASE_SKU",
                "BASE_TAP_DEPTH",
                "SCREW_GRIP",
                "LINEAR_3PL",
                "SCREW_ENGAGEMENT_PRINTED",
                "SCREW_ENGAGEMENT_PRINTED_D",
                "SCREW_TIP_CLEARANCE_PRINTED",
                "SCREW_ENGAGEMENT_MIN",
                "SCREW_TIP_CLEARANCE_MIN",
            ),
        ),
    },
    precision={"dia": 2, "station": 1, "height": 1},
)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open vise-stop source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
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
            0: "Rocker Vise Blank-End Stop Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm vise blank-end stop; milled aluminium L; MHA-CH-006-TL-01",
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
        raise RuntimeError("failed to stand the vise stop's side view upright")
    drawing_model.EditRebuild3()
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (elevation, plan, side):
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
            side,
            keep=SIDE_KEEP,
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) and the drilled-hole band are
    # authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    if not auto_center_marks(adapter, side, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the drilled holes")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Vise Blank-End Stop Drawing",
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
