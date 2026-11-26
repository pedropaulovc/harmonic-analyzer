r"""Manufacturing drawing of the separate brass stop cover.

The sheet prints decimal inch (the part's ``drawing_unit: in``). The cover
face locates both clearance holes from one finished end and the head-side
edge. The aligned end view gives thickness; the native clearance callout
gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
The native clearance callout carries the match-drill line; the pilot and
opening sequence lives in the plate's traveler (cad/process/ms_stop_plate,
Setups 3-4), not on this sheet.
Separate native chamfer size and angle retain their model-owned precision.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import set_dimension_callouts, set_reference_dimension
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from _printed_tolerance import angular_band_deg
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from ms_stop_plate_notes import MATCHED_PAIR_NOTE, NOTE_NUMBER
from solidworks_mcp.adapters.solidworks.drawing import add_note, auto_center_marks, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ms_stop_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.175, 0.170)
# Far enough right that the thickness text ends clear of the face view.
RIGHT_CENTER = (0.360, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.090)
FRONT_KEEP = {
    "PlateLength": (0.175, 0.235), "PlateHeight": (0.030, 0.170),
    "RoofChamferSize": (0.247, 0.225), "RoofChamferAngle": (0.227, 0.205),
    # Hole-location texts sit where no other witness line crosses their
    # mate callouts: .150 outboard right, .160 below its own witness span and
    # the .56 arrow, .690 centred between its witness lines.
    "PlateLeftFromEnd": (0.250, 0.113),
    "PlateRightFromEnd": (0.182, 0.095),
    "PlateFromHeadFace": (0.100, 0.122),
}
# Text left of the thin edge view, so neither witness line strikes it.
RIGHT_KEEP = {"PlateThickness": (0.327, 0.225)}
# Rule 4: the hole callout links note 1 (ms_stop_plate_notes.MATCHED_PAIR_NOTE),
# which names the matched pair and its screws once and gives the trial on
# MHA-MS-02. Rule 4 form 2: the holes are pair-drilled with the block, so the
# three hole locations print as references, the note's screw trial the
# requirement. Rule 4 (stock that is good enough stays stock): the thickness
# is the .040 sheet as supplied (fit audit 2026-11-23,
# MHA-MS-03.plate_thickness), a reference over its stock.
NOTE_LINK = f"SEE NOTE {NOTE_NUMBER}"
THICKNESS_STOCK = "SHEET AS SUPPLIED"
DIMENSION_CALLOUTS = {"PlateThickness": THICKNESS_STOCK}
REFERENCE_DIMENSIONS = frozenset({*part.PLATE_LOCATION_DIMENSIONS, "PlateThickness"})
# Upper-left corner of the note: the open top-left field, as on MHA-MS-02.
MATCHED_PAIR_NOTE_XY = (0.020, 0.262)
# The size rows are wider than the room between the .56 witnesses, so the
# callout sits below the cover face, left of the hole-station texts.
CLEARANCE_CALLOUT_XY = (0.075, 0.100)
CLEARANCE_PRECISION = {"hw-diam": part.HOLE_CALLOUT_PRECISION}
# Leadered labels name the X=0 end and Y=0 edge the match-drill clamp aligns.
# Note positions are the text's upper-left corner.
LOCATING_END_XY = (0.228, 0.128)
# The edge label sits wholly left of its leader's landing point, so the
# leader leaves the text's end, between the two hole witness lines.
LOCATING_EDGE_XY = (0.150, 0.130)
LOCATING_EDGE_X_MM = 7.0

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, beside the constants of the
# code that prints it, in the part frame (ms_stop_plate_spec: X = 0 the
# LOCATING END, Y = 0 the LOCATING EDGE, Z = 0 the face that seats on the
# MHA-MS-02 mating face, the sheet's .040 thickness toward -Z). A band is the
# title block's row for the places the sheet prints
# (PLATE_DRAWING_PRECISION_BY_NAME) on the printed nominal; the clearance
# holes take the DRILLED HOLES row (HOLE_CALLOUT_PRECISION). The references
# (REFERENCE_DIMENSIONS) carry their analysis band: the receiving range of
# the sheet (PLATE_THICKNESS_TOLERANCE_MM) and the pair drill's DRO places
# (PLATE_HOLE_POSITION_TOLERANCE_MM), which every web proof in ms_stop_spec
# uses. The holes are opened from the #49 pilot the pair drill puts through
# the plate and into the block (MHA-MS-02's 2X Ø.073 to .30 from its mating
# face), carried here as the pair's pilot. The declarations print nothing.
_P = part.PLATE_DRAWING_PRECISION_BY_NAME
_SPEC = "ms_stop_spec"
_SELF = "draw_ms_stop_plate"
_FRAME = "__frame__"
_BUILD = ("build_ms_stop_plate", "build")
_PRECISION = (_SPEC, "PLATE_DRAWING_PRECISION_BY_NAME")
_ANGULAR_BAND_DEG = angular_band_deg(unit=part.UNIT)
_CHAMFER_DIAGONAL = math.sqrt(0.5)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


def _printed(
    name: str, value: float, *sources: Any
) -> tuple[list[float], tuple[Any, ...]]:
    """The title block's band for the printed places of dimension ``name``."""
    return (
        limits(value, _P[name], unit=part.UNIT),
        (*sources, (_SPEC, "UNIT"), _PRECISION),
    )


