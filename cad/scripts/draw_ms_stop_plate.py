r"""Manufacturing drawing of the separate brass stop cover.

The sheet prints decimal inch (the part's ``drawing_unit: in``). The cover
face locates both clearance holes from one finished end and the head-side
edge. The aligned end view gives thickness; the native clearance callout
gives the decimal drill size, never merely a screw designation.
The shared millimetre hole-mouth coordinates convert to COM metres before
projection into the cover-side *Back view.
The two native, model-owned drill steps use different holes: the pilot's
construction circle at sheet right and the finished clearance rim at left.
Native outside arrows identify each circle, with settled identity and landing
readbacks. The clearance's native diameter variable prints three inch places;
the actual #2 close drill is .094, not the rounded .09's inferred .090.
Separate native chamfer size and angle retain their model-owned precision.
Every imported dimension prints the text and quantity prefix its part
authored (``ms_stop_callouts``); the sheet writes none, and the source part
is proved clean -- file SHA-256 and save flag -- before any view and at every
save/close boundary.
"""

from __future__ import annotations

import argparse
import math
import sys
from enum import StrEnum
from typing import Any

import _telemetry
import ms_stop_callouts as callouts
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
    rebuild_drawing,
)
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_edges import scan_view_edges
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_view_display import set_hidden_lines_removed
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _ms_drawing_contract import assert_manufacturing_dimensions
from _drawing_source_guard import (
    assert_source_closed,
    capture_clean_source,
    source_checkpoint,
)
from _ms_drawing_guards import assert_imported_text
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

# The drawing's own registry package: its drawing_unit (in) selects the sheet.
PACKAGE = "ms-stop-plate"
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
# The second hole's clearance approaches from the left, between the overall
# height's witnesses; the right hole's pilot approaches from the right.
CLEARANCE_CALLOUT_XY = (0.080, 0.178)
CLEARANCE_PROCESS = "REMOVE PLATE; THEN DRILL\n"
# Leadered labels name the X=0 end and Y=0 edge the match-drill clamp aligns.
# Note positions are the text's upper-left corner.
LOCATING_END_XY = (0.228, 0.128)
# The edge label sits wholly left of its leader's landing point, so the
# leader leaves the text's end, between the two hole witness lines.
LOCATING_EDGE_XY = (0.150, 0.130)
LOCATING_EDGE_X_MM = 7.0


class DrillStep(StrEnum):
    PILOT = "pilot"
    CLEARANCE = "clearance"


def _assert_pilot_diameter(adapter: Any, annotations: list[Any]) -> None:
    """The pilot step is the model's own diameter, its leader on the
    concentric, earlier pilot circle; read only."""
    annotation = next(
        item for item in annotations
        if dimension_name(adapter, item) == "PilotDrillDiameter"
    )
    annotation = _early_bound(annotation, "IAnnotation")
    native = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if int(native.Type2) != 6:  # swDiameterDimension
        raise RuntimeError("match-drill pilot is not a native model diameter")


def _outside_drill_arrow(display: Any) -> None:
    """A single outside arrow points inward to its own native circle."""
    display = _early_bound(display, "IDisplayDimension")
    display.ArrowSide = 1  # swDimArrowsOutside
    display.SetSecondArrow(False, False)
    if (int(display.ArrowSide) != 1 or bool(display.GetUseDocSecondArrow())
            or bool(display.GetSecondArrow())):
        raise RuntimeError("stop plate drill arrow styling did not persist")


def _pilot_attachment(source: Any) -> Any:
    """Resolve the named model sketch, never a hit-test on concentric circles."""
    feature = _early_bound(source, "IPartDoc").FeatureByName("PilotDrillReference")
    if feature is None:
        raise RuntimeError("missing model pilot reference")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch",
    )
    segments = tuple(sketch.GetSketchSegments() or ())
    if len(segments) != 1:
        raise RuntimeError("model pilot reference must own exactly one circle")
    segment = _early_bound(segments[0], "ISketchSegment")
    if int(segment.GetType()) != 1 or not bool(segment.ConstructionGeometry):
        raise RuntimeError("model pilot reference is not a construction circle")
    arc = _early_bound(segment, "ISketchArc")
    center = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    if (abs(float(arc.GetRadius()) - part.PLATE_TAP_DRILL_DIA / 2000.0) > 1e-8
            or abs(float(center.X) - part.PLATE_HOLE_XS[0] / 1000.0) > 1e-8
            or abs(float(center.Y) - part.PLATE_HOLE_Y / 1000.0) > 1e-8):
        raise RuntimeError("model pilot reference circle differs from its drill station")
    return segments[0]


