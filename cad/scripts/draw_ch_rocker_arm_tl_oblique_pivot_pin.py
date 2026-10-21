r"""Create the oblique trammel pivot-pin drawing (MHA-CH-06-TL-23).

Layout evidence: the d349b9930 native PDF and layout-audit report from worker
swmaker00000a, drawing leaf 2026-10-21T05:32:39Z. All 20 gating records are
visible paper defects, not collector phantoms: five strike the flange/upper-boss
stack, three strike the bearing-end lead, eight involve the carrier-end lead,
cross-hole size or 6.0 station, three involve the lower-boss/fit/radius group,
and one is the inspection note's right-border overrun.

Keep the 3:1 profile and 2:1 pictorial. The upper-boss block occupies the
90.5..164 mm witness bay; the flange and fitted lower-boss blocks stack in
the 213.5..279.5 mm bay. In particular the lower-boss line is above its
182.05 mm witness origins, so neither witness descends through the native
R0.2 MAX shoulder at Y134.2219 mm or its material-arc leader. The radius
itself, its attachment and the measured (1.15) reference remain unchanged.

The two left callouts have separate rows outside X90.5; the bearing-end lead
uses clear paper below the pictorial. Budget the inspection note's measured
107.7045 mm native extent, not character count. Raising the bearing-fit block
also separates it from the flange-diameter block. Of the six advisory records,
the cross-hole diameter crossing its own axis-location witness is an ordinary
dimension intersection, not a text collision; the other five motivate the
same lane repairs. No finding is masked or reclassified here. These are
measured-boundary placement choices, not after-fix native acceptance: the
owner must regenerate the audit/PDF and inspect complete text and leaders.
"""

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

# The integral flange and transverse cross hole are visible in the Right
# projection. Native model dimensions remain the sole printed size authority.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0
PROFILE_CENTER = (0.185, 0.164)
ISO_CENTER = (0.355, 0.205)
ISO_SCALE = (2, 1)
ISO_NOTE_XY = (0.325, 0.252)
# The native four-row note is 107.7045 mm wide. Keep its whole extent clear
# of the right border, bearing-fit text and 66 mm title-block keep-out.
STOP_FACE_NOTE_XY = (0.302, 0.096)
INSPECTION_NOTE_CHAR_HEIGHT = 0.0035
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
    "UpperBossHeight": (0.125, 0.211),
    "PinLength": (_span_mid(0.0), ROW_Y[2]),
    "TopChamfer": (0.050, CHAMFER_Y),
    "BottomChamfer": (0.310, 0.130),
    "BearingDia": (_x(BEARING_LENGTH / 2.0), 0.104),
    "CarrierDia": (_x(OVERALL_LENGTH) + 0.004, 0.082),
    "CollarDia": (_x(CARRIER_STATION - 5.0), 0.127),
    "FlangeDia": (_x(part_spec.FLANGE_BOTTOM_STATION + part_spec.FLANGE_THICK / 2.0), 0.079),
    "FlangeThick": (0.249, 0.224),
    "LowerBossHeight": (0.245, 0.202),
    "CarrierFilletR": (_x(CARRIER_STATION) - 0.012, 0.137),
    "SeatFilletR": (_x(COLLAR_STATION) + 0.012, 0.137),
    "CrossHoleDia": (0.050, 0.230),
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

for _stop_name, _normal, _station in (
    ("flange_lower_stop", (0.0, 0.0, -1.0), part_spec.FLANGE_BOTTOM_STATION),
    ("flange_upper_stop", (0.0, 0.0, 1.0), part_spec.FLANGE_TOP_STATION),
):
    requirement(
        _stop_name,
        kind="face",
        faces=(PlanarFace(_normal, _normal[2] * _station),),
        requirements=("note",),
        fields={
            "normal": (list(_normal), ("__frame__",)),
            "plane": (
                {"frame": "model", "axis": "z", "value": _station},
                ("FLANGE_BOTTOM_STATION", "FLANGE_TOP_STATION"),
            ),
            "note": (
                " ".join(part_spec.STOP_FACE_INSPECTION_NOTE.splitlines()),
                (
                    "STOP_FACE_INSPECTION_NOTE",
                    "STOP_FACE_VARIATION_MAX",
                    "STOP_FACE_MEASUREMENT_DIAMETER",
                ),
            ),
        },
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
        "Stop Face Inspection",
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
    add_property_linked_note(
        adapter,
        "Stop Face Inspection",
        *STOP_FACE_NOTE_XY,
        char_height=INSPECTION_NOTE_CHAR_HEIGHT,
    )

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