def _reference(
    value: float, band_mm: float, band_source: str, *sources: Any
) -> tuple[list[float], tuple[Any, ...]]:
    """A reference dimension's analysis band (it prints none): ``band_source``,
    a ms_stop_spec half-width, about the model nominal."""
    return (
        [value - band_mm, value + band_mm],
        (*sources, (_SPEC, band_source), (_SELF, "REFERENCE_DIMENSIONS")),
    )


part_metadata(
    fields={
        "material.thickness": (
            part.PLATE_THICKNESS,
            ((_SPEC, "PLATE_THICKNESS"), (_SPEC, "PLATE_THICKNESS_TOLERANCE_MM")),
        ),
    },
    model_sources=(
        _BUILD,
        (_SPEC, "BLOCK_LENGTH"),
        (_SPEC, "BLOCK_HEIGHT"),
        (_SPEC, "PLATE_THICKNESS"),
    ),
    precision_sources=(
        _PRECISION,
        (_SPEC, "HOLE_CALLOUT_PRECISION"),
        (_SELF, "CLEARANCE_PRECISION"),
    ),
)
# The X = 0 end and Y = 0 edge, labelled LOCATING END and LOCATING EDGE: the
# pair clamp sets both flush with the block's, and every station runs from
# them.
for _name, _normal, _axis, _note in (
    ("locating_end", (-1.0, 0.0, 0.0), "x", part.LOCATING_END_NOTE),
    ("locating_edge", (0.0, -1.0, 0.0), "y", part.LOCATING_EDGE_NOTE),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, 0.0),),
        requirements=("plane",),
        fields={
            "plane": (_plane(_axis, 0.0), (_FRAME, _BUILD)),
            "note": (
                _note,
                (
                    (_SPEC, "LOCATING_END_NOTE"),
                    (_SPEC, "LOCATING_EDGE_NOTE"),
                    (_SELF, "_label_locating_edges"),
                ),
            ),
        },
    )
# The length .84 and height .56 (FRONT_KEEP), each from its locating face.
for _name, _normal, _axis, _value, _key, _dim, _source, _from in (
    (
        "far_end",
        (1.0, 0.0, 0.0),
        "x",
        part.BLOCK_LENGTH,
        "length",
        "PlateLength",
        "BLOCK_LENGTH",
        "locating_end",
    ),
    (
        "roof_edge",
        (0.0, 1.0, 0.0),
        "y",
        part.BLOCK_HEIGHT,
        "height",
        "PlateHeight",
        "BLOCK_HEIGHT",
        "locating_edge",
    ),
):
    requirement(
        _name,
        kind="face",
        faces=(PlanarFace(_normal, _value),),
        requirements=(_key,),
        fields={
            "plane": (_plane(_axis, _value), ((_SPEC, _source),)),
            _key: _printed(_dim, _value, (_SPEC, _source), (_SELF, "FRONT_KEEP")),
            f"{_key}_nominal": (_value, ((_SPEC, _source),)),
            f"{_key}_from": (_from, ((_SELF, "FRONT_KEEP"),)),
        },
        precision={_key: _P[_dim]},
    )
