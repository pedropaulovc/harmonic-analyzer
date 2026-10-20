r"""Create the drawing for the oblique trammel's pivot pin (MHA-CH-06-TL-23)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import place_view

from _check import check
from _drawing_edges import scan_view_edges
from _drawing_gdt import add_feature_control_frame
from _gear_drawing_entities import visible_circle_edge
from _gtol_face_read import face_geometry
from _native_axis_datum import add_native_axis_datum
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

# The integral flange and transverse cross hole are visible in the Right
# projection. Native model dimensions remain the sole printed size authority.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
PROFILE_CENTER = (0.185, 0.164)
ISO_CENTER = (0.355, 0.205)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.325, 0.252)
_ABOVE = PROFILE_CENTER[1] + part_spec.FLANGE_DIA / 2.0 * _S
_BELOW = PROFILE_CENTER[1] - part_spec.FLANGE_DIA / 2.0 * _S


def _x(z_mm: float) -> float:
    """Sheet X of a model station (the view centres on the model box)."""
    return PROFILE_CENTER[0] - (z_mm - OVERALL_LENGTH / 2.0) * _S


def _span_mid(station_mm: float) -> float:
    return (_x(OVERALL_LENGTH) + _x(station_mm)) / 2.0


ROW_Y = (_ABOVE + 0.012, _ABOVE + 0.024, _ABOVE + 0.036)
CHAMFER_Y = _ABOVE - 0.025
PROFILE_KEEP = {
    "CarrierLength": (_span_mid(CARRIER_STATION), ROW_Y[0]),
    "BearingLength": (_x(BEARING_LENGTH / 2.0), ROW_Y[1]),
    "UpperBossHeight": (_x((part_spec.FLANGE_TOP_STATION + CARRIER_STATION) / 2.0), 0.210),
    "PinLength": (_span_mid(0.0), ROW_Y[2]),
    "TopChamfer": (_x(OVERALL_LENGTH) - 0.012, CHAMFER_Y),
    "BottomChamfer": (_x(0.0) + 0.012, CHAMFER_Y),
    "BearingDia": (_x(BEARING_LENGTH / 2.0), 0.101),
    "CarrierDia": (_x(OVERALL_LENGTH) + 0.004, 0.082),
    "CollarDia": (_x(CARRIER_STATION - 5.0), 0.127),
    "FlangeDia": (_x(part_spec.FLANGE_BOTTOM_STATION + part_spec.FLANGE_THICK / 2.0), 0.079),
    "FlangeThick": (_x(part_spec.FLANGE_BOTTOM_STATION + part_spec.FLANGE_THICK / 2.0), 0.229),
    "LowerBossHeight": (0.303, 0.118),
    "CarrierFilletR": (_x(CARRIER_STATION) - 0.012, 0.137),
    "SeatFilletR": (_x(COLLAR_STATION) + 0.012, 0.137),
    "CrossHoleDia": (_x(part_spec.CROSS_HOLE_STATION) - 0.035, 0.209),
    "CrossHoleFromEnd": (_x(OVERALL_LENGTH - part_spec.CROSS_HOLE_FROM_END / 2.0), 0.192),
}
CENTERLINE_PICK = (_x(CARRIER_STATION - 5.0), PROFILE_CENTER[1] + 0.003)


_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))
_FROM_TOP = ("top_face", (("draw_ch_rocker_arm_tl_oblique_pivot_pin", "build"),))
_FROM_BOTTOM = ("bottom_face", (("draw_ch_rocker_arm_tl_oblique_pivot_pin", "build"),))


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
            limits(part_spec.BEARING_LENGTH, part_spec.LENGTH_PLACES),
            ("BEARING_LENGTH",),
        ),
        "station_nominal": (part_spec.BEARING_LENGTH, ("BEARING_LENGTH",)),
        "height_from": _FROM_BOTTOM,
    },
    precision={"station": part_spec.LENGTH_PLACES},
)

requirement(
    "bottom_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=(),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
    },
)

requirement(
    "collar",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.COLLAR_DIA,
            contains_z_mm=(part_spec.FLANGE_TOP_STATION + part_spec.CARRIER_STATION) / 2.0,
        ),
    ),
    requirements=("dia", "length"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.COLLAR_DIA, part_spec.COLLAR_PLACES),
            ("COLLAR_DIA",),
        ),
        "dia_nominal": (part_spec.COLLAR_DIA, ("COLLAR_DIA",)),
        "length": (
            limits(part_spec.UPPER_BOSS_HEIGHT, part_spec.UPPER_BOSS_PLACES),
            ("UPPER_BOSS_HEIGHT", "UPPER_BOSS_PLACES"),
        ),
        "length_nominal": (part_spec.UPPER_BOSS_HEIGHT, ("UPPER_BOSS_HEIGHT",)),
    },
    precision={"dia": part_spec.COLLAR_PLACES, "length": part_spec.UPPER_BOSS_PLACES},
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

requirement(
    "captive_flange",
    kind="boss",
    faces=(CylinderFace(part_spec.FLANGE_DIA),),
    requirements=("dia", "length"),
    fields={
        "axis": _AXIS,
        "dia": (
            limits(part_spec.FLANGE_DIA, 2, part_spec.FLANGE_DIA_BAND),
            ("FLANGE_DIA", "FLANGE_DIA_BAND"),
        ),
        "dia_nominal": (part_spec.FLANGE_DIA, ("FLANGE_DIA",)),
        "length": (
            limits(part_spec.FLANGE_THICK, part_spec.FLANGE_THICK_PLACES),
            ("FLANGE_THICK", "FLANGE_THICK_PLACES"),
        ),
        "length_nominal": (part_spec.FLANGE_THICK, ("FLANGE_THICK",)),
    },
    precision={"dia": 2, "length": part_spec.FLANGE_THICK_PLACES},
)

requirement(
    "lower_inner_race_boss",
    kind="boss",
    faces=(
        CylinderFace(
            part_spec.COLLAR_DIA,
            contains_z_mm=part_spec.COLLAR_STATION + part_spec.LOWER_BOSS_HEIGHT / 2.0,
        ),
    ),
    requirements=("note",),
    fields={
        "axis": _AXIS,
        "note": (
            " ".join(part_spec.DIMENSION_CALLOUTS["LowerBossHeight"].splitlines()),
            ("LOWER_BOSS_HEIGHT", "DIMENSION_CALLOUTS"),
        ),
    },
)

requirement(
    "clevis_cross_hole",
    kind="hole",
    faces=(CylinderFace(part_spec.CROSS_HOLE_DIA),),
    requirements=("dia", "station", "thru"),
    fields={
        "axis": ([1.0, 0.0, 0.0], ("__frame__",)),
        "at": ([0.0, 0.0, part_spec.CROSS_HOLE_STATION], ("CROSS_HOLE_STATION",)),
        "dia": (
            limits(part_spec.CROSS_HOLE_DIA, 2, part_spec.CROSS_HOLE_BAND),
            ("CROSS_HOLE_DIA", "CROSS_HOLE_BAND"),
        ),
        "dia_nominal": (part_spec.CROSS_HOLE_DIA, ("CROSS_HOLE_DIA",)),
        "station": (limits(part_spec.CROSS_HOLE_FROM_END, part_spec.LENGTH_PLACES), ("CROSS_HOLE_FROM_END",)),
        "station_nominal": (part_spec.CROSS_HOLE_FROM_END, ("CROSS_HOLE_FROM_END",)),
        "height_from": _FROM_TOP,
        "thru": (True, ("DIMENSION_CALLOUTS",)),
    },
    precision={"dia": 2, "station": part_spec.LENGTH_PLACES},
)


def _flange_square_frames(adapter: Any, profile: Any, end: Any) -> None:
    """Both real stop faces, not just the revolve's nominal square geometry."""
    add_native_axis_datum(
        adapter, end,
        entity=visible_circle_edge(adapter, end, part_spec.BEARING_DIA),
        source_path=SOURCE, radius_m=part_spec.BEARING_DIA / 2000.0,
        datum="A", label="pin bearing-journal axis", shoulder=True,
        stability_tolerance_m=0.0001,
    )
    rims = scan_view_edges(profile, label="captured flange rims")
    for control, station, side in zip(
        part_spec.GEOMETRIC_CONTROLS,
        (part_spec.FLANGE_BOTTOM_STATION, part_spec.FLANGE_TOP_STATION),
        (1.0, -1.0),
        strict=True,
    ):
        matches = [
            item for item in rims.circles
            if abs(item.circle[2] - station) < 1e-4
            and abs(item.circle[6] - part_spec.FLANGE_DIA / 2.0) < 1e-4
        ]
        if len(matches) != 1:
            raise RuntimeError(f"{control.key}: expected one flange-face rim")
        faces = []
        for face in matches[0].edge.GetTwoAdjacentFaces2() or ():
            geometry = None if face is None else face_geometry(face)
            if geometry is not None and control.face.matches(geometry):
                faces.append(face)
        if len(faces) != 1:
            raise RuntimeError(f"{control.key}: rim does not identify one stop face")
        landing = (_x(station), PROFILE_CENTER[1] + part_spec.FLANGE_DIA * _S / 3.0)
        add_feature_control_frame(
            adapter, profile, entity=faces[0], entity_type="FACE",
            leader_attach_xy=landing,
            frame_xy=(landing[0] + side * 0.025 - (0.027 if side < 0.0 else 0.0), landing[1] + 0.004),
            characteristic=control.characteristic, tolerance=control.tolerance,
            datums=control.datums, label=control.key,
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
    end = place_view(adapter, str(SOURCE), "*Back", 0.355, 0.105, scale=(2, 1))
    for view in (profile, iso, end):
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
    _flange_square_frames(adapter, profile, end)

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
