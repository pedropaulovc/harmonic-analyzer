r"""Create the integral MHA-102 pinion-arbor manufacturing drawing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_arbor_spec import (
    BACK_JOURNAL_Z,
    CROSS_HOLE_CALLOUT,
    DRAWING_PRECISION_BY_NAME,
    FRONT_JOURNAL_Z,
    HEAD_CAP_SAG,
    HEAD_CENTER_Z,
    HEAD_FRONT_Z,
    OVERALL_LEN,
    SHAFT_DIA,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    delete_view,
    iter_views,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png
SHEET_SCALE = (1.0, 1.0)
PRINCIPAL_CENTER = (0.200, 0.170)
ISO_CENTER = (0.365, 0.225)
DETAIL_CENTER = (0.165, 0.235)
DETAIL_SCALE = (2, 1)
DETAIL_RADIUS_MM = 15.0
# The native "DETAIL A / SCALE 2:1" label sits centred under its own detail
# circle, this far below it (the label's anchor is its top edge): clear of the
# HeadLen text that rides the circle's lower edge.  The bond-zone ShaftDia
# line then moves right of the label so its upper arrow misses "SCALE 2:1".
DETAIL_LABEL_DROP = 0.012
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1]
    - DETAIL_RADIUS_MM * DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
    - DETAIL_LABEL_DROP,
)
# Every turned diameter lives in an end-on Front-plane profile sketch, so the
# end-on donor imports all three and each moves onto the 1:1 profile.
DONOR_KEEP = {
    "ShaftDia": (0.030, 0.145),
    "NeckDia": (0.055, 0.145),
    "HeadDia": (0.030, 0.215),
}
# Profile scale is 1:1 with the head to the right, so model z maps to sheet
# x = 0.200 - (z - 106.725) / 1000: the front land (z 49-61) spans x
# 0.246-0.258 and the back land (z 202-214) x 0.093-0.105.  Land lengths ride
# just above the shaft, each land's diameter hangs below it with its Ra symbol
# beside it, and the two stations from the head shoulder stack under those.
PRINCIPAL_KEEP = {
    "FrontJournalLen": (0.252, 0.188),
    "BackJournalLen": (0.099, 0.188),
    "FrontJournalDia": (0.250, 0.150),
    "BackJournalDia": (0.099, 0.150),
    "FrontJournalFromHeadRear": (0.283, 0.130),
    "BackJournalFromHeadRear": (0.207, 0.115),
    # Right of the overall-length witness at the front crown apex (x 0.3215).
    "NeckLen": (0.340, 0.100),
    "BackRimFromHeadRear": (0.205, 0.095),
    "OverallLen": (0.205, 0.080),
    "BackCapSagDim": (0.055, 0.220),
    # Radial leader down-left from the back crown, below the shaft axis and
    # clear of the (1.2) sag reference above it and the overall witnesses.
    "BackCapR": (0.045, 0.140),
}
DETAIL_KEEP = {
    "HeadLen": (0.165, 0.201),
    "HeadCapR": (0.195, 0.262),
    "HeadCapSagDim": (0.205, 0.210),
    # Above the hole's centre line, so the leader drops onto the hole edge.
    "CrossHoleDia": (0.245, 0.256),
}
# The head and neck sit inside detail A's fence at the right end of the
# profile (x 0.296-0.320, axis y 0.171): the neck's text rides above its own
# station, and the head's is pushed right of the crown so the two stay apart
# and clear of the isometric's lower end and the NeckLen/OverallLen witnesses.
DIAMETER_POSITIONS = {
    "HeadDia": (0.340, 0.192),
    "NeckDia": (0.300, 0.194),
    # Below the bond zone, between the two land diameters.
    "ShaftDia": (0.195, 0.150),
}
DIMENSION_CALLOUTS = {
    "BackRimFromHeadRear": "FROM BACK CROWN ROOT TO HEAD SHOULDER",
    "OverallLen": "OVERALL",
    "BackCapSagDim": "BACK CROWN",
    "CrossHoleDia": CROSS_HOLE_CALLOUT,
    "FrontJournalDia": "JOURNAL",
    "BackJournalDia": "JOURNAL",
}
# The turning axis runs the full part and this far past each crown.
AXIS_OVERSHOOT_MM = 3.0
# Each land's Ra symbol hangs off the lower flank on the land's head side of
# its diameter line, clear of the split-line rings at the land ends.
JOURNAL_FINISHES = {
    "front_journal": (FRONT_JOURNAL_Z + 2.0, (0.262, 0.150)),
    "back_journal": (BACK_JOURNAL_Z + 2.0, (0.108, 0.150)),
}


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
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, source_view)):
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
    drawing.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
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


def _head_detail(adapter: Any, parent_view: Any) -> Any:
    """Create an enlarged native detail of the crowded turned head."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate integral-arbor detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter,
        parent_view,
        (0.0, 0.0, HEAD_CENTER_Z / 1000.0),
        label="integral-arbor head detail centre",
    )
    radius = DETAIL_RADIUS_MM / 1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(
            point.MultiplyTransform(transform), "IMathPoint"
        )
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create integral-arbor detail fence")
    detail = drawing.CreateDetailViewAt4(
        *DETAIL_CENTER,
        0.0,
        0,
        *DETAIL_SCALE,
        "A",
        1,
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create integral-arbor head detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("integral-arbor head detail has invalid bounds")
    target = [
        position[axis]
        + DETAIL_CENTER[axis]
        - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position integral-arbor head detail")
    draw.EditRebuild3()
    return detail


def _add_turning_axis(adapter: Any, view: Any) -> None:
    """Draw one centreline over the whole turned axis.

    The journal split lines cut the Ø8 cylinder into five faces, so a
    face-derived ``InsertCenterLine2`` would cover a single zone.  The axis is
    instead a view-sketch centreline between two model points on it, created
    direct-to-database so screen-space inference cannot snap an end onto the
    crown apex.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the integral-arbor profile for its axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    front_z = HEAD_FRONT_Z - HEAD_CAP_SAG - AXIS_OVERSHOOT_MM
    points = []
    for z in (front_z, front_z + OVERALL_LEN + 2.0 * AXIS_OVERSHOOT_MM):
        x, y = model_point_in_view(
            adapter, view, (0.0, 0.0, z / 1000.0), label="integral-arbor axis end"
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError("failed to create the integral-arbor turning axis")
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("integral-arbor turning axis colour did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


def _position_detail_label(adapter: Any, detail: Any) -> None:
    """Centre the native detail label under its own detail circle."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before positioning detail label")
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native detail label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*DETAIL_LABEL_XY, 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native detail label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, target) > 1e-8:
        raise RuntimeError(f"native detail label position did not persist: {actual}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Integral Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "integral arbor and grip head; reamed, bonded crossrod hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Front", 0.030, 0.180, scale=(2, 1))
    # Looking along model Y presents the reamed cross-hole as a true
    # circle while retaining the entire turned profile in one horizontal view.
    principal = place_view(
        adapter, str(SOURCE), "*Top", *PRINCIPAL_CENTER, scale=SHEET_SCALE
    )
    native_principal = _early_bound(principal, "IView")
    native_principal.Angle = -math.pi / 2.0
    if abs(math.remainder(float(native_principal.Angle) + math.pi / 2.0, 2.0 * math.pi)) > 1e-9:
        raise RuntimeError("failed to orient the integral arbor horizontally")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (donor, principal, iso):
        set_hidden_lines_removed(adapter, view)

    detail = _head_detail(adapter, principal)
    set_hidden_lines_removed(adapter, detail)
    donor_annotations = curate_view_dimensions(
        adapter, donor, keep=DONOR_KEEP, view_label="diameter donor"
    )
    principal_annotations = curate_view_dimensions(
        adapter, principal, keep=PRINCIPAL_KEEP, view_label="integral-arbor profile"
    )
    detail_annotations = curate_view_dimensions(
        adapter, detail, keep=DETAIL_KEEP, view_label="integral-arbor head detail"
    )
    for label, kept in (
        ("donor", donor_annotations),
        ("principal", principal_annotations),
        ("detail", detail_annotations),
    ):
        names = sorted(dimension_name(adapter, annotation) for annotation in kept)
        _telemetry.info(
            f"pinion-arbor {label} view kept {len(kept)} imported dimensions: {names}",
            view=label,
            kept=len(kept),
            names=",".join(names),
        )
    moved_diameters = []
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        moved_diameters.append(
            _move_dimension(
                adapter,
                annotation,
                principal,
                DIAMETER_POSITIONS[name],
                source_view=donor,
            )
        )
    principal_count = len(_early_bound(principal, "IView").GetAnnotations() or ())
    _telemetry.info(
        f"pinion-arbor moved {len(moved_diameters)} diameters donor -> principal; "
        f"principal now carries {principal_count} annotations",
        moved=len(moved_diameters),
        principal_annotations=principal_count,
    )
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")
    annotations = [
        *moved_diameters,
        *principal_annotations,
        *detail_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name, label in {
        "HeadCapSagDim": "front-crown height reference",
        "BackCapSagDim": "back-crown descriptive reference",
        "OverallLen": "overall length reference",
    }.items():
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {label}")
        set_reference_dimension(adapter, matches[0], label=label)

    if not auto_center_marks(adapter, detail, holes=True, size=0.0025):
        raise RuntimeError("failed to add center mark to the detailed grip cross-hole")
    _add_turning_axis(adapter, principal)
    for key, (station_z, symbol_xy) in JOURNAL_FINISHES.items():
        land_x, axis_y = model_point_in_view(
            adapter,
            principal,
            (0.0, 0.0, station_z / 1000.0),
            label=f"arbor {key} finish station",
        )
        add_surface_finish(
            adapter,
            principal,
            edge_xy=(land_x, axis_y - SHAFT_DIA / 2000.0),
            symbol_xy=symbol_xy,
            control=surface_finish_by_key(SURFACE_FINISHES, key),
            label=f"arbor {key} finish",
            entity_type="SILHOUETTE",
            char_height=0.0025,
        )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.335, 0.255)
    _position_detail_label(adapter, detail)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Integral Pinion Arbor Manufacturing Drawing",
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