# The seating face (Z = 0) and the outer face: the sheet's (.040) as a
# reference over SHEET AS SUPPLIED (RIGHT_KEEP PlateThickness, THICKNESS_STOCK),
# its band the receiving range (PLATE_THICKNESS_TOLERANCE_MM).
requirement(
    "seating_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part.PLATE_Z_MAX),),
    requirements=("plane",),
    fields={"plane": (_plane("z", part.PLATE_Z_MAX), (_FRAME, (_SPEC, "PLATE_Z_MAX")))},
)
requirement(
    "outer_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), -part.PLATE_Z_MIN),),
    requirements=("thickness",),
    fields={
        "plane": (_plane("z", part.PLATE_Z_MIN), ((_SPEC, "PLATE_Z_MIN"),)),
        "thickness": _reference(
            part.PLATE_THICKNESS,
            part.PLATE_THICKNESS_TOLERANCE_MM,
            "PLATE_THICKNESS_TOLERANCE_MM",
            (_SPEC, "PLATE_THICKNESS"),
            (_SELF, "RIGHT_KEEP"),
        ),
        "thickness_nominal": (part.PLATE_THICKNESS, ((_SPEC, "PLATE_THICKNESS"),)),
        "thickness_from": ("seating_face", ((_SELF, "RIGHT_KEEP"),)),
        "as_supplied": (True, ((_SELF, "THICKNESS_STOCK"),)),
        "dimension_type": ("reference", ((_SELF, "REFERENCE_DIMENSIONS"),)),
        "callout": (THICKNESS_STOCK, ((_SELF, "DIMENSION_CALLOUTS"),)),
    },
    precision={"thickness": _P["PlateThickness"]},
)
# The roof edge's two corners, 2X .04 X 45° (FRONT_KEEP RoofChamfer*), as the
# block's roof chamfers.
requirement(
    "roof_chamfers",
    kind="chamfer",
    faces=(
        PlanarFace(
            (-_CHAMFER_DIAGONAL, _CHAMFER_DIAGONAL, 0.0),
            (part.BLOCK_HEIGHT - part.ROOF_END_CHAMFER) * _CHAMFER_DIAGONAL,
        ),
        PlanarFace(
            (_CHAMFER_DIAGONAL, _CHAMFER_DIAGONAL, 0.0),
            (part.BLOCK_LENGTH + part.BLOCK_HEIGHT - part.ROOF_END_CHAMFER)
            * _CHAMFER_DIAGONAL,
        ),
    ),
    requirements=("size", "angle_deg"),
    fields={
        "count": (2, ((_SELF, "_style_plate_chamfer"),)),
        "edge": ("roof_edge", ((_SPEC, "ROOF_END_CHAMFER"),)),
        "size": _printed(
            "RoofChamferSize",
            part.ROOF_END_CHAMFER,
            (_SPEC, "ROOF_END_CHAMFER"),
            (_SELF, "FRONT_KEEP"),
        ),
        "size_nominal": (part.ROOF_END_CHAMFER, ((_SPEC, "ROOF_END_CHAMFER"),)),
        "angle_deg": (
            [
                part.ROOF_CHAMFER_ANGLE - _ANGULAR_BAND_DEG,
                part.ROOF_CHAMFER_ANGLE + _ANGULAR_BAND_DEG,
            ],
            ((_SPEC, "ROOF_CHAMFER_ANGLE"), (_SPEC, "UNIT"), (_SELF, "FRONT_KEEP")),
        ),
        "angle_deg_nominal": (
            part.ROOF_CHAMFER_ANGLE,
            ((_SPEC, "ROOF_CHAMFER_ANGLE"),),
        ),
    },
    precision={"size": _P["RoofChamferSize"], "angle_deg": _P["RoofChamferAngle"]},
)
# The two clearance holes, THRU from the outer face: one native callout (2X
# Ø.094 THRU ALL, SEE NOTE 1), stations (.150) and (.690) from the locating
# end and (.160) from the locating edge as references (rule 4 form 2: made
# with MHA-MS-02 in the pair drill, note 1's screw trial the requirement);
# each opened from the pair's #49 pilot.
_CLEARANCE = (
    drilled_limits(
        part.PLATE_CLEARANCE_DIA, part.HOLE_CALLOUT_PRECISION, unit=part.UNIT
    ),
    ((_SPEC, "PLATE_CLEARANCE_DIA"), (_SPEC, "UNIT"), (_SELF, "CLEARANCE_PRECISION")),
)
for _index, (_x, _dim) in enumerate(
    zip(part.PLATE_HOLE_XS, ("PlateLeftFromEnd", "PlateRightFromEnd"), strict=True), 1
):
    requirement(
        f"clearance_hole_{_index}",
        kind="hole",
        faces=(CylinderFace(part.PLATE_CLEARANCE_DIA, contains_x_mm=_x),),
        requirements=("dia", "thru", "station", "height"),
        fields={
            "at": (
                [_x, part.PLATE_HOLE_Y, part.PLATE_Z_MIN],
                ((_SPEC, "PLATE_HOLE_POINTS"),),
            ),
            "axis": ((0.0, 0.0, 1.0), ((_SPEC, "PLATE_HOLE_NORMAL"), _FRAME)),
            "process": ("drill", ((_SPEC, "PLATE_CLEARANCE_SPEC"),)),
            "dia": _CLEARANCE,
            "nominal_dia": (
                part.PLATE_CLEARANCE_DIA,
                ((_SPEC, "PLATE_CLEARANCE_DIA"),),
            ),
            "clearance_for": (
                part.PLATE_CLEARANCE_SPEC.size,
                ((_SPEC, "PLATE_CLEARANCE_SPEC"),),
            ),
            "thru": (True, ((_SPEC, "PLATE_CLEARANCE_SPEC"), (_SELF, "build"))),
            "station": _reference(
                _x,
                part.PLATE_HOLE_POSITION_TOLERANCE_MM,
                "PLATE_HOLE_POSITION_TOLERANCE_MM",
                (_SPEC, "PLATE_HOLE_XS"),
                (_SELF, "FRONT_KEEP"),
            ),
            "station_nominal": (_x, ((_SPEC, "PLATE_HOLE_XS"),)),
            "station_from": ("locating_end", ((_SELF, "FRONT_KEEP"),)),
            "height": _reference(
                part.PLATE_HOLE_Y,
                part.PLATE_HOLE_POSITION_TOLERANCE_MM,
                "PLATE_HOLE_POSITION_TOLERANCE_MM",
                (_SPEC, "PLATE_HOLE_Y"),
                (_SELF, "FRONT_KEEP"),
            ),
            "height_nominal": (part.PLATE_HOLE_Y, ((_SPEC, "PLATE_HOLE_Y"),)),
            "height_from": ("locating_edge", ((_SELF, "FRONT_KEEP"),)),
            "dimension_type": ("reference", ((_SELF, "REFERENCE_DIMENSIONS"),)),
            "callout": (NOTE_LINK, ((_SELF, "NOTE_LINK"),)),
            # The pair drill (MHA-MS-02's callout: 2X Ø.073 ↓.30 MATCH-DRILL
            # FROM MHA-MS-03 STOP PLATE): the #49 pilot through this plate
            # and into the block to .30 below the block's mating face.
            "pair_pilot_dia": (
                part.PLATE_TAP_DRILL_DIA,
                ((_SPEC, "PLATE_TAP_DRILL_DIA"),),
            ),
            "pair_pilot_depth_in_mate": (
                limits(
                    part.PLATE_TAP_DRILL_DEPTH,
                    part.TAP_DEPTH_PRECISION,
                    unit=part.UNIT,
                ),
                ((_SPEC, "PLATE_TAP_DRILL_DEPTH"), (_SPEC, "TAP_DEPTH_TOLERANCE_MM")),
            ),
            "pair_pilot_depth_in_mate_nominal": (
                part.PLATE_TAP_DRILL_DEPTH,
                ((_SPEC, "PLATE_TAP_DRILL_DEPTH"),),
            ),
            "mate": (
                _config.parts("ms-stop-block")["number"],
                ((_SPEC, "PLATE_TAP_SPEC"),),
            ),
        },
        precision={
            "dia": part.HOLE_CALLOUT_PRECISION,
            "station": _P[_dim],
            "height": _P["PlateFromHeadFace"],
            "pair_pilot_depth_in_mate": part.TAP_DEPTH_PRECISION,
        },
    )


