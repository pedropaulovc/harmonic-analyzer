r"""Manufacturing drawing of the separate brass stop cover.

The sheet prints decimal inch (the part's ``drawing_unit: in``). The cover
face locates both clearance holes from one finished end and the head-side
edge. The aligned end view gives thickness; the native clearance callout
gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
The two native, model-owned drill steps use different holes so their leaders
never cross: the pilot's phantom circle from the right, the finished
clearance rim from the left, each with one outside arrow on its own circle.
Separate native chamfer size and angle retain their model-owned precision.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _config
import _telemetry
import ms_stop_spec as part
from _check import check
from solidworks_mcp.adapters.sw_type_info import constant
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
from _drawing_dimensions import set_dimension_callouts
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _part_properties import part_drawing_unit
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ms_stop_plate"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"])
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.175, 0.170)
# Far enough right that the pilot callout and the thickness text end clear of it.
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
    # Right of the outline and below the chamfer-size dimension line.
    "PilotDrillDiameter": (0.285, 0.178),
}
# Text left of the thin edge view, so neither witness line strikes it.
RIGHT_KEEP = {"PlateThickness": (0.327, 0.225)}
HOLE_STATION_FIT = f"LOCATES MS-STOP-BLOCK\n{_config.parts('ms-stop-block')['number']} TAPS"
DIMENSION_CALLOUTS = {
    "PilotDrillDiameter": (
        "LAYOUT ON THIS PLATE; PILOT\n"
        f"THROUGH INTO MS-STOP-BLOCK {_config.parts('ms-stop-block')['number']}\n"
        f"CLAMPED, {part.MATCH_DRILL_DATUM_ALIGNMENT}\n"
        f"{part.MATCHED_PAIR_NOTE}"
    ),
    # The +/-.004 hole stations become the block's tapped-hole stations.
    **{name: HOLE_STATION_FIT for name in part.PLATE_LOCATION_DIMENSIONS},
    # The thickness band sets the plate screws' reach into the blind taps.
    "PlateThickness": (
        "SETS SCREW REACH IN\nMS-STOP-BLOCK\n"
        f"{_config.parts('ms-stop-block')['number']} TAPS"
    ),
}
# The left-sheet hole's clearance approaches from the left, between the
# overall height's witnesses; the right-sheet hole's pilot from the right.
# Two rows keep the text (one row was 103 mm at run 308) clear of the .56
# dimension line; the native size row reads DRILL 2X <dia> THRU ALL.
CLEARANCE_CALLOUT_XY = (0.080, 0.178)
CLEARANCE_PROCESS = "REMOVE PLATE; THEN\nDRILL"
CLEARANCE_PRECISION = {"hw-diam": part.HOLE_CALLOUT_PRECISION}
# Leadered labels name the X=0 end and Y=0 edge the match-drill clamp aligns.
# Note positions are the text's upper-left corner.
LOCATING_END_XY = (0.228, 0.128)
# The edge label sits wholly left of its leader's landing point, so the
# leader leaves the text's end, between the two hole witness lines.
LOCATING_EDGE_XY = (0.150, 0.130)
LOCATING_EDGE_X_MM = 7.0


def _style_pilot_diameter(adapter: Any, annotations: list[Any]) -> None:
    """Keep the model diameter's leader on the concentric, earlier pilot step."""
    annotation = next(
        item for item in annotations
        if dimension_name(adapter, item) == "PilotDrillDiameter"
    )
    annotation = _early_bound(annotation, "IAnnotation")
    native = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(native.Type2) != 6:  # swDiameterDimension
        raise RuntimeError("match-drill pilot is not a native model diameter")
    # The importer shows this construction circle inside the right-sheet
    # clearance; its own outside arrow lands on it, not on the clearance rim.
    _outside_arrow(native)
    definition = str(native.GetText(5) or "")
    prefix = f"2X {definition}"
    native.SetText(1, prefix)
    if str(native.GetText(5) or "") != prefix:
        raise RuntimeError("native pilot quantity prefix did not persist")


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


# The shown Ø1.85 pilot reference circle read as a tapped-hole symbol inside
# the opened Ø2.40 hole (machinist review, run 20261023T231957372Z-0d874475).
# A phantom circle is the convention for a removed, earlier-stage feature.
# swLineStyles_e.swLinePHANTOM = 2, swLineWeights_e.swLW_THIN = 0.
CONSTRUCTION_CURVE_FONT = {
    "swLineFontConstructionCurvesStyle": 2,
    "swLineFontConstructionCurvesThickness": 0,
}


@_telemetry.traced("drawing.ms_stop_plate_construction_font")
def _construction_curve_font(drawing: Any) -> None:
    """Construction curves phantom and thin: the pilot reads as an earlier stage."""
    extension = _early_bound(drawing.Extension, "IModelDocExtension")
    option = constant("swDetailingNoOptionSpecified")
    for name, value in CONSTRUCTION_CURVE_FONT.items():
        pref = constant(name)
        if not extension.SetUserPreferenceInteger(pref, option, value):
            raise RuntimeError(f"failed to set document line font {name}")
        if int(extension.GetUserPreferenceInteger(pref, option)) != value:
            raise RuntimeError(f"document line font {name} readback differs")


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


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source stop cover missing: {SOURCE}")
    check("open stop cover", await adapter.open_model(str(SOURCE)))
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(adapter.currentModel, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout,
                                        unit=part_drawing_unit("ms-stop-plate"))
    _construction_curve_font(drawing)
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
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _style_pilot_diameter(adapter, annotations)
    _style_plate_chamfer(adapter, annotations)
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + part.PLATE_CLEARANCE_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # *Back reverses X: this is the left-sheet hole, away from the imported
    # pilot. Two native callouts avoid an unverified note dimension-link
    # format while keeping both 2X quantities and sizes live.
    # Unclamping first makes the opening this plate's alone, not the block's.
    clearance = add_native_hole_callout(adapter, front, edge_xy=edge, callout_xy=CLEARANCE_CALLOUT_XY,
                                        label="two cover clearance holes",
                                        process=CLEARANCE_PROCESS)
    set_hole_callout_precision(clearance, CLEARANCE_PRECISION, label="two cover clearance holes")
    _outside_arrow(clearance)
    _label_locating_edges(adapter, front)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("stop clearance centre marks failed")
    assert_manufacturing_dimensions(
        adapter, annotations, part.PLATE_DRAWING_VALUES_BY_NAME,
        part.PLATE_DRAWING_PRECISION_BY_NAME,
        bands={
            "PlateThickness": (-part.PLATE_THICKNESS_TOLERANCE_MM, part.PLATE_THICKNESS_TOLERANCE_MM),
            **{name: (-part.PLATE_HOLE_POSITION_TOLERANCE_MM, part.PLATE_HOLE_POSITION_TOLERANCE_MM)
               for name in part.PLATE_LOCATION_DIMENSIONS},
        },
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.124)
    return await finalize_drawing(adapter, OUTPUTS,
                                  pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                  scale=SHEET_SCALE, layout=SPEC.layout)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
