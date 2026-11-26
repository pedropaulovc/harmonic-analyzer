r"""Create the crankshaft MHA-DT-11 manufacturing drawing under drawing-guidelines.md.

The SLDPRT remains authoritative.  A shaft carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the three running/seat diameters keep
their native size bands, the journal keeps one bearing-surface finish, and
every length is an ordinary model dimension at its part-authored places.

The model's shaft axis runs along +Y from the dome root (local y=0, the plane
where MHA-DT-06 and MHA-DT-31 finish flush).  The single longitudinal view is the
``*Right`` orientation rotated a quarter turn in the sheet so the shaft lies
horizontal, as it sits in the lathe: dome on the left, far end on the right,
the MHA-DT-09 cross-hole seen as a true circle.  The crank-end view is the
``*Bottom`` orientation, which is exactly the third-angle LEFT view of that
rotated profile, so it sits on the profile's axis to its left at sheet scale.
It looks onto the seat spigot's face, so the two drive-pin holes show there
as true circles and are located and called out in that view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crankshaft.py dt-crankshaft
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any, Callable, Sequence

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    _SW_PREF_UNITS_LINEAR,
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
    visible_component_entities,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import place_callout_clear
from _drawing_attachment import _assert_attached_to
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_selection import _select_view_entity
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_face_read import face_geometry
from _gtol_planar import PlanarFace
from _gtol_sphere import SphereFace
from _printed_limits import drilled_limits, limits
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from build_dt_crankshaft import PINION_PIN_DIA, PINION_PIN_STATION_Y
from dt_crank_drive_gear_spec import inch_text
from dt_crankshaft_notes import (
    CENTRE_STUB_NOTE,
    CENTRES_NOTE,
    CROSS_HOLE_NOTE,
    FIT_CLEARANCES,
    SPIGOT_NOTE,
    COLLAR_REAR_MATE,
    COLLAR_SEAT_MATE,
    CROSS_HOLE_CALLOUT,
    DRIVE_PIN_CALLOUT,
    DRIVE_PIN_DEPTH_BAND,
    FIDUCIAL_NOTE,
    FIT_CALLOUT,
    JOURNAL_FIT,
    KNOCKOUT_CALLOUT_ABOVE,
    KNOCKOUT_CALLOUT_BELOW,
    NECKS,
    PINION_PIN_CALLOUT,
    SHAFT_LENGTH_MATE,
    SHEET_NOTES,
    SLIDING_FIT,
    SPIGOT_CALLOUT,
)
from dt_crankshaft_spec import (
    COLLAR_STATION_TOL,
    DRIVE_PIN_DEPTH,
    DRIVE_PIN_DEPTH_TOL,
    DRIVE_PIN_HOLE_BAND,
    DRIVE_PIN_KNOCKOUT_LENGTH,
    DRIVE_PIN_KNOCKOUT_PROCESS,
    DRIVE_PIN_KNOCKOUT_RIM_WORST,
    DRIVE_PIN_OFFSET_TOL,
    DRIVE_PIN_SPIGOT_RIM_WORST,
    NECK_DIA_TOL,
    RELIEF_DIA,
    SHAFT_LENGTH_BAND,
    SPIGOT_DIA_BAND,
    UNIT,
)
from dt_crankshaft_spec import (
    COLLAR_REAR,
    CROSS_HOLE_PROCESS,
    DIAMETER_REFERENCES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRIVE_PIN_CIRCLE_RADIUS,
    DRIVE_PIN_FLOOR,
    DRIVE_PIN_HOLE_DIA,
    DRIVE_PIN_HOLE_PROCESS,
    DRIVE_PIN_KNOCKOUT_DIA,
    FIDUCIAL_MODEL_DIA,
    HOLE_CALLOUT_PLACES,
    JOURNAL_DIA,
    JOURNAL_END,
    JOURNAL_START,
    PIN_HOLE_HEIGHT,
    PIN_HOLE_SPEC,
    PINION_SEAT_DIA,
    REFERENCE_DIMENSIONS,
    RELIEF_END,
    RELIEF_START,
    SEAT_COLLAR,
    SEAT_STEP,
    SHAFT_DIA,
    SHAFT_DOME_HEIGHT,
    SHAFT_LENGTH,
    SPHERICAL_DIMENSIONS,
    SPIGOT_DIA,
    SURFACE_FINISHES,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["dt_crankshaft"]
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
_PIN_HOLE_DIA = blind_cut_dia_mm(PIN_HOLE_SPEC)

# Feature requirements (package:features; the drilled_block adapter's kinds),
# in the model frame: the shaft axis along +Y from the dome root (y 0), every
# printed station from the FAR END (y = SHAFT_LENGTH), the one faced end the
# shop zeroes on; the drive-pin holes along +Y into the collar's seat face at
# z = +/-DRIVE_PIN_CIRCLE_RADIUS; the #9 cross hole along model X.  The
# declarations print nothing; each band is the one the sheet prints
# (DRAWING_PRECISION_BY_NAME places, the title block's rows, each
# dimension's own band).
_P = DRAWING_PRECISION_BY_NAME
_NOTES = "dt_crankshaft_notes"
_FRAME = ("build_dt_crankshaft", "__frame__")
_FAR = ("SHAFT_LENGTH",)
_PRINT = ("UNIT", "DRAWING_PRECISION_BY_NAME")
_FIT = ((_NOTES, "FIT_CLEARANCES"), (_NOTES, "FIT_NOTE"))
_HUB = "dt_crank_hub_geometry"
_SD = (_HUB, "SHAFT_DIA")


def _cap_radius(height: float) -> float:
    """The sphere a cap ``height`` high on the Ø.375 lies on."""
    return ((SHAFT_DIA / 2.0) ** 2 + height**2) / (2.0 * height)


_DOME_HEIGHT_LIMITS = limits(SHAFT_DOME_HEIGHT, _P["DomeHeight"], unit=UNIT)
_DOME_R = _cap_radius(SHAFT_DOME_HEIGHT)


def _plane_y(value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": "y", "value": value}


def _far_station(
    y: float, name: str, band: tuple[float, float] | None = None
) -> list[float]:
    """Model y's station from the far end, limited at ``name``'s places."""
    return limits(SHAFT_LENGTH - y, _P[name], band, unit=UNIT)


def _drive_pin_fields(z: float) -> dict[str, Any]:
    """One reamed drive-pin hole, blind from the seat face at model ``z``."""
    return {
        "at": ([0.0, SEAT_COLLAR, z], ("SEAT_COLLAR", "DRIVE_PIN_CIRCLE_RADIUS")),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(DRIVE_PIN_HOLE_DIA, HOLE_CALLOUT_PLACES, DRIVE_PIN_HOLE_BAND, unit=UNIT),
            ("DRIVE_PIN_HOLE_DIA", "DRIVE_PIN_HOLE_BAND", "HOLE_CALLOUT_PLACES"),
        ),
        "nominal_dia": (DRIVE_PIN_HOLE_DIA, ("DRIVE_PIN_HOLE_DIA",)),
        "process": ("ream", ("DRIVE_PIN_HOLE_PROCESS",)),
        "depth": (
            limits(
                DRIVE_PIN_DEPTH,
                HOLE_CALLOUT_PLACES,
                (DRIVE_PIN_DEPTH_TOL, -DRIVE_PIN_DEPTH_TOL),
                unit=UNIT,
            ),
            ("DRIVE_PIN_DEPTH", "DRIVE_PIN_DEPTH_TOL", "HOLE_CALLOUT_PLACES"),
        ),
        "depth_nominal": (DRIVE_PIN_DEPTH, ("DRIVE_PIN_DEPTH",)),
        "offset": (
            limits(
                DRIVE_PIN_CIRCLE_RADIUS,
                _P["DrivePinOffset1"],
                (DRIVE_PIN_OFFSET_TOL, -DRIVE_PIN_OFFSET_TOL),
                unit=UNIT,
            ),
            ("DRIVE_PIN_CIRCLE_RADIUS", "DRIVE_PIN_OFFSET_TOL", *_PRINT),
        ),
        "offset_nominal": (DRIVE_PIN_CIRCLE_RADIUS, ("DRIVE_PIN_CIRCLE_RADIUS",)),
        "offset_from": ("hub_shaft", ("DRIVE_PIN_CIRCLE_RADIUS",)),
        "offset_axis": ("z", (_FRAME,)),
        "callout": (DRIVE_PIN_CALLOUT, ((_NOTES, "DRIVE_PIN_CALLOUT"),)),
        "rim_min": (DRIVE_PIN_SPIGOT_RIM_WORST, ("DRIVE_PIN_SPIGOT_RIM_WORST",)),
    }


def _knockout_fields(z: float) -> dict[str, Any]:
    """One #54 knockout, from its drive-pin hole's floor through the rear face."""
    return {
        "at": ([0.0, DRIVE_PIN_FLOOR, z], ("DRIVE_PIN_FLOOR", "DRIVE_PIN_CIRCLE_RADIUS")),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (
            drilled_limits(DRIVE_PIN_KNOCKOUT_DIA, 3, unit=UNIT),
            ("DRIVE_PIN_KNOCKOUT_DIA", "UNIT"),
        ),
        "nominal_dia": (DRIVE_PIN_KNOCKOUT_DIA, ("DRIVE_PIN_KNOCKOUT_DIA",)),
        "process": ("drill", ("DRIVE_PIN_KNOCKOUT_PROCESS",)),
        "drill": (DRIVE_PIN_KNOCKOUT_PROCESS, ("DRIVE_PIN_KNOCKOUT_PROCESS",)),
        "length_nominal": (DRIVE_PIN_KNOCKOUT_LENGTH, ("DRIVE_PIN_KNOCKOUT_LENGTH",)),
        "thru_to": ("collar_rear", ("DRIVE_PIN_KNOCKOUT_LENGTH",)),
        "callout": (
            f"{KNOCKOUT_CALLOUT_ABOVE}\n{KNOCKOUT_CALLOUT_BELOW}",
            ((_NOTES, "KNOCKOUT_CALLOUT_ABOVE"), (_NOTES, "KNOCKOUT_CALLOUT_BELOW")),
        ),
        "wall_min": (DRIVE_PIN_KNOCKOUT_RIM_WORST, ("DRIVE_PIN_KNOCKOUT_RIM_WORST",)),
    }