def _append_callout_lines(display: Any, lines: str) -> None:
    """Append text rows below the native callout; its variables stay live."""
    native = _early_bound(display, "IDisplayDimension")
    if not native.IsHoleCallout():
        raise RuntimeError("stop plate function line requires a native hole callout")
    revised = str(native.GetText(5) or "").rstrip("\r\n") + "\n" + lines
    native.SetText(1, revised)  # swDimensionTextPrefix; void return
    if str(native.GetText(5) or "") != revised:
        raise RuntimeError("stop plate callout function line did not persist")


def _outside_arrow(display: Any) -> None:
    """One outside arrow on the dimensioned circle; no leader through its centre."""
    display = _early_bound(display, "IDisplayDimension")
    display.ArrowSide = 1  # swDimArrowsOutside
    display.SetSecondArrow(False, False)  # UseDoc, SecondArrow
    if (int(display.ArrowSide) != 1 or bool(display.GetUseDocSecondArrow())
            or bool(display.GetSecondArrow())):
        raise RuntimeError("stop plate drill arrow styling did not persist")


def _style_plate_chamfer(adapter: Any, annotations: list[Any]) -> None:
    """Keep two separate native dimensions, never a pseudo combined callout."""
    remaining = {"RoofChamferSize": "2X ", "RoofChamferAngle": ""}
    for annotation in annotations:
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        native = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        # Prefix only: SetText(All) would suppress the model-owned value.
        definition = str(native.GetText(5) or "")
        revised = prefix + definition
        native.SetText(1, revised)
        if str(native.GetText(5) or "") != revised:
            raise RuntimeError("native plate chamfer prefix did not persist")
    if remaining:
        raise RuntimeError(f"missing native plate chamfer dimensions: {sorted(remaining)}")


