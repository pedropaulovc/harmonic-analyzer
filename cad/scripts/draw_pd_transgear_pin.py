r"""Create the MHA-PD-23 transgear pin manufacturing drawing.

The SLDPRT remains authoritative.  A turned pin carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the turned shank and the
press land print reference Øs, both linked by SEE NOTE 1 to
the numbered note naming their fits, and one bearing-surface finish; the
MHA-PD-VN-61 ring groove its catalogue Ø and width bands, and every other
size is an ordinary model dimension at its part-authored places.

The pin axis is model +Z, so the ``*Right`` view lays it horizontal as it
sits in the lathe: model +Z runs to paper-LEFT, putting the domed tip on the
left and the head on the right.  Every feature is visible, so the side view
removes hidden lines.  The head's underside (its seat on the MHA-PD-18 arm) is
the one origin: the groove's load wall, the pin's functional station, and the
tip's apex are dimensioned from it, and the head land runs back from it.  The
land ahead of the groove, the dome heights and the apex-to-tip overall print
as references.  The sheet prints decimal inch (the part's ``drawing_unit``);
the model keeps its millimetre nominals.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pd_transgear_pin.py pd-transgear-pin
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_face_resolve import resolve_faces
from _gtol_planar import PlanarFace
from _gtol_sphere import SphereFace
from _gtol_torus import TorusFace
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import pd_transgear_arm_geometry as ARM
import pd_transgear_feed_pinion_spec as SLEEVE
import pd_transgear_pin_callouts as callouts
from pd_transgear_pin_spec import (
    ARM_NUMBER,
    DIA,
    DIA_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FRONT_LAND,
    GROOVE_DIA,
    GROOVE_DIA_BAND,
    GROOVE_REAR_STATION,
    GROOVE_STATION,
    GROOVE_STATION_BAND,
    GROOVE_WIDTH,
    GROOVE_WIDTH_BAND,
    HEAD_DIA,
    HEAD_DOME_R,
    HEAD_DOME_SAG,
    HEAD_HEIGHT,
    HEAD_LAND,
    LENGTH,
    OVERALL_LENGTH,
    PRESS_INTERFERENCE,
    PRESS_LAND_DIA,
    PRESS_LAND_LENGTH,
    RING_NUMBER,
    RUNNING_MATES,
    SEAT_FILLET_R,
    SURFACE_FINISHES,
    TIP_DOME_R,
    TIP_DOME_SAG,
    TIP_STATION,
    UNIT,
)

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_transgear_pin"]
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

# The side view prints at the sheet scale, so it needs no caption.  3:1 lays
# the 2.14 in pin 163 mm long and the .020 groove 1.5 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.170, 0.165)
ISO_CENTER = (0.345, 0.225)
ISO_SCALE = (2, 1)
_MID_Z = (LENGTH - HEAD_HEIGHT) / 2.0


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the pin axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_APEX_X = _sheet_x(-HEAD_HEIGHT)
HEAD_BACK_X = _sheet_x(-HEAD_LAND)
SEAT_X = _sheet_x(0.0)
LAND_END_X = _sheet_x(PRESS_LAND_LENGTH)
LAND_MID_X = (SEAT_X + LAND_END_X) / 2.0
GROOVE_REAR_X = _sheet_x(GROOVE_REAR_STATION)
LOAD_WALL_X = _sheet_x(GROOVE_STATION)
FRONT_END_X = _sheet_x(GROOVE_STATION + FRONT_LAND)
TIP_X = _sheet_x(LENGTH)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
SHANK_TOP_Y = _sheet_y(DIA / 2.0)
GROOVE_MID_X = (GROOVE_REAR_X + LOAD_WALL_X) / 2.0
SHANK_MID_X = (SEAT_X + GROOVE_REAR_X) / 2.0
HEAD_LAND_MID_X = (HEAD_BACK_X + SEAT_X) / 2.0

# One axial row under the profile: the functional station (head seat to the
# groove's load wall, naming the stack it sets), the reference land off that
# wall, and the head land off the seat with its text right of the head.  The
# tip apex's station from the seat runs in a second row below the station's
# callout, the reference overall apex to tip in a third.  The groove width
# hangs between the row and the profile, its text
# and ring callout toward the head, clear of the groove's rear-wall extension
# line (at +0.016 that line struck the 0.737, run 20261024T022718524Z) and of
# the station's load-wall extension line; the head dome's reference height
# sits at the same height right of the head.  The diameters
# stand above the profile, each on its own section: the shank Ø's SEE NOTE 1
# under its value, the groove Ø above it with the ring's name above its
# value.  The tip dome's reference height stands above the tip.  The press
# land (#2415) takes its reference Ø above its own length and its .XX length
# in a row of its own between the profile and the station's row, the shorter
# baseline nearer the part; the seat root's R MAX stands left of the land,
# over that row.
_ROW_Y = SIDE_CENTER[1] - 0.036
SIDE_KEEP = {
    "GrooveStation": ((SEAT_X + LOAD_WALL_X) / 2.0, _ROW_Y),
    # Left of the tip apex's extension line (shared by the 51.35 and the
    # overall), which ran through the ')' at FRONT_END_X - 0.010 (layout
    # audit text-on-line, run 20261024T060429646Z).
    "FrontLand": (TIP_X - 0.008, _ROW_Y),
    "HeadLand": (HEAD_APEX_X + 0.010, _ROW_Y),
    "LandLength": (LAND_MID_X, SIDE_CENTER[1] - 0.024),
    # Near the land's end, so the R MAX leader rising to the seat corner
    # passes under its lower arrow (at the land's middle it crossed the
    # arrow: machinist review, run 20261111T224008804Z).
    "LandDia": (LAND_END_X + 0.006, SHANK_TOP_Y + 0.025),
    "GrooveWidth": (GROOVE_MID_X + 0.032, SIDE_CENTER[1] - 0.016),
    "HeadDia": (HEAD_LAND_MID_X, HEAD_TOP_Y + 0.010),
    # At the shank's middle: its dimension line, and the arrow below the
    # shank, stand clear right of the groove width's text and ring callout
    # (34 mm left of here the lower arrow struck the +0.0762, run
    # 20261024T030409384Z).  The callout under the value runs right from
    # the line, high enough that it clears the Ra symbol and the head Ø.
    "ShankDia": (SHANK_MID_X, SHANK_TOP_Y + 0.046),
    # Above the shank Ø's whole block, with a text gap past the audit's
    # 3.57 mm (+0.068 left 2.80 to the shank Ø's 0.000): its shoulder, as
    # wide as the ring callout, ends left of the shank Ø's +0.000.
    "GrooveDia": (GROOVE_MID_X, SHANK_TOP_Y + 0.072),
    "HeadDomeR": (HEAD_APEX_X + 0.012, SIDE_CENTER[1] + 0.006),
    "HeadDomeSagDim": (HEAD_APEX_X + 0.012, SIDE_CENTER[1] - 0.016),
    "TipDomeR": (TIP_X - 0.012, SIDE_CENTER[1] - 0.016),
    "TipDomeSagDim": (TIP_X - 0.012, SIDE_CENTER[1] + 0.016),
    # The tip apex from the head seat, the pin's one faced origin (rule 11):
    # the one controlled length at that end, under the station's three-row
    # callout.
    "TipDomeZ": ((SEAT_X + TIP_X) / 2.0, _ROW_Y - 0.027),
    # The seat root's one-line R MAX under the shank, its shelf ending short
    # of the land end's extension line: the 23 mm text does not fit between
    # that line and the seat's (the 1.8600's, 2.02's, .09's and .29's), where
    # run 20261111T193324863Z printed it crossed by the seat's (text-on-line),
    # and at LAND_END_X - 0.014 its shelf, 2.7 mm past the text, crossed the
    # land end's (shoulder-crosses-line, run 20261111T201934013Z).  Its
    # leader rises steeply to the lower corner over the land, crossing only
    # the land end's extension line, under the land Ø's lower arrow and above
    # the land's .29 row.
    "SeatRadius": (LAND_END_X - 0.018, SIDE_CENTER[1] - 0.016),
}
# The callouts and the dome heights' reference parentheses are authored on
# the part's dimensions (``pd_transgear_pin_callouts``); the sheet only
# proves they arrived.
OVERALL_TEXT_XY = (SIDE_CENTER[0], _ROW_Y - 0.047)
# The shank's finish: the part-owned ``journal`` control's ONE Ø.125
# cylinder, resolved on the part the side view references and attached as
# that model FACE, its leader landing on the upper outline ahead of the press
# land, between the shank Ø's tolerance stack and the land's reference Ø.
# Not a SILHOUETTE pick: on farm runs 20261111T181535941Z and
# 20261111T190609060Z ISilhouetteEdge::GetFace failed IsSame against the
# picked silhouette's (same_entity=False, dangling=False), with or without a
# selection-point landing (draw_mg_magnifying_lever's rod finish; the face is
# proven by IsSame and the landing readback pins the flank and station).
FINISH_STATION_MM = PRESS_LAND_LENGTH + 0.013 * 1000.0 / _S
FINISH_SYMBOL = (_sheet_x(FINISH_STATION_MM), SHANK_TOP_Y + 0.008)
# A point on the shank face, clear of the Ø dimension line.
CENTERLINE_PICK = (SHANK_MID_X + 0.010, SIDE_CENTER[1] + 0.001)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.040)
NOTES_XY = (0.016, 0.070)

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (pd_transgear_pin_spec: one revolve about local +Z; z = 0 is the head's
# underside, the seat).  The domed ends are the part's ends: the head's apex
# (datum end, z = -HEAD_HEIGHT) and the tip's (far end, z = LENGTH), the
# overall between them a reference.  The seat is the pin's one faced origin
# (rule 11): the head land, the press land's length, the groove's load wall
# and the tip apex are stationed from it (``station_from = "shoulder"``; the
# head land runs back to the head dome's root).  The press land is a
# reference Ø turned to the measured MHA-PD-18 ream for its interference;
# the shank takes its +.0000/-.0002 band and, as REF, its running clearance
# in its mates' measured reams (note 1).  Each ``span`` is a feature's
# model-Z extent.  The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_pd_transgear_pin"
_KEEP = (_SELF, "SIDE_KEEP")
_NOTES = ("pd_transgear_pin_callouts", "DRAWING_NOTES")
_SLEEVE = "pd_transgear_feed_pinion_spec"
_TIP_ROOT = LENGTH - TIP_DOME_SAG
part_metadata(
    model_sources=(
        "LENGTH",
        "OVERALL_LENGTH",
        "HEAD_DIA",
        "HEAD_LAND",
        "HEAD_DOME_R",
        "TIP_DOME_R",
        "DIA",
        "PRESS_LAND_DIA",
        "PRESS_LAND_LENGTH",
        "GROOVE_STATION",
        "GROOVE_DIA",
        "GROOVE_WIDTH",
        "SEAT_FILLET_R",
    ),
    precision_sources=("DRAWING_PRECISION_BY_NAME", "DRAWING_REFERENCE_PRECISION"),
)
requirement(
    "datum_end",
    kind="dome",
    faces=(SphereFace(2.0 * HEAD_DOME_R),),
    requirements=("radius", "height_ref"),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": -HEAD_HEIGHT},
            ("HEAD_HEIGHT",),
        ),
        "outward": ([0.0, 0.0, -1.0], ("HEAD_HEIGHT",)),
        "radius": (
            limits(HEAD_DOME_R, _P["HeadDomeR"], unit=UNIT),
            ("HEAD_DOME_R", "UNIT", _KEEP),
        ),
        "radius_nominal": (HEAD_DOME_R, ("HEAD_DOME_R",)),
        "height_ref": (HEAD_DOME_SAG, ("HEAD_DOME_SAG", _KEEP)),
    },
    precision={"radius": _P["HeadDomeR"], "height_ref": _P["HeadDomeSagDim"]},
)
requirement(
    "far_end",
    kind="dome",
    faces=(SphereFace(2.0 * TIP_DOME_R),),
    requirements=("radius", "height_ref", "length_ref", "station"),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": LENGTH}, ("LENGTH",)),
        "outward": ([0.0, 0.0, 1.0], ("LENGTH",)),
        "radius": (
            limits(TIP_DOME_R, _P["TipDomeR"], unit=UNIT),
            ("TIP_DOME_R", "UNIT", _KEEP),
        ),
        "radius_nominal": (TIP_DOME_R, ("TIP_DOME_R",)),
        "height_ref": (TIP_DOME_SAG, ("TIP_DOME_SAG", _KEEP)),
        "length_ref": (
            OVERALL_LENGTH,
            (
                "OVERALL_LENGTH",
                "DRAWING_REFERENCE_PRECISION",
                (_SELF, "OVERALL_TEXT_XY"),
            ),
        ),
        "length_from": ("datum_end", ((_SELF, "OVERALL_TEXT_XY"),)),
        "station": (
            limits(TIP_STATION, _P["TipDomeZ"], unit=UNIT),
            ("TIP_STATION", "UNIT", _KEEP),
        ),
        "station_nominal": (TIP_STATION, ("TIP_STATION",)),
        "station_from": ("shoulder", (_KEEP,)),
    },
    precision={
        "radius": _P["TipDomeR"],
        "height_ref": _P["TipDomeSagDim"],
        "length_ref": DRAWING_REFERENCE_PRECISION,
        "station": _P["TipDomeZ"],
    },
)
requirement(
    "shoulder",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), 0.0),),
    requirements=("station",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("HEAD_LAND",)),
        "outward": ([0.0, 0.0, 1.0], ("HEAD_LAND",)),
        "origin": (True, ((_SELF, "SIDE_KEEP"),)),
        "station": (
            limits(HEAD_LAND, _P["HeadLand"], unit=UNIT),
            ("HEAD_LAND", "UNIT", _KEEP),
        ),
        "station_nominal": (HEAD_LAND, ("HEAD_LAND",)),
        "station_from": ("datum_root", (_KEEP,)),
        "seats_on": (ARM_NUMBER, ("ARM_NUMBER",)),
    },
    precision={"station": _P["HeadLand"]},
)
requirement(
    "step_head",
    kind="diameter",
    faces=(CylinderFace(HEAD_DIA),),
    requirements=("dia",),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("HEAD_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("HEAD_DIA",)),
        "span": ([-HEAD_LAND, 0.0], ("HEAD_LAND",)),
        "dia": (
            limits(HEAD_DIA, _P["HeadDia"], unit=UNIT),
            ("HEAD_DIA", "UNIT", _KEEP),
        ),
        "dia_nominal": (HEAD_DIA, ("HEAD_DIA",)),
    },
    precision={"dia": _P["HeadDia"]},
)
requirement(
    "step_land",
    kind="diameter",
    faces=(CylinderFace(PRESS_LAND_DIA, contains_z_mm=PRESS_LAND_LENGTH / 2.0),),
    requirements=("dia_ref", "diametral_interference", "length"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("PRESS_LAND_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("PRESS_LAND_DIA",)),
        "span": ([0.0, PRESS_LAND_LENGTH], ("PRESS_LAND_LENGTH",)),
        "dia_ref": (PRESS_LAND_DIA, ("PRESS_LAND_DIA", _KEEP, _NOTES)),
        "diametral_interference": (
            [PRESS_INTERFERENCE[0], PRESS_INTERFERENCE[1]],
            ("PRESS_INTERFERENCE", _NOTES),
        ),
        "mate": (ARM_NUMBER, ("ARM_NUMBER", _NOTES)),
        "mate_dia": (
            [ARM.PIN_BORE_DIA_MIN, ARM.PIN_BORE_DIA_MAX],
            (
                ("pd_transgear_arm_geometry", "PIN_BORE_DIA_MIN"),
                ("pd_transgear_arm_geometry", "PIN_BORE_DIA_MAX"),
                _NOTES,
            ),
        ),
        "length": (
            limits(PRESS_LAND_LENGTH, _P["LandLength"], unit=UNIT),
            ("PRESS_LAND_LENGTH", "UNIT", _KEEP),
        ),
        "length_nominal": (PRESS_LAND_LENGTH, ("PRESS_LAND_LENGTH",)),
        "length_from": ("shoulder", (_KEEP,)),
        "callout": (
            callouts.SHANK_CALLOUT,
            (("pd_transgear_pin_callouts", "SHANK_CALLOUT"), _NOTES),
        ),
    },
    precision={"dia_ref": _P["LandDia"], "length": _P["LandLength"]},
)
# The shank prints a reference Ø made to fit (note 1) and no band.  The
# ``dia`` and ``diametral_clearance`` declared here are the spec's ANALYSIS
# numbers (pd_transgear_pin_spec.DIA_BAND, the shank the fit is modelled to
# produce, and the clearance it gives), bound only because the traveler's
# turned_shaft adapter sizes its cuts and draws its diagrams from a band
# (prechips has no made-to-fit form: its REF form prints the clearance and
# its labels overrun the diagram).  No traveler step quotes them as an
# acceptance: the acceptance is the mates tried on the journal.
_ANALYSIS_PLACES = 4
requirement(
    "outer",
    kind="diameter",
    faces=(
        CylinderFace(
            DIA, contains_z_mm=(PRESS_LAND_LENGTH + GROOVE_REAR_STATION) / 2.0
        ),
        CylinderFace(DIA, contains_z_mm=(GROOVE_STATION + _TIP_ROOT) / 2.0),
    ),
    requirements=("dia", "diametral_clearance"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("DIA",)),
        "at": ([0.0, 0.0, 0.0], ("DIA",)),
        "span": (
            [PRESS_LAND_LENGTH, _TIP_ROOT],
            ("PRESS_LAND_LENGTH", "LENGTH", "TIP_DOME_SAG"),
        ),
        "dia": (
            limits(DIA, _ANALYSIS_PLACES, DIA_BAND, unit=UNIT),
            ("DIA", "DIA_BAND", "UNIT", _NOTES),
        ),
        "dia_nominal": (DIA, ("DIA",)),
        "diametral_clearance": (
            list(SLEEVE.BORE_DIAMETRAL_CLEARANCE),
            ((_SLEEVE, "BORE_DIAMETRAL_CLEARANCE"), "DIA_BAND"),
        ),
        "mates": (list(RUNNING_MATES), ("RUNNING_MATES", _NOTES)),
        "callout": (
            callouts.SHANK_CALLOUT,
            (("pd_transgear_pin_callouts", "SHANK_CALLOUT"), _NOTES),
        ),
    },
    precision={"dia": _ANALYSIS_PLACES},
)
requirement(
    "groove",
    kind="groove",
    faces=(
        CylinderFace(GROOVE_DIA),
        PlanarFace((0.0, 0.0, -1.0), -GROOVE_STATION),
        PlanarFace((0.0, 0.0, 1.0), GROOVE_REAR_STATION),
    ),
    requirements=("dia", "width", "station"),
    fields={
        "axis": ([0.0, 0.0, 1.0], ("GROOVE_DIA",)),
        "at": ([0.0, 0.0, 0.0], ("GROOVE_DIA",)),
        "span": (
            [GROOVE_REAR_STATION, GROOVE_STATION],
            ("GROOVE_STATION", "GROOVE_WIDTH"),
        ),
        "dia": (
            limits(GROOVE_DIA, _P["GrooveDia"], GROOVE_DIA_BAND, unit=UNIT),
            ("GROOVE_DIA", "GROOVE_DIA_BAND", "UNIT", _KEEP),
        ),
        "dia_nominal": (GROOVE_DIA, ("GROOVE_DIA",)),
        "width": (
            limits(GROOVE_WIDTH, _P["GrooveWidth"], GROOVE_WIDTH_BAND, unit=UNIT),
            ("GROOVE_WIDTH", "GROOVE_WIDTH_BAND", "UNIT", _KEEP),
        ),
        "width_nominal": (GROOVE_WIDTH, ("GROOVE_WIDTH",)),
        "station": (
            limits(
                GROOVE_STATION,
                _P["GrooveStation"],
                (GROOVE_STATION_BAND, -GROOVE_STATION_BAND),
                unit=UNIT,
            ),
            ("GROOVE_STATION", "GROOVE_STATION_BAND", "UNIT", _KEEP),
        ),
        "station_nominal": (GROOVE_STATION, ("GROOVE_STATION",)),
        "station_from": ("shoulder", (_KEEP,)),
        "station_to": ("far_wall", (_KEEP,)),
        "ring": (RING_NUMBER, ("RING_NUMBER", _NOTES)),
        "callout": (
            callouts.GROOVE_CALLOUT,
            (("pd_transgear_pin_callouts", "GROOVE_CALLOUT"), _NOTES),
        ),
    },
    precision={
        "dia": _P["GrooveDia"],
        "width": _P["GrooveWidth"],
        "station": _P["GrooveStation"],
    },
)
requirement(
    "fillet_seat",
    kind="fillet",
    faces=(TorusFace(PRESS_LAND_DIA / 2.0 + SEAT_FILLET_R, SEAT_FILLET_R),),
    requirements=("radius_max",),
    fields={
        "radius_max": (SEAT_FILLET_R, ("SEAT_FILLET_R", _KEEP)),
        "radius_nominal": (SEAT_FILLET_R, ("SEAT_FILLET_R",)),
        "axis": ([0.0, 0.0, 1.0], ("SEAT_FILLET_R",)),
        "at": ([0.0, 0.0, 0.0], ("SEAT_FILLET_R",)),
        "between": (["shoulder", "step_land"], ("SEAT_FILLET_R",)),
    },
    precision={"radius_max": _P["SeatRadius"]},
)


def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored.

    The mates, the stack and the reference marks print nowhere else on the
    sheet, so a lost lane must fail the drawing.  Read-only: text set from
    the sheet would write through to the source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    printed = {
        (name, lane): str(displays[name][0].GetText(lane) or "")
        for name, lanes in wanted.items()
        for lane in lanes
    }
    wrong = {
        key: text
        for key, text in printed.items()
        if callouts.callout_rows(text) != callouts.callout_rows(wanted[key[0]][key[1]])
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


def _dress_seat_radius(adapter: Any, annotations: list[Any]) -> None:
    """The seat root's R MAX prints radial, and its leader stops at the
    corner: ``ArcExtensionLineOrOppositeSide`` False keeps it from running on
    through the arc centre into the head (draw_pn_pen_rod's shoulder)."""
    found = [a for a in annotations if dimension_name(adapter, a) == "SeatRadius"]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one SeatRadius on the side view, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported seat radius is not radial")
    display.ArcExtensionLineOrOppositeSide = False
    if display.ArcExtensionLineOrOppositeSide is not False:
        raise RuntimeError("SeatRadius leader still runs to the opposite side")


def _shank_finish_pick(adapter: Any, side: Any) -> tuple[Any, tuple[float, float]]:
    """The shank finish's target: ``(controlled face, sheet landing)``.

    The face is the one the part's own Ra PMI names (``SURFACE_FINISHES``'
    ``journal``), resolved on the part the side view references; the landing
    is the upper of the shank's two outline points at ``FINISH_STATION_MM``.
    """
    document = _early_bound(
        _early_bound(side, "IView").ReferencedDocument, "IModelDoc2"
    )
    control = surface_finish_by_key(SURFACE_FINISHES, "journal")
    face = resolve_faces(document, {control.key: control.face})[control.key]
    flanks = model_points_in_view(
        adapter,
        side,
        tuple(
            (0.0, sign * DIA / 2000.0, FINISH_STATION_MM / 1000.0)
            for sign in (1.0, -1.0)
        ),
        label="MHA-PD-23 shank finish landing",
        names=("flank +Y", "flank -Y"),
    )
    return face, max(flanks, key=lambda xy: xy[1])


def _overall_reference(adapter: Any, side: Any) -> None:
    """The overall REF, head apex to tip apex (rule 10), for the bar cut.

    A drawing-owned dimension, so its reference parentheses are the sheet's
    own text, not an imported part dimension's.
    """
    label = "pin overall length reference"
    head_apex, tip_apex = model_points_in_view(
        adapter,
        side,
        ((0.0, 0.0, -HEAD_HEIGHT / 1000.0), (0.0, 0.0, LENGTH / 1000.0)),
        label=label,
        names=("head apex", "tip apex"),
    )
    display = add_edge_dimension(
        adapter,
        side,
        p0=tip_apex,
        p1=head_apex,
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="horizontal",
        entity_type="SILHOUETTE",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension_type = int(display.Type2)
    # swLinearDimension, swHorLinearDimension: the curved silhouette picks
    # must still give a length before SystemValue is read as metres.
    if dimension_type not in (2, 11):
        raise RuntimeError(
            f"{label}: expected a linear dimension, got type {dimension_type}"
        )
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if not math.isclose(measured_mm, OVERALL_LENGTH, abs_tol=1e-4):
        # A pick on a dome may resolve to its centre; the overall runs to
        # each apex, the arcs' far extremes.
        set_arc_endpoints_to_max(adapter, display, label=label)
    # Value-only: both picks are dome apexes located by coordinate, and the
    # apex-to-apex sum is the one value a centre-anchored pick cannot give.
    # Rejects a non-finite readback too.
    assert_dimension_measures(
        adapter, display, expected_mm=OVERALL_LENGTH, label=label, tolerance_mm=1e-4
    )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open transgear-pin source", adapter.open_model(str(SOURCE)))
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
            0: "Transgear Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear pin; turned steel; ring groove",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, side)
    set_hidden_lines_removed(adapter, iso)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_authored_text(adapter, annotations)
    _dress_seat_radius(adapter, annotations)
    _overall_reference(adapter, side)

    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-PD-23 turning axis",
    )
    shank_face, shank_landing = _shank_finish_pick(adapter, side)
    add_surface_finish(
        adapter,
        side,
        entity=shank_face,
        leader_attach_xy=shank_landing,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "journal"),
        label="MHA-PD-23 shank finish",
        entity_type="FACE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Pin Manufacturing Drawing",
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