part_metadata(
    model_sources=(_FRAME, "SHAFT_LENGTH", _SD, "SHAFT_DOME_HEIGHT"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)
requirement(
    "far_end",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), SHAFT_LENGTH),),
    requirements=("plane", "length"),
    fields={
        "plane": (_plane_y(SHAFT_LENGTH), _FAR),
        "outward": ([0.0, 1.0, 0.0], (_FRAME,)),
        # Depth: the far end to the dome root, +.000/-.016, which sets the
        # MHA-DT-31 to MHA-PD-09 clearance.
        "length": (
            limits(SHAFT_LENGTH, _P["Depth"], SHAFT_LENGTH_BAND, unit=UNIT),
            ("SHAFT_LENGTH", "SHAFT_LENGTH_BAND", *_PRINT),
        ),
        "length_nominal": (SHAFT_LENGTH, _FAR),
        "length_callout": (SHAFT_LENGTH_MATE.strip(), ((_NOTES, "SHAFT_LENGTH_MATE"),)),
        "centres_note": (CENTRES_NOTE, ((_NOTES, "CENTRES_NOTE"),)),
    },
    precision={"length": _P["Depth"]},
)
# The dome end: a spherical cap DomeHeight high on the Ø.375, its radius the
# one the printed height band gives (the SR prints as a reference), and the
# (5.14) overall a reference too.  Note 4: no centre in the finished dome.
requirement(
    "dome",
    kind="arc",
    faces=(SphereFace(2.0 * _DOME_R, (0.0, _DOME_R - SHAFT_DOME_HEIGHT, 0.0)),),
    requirements=("height", "radius"),
    fields={
        "center": ([0.0, _DOME_R - SHAFT_DOME_HEIGHT, 0.0], (_SD, "SHAFT_DOME_HEIGHT")),
        "axis": ([1.0, 0.0, 0.0], (_FRAME,)),
        "apex": ([0.0, -1.0, 0.0], (_FRAME,)),
        "radius": (
            [_cap_radius(_DOME_HEIGHT_LIMITS[1]), _cap_radius(_DOME_HEIGHT_LIMITS[0])],
            (_SD, "SHAFT_DOME_HEIGHT", *_PRINT),
        ),
        "radius_nominal": (_DOME_R, (_SD, "SHAFT_DOME_HEIGHT")),
        "height": (_DOME_HEIGHT_LIMITS, ("SHAFT_DOME_HEIGHT", *_PRINT)),
        "height_nominal": (SHAFT_DOME_HEIGHT, ("SHAFT_DOME_HEIGHT",)),
        "overall_ref": (
            SHAFT_LENGTH + SHAFT_DOME_HEIGHT,
            ("SHAFT_LENGTH", "SHAFT_DOME_HEIGHT"),
        ),
        "centre_note": (CENTRE_STUB_NOTE, ((_NOTES, "CENTRE_STUB_NOTE"),)),
    },
    precision={"height": _P["DomeHeight"], "radius": _P["DomeSphereRadius"]},
)
# The (Ø.3750) sliding fit in the MHA-DT-31 crank hub, from the dome root to
# the collar's seat face: a REF turned to the hub's measured bore, note 3's
# clearance the requirement (drawing-guidelines rule 4, form 2).
requirement(
    "hub_shaft",
    kind="outside_cylinder",
    faces=(CylinderFace(SHAFT_DIA, contains_y_mm=SEAT_COLLAR / 2.0),),
    requirements=("dia_ref", "diametral_clearance"),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia_ref": (SHAFT_DIA, (_SD, "REFERENCE_DIMENSIONS", *_PRINT)),
        "length_nominal": (SEAT_COLLAR, ("SEAT_COLLAR",)),
        "mates": ("MHA-DT-31", _FIT),
        "diametral_clearance": (list(FIT_CLEARANCES["MHA-DT-31"]), _FIT),
    },
    precision={"dia_ref": _P["ShaftDiaDim"]},
)
# The Ø.689 seat spigot (note 2): its seat face (dome side, where the drive
# pins enter) and its rear face (Ra 63, bears on MHA-DT-05), each a .XXX
# station from the far end.
requirement(
    "spigot",
    kind="outside_cylinder",
    faces=(CylinderFace(SPIGOT_DIA),),
    requirements=("dia",),
    fields={
        "at": ([0.0, SEAT_COLLAR, 0.0], ("SEAT_COLLAR",)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(SPIGOT_DIA, _P["SpigotDiaDim"], SPIGOT_DIA_BAND, unit=UNIT),
            ("SPIGOT_DIA", "SPIGOT_DIA_BAND", *_PRINT),
        ),
        "nominal_dia": (SPIGOT_DIA, ("SPIGOT_DIA",)),
        "length_nominal": (COLLAR_REAR - SEAT_COLLAR, ("COLLAR_REAR", "SEAT_COLLAR")),
        "note": (SPIGOT_NOTE, ((_NOTES, "SPIGOT_NOTE"),)),
    },
    precision={"dia": _P["SpigotDiaDim"]},
)
requirement(
    "collar_seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), -SEAT_COLLAR),),
    requirements=("plane", "station"),
    fields={
        "plane": (_plane_y(SEAT_COLLAR), ("SEAT_COLLAR",)),
        "outward": ([0.0, -1.0, 0.0], (_FRAME,)),
        "station": (
            _far_station(SEAT_COLLAR, "CollarSeatStation"),
            ("SEAT_COLLAR", *_FAR, *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - SEAT_COLLAR, ("SEAT_COLLAR", *_FAR)),
        "station_from": ("far_end", _FAR),
    },
    precision={"station": _P["CollarSeatStation"]},
)
requirement(
    "collar_rear",
    kind="face",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face").face,),
    requirements=("plane", "station", "finish_ra"),
    fields={
        "plane": (_plane_y(COLLAR_REAR), ("COLLAR_REAR",)),
        "outward": ([0.0, 1.0, 0.0], (_FRAME,)),
        "station": (
            _far_station(
                COLLAR_REAR,
                "CollarRearStation",
                (COLLAR_STATION_TOL, -COLLAR_STATION_TOL),
            ),
            ("COLLAR_REAR", "COLLAR_STATION_TOL", *_FAR, *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - COLLAR_REAR, ("COLLAR_REAR", *_FAR)),
        "station_from": ("far_end", _FAR),
        "finish_ra": (
            surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face").roughness_um,
            ("SURFACE_FINISHES",),
        ),
    },
    precision={"station": _P["CollarRearStation"], "finish_ra": 1},
)
# The two Ø.375 +/-.010 necks either side of the journals.
requirement(
    "neck_outboard",
    kind="outside_cylinder",
    faces=(CylinderFace(SHAFT_DIA, contains_y_mm=(COLLAR_REAR + JOURNAL_START) / 2.0),),
    requirements=("dia",),
    fields={
        "at": ([0.0, COLLAR_REAR, 0.0], ("COLLAR_REAR",)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(SHAFT_DIA, _P["NeckDiaDim"], (NECK_DIA_TOL, -NECK_DIA_TOL), unit=UNIT),
            (_SD, "NECK_DIA_TOL", *_PRINT),
        ),
        "nominal_dia": (SHAFT_DIA, (_SD,)),
        "length_nominal": (JOURNAL_START - COLLAR_REAR, ("JOURNAL_START", "COLLAR_REAR")),
    },
    precision={"dia": _P["NeckDiaDim"]},
)
requirement(
    "neck_inboard",
    kind="outside_cylinder",
    faces=(CylinderFace(SHAFT_DIA, contains_y_mm=(JOURNAL_END + SEAT_STEP) / 2.0),),
    requirements=("dia",),
    fields={
        "at": ([0.0, JOURNAL_END, 0.0], ("JOURNAL_END",)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (
            limits(SHAFT_DIA, _P["NeckDiaDim"], (NECK_DIA_TOL, -NECK_DIA_TOL), unit=UNIT),
            (_SD, "NECK_DIA_TOL", *_PRINT),
        ),
        "nominal_dia": (SHAFT_DIA, (_SD,)),
        "length_nominal": (SEAT_STEP - JOURNAL_END, ("SEAT_STEP", "JOURNAL_END")),
    },
    precision={"dia": _P["NeckDiaDim"]},
)
# The 2X (Ø.4375) running fits in MHA-DT-05 (note 3, Ra 63), REFs turned to
# its measured crank bores: each end a .XX station from the far end,
# ``station`` the end nearer the far end.
requirement(
    "outboard_journal",
    kind="journal",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "outboard_journal").face,),
    requirements=("dia_ref", "diametral_clearance", "station", "end_station", "finish_ra"),
    fields={
        "at": ([0.0, RELIEF_START, 0.0], ("RELIEF_START",)),
        "axis": ([0.0, -1.0, 0.0], (_FRAME,)),
        "dia_ref": (JOURNAL_DIA, ("JOURNAL_DIA", "REFERENCE_DIMENSIONS", *_PRINT)),
        "station": (
            _far_station(RELIEF_START, "ReliefOutboardStation"),
            ("RELIEF_OUTBOARD_STATION", *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - RELIEF_START, ("RELIEF_OUTBOARD_STATION",)),
        "station_from": ("far_end", _FAR),
        "end_station": (
            _far_station(JOURNAL_START, "JournalOutboardStation"),
            ("JOURNAL_START", *_FAR, *_PRINT),
        ),
        "end_station_nominal": (SHAFT_LENGTH - JOURNAL_START, ("JOURNAL_START", *_FAR)),
        "finish_ra": (
            surface_finish_by_key(SURFACE_FINISHES, "outboard_journal").roughness_um,
            ("SURFACE_FINISHES",),
        ),
        "mates": ("MHA-DT-05", _FIT),
        "diametral_clearance": (list(FIT_CLEARANCES["MHA-DT-05"]), _FIT),
    },
    precision={
        "dia_ref": _P["JournalDiaDim"],
        "station": _P["ReliefOutboardStation"],
        "end_station": _P["JournalOutboardStation"],
        "finish_ra": 1,
    },
)
requirement(
    "inboard_journal",
    kind="journal",
    faces=(surface_finish_by_key(SURFACE_FINISHES, "inboard_journal").face,),
    requirements=("dia_ref", "diametral_clearance", "station", "end_station", "finish_ra"),
    fields={
        "at": ([0.0, JOURNAL_END, 0.0], ("JOURNAL_END",)),
        "axis": ([0.0, -1.0, 0.0], (_FRAME,)),
        "dia_ref": (JOURNAL_DIA, ("JOURNAL_DIA", "REFERENCE_DIMENSIONS", *_PRINT)),
        "station": (
            _far_station(JOURNAL_END, "JournalInboardStation"),
            ("JOURNAL_INBOARD_STATION", *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - JOURNAL_END, ("JOURNAL_INBOARD_STATION",)),
        "station_from": ("far_end", _FAR),
        "end_station": (
            _far_station(RELIEF_END, "ReliefInboardStation"),
            ("RELIEF_INBOARD_STATION", *_PRINT),
        ),
        "end_station_nominal": (SHAFT_LENGTH - RELIEF_END, ("RELIEF_INBOARD_STATION",)),
        "finish_ra": (
            surface_finish_by_key(SURFACE_FINISHES, "inboard_journal").roughness_um,
            ("SURFACE_FINISHES",),
        ),
        "mates": ("MHA-DT-05", _FIT),
        "diametral_clearance": (list(FIT_CLEARANCES["MHA-DT-05"]), _FIT),
    },
    precision={
        "dia_ref": _P["JournalDiaDim"],
        "station": _P["JournalInboardStation"],
        "end_station": _P["ReliefInboardStation"],
        "finish_ra": 1,
    },
)
requirement(
    "relief",
    kind="outside_cylinder",
    faces=(CylinderFace(RELIEF_DIA),),
    requirements=("dia",),
    fields={
        "at": ([0.0, RELIEF_START, 0.0], ("RELIEF_START",)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia": (limits(RELIEF_DIA, _P["ReliefDiaDim"], unit=UNIT), ("RELIEF_DIA", *_PRINT)),
        "nominal_dia": (RELIEF_DIA, ("RELIEF_DIA",)),
        "length_nominal": (RELIEF_END - RELIEF_START, ("RELIEF_END", "RELIEF_START")),
    },
    precision={"dia": _P["ReliefDiaDim"]},
)
# The (Ø.3125) sliding fit in the MHA-DT-10 pinion, from its step (a .XX
# station from the far end) to the far end: a REF turned to the pinion's
# measured bore, note 3's clearance the requirement.
requirement(
    "pinion_seat",
    kind="outside_cylinder",
    faces=(CylinderFace(PINION_SEAT_DIA),),
    requirements=("dia_ref", "diametral_clearance"),
    fields={
        "at": ([0.0, SEAT_STEP, 0.0], ("SEAT_STEP",)),
        "axis": ([0.0, 1.0, 0.0], (_FRAME,)),
        "dia_ref": (PINION_SEAT_DIA, ("PINION_SEAT_DIA", "REFERENCE_DIMENSIONS", *_PRINT)),
        "length_nominal": (SHAFT_LENGTH - SEAT_STEP, ("SEAT_STEP", *_FAR)),
        "mates": ("MHA-DT-10", _FIT),
        "diametral_clearance": (list(FIT_CLEARANCES["MHA-DT-10"]), _FIT),
        "match_ream_callout": (PINION_PIN_CALLOUT, ((_NOTES, "PINION_PIN_CALLOUT"),)),
    },
    precision={"dia_ref": _P["PinionSeatDiaDim"]},
)
requirement(
    "seat_step",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), SEAT_STEP),),
    requirements=("plane", "station"),
    fields={
        "plane": (_plane_y(SEAT_STEP), ("SEAT_STEP",)),
        "outward": ([0.0, 1.0, 0.0], (_FRAME,)),
        "station": (
            _far_station(SEAT_STEP, "PinionSeatStation"),
            ("PINION_SEAT_STATION", *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - SEAT_STEP, ("PINION_SEAT_STATION",)),
        "station_from": ("far_end", _FAR),
    },
    precision={"station": _P["PinionSeatStation"]},
)
# The #9 cross hole, drilled through along model X here; note 1 taper-reams
# it 1:48 at assembly with MHA-DT-31.
requirement(
    "cross_hole",
    kind="hole",
    faces=(CylinderFace(_PIN_HOLE_DIA),),
    requirements=("dia", "thru", "station"),
    fields={
        "at": ([-SHAFT_DIA / 2.0, PIN_HOLE_HEIGHT, 0.0], ("PIN_HOLE_HEIGHT", _SD)),
        "axis": ([1.0, 0.0, 0.0], (_FRAME,)),
        "dia": (drilled_limits(_PIN_HOLE_DIA, 3, unit=UNIT), ("PIN_HOLE_SPEC", "UNIT")),
        "nominal_dia": (_PIN_HOLE_DIA, ("PIN_HOLE_SPEC",)),
        "thru": (True, ("CROSS_HOLE_PROCESS",)),
        "process": ("drill", ("CROSS_HOLE_PROCESS",)),
        "drill": (CROSS_HOLE_PROCESS, ("CROSS_HOLE_PROCESS",)),
        "station": (
            _far_station(PIN_HOLE_HEIGHT, "PinHoleStation"),
            ("PIN_HOLE_HEIGHT", *_FAR, *_PRINT),
        ),
        "station_nominal": (SHAFT_LENGTH - PIN_HOLE_HEIGHT, ("PIN_HOLE_HEIGHT", *_FAR)),
        "station_from": ("far_end", _FAR),
        "note": (CROSS_HOLE_NOTE, ((_NOTES, "CROSS_HOLE_NOTE"),)),
    },
    precision={"dia": 3, "station": _P["PinHoleStation"]},
)
# The two reamed drive-pin holes (pressed MHA-DT-VN-67 pins for the MHA-PD-09
# sprocket), .2756 +/-.0009 either side of the axis along model Z, blind from
# the seat face; each #54 knockout runs on from its floor through the rear
# face.
requirement(
    "drive_pin_1",
    kind="hole",
    faces=(CylinderFace(DRIVE_PIN_HOLE_DIA, contains_z_mm=-DRIVE_PIN_CIRCLE_RADIUS),),
    requirements=("dia", "depth", "offset"),
    fields=_drive_pin_fields(-DRIVE_PIN_CIRCLE_RADIUS),
    precision={"dia": HOLE_CALLOUT_PLACES, "depth": HOLE_CALLOUT_PLACES, "offset": _P["DrivePinOffset1"]},
)
requirement(
    "drive_pin_2",
    kind="hole",
    faces=(CylinderFace(DRIVE_PIN_HOLE_DIA, contains_z_mm=DRIVE_PIN_CIRCLE_RADIUS),),
    requirements=("dia", "depth", "offset"),
    fields=_drive_pin_fields(DRIVE_PIN_CIRCLE_RADIUS),
    precision={"dia": HOLE_CALLOUT_PLACES, "depth": HOLE_CALLOUT_PLACES, "offset": _P["DrivePinOffset2"]},
)
requirement(
    "knockout_1",
    kind="knockout",
    faces=(CylinderFace(DRIVE_PIN_KNOCKOUT_DIA, contains_z_mm=-DRIVE_PIN_CIRCLE_RADIUS),),
    requirements=("dia",),
    fields=_knockout_fields(-DRIVE_PIN_CIRCLE_RADIUS),
    precision={"dia": 3},
)
requirement(
    "knockout_2",
    kind="knockout",
    faces=(CylinderFace(DRIVE_PIN_KNOCKOUT_DIA, contains_z_mm=DRIVE_PIN_CIRCLE_RADIUS),),
    requirements=("dia",),
    fields=_knockout_fields(DRIVE_PIN_CIRCLE_RADIUS),
    precision={"dia": 3},
)
# The centre-punched witness mark on the seat face (location not critical).
requirement(
    "punch_mark",
    kind="mark",
    faces=(CylinderFace(FIDUCIAL_MODEL_DIA),),
    requirements=("note",),
    fields={"note": (FIDUCIAL_NOTE, ((_NOTES, "FIDUCIAL_NOTE"),))},
)

# Both orthographic views print at the sheet scale, so neither needs a caption.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The profile sits 18 mm right of the sheet's middle so the gap between the
# end view and the dome tip holds the drive-pin locations' text left of the
# dome's extension lines; the isometric moves 8 mm right to keep clear of it.
SIDE_CENTER = (0.228, 0.180)
# Third-angle left view of the dome end, on the profile's axis.
END_CENTER = (0.036, SIDE_CENTER[1])
ISO_CENTER = (0.398, SIDE_CENTER[1])
ISO_SCALE = (1, 1)
# The *Right view rotated -90 degrees: model +Y runs to paper-right.
SIDE_VIEW_ANGLE = -math.pi / 2.0

# The side view is centred on the model bbox, dome tip (-DomeHeight) through
# the far end (+ShaftLength).
_BBOX_MID_Y = (SHAFT_LENGTH - SHAFT_DOME_HEIGHT) / 2.0


def _sheet_x(model_y_mm: float) -> float:
    """Sheet X of a model-Y station on the horizontal side view."""
    return SIDE_CENTER[0] + (model_y_mm - _BBOX_MID_Y) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the shaft axis (model +Z up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


DOME_TIP_X = _sheet_x(-SHAFT_DOME_HEIGHT)
DOME_ROOT_X = _sheet_x(0.0)
PIN_X = _sheet_x(PIN_HOLE_HEIGHT)
JOURNAL_START_X = _sheet_x(JOURNAL_START)
JOURNAL_END_X = _sheet_x(JOURNAL_END)
RELIEF_START_X = _sheet_x(RELIEF_START)
RELIEF_END_X = _sheet_x(RELIEF_END)
SEAT_STEP_X = _sheet_x(SEAT_STEP)
COLLAR_SEAT_X = _sheet_x(SEAT_COLLAR)
COLLAR_REAR_X = _sheet_x(COLLAR_REAR)
FAR_END_X = _sheet_x(SHAFT_LENGTH)
JOURNAL_FLANK_Y = _sheet_y(JOURNAL_DIA / 2.0)

# Baseline rows below the profile, all from the FAR END and stacked
# shortest-first so no extension line crosses a dimension line.  The text
# sits ~3 mm above its requested point and the dimension line ~5 mm below
# it; the two seat-collar stations make ten rows between the collar's
# underside and the title block, so the pitch closes from 12 to 9.5 mm.  The
# 2.0 dome height stands over the first row at the far left, where no
# baseline reaches; the last row clears the title block.
_ROW_PITCH = 0.0095
_ROW_Y = tuple(round(0.162 - k * _ROW_PITCH, 4) for k in range(10))
# The six diameters are authored in end-profile sketches; the end view
# receives them first and they are then dragged onto the profile (drawing-guidelines.md rule 11 (turned parts read like the lathe):
# diameters on the side view).  Their temporary end-view spots are clear of
# everything else on the sheet.
END_DIAMETERS = {
    "ShaftDiaDim": (0.036, 0.215),
    "JournalDiaDim": (0.036, 0.228),
    "ReliefDiaDim": (0.036, 0.241),
    "PinionSeatDiaDim": (0.036, 0.254),
    "SpigotDiaDim": (0.024, 0.241),
    "NeckDiaDim": (0.024, 0.228),
}
# The drive-pin holes' locations stay in the end view, the one view that
# shows them as true (visible) circles: each hole from the shaft axis, its
# dimension line just right of the view, text beyond the view's top (+Z hole)
# and bottom (-Z hole), in the gap before the dome's extension lines.  Each
# prints its value and band only (drawing-guidelines.md rule 7); the mate the
# band serves is named on the holes' REAM callout.
END_PIN_KEEP = {
    "DrivePinOffset1": (0.058, 0.210),
    "DrivePinOffset2": (0.058, 0.145),
}
END_KEEP = {**END_DIAMETERS, **END_PIN_KEEP}
SIDE_KEEP = {
    # Below the dome, 6 mm over the lower 7.000's text (machinist review of
    # 5a219a81904f: on the first row the 2.0 read as stacked on the 7.000).
    "DomeHeight": (DOME_TIP_X - 0.016, 0.168),
    "PinionSeatStation": ((SEAT_STEP_X + FAR_END_X) / 2.0, _ROW_Y[0]),
    "JournalInboardStation": ((JOURNAL_END_X + FAR_END_X) / 2.0, _ROW_Y[1]),
    "ReliefInboardStation": ((RELIEF_END_X + FAR_END_X) / 2.0, _ROW_Y[2]),
    "ReliefOutboardStation": ((RELIEF_START_X + FAR_END_X) / 2.0, _ROW_Y[3]),
    "JournalOutboardStation": ((JOURNAL_START_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[4]),
    "CollarRearStation": ((COLLAR_REAR_X + FAR_END_X) / 2.0, _ROW_Y[5]),
    "CollarSeatStation": ((COLLAR_SEAT_X + FAR_END_X) / 2.0 - 0.020, _ROW_Y[6]),
    "PinHoleStation": ((PIN_X + FAR_END_X) / 2.0, _ROW_Y[7]),
    # The shaft length's native unilateral block sits right of the reference
    # overall on the next row down, not over it; its stack suffix widens it
    # left, so the overall's text stands left of that (layout audit of
    # 902433a8d: 1.3 mm text clearance; round 2: the longer CLEARANCE suffix
    # left 1.34 mm to the (5.37), so the block stands 3 mm further right).
    "Depth": ((DOME_ROOT_X + FAR_END_X) / 2.0 + 0.038, _ROW_Y[8]),
    "OverallLength": ((DOME_TIP_X + FAR_END_X) / 2.0 - 0.030, _ROW_Y[9]),
    # Above the dome, between the +Z drive-pin location's text and the
    # Ø9.525 dimension: the radial leader runs down, right of the one and
    # left of the other, to the dome's sphere.
    "DomeSphereRadius": (DOME_TIP_X - 0.005, 0.230),
}
# The 16T pin cross-hole's size prints in its own callout, a REF Ø on the
# size line (PINION_PIN_CALLOUT): the model's REF witness PinionPinHoleDia
# stood its extension lines on the hole's dashed edges at the seat's top
# silhouette (drawing-guidelines.md rule 9: never dimension to a hidden line),
# so the side view's import deletes it.
UNPRINTED_DIMENSIONS = frozenset({"PinionPinHoleDia"})
# A dragged diameter prints its dimension line at the requested X with the
# text running to its RIGHT (run 20260923T030252135Z-49e46990).  Its
# extension lines run parallel to the axis from the profile SKETCH that owns
# it, so each must sit on the section that sketch starts: the Ø9.525 circle
# lies at the dome root, and placed on the far-end seat its extension lines
# drew solid through the journal (run 20260923T031747843Z-94724e44).
# The Ø9.525 sits on the core LEFT of the cross-hole, so its lines stop short
# of the hole the callout's leader leaves (leader-crosses-line, af13c8ff8);
# the Ø9.0 seat's sits on the seat, left of the pinion pin hole.
# Each banded diameter is a four-row block (fit / upper limit / value /
# mate) whose left edge stands on its dimension line and whose landing line
# runs under its widest row; each request is the block's centre.  The
# cross-hole callout's leader climbs from the hole at ~1.45 (dy/dx) to its
# block (HOLE_CALLOUT_XY): left of it the Ø9.525's block lands 3.5 mm clear
# of it, right of it the Ø17.50's block tops out 6 mm under it (machinist
# review of b5c02e5d6: the leader crossed the Ø9.525's landing line).  The
# Ø11.388 stands 4 mm right of the Ø17.50's block (layout audit of
# 902433a8d: 2.3 mm read as one callout), its landing line 2 mm over the
# outboard journal's finish symbol and its fit row 7 mm under the cross-hole
# callout's landing line; the relief's Ø10.4 stands right of it.
# The inch sliding band (0/-0.02032) widened the Ø9.525's block 6 mm to the
# right, onto the leader, so the block stands 4 mm higher, where the leader
# has climbed 2.8 mm past its landing line's end (machinist review, #290
# batch 0).
# The one model witness NeckDiaDim prints the core's Ø.375 ±.010 as 2X over
# the Ø9.000's block, the count naming both bare necks (no prose locator:
# round-3 machinist review): the collar-side land is 2.7 mm on the sheet,
# and its own 27 mm callout found no clear spot (farm run 10: on the collar,
# or across the outboard journal's leaders; a detail view cannot take the
# dragged diameter, draw_dt_cone_gear_shaft).
# The Ø9.000's line stays 2 mm past its step, clear of the retention-pin note.
DIAMETER_POSITIONS = {
    "ShaftDiaDim": (PIN_X - 0.016, 0.2235),
    # Its leader left of the journal finish symbol's V.
    "JournalDiaDim": (RELIEF_START_X - 0.0035, 0.224),
    "ReliefDiaDim": (RELIEF_START_X + 0.045, 0.212),
    # Raised 17 mm over the 16T pin cross-hole's REF Ø.
    "PinionSeatDiaDim": (SEAT_STEP_X + 0.002, 0.2295),
    "SpigotDiaDim": (COLLAR_SEAT_X + 0.0075, 0.2215),
    "NeckDiaDim": (JOURNAL_END_X + 0.0006, 0.230),
}
# Each fit diameter keeps its fit name above its value and links numbered
# note 3 (each mate, the matched-fit route and the clearance) under it, so
# each block stays as narrow as its value row: the #9 cross-hole's leader
# passes right of the Ø.3750's block and the 16T pin note's leader right of
# the Ø.3125's (farm round 1: the 116-mm route rows ran through both).  The
# bare necks carry their own loose diameter.  The 2X Ø.4375 names both
# bearing lands across the relief.  The spigot's diameter links
# note 2, the chain they clear.
CALLOUTS_ABOVE = {
    "ShaftDiaDim": SLIDING_FIT,
    "JournalDiaDim": JOURNAL_FIT,
    "PinionSeatDiaDim": SLIDING_FIT,
    "NeckDiaDim": NECKS,
}
# The drive-pin locations print their value and band only (drawing-guidelines.md
# rule 7): the sprocket they serve is named once, on the holes' REAM callout.
CALLOUTS_BELOW = {
    "OverallLength": "OVERALL",
    "ShaftDiaDim": FIT_CALLOUT,
    "JournalDiaDim": FIT_CALLOUT,
    "PinionSeatDiaDim": FIT_CALLOUT,
    "SpigotDiaDim": SPIGOT_CALLOUT,
}
# The Depth names its stack, and the three-place far-end collar stations
# link note 2, on their own row: a callout below would lift the value into
# the row above.
SUFFIXES = {
    "CollarRearStation": COLLAR_REAR_MATE,
    "CollarSeatStation": COLLAR_SEAT_MATE,
    "Depth": SHAFT_LENGTH_MATE,
}
# Both running lands carry separate part-owned finish symbols. The outboard
# symbol sits right of the Ø11.388 dimension line, its leader landing on the
# land just short of the relief shoulder; the inboard symbol retains its
# clear spot above the relief.  The collar's rear (boss) face takes its
# own symbol on that face's edge-on line ABOVE the axis, the symbol in the
# pocket over the outboard land under the spigot's Ø text: under the axis
# every way to that face crosses a station's extension line.
JOURNAL_FINISHES = {
    "outboard_journal": (
        (RELIEF_START_X - 0.0009, JOURNAL_FLANK_Y),
        # The V's tip over the land's right end: its left arm (2.1 mm) stays
        # right of the journal diameter's leader.
        (RELIEF_START_X - 0.0003, 0.203),
    ),
    "inboard_journal": (
        (RELIEF_END_X + 0.015, JOURNAL_FLANK_Y),
        (RELIEF_END_X + 0.012, 0.200),
    ),
}
# The landing on the rear (thrust) face's edge-on line, 0.8 mm (1.6 mm on the
# sheet) inside the collar's silhouette, so the head ends on that face and not
# on the corner it shares with the collar's OD (machinist review of e04fd60ab:
# a corner landing read as either surface).  The leader attaches to the
# planar face itself (_collar_rear_face): selected by its rim, SolidWorks
# lands a point on an edge-on circle at its projected extreme, the corner
# (run 20261001T051043622Z: requested y 0.1986, landed 0.2006).  The symbol
# stands under the spigot's Ø block, right of the face; its short leader
# falls 2.4 mm to the landing on the Ø.689 face (run
# 20261111T221902124Z: the head ends on the face, clear of both Ø blocks).
COLLAR_REAR_FINISH = (
    (COLLAR_REAR_X, _sheet_y(SPIGOT_DIA / 2.0 - 0.8)),
    (COLLAR_REAR_X + 0.0069, 0.1983),
)
# The drive-pin holes' native REAM callout (size and depth from the cut, the
# depth's band appended by _band_hole_depth)
# with the press prose under it on two long rows (four rows in all): its
# leader picks the upper hole's rim and the text sits above the end view and
# the dome, left of the cross-hole callout, inside the top border.  The text
# centres on this anchor, and the press row runs ~110 mm wide, so its left end
# printed 3 mm past the inner border (run 15 and 06a20f94c): the callout is
# moved from its read-back box to clear the zone frame, and the placement is
# asserted (place_callout_clear).
DRIVE_PIN_CALLOUT_XY = (0.066, 0.250)
# Text centred up-right of the cross-hole: the callout's leader leaves the
# text's left end and runs down-left at ~55 deg to the hole, a clean
# crossing of the 122.7 station's extension line rather than a near
# parallel one (run 20260923T030252135Z-49e46990).  Its drill row and its
# SEE NOTE 1 row centre on y 0.251; its left end sets the leader's slope that
# the diameter blocks under it are laid out around (DIAMETER_POSITIONS).
HOLE_CALLOUT_XY = (PIN_X + 0.077, 0.251)
# The Hole Wizard drills' (#9 cross-hole, #54 knockouts) native size prints
# the title block's .XXX on the inch sheet.
WIZARD_CALLOUT_PRECISION = {"hw-diam": 3}
# The knockouts' native callout (drill above, size, purpose below; ~44 mm
# wide) centres under the end view, below the lower drive-pin location's
# text and left of the dome's extension line (x 0.0897).
# Its leader leaves the text's left end up-left to the lower hole's floor.
KNOCKOUT_CALLOUT_XY = (0.064, 0.115)
# The punch-mark note's two rows (~53 mm) sit, anchored upper-left, below the
# knockout callout (its last row at y ~0.107) and left of the dome's extension
# line (x 0.0897).  The mark lies left of the text's middle, so the leader
# leaves the text's left end and rises steeply to the mark at about 225 deg on
# the dome: clear of its own first row, and left of the knockout callout's
# leader (x 0.036-0.038) all the way up.  #1679 (owner ruling 2026-11-13):
# the knockout callout gained its WALL row, and SolidWorks centres the block
# on its point, so its last row stands half a row (2.7 mm) lower; the note
# drops 3 mm with it.
FIDUCIAL_NOTE_XY = (0.022, 0.097)
# The 16T retention-pin hole is match-drilled through the seated pinion's
# radial hole at assembly; its callout (dt_crankshaft_notes.PINION_PIN_CALLOUT)
# gives the REF size, the operation, the pinion hole that locates it and the
# pin's fit.  A bare transfer note gave the shaft's machinist none of these
# (machinist review of 4d4e038e3).  The note is attached to the hole's own visible rim edge: a radial hole in a
# round shaft has a saddle rim, not a circle, so a native Hole Wizard
# callout cannot bind to it (run1-61671871a).  Its TEXT sits, anchored
# upper-left, in the free field above the far-end seat, right of the cross-hole
# callout's text (which spans ~30 mm right of its centre) and left of the
# isometric; it is placed from its own measured box.
# Its leader must end on the hole, which the side view shows straddling the
# axis -- below the field's floor -- so the leader is held to the hole's
# window instead (run1b-e7fd1a2ec: the leader tip, not the text, read 0.3 mm
# under the floor).
PINION_PIN_X = _sheet_x(PINION_PIN_STATION_Y)
# The leader lands on the right of the rim (layout audit of bb0779352:
# landed lower-left, it crossed the then REF Ø's right extension line).  The
# rim edge this picks is the saddle's far lobe, not the outline circle;
# SolidWorks snapped a landing at the circle's right extreme to (+2.0, +0.55)
# mm from the hole's station on the axis (run 20261101T171554477Z-3604067c),
# so it lands there.
PINION_PIN_LEADER_LANDING = (PINION_PIN_X + 0.0020, SIDE_CENTER[1] + 0.00055)
# High in its field (top row ~4.5 mm under the border), so the right neck's
# Ø.375 and the Ø.3125's block stand under it.  Its last (longest, ~125 mm)
# row ends near x 0.370, where the leader starts (round 2: the leader leaves
# the end of the last row), so the leader drops right of the Ø.3125's block
# (ends x 0.3526) and left of the isometric (starts x 0.3779).  The text's
# left end stays right of the #9 cross-hole callout's text (ends x 0.2282).
PINION_PIN_NOTE_XY = (0.2455, 0.264)
PINION_PIN_NOTE_FIELD = (
    HOLE_CALLOUT_XY[0] + 0.032,
    SIDE_CENTER[1],
    ISO_CENTER[0] - 0.012,
    0.2657,  # 1 mm inside the ASME B inner border
)
# Every point of the rim lies within the hole's half-width (plus 0.5 mm of
# pick slack) of its station and inside the shaft's silhouette.
PINION_PIN_HOLE_WINDOW = (
    PINION_PIN_X - (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(-PINION_SEAT_DIA / 2.0),
    PINION_PIN_X + (PINION_PIN_DIA / 2.0 + 0.5) * _S / 1000.0,
    _sheet_y(PINION_SEAT_DIA / 2.0),
)
NOTE_FIELD_MARGIN = 0.001
NOTES_XY = (0.016, 0.062)
# The numbered notes, under the general note's one line with 3.6 mm of air
# (round 2 text-separation: 2.4 mm read as one block), left of the title
# block.
SHEET_NOTES_XY = (NOTES_XY[0], NOTES_XY[1] - 0.0075)
# The plain Ø9.000 end is the right-hand edge of FRONT (the horizontal
# ``side`` view), not the top end of the pictorial. Pick its lower half so
# the centre permission's leader stays away from MATCH DRILL above the axis.
FAR_END_FRONT_RIM_PICK = (
    FAR_END_X,
    _sheet_y(-PINION_SEAT_DIA / 4.0),
)
FAR_END_FRONT_RIM_WINDOW = (
    FAR_END_FRONT_RIM_PICK[0] - 0.0005,
    FAR_END_FRONT_RIM_PICK[1] - 0.0005,
    FAR_END_FRONT_RIM_PICK[0] + 0.0005,
    FAR_END_FRONT_RIM_PICK[1] + 0.0005,
)
# The two-row note sits well below the isometric caption, so it does not
# read as part of it, above the title block. Its leader rises in the corridor
# RIGHT of the FRONT station witnesses and LEFT of the pictorial/caption,
# directly to the plain end.
CENTRES_NOTE_XY = (0.370, 0.085)
NOTE_TEXT_GAP = 0.0035  # one 3.5 mm note-text height
ISO_NOTE_XY = (0.376, 0.108)


def _set_callout_text(display: Any, which: int, text: str, label: str) -> None:
    """Put prose ABOVE (``which`` 3) or UNDER (4) a native hole callout.

    The drill size reads first, in the order the work is done; the fit and
    mate prose follows in the callout-below compartment (the Ø9.550 bore
    callout's order).  ``SetText`` reports nothing, so it is read back.
    """
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(which, text)  # swDimensionTextCalloutAbove/Below
    applied = str(display.GetText(which) or "")
    if applied.replace("\r", "") != text:
        raise RuntimeError(f"{label}: callout text {which} did not persist: {applied!r}")


def _set_dimension_suffixes(
    adapter: Any, annotations: list[Any], suffixes: dict[str, str]
) -> None:
    """Append each named dimension's mate to its value on the same line.

    ``SetText`` reports nothing, so each suffix is read back.
    """
    remaining = dict(suffixes)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(2, text)  # swDimensionTextSuffix
        applied = str(display.GetText(2) or "")
        if applied.replace("\r", "") != text:
            raise RuntimeError(f"{name}: suffix did not persist: {applied!r}")
    if remaining:
        raise RuntimeError(f"dimension suffixes not applied: {sorted(remaining)}")


# Format-definition parts of a display dimension and the writable part each
# one is set through (swDimensionTextParts_e): prefix, suffix, callout above,
# callout below.
_DEFINITION_TO_WRITABLE = {5: 1, 6: 2, 7: 3, 8: 4}


def _depth_banded_definition(
    definitions: dict[int, str], band: str, process: str
) -> tuple[int, str]:
    """The one format part ending on the callout's depth: ``process`` before
    the depth, ``band`` after it.

    A native hole callout splits its text across the prefix, suffix and
    callout compartments; on the farm the drive-pin callout's prefix read
    ``2X <MOD-DIAM>`` and its depth sat in another part (run
    20261001T011714683Z).  Exactly one part may carry ``<HOLE-DEPTH>``, once,
    followed by the depth alone; anything else (no depth, two, text after it,
    a band or the process already there) fails loud.  Rule 26 orders a hole
    callout size, process, depth (``2X Ø.0930 +.0005/.0000 REAM ↧ .1555``;
    round-3 machinist review: REAM before the size), so the process joins the
    depth's part, after the native size and its band (draw_dt_cone_swing_
    platform.process_after_size, the same order before THRU).
    """
    if set(definitions) != set(_DEFINITION_TO_WRITABLE):
        raise RuntimeError(f"unexpected hole callout parts: {definitions!r}")
    holders = [part for part, text in definitions.items() if "<HOLE-DEPTH>" in text]
    joined = "\n".join(definitions.values())
    if len(holders) != 1 or band in joined or re.search(rf"\b{re.escape(process)}\b", joined):
        raise RuntimeError(f"hole callout has no single closing depth: {definitions!r}")
    part = holders[0]
    definition = definitions[part]
    head, _marker, tail = definition.rpartition("<HOLE-DEPTH>")
    if "<HOLE-DEPTH>" in head or len(tail.split()) != 1:
        raise RuntimeError(f"hole callout has no single closing depth: {definitions!r}")
    # The leading space keeps the process off the native size's stacked band
    # when the depth opens its own part.
    return part, f"{head.rstrip()} {process} <HOLE-DEPTH>{tail.rstrip()} {band}"


def _drop_coaxial_step(display: Any, step_dia: float, label: str) -> None:
    """Clear the coaxial hole's step SolidWorks folds into a native callout.

    Each pin hole and its knockout meet end to end, so a callout on either
    reads the pair as one stepped hole: on the farm the drive-pin callout
    carried ``<MOD-DIAM>1.40<HOLE-DEPTH>12.63`` in its callout-above part (run
    20261018T110810560Z-720787ec).  Each hole has its own callout naming its
    process, so the other's step is cleared.  Only a part holding nothing but
    that step is cleared; the step anywhere else fails loud.  The stepped
    reading also put a bare counterbore symbol (``<HOLE-SPOT>``) before the
    size (machinist review of b5c02e5d6), so it goes with the step.  Read
    back.
    """
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    holders = [
        part for part, text in definitions.items() if _has_coaxial_step(text, step_dia)
    ]
    for part in holders:
        if not _has_coaxial_step(definitions[part], step_dia, leading=True):
            raise RuntimeError(f"{label}: coaxial step mixed into part {part}: {definitions!r}")
        display.SetText(_DEFINITION_TO_WRITABLE[part], "")
        if str(display.GetText(part) or ""):
            raise RuntimeError(f"{label}: coaxial step in part {part} did not clear")
    if not holders:
        return
    prefix = definitions[5]
    if "<HOLE-SPOT>" in prefix:
        bare = prefix.replace("<HOLE-SPOT>", "")
        display.SetText(_DEFINITION_TO_WRITABLE[5], bare)
        applied = str(display.GetText(5) or "")
        if applied.replace("\r", "") != bare:
            raise RuntimeError(f"{label}: counterbore symbol did not clear: {applied!r}")
    _telemetry.info(f"{label}: cleared coaxial step from parts {holders}: {definitions!r}")


# swLengthUnit_e.swINCHES: the unit ``set_units_inch`` writes.
_SW_LENGTH_INCHES = 3
# Every step SolidWorks folds into a callout prints as ``<MOD-DIAM>`` and a
# decimal at the sheet's places.
_STEP_SIZE = re.compile(r"<MOD-DIAM>(\d*\.\d+)")


def _has_coaxial_step(text: str, step_dia: float, *, leading: bool = False) -> bool:
    """Whether ``text`` prints ``step_dia`` (mm) as an inch ``<MOD-DIAM>``
    size -- anywhere, or (``leading``) as its first characters."""
    matches = [_STEP_SIZE.match(text)] if leading else _STEP_SIZE.finditer(text)
    for match in matches:
        if match is None:
            continue
        printed = match.group(1)
        if printed == inch_text(step_dia, len(printed.partition(".")[2])):
            return True
    return False


def _require_inch_sheet(draw: Any, label: str) -> None:
    """Refuse unless the drawing's linear unit is the inch.

    The depth band is typed text in inches: SolidWorks re-renders the
    callout's native depth in the sheet's units but never the text after it,
    so the band is only true on an inch sheet.  The callout has no native route for it:
    ``GetHoleCalloutVariables`` raised DISP_E_BADVARTYPE on this cut-extrude
    callout on the farm (run 20261003T001156794Z); every repo caller it works
    for is a Hole Wizard feature.  Reads the document preference
    ``set_units_inch`` writes (``IModelDoc2::GetUserPreferenceIntegerValue``).
    """
    doc = _early_bound(draw, "IModelDoc2")
    unit = doc.GetUserPreferenceIntegerValue(_SW_PREF_UNITS_LINEAR)
    if type(unit) is not int or unit != _SW_LENGTH_INCHES:
        raise RuntimeError(
            f"{label}: the typed depth band is inches, but the sheet's linear unit"
            f" is {unit!r} (swLengthUnit_e; swINCHES = {_SW_LENGTH_INCHES})"
        )


def _band_hole_depth(display: Any, band: str, process: str, draw: Any, label: str) -> None:
    """Print the hole's process before, and the part's depth band after, the
    native callout's depth (``_depth_banded_definition``).

    The cut's depth carries the band in the part, but the callout prints the
    depth bare; the band joins the format text of the part holding the depth,
    where the native size and depth stay associative.  Read back like the
    prose.  The callout-below compartment is rewritten by the matched-fit
    prose afterwards, so a depth there is refused rather than lost.  The band
    is inch text, so the sheet must be inch (``_require_inch_sheet``).
    """
    _require_inch_sheet(draw, label)
    display = _early_bound(display, "IDisplayDimension")
    definitions = {
        part: str(display.GetText(part) or "") for part in _DEFINITION_TO_WRITABLE
    }
    part, updated = _depth_banded_definition(definitions, band, process)
    if part == 8:
        raise RuntimeError(
            f"{label}: depth is in the callout-below text: {definitions!r}"
        )
    display.SetText(_DEFINITION_TO_WRITABLE[part], updated)
    applied = str(display.GetText(part) or "")
    if applied.replace("\r", "") != updated.replace("\r", ""):
        raise RuntimeError(f"{label}: depth band did not persist: {applied!r}")
    _telemetry.info(f"{label}: process and depth band joined format part {part}: {updated!r}")


Box = tuple[float, float, float, float]


def _shift_into_field(text: Box, field: Box, margin: float) -> tuple[float, float]:
    """Return the (dx, dy) that brings a measured text box ``margin`` inside ``field``.

    Boxes are (x0, y0, x1, y1) in sheet metres.  A box already inside moves
    (0, 0); one too big for the field fails loud, naming the overflow.
    """
    x0, y0, x1, y1 = text
    fx0, fy0, fx1, fy1 = field
    spare_x = (fx1 - fx0 - 2.0 * margin) - (x1 - x0)
    spare_y = (fy1 - fy0 - 2.0 * margin) - (y1 - y0)
    if spare_x < 0.0 or spare_y < 0.0:
        raise RuntimeError(
            f"text box {text} cannot sit {margin} inside field {field}: "
            f"over by {max(-spare_x, 0.0):.4f} wide, {max(-spare_y, 0.0):.4f} tall"
        )
    dx = max(0.0, fx0 + margin - x0) - max(0.0, x1 - (fx1 - margin))
    dy = max(0.0, fy0 + margin - y0) - max(0.0, y1 - (fy1 - margin))
    return dx, dy


def _leader_tip(points: Sequence[float], target: tuple[float, float]) -> tuple[float, float]:
    """Return the leader point (flat x, y, z triples) nearest ``target``."""
    triples = [
        (float(points[i]), float(points[i + 1])) for i in range(0, len(points) - 2, 3)
    ]
    if not triples:
        raise RuntimeError("note reports no leader points")
    return min(triples, key=lambda p: math.hypot(p[0] - target[0], p[1] - target[1]))


def _inside(point: tuple[float, float], box: Box) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _note_text_box(drawing_model: Any, annotation: Any, note: Any, label: str) -> Box:
    """Measure a leadered note's TEXT box: GetExtent includes the leader.

    The leader is hidden for the read and restored (straight, as
    ``add_attached_note`` makes it), then re-verified to still attach once.
    """
    if annotation.SetLeader3(0, 0, True, False, False, False) != 0:  # swNO_LEADER
        raise RuntimeError(f"{label}: could not hide the leader to measure the text")
    drawing_model.GraphicsRedraw2()
    extent = tuple(float(v) for v in (note.GetExtent() or ()))
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:  # swSTRAIGHT
        raise RuntimeError(f"{label}: could not restore the leader")
    drawing_model.GraphicsRedraw2()
    if int(annotation.GetLeaderCount()) != 1 or int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"{label}: note lost its one attached leader while measured")
    if len(extent) < 5:
        raise RuntimeError(f"{label}: note text extent unreadable: {extent}")
    return extent[0], extent[1], extent[3], extent[4]


def _place_note_text_in_field(
    drawing_model: Any, note: Any, field: Box, *, hole: Box, label: str
) -> Box:
    """Move a leadered note's text inside ``field`` from its measured box.

    Its leader must still end inside ``hole``.  Everything read is logged.
    Returns the placed text box.
    """
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text = _note_text_box(drawing_model, annotation, note, label)
    dx, dy = _shift_into_field(text, field, NOTE_FIELD_MARGIN)
    if dx or dy:
        x, y = (float(v) for v in tuple(annotation.GetPosition())[:2])
        if not annotation.SetPosition2(x + dx, y + dy, 0.0):
            raise RuntimeError(f"{label}: failed to move the note by ({dx}, {dy})")
        text = _note_text_box(drawing_model, annotation, note, label)
    leader = tuple(float(v) for v in (note.GetLeaderInfo() or ()))
    centre = ((hole[0] + hole[2]) / 2.0, (hole[1] + hole[3]) / 2.0)
    tip = _leader_tip(leader, centre)
    _telemetry.info(
        f"{label}: text box {text} moved ({dx:.4f}, {dy:.4f}); leader {leader}; tip {tip}"
    )
    if _shift_into_field(text, field, 0.0) != (0.0, 0.0):
        raise RuntimeError(f"{label}: text box {text} left its field {field}")
    if not _inside(tip, hole):
        raise RuntimeError(f"{label}: leader tip {tip} is off the hole window {hole}")
    return text


def _visible_cross_hole_edge(
    adapter: Any,
    view: Any,
    diameter_mm: float,
    *,
    view_label: str = "side",
    accept: Callable[[Any], bool] | None = None,
) -> Any:
    """Return a visible rim edge adjacent to a modeled hole cylinder.

    ``accept`` narrows the candidates further (an ``IEdge`` predicate) when a
    view shows more than one rim of that size.
    """
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            adjacent_faces = edge.GetTwoAdjacentFaces2() or ()
            for face in adjacent_faces:
                if face is None:
                    continue
                face = _early_bound(face, "IFace2")
                surface = _early_bound(face.GetSurface(), "ISurface")
                if not surface.IsCylinder():
                    continue
                parameters = surface.CylinderParams
                if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                    continue
                if accept is None or accept(edge):
                    candidates.append(edge)
                break
    if not candidates:
        raise RuntimeError(
            f"crankshaft {view_label} view has no visible edge adjacent to a "
            f"hole cylindrical face at radius {expected_radius_m:g} m"
        )
    return candidates[0]


def _is_upper_seat_rim(edge: Any) -> bool:
    """Whether an edge is the +Z drive-pin hole's rim on the spigot's seat face.

    The *Bottom end view prints model +Z up, so the +Z hole is the upper one,
    nearest its callout above the view; its seat-face rim, not its floor.
    """
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if not curve.IsCircle():
        return False
    cx, cy, cz = (float(v) * 1000.0 for v in tuple(curve.CircleParams)[:3])
    return (
        abs(cx) < 1e-3
        and abs(cy - SEAT_COLLAR) < 1e-3
        and abs(cz - DRIVE_PIN_CIRCLE_RADIUS) < 1e-3
    )


def _is_lower_knockout_floor(edge: Any) -> bool:
    """Whether an edge is the -Z knockout's circle on its drive-pin hole floor.

    The lower hole is the knockout callout's nearest; the floor circle, not
    the knockout's exit on the collar's rear face, is what the end view sees.
    """
    curve = _early_bound(edge.GetCurve(), "ICurve")
    if not curve.IsCircle():
        return False
    cx, cy, cz = (float(v) * 1000.0 for v in tuple(curve.CircleParams)[:3])
    return (
        abs(cx) < 1e-3
        and abs(cy - DRIVE_PIN_FLOOR) < 1e-3
        and abs(cz + DRIVE_PIN_CIRCLE_RADIUS) < 1e-3
    )


def _collar_rear_rim(adapter: Any, view: Any) -> Any:
    """Return the collar's rear-face rim, seen edge-on in the side view.

    A sheet pick on that vertical line found no edge natively (run
    20261001T035353825Z) though the same pick passed on f7c9771b3.  The
    model circle centred on the shaft axis at the rear-face station is
    unambiguous; the collar's other rim sits at its seat face,
    SEAT_COLLAR.
    """
    radius_mm = SPIGOT_DIA / 2.0
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(curve.CircleParams)
            cx, cy, cz = (float(v) * 1000.0 for v in params[:3])
            if (
                abs(cx) < 1e-3
                and abs(cz) < 1e-3
                and abs(cy - COLLAR_REAR) < 1e-3
                and abs(float(params[6]) * 1000.0 - radius_mm) < 1e-3
            ):
                return edge
    raise RuntimeError(
        f"crankshaft side view has no visible Ø{SPIGOT_DIA} rim at the collar "
        f"rear station {COLLAR_REAR}"
    )


def _collar_rear_face(rim: Any) -> Any:
    """Return the controlled planar rear (thrust) face that ``rim`` bounds.

    The rim joins that face and the collar's OD; only the face matches the
    part-owned ``collar_rear_face`` finish control.  None or both fail.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face")
    faces = tuple(
        face for face in (_early_bound(rim, "IEdge").GetTwoAdjacentFaces2() or ())
        if face is not None
    )
    geometries = [face_geometry(face) for face in faces]
    matches = [
        face for face, geometry in zip(faces, geometries)
        if geometry is not None and control.face.matches(geometry)
    ]
    if len(faces) != 2 or len(matches) != 1:
        raise RuntimeError(
            f"crankshaft collar rear rim: expected one {control.face!r} of its two "
            f"faces, matched {len(matches)} of {len(faces)}"
        )
    return matches[0]


def _far_end_rim(adapter: Any, view: Any) -> Any:
    """Return the plain far end's Ø9.000 rim, the end a lathe centre may enter.

    The model circle centred on the shaft axis at SHAFT_LENGTH with the
    seat's radius is that end face's only boundary; the seat step's Ø9.000
    circle sits at SEAT_STEP.  None or several fail rather than land the
    note's leader on another edge.
    """
    radius_mm = PINION_SEAT_DIA / 2.0
    matches: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 1
                ),  # swViewEntityType_Edge
                default=(),
            )
            or ()
        )
        for edge in edges:
            edge = _early_bound(edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            params = tuple(curve.CircleParams)
            cx, cy, cz = (float(v) * 1000.0 for v in params[:3])
            if (
                abs(cx) < 1e-3
                and abs(cz) < 1e-3
                and abs(cy - SHAFT_LENGTH) < 1e-3
                and abs(float(params[6]) * 1000.0 - radius_mm) < 1e-3
            ):
                matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(
            f"crankshaft FRONT shows {len(matches)} visible Ø{PINION_SEAT_DIA} "
            f"rims at the plain end station {SHAFT_LENGTH}; expected exactly one"
        )
    return matches[0]


@_telemetry.traced("drawing.crankshaft.finish_leader", label_param="label")
def _straighten_finish_leader(symbol: Any, *, label: str) -> None:
    """One straight leader ending in a filled arrow on a finish symbol."""
    if symbol is None:
        raise RuntimeError(f"{label}: missing captured native symbol")
    annotation = _early_bound(symbol, "ISFSymbol").GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"{label}: missing captured native annotation")
    annotation = _early_bound(annotation, "IAnnotation")
    status = annotation.SetLeader3(1, 0, False, False, False, False)
    if type(status) is not int or status != 0:
        raise RuntimeError(f"{label}: SetLeader3 failed ({status!r})")
    status = annotation.SetArrowHeadStyleAtIndex(0, 1)  # swCLOSED_ARROWHEAD
    if type(status) is not int or status != 0:
        raise RuntimeError(f"{label}: SetArrowHeadStyleAtIndex failed ({status!r})")


def _centres_note_field() -> Box:
    """Text below the pictorial caption, right of FRONT's station witnesses."""
    return (
        FAR_END_X + NOTE_TEXT_GAP,
        0.068,
        0.4181,
        ISO_NOTE_XY[1] - 2.0 * 0.005 - NOTE_TEXT_GAP,  # both caption rows
    )


def _add_centres_note(adapter: Any, drawing_model: Any, side: Any) -> Any:
    """Flag the FRONT plain end where a lathe centre hole may go."""
    label = "lathe centre hole end"
    # An edge-on rim can miss coordinate hit-testing. Use the same exact-edge
    # selection + pre-insertion landing pattern as add_toothspace_callout.
    rim = _far_end_rim(adapter, side)
    _select_view_entity(adapter, side, "EDGE", None, label=label, entity=rim)
    selection = _early_bound(drawing_model.SelectionManager, "ISelectionMgr")
    x, y = FAR_END_FRONT_RIM_PICK
    if selection.SetSelectionPoint2(1, -1, x, y, 0.0) is not True:
        raise RuntimeError(f"{label}: failed to set the FRONT plain-end landing")
    note = drawing_model.InsertNote(CENTRES_NOTE)
    if note is None:
        raise RuntimeError(f"{label}: failed to insert the note")
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"{label}: failed to create the leader")
    if not annotation.SetPosition2(*CENTRES_NOTE_XY, 0.0):
        raise RuntimeError(f"{label}: failed to position the note")
    rebuild_drawing(adapter, label=label)
    _place_note_text_in_field(
        drawing_model,
        note,
        _centres_note_field(),
        hole=FAR_END_FRONT_RIM_WINDOW,
        label=label,
    )
    _assert_attached_to(
        adapter, annotation, rim, entity_type="EDGE", what="attached note", label=label
    )
    drawing_model.ClearSelection2(True)
    return note


def _visible_cylindrical_face(adapter: Any, view: Any, diameter_mm: float) -> Any:
    """Return the requested modeled OD face in the crankshaft side view."""
    expected_radius_m = diameter_mm / 2000.0
    candidates: list[tuple[float, Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        faces = (
            adapter._attempt(
                lambda c=component: visible_component_entities(
                    view, c, 3
                ),  # swViewEntityType_Face
                default=(),
            )
            or ()
        )
        for face in faces:
            face = _early_bound(face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if not surface.IsCylinder():
                continue
            parameters = surface.CylinderParams
            if abs(float(parameters[6]) - expected_radius_m) > 1e-6:
                continue
            candidates.append((float(face.GetArea()), face))
    if not candidates:
        raise RuntimeError(
            f"crankshaft side view has no visible cylindrical face at "
            f"radius {expected_radius_m:g} m"
        )
    return max(candidates, key=lambda candidate: candidate[0])[1]


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move a native model dimension and verify its new drawing-view owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name,
        "DIMENSION",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"failed to select model dimension {name}: {selection_name!r}")
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    matches = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
        if dimension_name(adapter, _early_bound(item, "IAnnotation")) == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print a model radius as the ASME spherical reference ``(SR6.7)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced end diameter already fixes it.  Whatever radius prefix the
    display carries is kept behind the ``(S``; the readback proves it stuck.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(
        f"{label}: spherical reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(f"failed to mark {label} as a spherical reference: {applied}")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crankshaft source", adapter.open_model(str(SOURCE)))
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
    # Inch sheet (#290).  The drive-pin holes are a cut, not a Hole Wizard
    # feature, so their native callout prints at the document's places: the
    # sheet opens at HOLE_CALLOUT_PLACES, and every Hole Wizard callout is set
    # back to the title block's three below.
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        decimals=HOLE_CALLOUT_PLACES,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crankshaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crankshaft; domed nose; hub taper pin; punched fiducial",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    native_side = _early_bound(side, "IView")
    native_side.Angle = SIDE_VIEW_ANGLE
    if abs(math.remainder(float(native_side.Angle) - SIDE_VIEW_ANGLE, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to lay the crankshaft profile horizontal")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="crank-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    moved = [
        _move_dimension(
            adapter,
            annotation,
            side,
            DIAMETER_POSITIONS[dimension_name(adapter, annotation)],
            source_view=end,
        )
        for annotation in end_annotations
        if dimension_name(adapter, annotation) in END_DIAMETERS
    ]
    end_kept = [
        annotation
        for annotation in end_annotations
        if dimension_name(adapter, annotation) in END_PIN_KEEP
    ]
    if len(end_kept) != len(END_PIN_KEEP):
        raise RuntimeError("the end view lost a drive-pin hole location dimension")
    annotations = [*moved, *end_kept, *side_annotations]
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _set_dimension_suffixes(adapter, annotations, SUFFIXES)
    assert_imported_precision(
        adapter,
        annotations,
        {
            name: places
            for name, places in DRAWING_PRECISION_BY_NAME.items()
            if name not in UNPRINTED_DIMENSIONS
        },
    )
    for name in sorted(REFERENCE_DIMENSIONS - UNPRINTED_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one crankshaft {name} reference dimension")
        if name in SPHERICAL_DIMENSIONS:
            _set_spherical_reference(adapter, matches[0], label=f"crankshaft {name}")
            continue
        set_reference_dimension(
            adapter,
            matches[0],
            label=f"crankshaft {name}",
            diameter=name in DIAMETER_REFERENCES,
        )

    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; the end view gets the
    # ASME centre mark, the side view marks the cross-hole circle.
    for view, label in ((end, "end"), (side, "side")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")
    add_view_centerline(
        adapter,
        side,
        label="crankshaft turning axis",
        face=_visible_cylindrical_face(adapter, side, SHAFT_DIA),
    )

    cross_hole = add_native_hole_callout(
        adapter,
        side,
        callout_xy=HOLE_CALLOUT_XY,
        label="tapered-pin cross-hole",
        edge=_visible_cross_hole_edge(adapter, side, _PIN_HOLE_DIA),
        process=CROSS_HOLE_PROCESS,
    )
    _set_callout_text(cross_hole, 4, CROSS_HOLE_CALLOUT, "tapered-pin cross-hole")
    set_hole_callout_precision(
        cross_hole, WIZARD_CALLOUT_PRECISION, label="tapered-pin cross-hole"
    )
    drive_pins = add_native_hole_callout(
        adapter,
        end,
        callout_xy=DRIVE_PIN_CALLOUT_XY,
        label="seat-collar drive-pin holes",
        edge=_visible_cross_hole_edge(
            adapter,
            end,
            DRIVE_PIN_HOLE_DIA,
            view_label="end",
            accept=_is_upper_seat_rim,
        ),
        # Only the count leads; REAM follows the size (_band_hole_depth).
        process="2X",
    )
    _drop_coaxial_step(drive_pins, DRIVE_PIN_KNOCKOUT_DIA, "seat-collar drive-pin holes")
    _band_hole_depth(
        drive_pins,
        DRIVE_PIN_DEPTH_BAND,
        DRIVE_PIN_HOLE_PROCESS,
        drawing_model,
        "seat-collar drive-pin holes",
    )
    _set_callout_text(drive_pins, 4, DRIVE_PIN_CALLOUT, "seat-collar drive-pin holes")
    place_callout_clear(
        adapter,
        _early_bound(drive_pins, "IDisplayDimension").GetAnnotation(),
        label="seat-collar drive-pin holes",
        below={},
        beside={},
    )
    knockouts = add_native_hole_callout(
        adapter,
        end,
        callout_xy=KNOCKOUT_CALLOUT_XY,
        label="drive-pin knockout holes",
        edge=_visible_cross_hole_edge(
            adapter,
            end,
            DRIVE_PIN_KNOCKOUT_DIA,
            view_label="end",
            accept=_is_lower_knockout_floor,
        ),
    )
    _drop_coaxial_step(knockouts, DRIVE_PIN_HOLE_DIA, "drive-pin knockout holes")
    _set_callout_text(knockouts, 3, KNOCKOUT_CALLOUT_ABOVE, "drive-pin knockout holes")
    _set_callout_text(knockouts, 4, KNOCKOUT_CALLOUT_BELOW, "drive-pin knockout holes")
    set_hole_callout_precision(
        knockouts, WIZARD_CALLOUT_PRECISION, label="drive-pin knockout holes"
    )
    add_attached_note(
        adapter,
        end,
        text=FIDUCIAL_NOTE,
        entity=_visible_cross_hole_edge(
            adapter, end, FIDUCIAL_MODEL_DIA, view_label="end"
        ),
        note_xy=FIDUCIAL_NOTE_XY,
        label="dome punch mark",
    )
    pinion_note = add_attached_note(
        adapter,
        side,
        text=PINION_PIN_CALLOUT,
        entity=_visible_cross_hole_edge(adapter, side, PINION_PIN_DIA),
        note_xy=PINION_PIN_NOTE_XY,
        leader_attach_xy=PINION_PIN_LEADER_LANDING,
        label="16T retention-pin transfer",
    )
    _place_note_text_in_field(
        drawing_model,
        pinion_note,
        PINION_PIN_NOTE_FIELD,
        hole=PINION_PIN_HOLE_WINDOW,
        label="16T retention-pin transfer",
    )
    _add_centres_note(adapter, drawing_model, side)
    # A straight leader: the factory's bent knee ran left from the V through
    # the journal diameter's leader (layout audit, farm run 10).
    _straighten_finish_leader(
        add_surface_finish(
            adapter,
            side,
            edge_xy=JOURNAL_FINISHES["outboard_journal"][0],
            symbol_xy=JOURNAL_FINISHES["outboard_journal"][1],
            control=surface_finish_by_key(SURFACE_FINISHES, "outboard_journal"),
            label="crankshaft outboard journal finish",
            entity_type="SILHOUETTE",
            char_height=0.0025,
        ),
        label="crankshaft outboard journal finish",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=JOURNAL_FINISHES["inboard_journal"][0],
        symbol_xy=JOURNAL_FINISHES["inboard_journal"][1],
        control=surface_finish_by_key(SURFACE_FINISHES, "inboard_journal"),
        label="crankshaft inboard journal finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    collar_rear_face = _collar_rear_face(_collar_rear_rim(adapter, side))
    # A straight native route; the symbol origin and the exact physical tip
    # stay the factory's. A smart arrowhead on a FACE attachment prints a dot
    # (swDOT_ARROWHEAD, farm run 20261023T182235406Z).
    _straighten_finish_leader(
        add_surface_finish(
            adapter,
            side,
            entity=collar_rear_face,
            entity_type="FACE",
            leader_attach_xy=COLLAR_REAR_FINISH[0],
            symbol_xy=COLLAR_REAR_FINISH[1],
            control=surface_finish_by_key(SURFACE_FINISHES, "collar_rear_face"),
            label="crankshaft collar rear (post boss) face finish",
            char_height=0.0025,
        ),
        label="crankshaft collar rear finish",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    if add_note(adapter, SHEET_NOTES, *SHEET_NOTES_XY) is None:
        raise RuntimeError("failed to add the crankshaft's numbered notes")
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The end view prints hidden lines removed with the rest (drawing-guidelines.md
    # rule 9 (show internal shape in solid lines)): the punch mark is flagged by
    # its own leader, so no dashed cross-hole is needed to clock it.

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crankshaft Manufacturing Drawing",
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