def _mark_reference_dimensions(adapter: Any, annotations: list[Any]) -> None:
    """Parenthesize the three hole locations and the stock thickness
    (REFERENCE_DIMENSIONS), one native dimension each."""
    references = [
        (name, annotation)
        for annotation in annotations
        if (name := dimension_name(adapter, annotation)) in REFERENCE_DIMENSIONS
    ]
    if sorted(name for name, _ in references) != sorted(REFERENCE_DIMENSIONS):
        raise RuntimeError(
            f"expected one native reference dimension each: {sorted(REFERENCE_DIMENSIONS)}"
        )
    for name, annotation in references:
        set_reference_dimension(adapter, annotation, label=f"{name} reference")


def _label_locating_edges(adapter: Any, front: Any) -> None:
    """Leader the match-drill X=0 end and Y=0 edge on the cover-face view."""
    face_z = part.PLATE_Z_MIN / 1000.0
    for text, model_xyz, note_xy in (
        (part.LOCATING_END_NOTE, (0.0, 1.0 / 1000.0, face_z), LOCATING_END_XY),
        (part.LOCATING_EDGE_NOTE, (LOCATING_EDGE_X_MM / 1000.0, 0.0, face_z), LOCATING_EDGE_XY),
    ):
        edge_xy = model_point_in_view(adapter, front, model_xyz, label=text.lower())
        add_attached_note(adapter, front, text=text, entity_xy=edge_xy,
                          note_xy=note_xy, label=text.lower())


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop cover missing: {SOURCE}")
    check("open stop cover", adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout,
                                        unit=part_drawing_unit("ms-stop-plate"))
    stamp_drawing_summary(adapter, drawing, {
        0: "Measuring Stick Stop Plate Manufacturing Drawing",
        1: "Harmonic Analyzer hobby-machinist book drawing",
        2: "Harmonic Analyzer Project", 3: "brass stop plate; separate cover; clearance holes",
        4: "Generated from the project-owned ASME B drawing standard",
    })
    front = place_view(adapter, str(SOURCE), "*Back", *FRONT_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Left", *RIGHT_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2.0, 1.0))
    annotations = []
    for view, keep, label in ((front, FRONT_KEEP, "cover face"), (right, RIGHT_KEEP, "cover edge")):
        set_hidden_lines_removed(adapter, view)
        annotations += curate_view_dimensions(adapter, view, keep=keep, view_label=label,
                                               dimensions_by_feature=part.PLATE_DRAWING_DIMENSIONS)
    set_hidden_lines_removed(adapter, iso)
    _style_plate_chamfer(adapter, annotations)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _mark_reference_dimensions(adapter, annotations)
    # The rim's lower outboard point, off the .160 witness through the centre,
    # so the leader from the callout below crosses no station line.
    rim = part.PLATE_CLEARANCE_DIA / 2.0 / math.sqrt(2.0)
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + rim) / 1000.0,
            (part.PLATE_HOLE_Y - rim) / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # *Back reverses X: this is the left-sheet hole. Rule 26: size first, so
    # the native callout prints 2X Ø.094 THRU with no process word ahead of it.
    clearance = add_native_hole_callout(adapter, front, edge_xy=edge, callout_xy=CLEARANCE_CALLOUT_XY,
                                        label="two cover clearance holes")
    _append_callout_lines(clearance, NOTE_LINK)
    set_hole_callout_precision(clearance, CLEARANCE_PRECISION, label="two cover clearance holes")
    _outside_arrow(clearance)
    _label_locating_edges(adapter, front)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("stop clearance centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.PLATE_DRAWING_VALUES_BY_NAME,
        part.PLATE_DRAWING_PRECISION_BY_NAME,
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.124)
    if add_note(adapter, MATCHED_PAIR_NOTE, *MATCHED_PAIR_NOTE_XY) is None:
        raise RuntimeError("failed to add the stop plate matched-pair note")
    return finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
