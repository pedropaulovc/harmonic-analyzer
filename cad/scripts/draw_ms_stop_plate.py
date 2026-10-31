r"""Manufacturing drawing of the separate brass stop cover.

The sheet prints decimal inch (the part's ``drawing_unit: in``). The cover
face locates both clearance holes from one finished end and the head-side
edge. The aligned end view gives thickness; the native clearance callout
gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
The native clearance callout carries the match-drill line; the pilot and
opening sequence lives in the assembly sheet's step 1, not on this part.
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
HOLE_STATION_FIT = f"LOCATES MS-STOP-BLOCK\n{_config.parts('ms-stop-block')['number']} TAPS"
DIMENSION_CALLOUTS = {
    # The +/-.004 hole stations become the block's tapped-hole stations.
    **{name: HOLE_STATION_FIT for name in part.PLATE_LOCATION_DIMENSIONS},
    # The thickness band sets the plate screws' reach into the blind taps.
    "PlateThickness": (
        "SETS SCREW REACH IN\nMS-STOP-BLOCK\n"
        f"{_config.parts('ms-stop-block')['number']} TAPS"
    ),
}
# The three-row callout is wider than the room between the .56 witnesses, so
# it sits below the cover face, left of the hole-station texts.
CLEARANCE_CALLOUT_XY = (0.075, 0.100)
# Function, not procedure (rule 7 flags the pair at its match-drill callouts).
CLEARANCE_FUNCTION = (
    f"MATCH DRILL WITH MS-STOP-BLOCK {_config.parts('ms-stop-block')['number']}\n"
    f"{part.MATCHED_PAIR_NOTE}"
)
CLEARANCE_PRECISION = {"hw-diam": part.HOLE_CALLOUT_PRECISION}
# Leadered labels name the X=0 end and Y=0 edge the match-drill clamp aligns.
# Note positions are the text's upper-left corner.
LOCATING_END_XY = (0.228, 0.128)
# The edge label sits wholly left of its leader's landing point, so the
# leader leaves the text's end, between the two hole witness lines.
LOCATING_EDGE_XY = (0.150, 0.130)
LOCATING_EDGE_X_MM = 7.0


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
    _style_plate_chamfer(adapter, annotations)
    # The rim's lower outboard point, off the .160 witness through the centre,
    # so the leader from the callout below crosses no station line.
    rim = part.PLATE_CLEARANCE_DIA / 2.0 / math.sqrt(2.0)
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + rim) / 1000.0,
            (part.PLATE_HOLE_Y - rim) / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # *Back reverses X: this is the left-sheet hole.
    clearance = add_native_hole_callout(adapter, front, edge_xy=edge, callout_xy=CLEARANCE_CALLOUT_XY,
                                        label="two cover clearance holes")
    _append_callout_lines(clearance, CLEARANCE_FUNCTION)
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