def _assert_drill_attachment(
    adapter: Any, view: Any, annotation: Any, entity: Any, *,
    step: DrillStep,
) -> None:
    """Prove the native entity AND actual printed arrow tip, after rebuilding.

    Imported pilot identity must match the independently resolved source sketch
    segment, not merely a concentric edge. Refusals retain every attachment
    predicate's readback so a drawing-context wrapper mismatch can be
    distinguished from missing, wrong-type or dangling geometry.
    """
    annotation = _early_bound(annotation, "IAnnotation")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    kinds = tuple(int(kind) for kind in (annotation.GetAttachedEntityTypes() or ()))
    step = DrillStep(step)
    is_pilot = step is DrillStep.PILOT
    expected_kinds = (10, 24) if is_pilot else (1,)  # sketch segment / external segment / edge
    label = step.value
    dangling = bool(annotation.IsDangling())
    count = int(annotation.GetAttachedEntityCount3())
    presence = tuple(item is not None for item in attached)
    comparable = (
        count == 1 and len(attached) == 1 and presence == (True,)
        and len(kinds) == 1 and kinds[0] in expected_kinds
    )
    same = int(adapter.swApp.IsSame(attached[0], entity)) if comparable else None
    if dangling or not comparable or same != 1:
        expected_source = "PilotDrillReference" if is_pilot else "PlateClearances"
        raise RuntimeError(
            f"stop plate {label} lost its native circle attachment: "
            f"count={count}, entities={len(attached)}, types={kinds}, "
            f"entity_presence={presence}, dangling={dangling}, IsSame={same}, "
            f"expected_types={expected_kinds}, expected_source={expected_source}, "
            f"expected_entity_present={entity is not None}"
        )
    index = 0 if is_pilot else 1
    center = model_point_in_view(adapter, view, (
        part.PLATE_HOLE_XS[index] / 1000.0, part.PLATE_HOLE_Y / 1000.0,
        (0.0 if is_pilot else part.PLATE_Z_MIN) / 1000.0,
    ), label=f"{label} arrow circle")
    diameter = part.PLATE_TAP_DRILL_DIA if is_pilot else part.PLATE_CLEARANCE_DIA
    radius = diameter / 2000.0 * float(_early_bound(view, "IView").ScaleDecimal)
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError(f"stop plate {label} must have one native arrow")
    arrow = tuple(float(value) for value in data.GetArrowHeadAtIndex2(0))
    # 0.1 sheet mm is well below the >1 mm pilot/clearance radial separation.
    if (len(arrow) < 3 or not all(math.isfinite(value) for value in arrow[:3])
            or abs(math.dist(arrow[:2], center) - radius) > 0.0001):
        raise RuntimeError(f"stop plate {label} arrow does not land on its own circle")


# The shown .073 pilot reference circle read as a tapped-hole symbol inside
# the opened clearance hole (machinist review, run 20261023T231957372Z-0d874475).
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
    source = capture_clean_source(SOURCE, adapter.currentModel, label="stop cover source")
    guard = source_checkpoint(source)
    properties = ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity")
    read_required_properties(source.model, properties,
                             required=("Number", "Material Specification", "Finish", "Quantity"))
    drawing, _sheet = new_project_drawing(adapter, property_view=PART_STEM,
                                        scale=SHEET_SCALE, layout=SPEC.layout,
                                        package_name=PACKAGE, checkpoint=guard)
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
    assert_imported_text(adapter, annotations, callouts.PLATE_CALLOUTS, callouts.PLATE_PREFIXES)
    _assert_pilot_diameter(adapter, annotations)
    pilot_annotation = next(
        item for item in annotations
        if dimension_name(adapter, item) == "PilotDrillDiameter"
    )
    pilot_entity = _pilot_attachment(source.model)
    _outside_drill_arrow(_early_bound(pilot_annotation, "IAnnotation").GetSpecificAnnotation())
    clearance_entity = scan_view_edges(front, label="cover clearance").circle_at(
        (part.PLATE_HOLE_XS[1], part.PLATE_HOLE_Y, part.PLATE_Z_MIN),
        part.PLATE_CLEARANCE_DIA / 2.0, axis=(0.0, 0.0, 1.0),
        label="left-sheet cover clearance",
    ).edge
    edge = model_point_in_view(
        adapter, front, (
            (part.PLATE_HOLE_XS[1] + part.PLATE_CLEARANCE_DIA / 2.0) / 1000.0,
            part.PLATE_HOLE_Y / 1000.0, part.PLATE_Z_MIN / 1000.0,
        ), label="plate clearance mouth")
    # *Back reverses X: clearance uses the left-sheet hole, away from the
    # right-sheet pilot. The named visible rim also defeats ambiguous picks.
    clearance = add_native_hole_callout(
        adapter, front, edge_xy=edge, edge=clearance_entity,
        callout_xy=CLEARANCE_CALLOUT_XY, label="two cover clearance holes",
        process=CLEARANCE_PROCESS,
    )
    set_hole_callout_precision(
        clearance, {"hw-diam": part.HOLE_CALLOUT_PRECISION},
        label="cover clearance drill",
    )
    _outside_drill_arrow(clearance)
    rebuild_drawing(adapter, label="stop plate drill arrows")

    def assert_drill_attachments() -> None:
        _assert_drill_attachment(
            adapter, front, pilot_annotation, pilot_entity, step=DrillStep.PILOT,
        )
        _assert_drill_attachment(
            adapter, front, _early_bound(clearance, "IDisplayDimension").GetAnnotation(),
            clearance_entity, step=DrillStep.CLEARANCE,
        )

    assert_drill_attachments()
    _label_locating_edges(adapter, front)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("stop clearance centre marks failed")
    # The thickness and the master stations ride the title block's .XXX.
    assert_manufacturing_dimensions(
        adapter, annotations, part.PLATE_DRAWING_VALUES_BY_NAME,
        part.PLATE_DRAWING_PRECISION_BY_NAME,
        angular=frozenset({"RoofChamferAngle"}),
    )
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Isometric View Note", ISO_CENTER[0] - 0.030, 0.124)
    artifacts = await finalize_drawing(adapter, OUTPUTS,
                                       pdf_title="Measuring Stick Stop Plate Manufacturing Drawing",
                                       scale=SHEET_SCALE, layout=SPEC.layout,
                                       package_name=PACKAGE, checkpoint=guard,
                                       settled_checks=(assert_drill_attachments,))
    assert_source_closed(source, stage="after finalize")
    return artifacts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
