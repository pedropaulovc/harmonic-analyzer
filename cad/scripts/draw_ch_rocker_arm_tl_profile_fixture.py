r"""Create the drawing for the rocker arm profile fixture (MHA-CH-006-TL-02).

Three landscape sheets:

* PLAN (1:2): the plate plan with its outline located from the locating bore
  axis, section D-D through the bore axis for every height, detail E for the
  bore and the hub-stand counterbore, and the hole callouts.
* TAGS (1:1): the plan again with one arrowed tag per pocket and hole, so the
  schedules can locate them without a dimension forest on the plan.
* SCHEDULE (1:4): the feature schedule (every tag located from the bore axis)
  and the shaded isometric.

The bonded-part schedule sits under the tagged plan on TAGS.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _select_view_entity,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    check_drawing_layout,
    create_blank_drawing_sheets,
    create_section_view,
    curate_view_dimensions,
    draw_note_table,
    finalize_drawing,
    model_point_in_view,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    scan_view_edges,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_rocker_arm_tl_profile_fixture_spec import (
    CLAMP_STUD_DRILL_DIA,
    CLAMP_STUD_POINTS,
    DETAIL_LABEL,
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FEATURE_SCHEDULE,
    FEATURE_SCHEDULE_HEADER,
    FEATURE_SCHEDULE_TITLE,
    HOLD_DOWN_CBORE_DIA,
    HOLD_DOWN_POINTS,
    LOCATING_BORE_DIA,
    LOCATING_BORE_FLOOR_Z,
    PAD_POCKETS,
    PAD_TOP_Z,
    PART_SCHEDULE,
    PART_SCHEDULE_HEADER,
    PART_SCHEDULE_TITLE,
    PIVOT_TAP_DRILL_DIA,
    PLATE_BOTTOM_Z,
    PLATE_EAST_X,
    PLATE_NORTH_Y,
    PLATE_SOUTH_Y,
    PLATE_TOP_Z,
    PLATE_WEST_X,
    REST_POCKETS,
    ROD_PIN_HOLE_DIA,
    ROD_PIN_HOLE_XY,
    SECTION_LABEL,
    STAND_POCKET_DEPTH,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_profile_fixture"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_NAMES = ("PLAN", "TAGS", "SCHEDULE")
SHEET_SCALES = {"PLAN": (1.0, 2.0), "TAGS": (1.0, 1.0), "SCHEDULE": (1.0, 4.0)}
# Right of the 1:1 TAGS plan's box (it reaches x 385.6 mm, run 20261007T182242302Z).
SHEET_COUNT_XY = (0.388, 0.262)

# --- Sheet PLAN -------------------------------------------------------------------
PLAN_CENTER = (0.120, 0.212)
PLAN_SCALE = (1, 2)
# Section D-D: a removed section along the bore axis (model Y 0) spanning the
# A1/B1 pads either side, so the pad tops, the hub stand and the bore stack
# read together.
SECTION_SPAN_X = (-32.0, 32.0)
SECTION_CENTER = (0.300, 0.128)
# Native view labels by their box's lower-left (sheet m). Left native, the
# section label met the title block and the detail label fell 47 mm under its
# circle onto section D-D (run 20261007T181225620Z; boxes 45.8 x 16.2 and
# 31.5 x 16.2 mm). The section label sits centred under the cut, the detail
# label right of its view box (76 mm square at 3:1, run 20261007T181821050Z).
SECTION_LABEL_LOWER_LEFT = (SECTION_CENTER[0] - 0.0229, 0.069)
SECTION_SCALE = (2, 1)
DETAIL_CENTER = (0.330, 0.212)
DETAIL_SCALE = (3, 1)
DETAIL_RADIUS_MM = 9.0
DETAIL_LABEL_LOWER_LEFT = (0.373, 0.204)
NOTES_XY = (0.016, 0.045)
# Under the plan's east half, above the elevation: on the plate it sat on H2's
# counterbore ring and crowded the plate edge (codex review of run
# 20261007T190010219Z). Text about 81 x 10 mm, centred here.
HOLD_DOWN_CALLOUT_XY = (0.168, 0.152)
# Right of the plate's east end: at x 228 its shoulder ran 15 mm along the
# PlateLength dimension line (run 20261007T185353671Z).
STUD_CALLOUT_XY = (0.250, 0.260)
# Sheet offsets (m) of each kept dimension from a projected model point (mm):
# {name: ((x, y[, z]) model mm, (dx, dy) sheet m)}.
PLAN_KEEP_AT = {
    "PlateLength": ((0.0, PLATE_NORTH_Y), (0.0, 0.009)),
    "PlateWidth": (
        (PLATE_WEST_X, (PLATE_NORTH_Y + PLATE_SOUTH_Y) / 2.0),
        (-0.011, 0.0),
    ),
    # The bore's location dimensions sit outside the plate (codex review of run
    # 20261007T190010219Z): from the west end under the plan, and from the south
    # edge right of the plate's east end.
    "PlateWestX": ((PLATE_WEST_X / 2.0, PLATE_SOUTH_Y), (0.0, -0.008)),
    "PlateSouthY": ((PLATE_EAST_X, PLATE_SOUTH_Y / 2.0), (0.008, 0.0)),
    "RodPinHoleDia": (ROD_PIN_HOLE_XY, (0.045, 0.012)),
}
# Section D-D, model (x, z) mm: the plate-top baseline ladder (counterbore and
# bore depths) right of the cut, the stand drop above the stand. A cut-only
# section has no plate face edges, so the plate's own heights go on the end
# elevation (run 20261007T175439611Z: PlateThick/PlateDrop not importable).
SECTION_KEEP_AT = {
    "StandDrop": ((-9.5, PAD_TOP_Z), (0.0, 0.010)),
    "StandPocketDepth": ((38.0, PLATE_TOP_Z - STAND_POCKET_DEPTH / 2.0), (0.0, 0.0)),
    "LocatingBoreDepth": (
        (47.0, (PLATE_TOP_Z + LOCATING_BORE_FLOOR_Z) / 2.0),
        (0.0, 0.0),
    ),
}
# Front elevation (*Bottom: model X right, Z up) projected under the plan at
# its scale: plate thickness left of it, the pad-top drop right of it (sheet
# offsets from the plate ends). A turned end view printed an empty rotation
# label over itself (run 20261007T180611940Z). Low enough to leave the
# PlateWestX dimension and the hold-down callout room under the plan.
ELEVATION_CENTER = (PLAN_CENTER[0], 0.125)
ELEVATION_KEEP_Z = {
    "PlateThick": ((PLATE_TOP_Z + PLATE_BOTTOM_Z) / 2.0, -0.012),
    "PlateDrop": ((PAD_TOP_Z + PLATE_TOP_Z) / 2.0, 0.012),
}
# Detail E, model (x, y) mm about the bore axis.
DETAIL_KEEP_AT = {
    "StandPocketDia": ((-8.0, 10.0), (0.0, 0.0)),
    "LocatingBoreDia": ((10.0, 5.0), (0.0, 0.0)),
}
PIVOT_CALLOUT_AT = (10.0, -7.0)

# --- Sheet TAGS ---------------------------------------------------------------------
TAG_CENTER = (0.200, 0.183)
TAG_SCALE = (1, 1)
ROW_PITCH = 0.0048
PART_SCHEDULE_TOP = 0.104
PART_COLUMNS = (0.016, 0.036, 0.064, 0.117, 0.145, 0.176)

# --- Sheet SCHEDULE -----------------------------------------------------------------
FEATURE_SCHEDULE_TOP = 0.258
FEATURE_COLUMNS = (0.016, 0.030, 0.072, 0.100, 0.128, 0.156, 0.184)
ISO_CENTER = (0.320, 0.185)
ISO_SCALE = (1, 4)
ISO_NOTE_XY = (0.272, 0.240)


def _mm_to_m(point: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(value / 1000.0 for value in point)


def _keep(
    adapter: Any,
    view: Any,
    placements: dict[str, tuple[tuple[float, ...], tuple[float, float]]],
    to_model: Any,
    *,
    label: str,
) -> dict[str, tuple[float, float]]:
    """Sheet positions for ``placements``: each model point projected, then offset."""
    names = list(placements)
    points = [_mm_to_m(to_model(placements[name][0])) for name in names]
    projected = model_points_in_view(adapter, view, points, label=label, names=names)
    return {
        name: (xy[0] + placements[name][1][0], xy[1] + placements[name][1][1])
        for name, xy in zip(names, projected, strict=True)
    }


def _plan_point(xy: tuple[float, ...]) -> tuple[float, float, float]:
    return (xy[0], xy[1], PLATE_TOP_Z)


def _section_point(xz: tuple[float, ...]) -> tuple[float, float, float]:
    return (xz[0], 0.0, xz[1])


def _orient_section(adapter: Any, view: Any) -> None:
    """Cut faces only, model X to the right and model Z up."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    if not section.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section D-D retained geometry behind the cutting plane")

    def axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin, east, up = model_points_in_view(
            adapter,
            view,
            [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0, 0.001)],
            label="section D-D orientation",
        )
        return (
            (east[0] - origin[0], east[1] - origin[1]),
            (up[0] - origin[0], up[1] - origin[1]),
        )

    horizontal, vertical = axes()
    if horizontal[0] * vertical[1] - horizontal[1] * vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section D-D cut direction")
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section D-D cut direction did not persist")
        horizontal, vertical = axes()
    view.Angle = float(view.Angle) - math.atan2(horizontal[1], horizontal[0])
    rebuild_drawing(adapter, label="section D-D angle")
    horizontal, vertical = axes()
    if (
        horizontal[0] <= 0.0
        or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0
        or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section D-D orientation did not persist: {horizontal=}, {vertical=}"
        )


def _center_on_outline(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so its outline (its ink) is centred on ``target``."""
    view = _early_bound(view, "IView")
    for _attempt in range(3):
        outline = tuple(float(value) for value in view.GetOutline())
        center = ((outline[0] + outline[2]) / 2.0, (outline[1] + outline[3]) / 2.0)
        if math.dist(center, target) < 0.0002:
            return
        position = tuple(float(value) for value in view.Position)
        moved = [position[axis] + target[axis] - center[axis] for axis in range(2)]
        if not view.SetViewPosition(double_array(moved), False):
            raise RuntimeError(f"failed to position {label}")
        rebuild_drawing(adapter, label=f"center {label}")
    raise RuntimeError(f"{label} outline did not settle on {target!r}")


def _elevation(adapter: Any) -> Any:
    """The plate's front elevation at the plan's scale, model Z up."""
    view = place_view(
        adapter, str(SOURCE), "*Bottom", *ELEVATION_CENTER, scale=PLAN_SCALE
    )
    origin, east, top = model_points_in_view(
        adapter,
        view,
        [(0.0, 0.0, 0.0), (0.001, 0.0, 0.0), (0.0, 0.0, 0.001)],
        label="elevation orientation",
    )
    if not (east[0] > origin[0] and top[1] > origin[1]):
        raise RuntimeError(f"*Bottom is not X right, Z up: {origin=}, {east=}, {top=}")
    set_hidden_lines_removed(adapter, view)
    return view


def _elevation_keep(adapter: Any, view: Any) -> dict[str, tuple[float, float]]:
    """Each plate height beside the plate end its sheet offset points to."""
    names = list(ELEVATION_KEEP_Z)
    points = [
        _mm_to_m((x, PLATE_SOUTH_Y, ELEVATION_KEEP_Z[name][0]))
        for name in names
        for x in (PLATE_WEST_X, PLATE_EAST_X)
    ]
    projected = model_points_in_view(adapter, view, points, label="elevation keep")
    keep = {}
    for index, name in enumerate(names):
        ends = projected[2 * index : 2 * index + 2]
        offset = ELEVATION_KEEP_Z[name][1]
        x = (min if offset < 0 else max)(end[0] for end in ends) + offset
        keep[name] = (x, ends[0][1])
    return keep


def _delete_thread_callouts(
    adapter: Any, view: Any, *, label: str, required: bool = True
) -> None:
    """Delete the model's cosmetic-thread callout notes from ``view`` (as
    ``delete_unnamed_imports`` deletes automatic ones): detail E carries the
    pivot tap's one callout, yet the model's "#10-24 Tapped Hole" note sat
    over the TAGS plan's tags A1-A3 (run 20261007T182242302Z) and printed
    again on the plan and the isometric (run 20261007T190010219Z). A hidden
    layer does not do: the layout audit boxes hidden-layer notes too
    (run 20261007T182758889Z). Deleted from the plan, it reappears on the
    next view cut from it (section D-D, run 20261007T191627896Z), so the
    derived views are swept too, where it may or may not land."""
    draw = adapter.currentModel
    deleted = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is None:
            continue
        note = _early_bound(raw_callout, "INote")
        callout = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
        draw.ClearSelection2(True)
        if not callout.Select2(False, 0):
            raise RuntimeError(f"failed to select a {label} thread callout")
        draw.EditDelete()
        deleted += 1
    draw.ClearSelection2(True)
    if not deleted:
        if required:
            raise RuntimeError(f"{label} has no cosmetic-thread callout to delete")
        return
    rebuild_drawing(adapter, label=f"delete {label} thread callouts")
    left = [
        str(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if any("Tapped Hole" in text for text in left):
        raise RuntimeError(f"{label} still carries a thread callout: {left!r}")


def _position_view_label(
    adapter: Any, view: Any, lower_left: tuple[float, float], *, label: str
) -> None:
    """Move a fresh view's one native label so its box's lower-left lands at
    ``lower_left`` (draw_dt_cone_swing_platform._position_view_label): the
    anchor is not the box corner, so shift it by the measured corner error.
    The sheet scale is pinned first so finalization cannot move it after."""
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALES["PLAN"], False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    notes = tuple(_read_member(view, "GetNotes") or ())
    if len(notes) != 1:
        texts = [str(_early_bound(found, "INote").GetText() or "") for found in notes]
        raise RuntimeError(f"expected one native {label}, found notes {texts!r}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    for _attempt in range(2):
        extent = tuple(float(value) for value in note.GetExtent())
        error = (lower_left[0] - extent[0], lower_left[1] - extent[1])
        if max(abs(error[0]), abs(error[1])) < 0.0002:
            break
        anchor = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(anchor[0] + error[0], anchor[1] + error[1], 0.0):
            raise RuntimeError(f"failed to position native {label}")
        rebuild_drawing(adapter, label=label)
    extent = tuple(float(value) for value in note.GetExtent())
    if max(abs(lower_left[0] - extent[0]), abs(lower_left[1] - extent[1])) > 0.0005:
        raise RuntimeError(
            f"native {label} landed at {extent[:2]}, requested {lower_left}"
        )


def _section(adapter: Any, plan: Any) -> Any:
    line = [
        model_point_in_view(
            adapter, plan, _mm_to_m((x, 0.0, PLATE_TOP_Z)), label="section D-D line"
        )
        for x in SECTION_SPAN_X
    ]
    view = create_section_view(
        adapter,
        plan,
        line_start=line[0],
        line_end=line[1],
        view_xy=SECTION_CENTER,
        section_label=SECTION_LABEL,
        scale=SECTION_SCALE,
        partial=True,
        label="bore-axis height section",
    )
    _orient_section(adapter, view)
    set_hidden_lines_removed(adapter, view)
    _center_on_outline(adapter, view, SECTION_CENTER, label="section D-D")
    _delete_thread_callouts(adapter, view, label="section D-D", required=False)
    _position_view_label(
        adapter, view, SECTION_LABEL_LOWER_LEFT, label="section D-D label"
    )
    return view


def _detail(adapter: Any, plan: Any) -> Any:
    """Detail E: the bore, the hub stand and its counterbore at 3:1."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, plan)):
        raise RuntimeError("failed to activate the plan for detail E")
    draw.ClearSelection2(True)
    center, rim = model_points_in_view(
        adapter,
        plan,
        [
            _mm_to_m((0.0, 0.0, PLATE_TOP_Z)),
            _mm_to_m((DETAIL_RADIUS_MM, 0.0, PLATE_TOP_Z)),
        ],
        label="detail E circle",
    )
    sketch = _early_bound(_early_bound(plan, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, rim):
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to sketch the detail E circle")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = plan
    if not _early_bound(circle, "ISketchSegment").Select4(False, selection_data):
        raise RuntimeError("failed to select the detail E circle")
    detail = ddoc.CreateDetailViewAt4(
        float(DETAIL_CENTER[0]),
        float(DETAIL_CENTER[1]),
        0.0,
        0,  # swDetViewSTANDARD
        float(DETAIL_SCALE[0]),
        float(DETAIL_SCALE[1]),
        DETAIL_LABEL,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError("CreateDetailViewAt4 returned no view for detail E")
    rebuild_drawing(adapter, label="create detail E")
    _center_on_outline(adapter, detail, DETAIL_CENTER, label="detail E")
    # A fresh detail view's projection lags its ink; settle it before anything
    # is placed through it (draw_dt_cone_swing_platform._create_detail_view).
    for attempt in range(3):
        projected = model_point_in_view(
            adapter,
            detail,
            _mm_to_m((0.0, 0.0, PLATE_TOP_Z)),
            label=f"detail E centre {attempt}",
        )
        if math.dist(projected, DETAIL_CENTER) < 0.0005:
            break
        rebuild_drawing(adapter, label="settle detail E")
    else:
        raise RuntimeError(
            f"detail E projects its centre to {projected!r}, not {DETAIL_CENTER!r}"
        )
    set_hidden_lines_removed(adapter, detail)
    _delete_thread_callouts(adapter, detail, label="detail E", required=False)
    _position_view_label(
        adapter, detail, DETAIL_LABEL_LOWER_LEFT, label="detail E label"
    )
    return detail


def _tag(
    adapter: Any, view: Any, text: str, edge: Any, xy: tuple[float, float]
) -> None:
    """One arrowed tag note on one model edge (add_hole_group_tags, by entity)."""
    _select_view_entity(adapter, view, "EDGE", None, label=f"tag {text}", entity=edge)
    draw = adapter.currentModel
    note = draw.InsertNote(text)
    if note is None:
        raise RuntimeError(f"failed to insert tag {text!r}")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if int(annotation.GetAttachedEntityCount3()) != 1:
        raise RuntimeError(f"tag {text!r} did not attach to its edge")
    if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
        raise RuntimeError(f"failed to give tag {text!r} its leader")
    if not annotation.SetPosition2(xy[0], xy[1], 0.0):
        raise RuntimeError(f"failed to position tag {text!r}")
    draw.ClearSelection2(True)


def _tags(adapter: Any, view: Any) -> None:
    """Tag every pocket and hole on the TAGS plan; the schedules carry the rest."""
    edges = scan_view_edges(view, label="tag plan")
    z = PLATE_TOP_Z
    targets: list[tuple[str, Any, tuple[float, float]]] = []
    for tag, cx, cy, _length, width in PAD_POCKETS:
        edge = edges.exact_line_through(
            (cx, cy + width / 2.0, z), label=f"pocket {tag}"
        )
        targets.append((tag, edge.edge, (cx, 17.0)))
    for tag, cx, cy, length, _width in REST_POCKETS:
        side = math.copysign(1.0, cx)
        edge = edges.exact_line_through(
            (cx + side * length / 2.0, cy, z), label=f"pocket {tag}"
        )
        targets.append((tag, edge.edge, (cx + side * 20.0, cy)))
    for index, (x, y) in enumerate(HOLD_DOWN_POINTS, start=1):
        edge = edges.circle_at(
            (x, y, z), HOLD_DOWN_CBORE_DIA / 2.0, axis=(0, 0, 1), label=f"H{index}"
        )
        targets.append(
            (
                f"H{index}",
                edge.edge,
                (x - math.copysign(15.0, x), -50.0 if y < 0 else 55.0),
            )
        )
    for index, (x, y) in enumerate(CLAMP_STUD_POINTS, start=1):
        edge = edges.circle_at(
            (x, y, z), CLAMP_STUD_DRILL_DIA / 2.0, axis=(0, 0, 1), label=f"S{index}"
        )
        targets.append(
            (
                f"S{index}",
                edge.edge,
                (x + math.copysign(12.0, x), -46.0 if y < 0 else 55.0),
            )
        )
    bore = edges.circle_at(
        (0.0, 0.0, PLATE_TOP_Z - STAND_POCKET_DEPTH),
        LOCATING_BORE_DIA / 2.0,
        axis=(0, 0, 1),
        label="L",
    )
    targets.append(("L", bore.edge, (0.0, -16.0)))
    pin = edges.circle_at(
        (*ROD_PIN_HOLE_XY, z), ROD_PIN_HOLE_DIA / 2.0, axis=(0, 0, 1), label="P"
    )
    targets.append(("P", pin.edge, (140.0, 18.0)))
    sheet_xy = model_points_in_view(
        adapter,
        view,
        [_mm_to_m(_plan_point(xy)) for _tag_text, _edge, xy in targets],
        label="tag positions",
        names=[tag for tag, _edge, _xy in targets],
    )
    for (tag, edge, _xy), xy in zip(targets, sheet_xy, strict=True):
        _tag(adapter, view, tag, edge, xy)
    rebuild_drawing(adapter, label="tag plan tags")


def _schedule(
    adapter: Any,
    title: str,
    header: tuple[str, ...],
    rows: tuple[tuple[str, ...], ...],
    *,
    columns: tuple[float, ...],
    top: float,
) -> None:
    if add_note(adapter, title, columns[0], top) is None:
        raise RuntimeError(f"failed to add schedule title {title!r}")
    body = (header, *rows)
    draw_note_table(
        adapter,
        rows=body,
        column_x=columns,
        row_y=[top - (index + 1.5) * ROW_PITCH for index in range(len(body))],
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open profile-fixture source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALES["PLAN"], layout=SPEC.layout
    )
    create_blank_drawing_sheets(
        adapter, SHEET_NAMES, label="profile fixture drawing package"
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Profile Fixture Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm profile fixture; bonded steel plate; MHA-CH-006-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    # --- PLAN ------------------------------------------------------------------
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate the PLAN sheet")
    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=PLAN_SCALE)
    set_hidden_lines_removed(adapter, plan)
    _delete_thread_callouts(adapter, plan, label="plan")
    section = _section(adapter, plan)
    detail = _detail(adapter, plan)
    elevation = _elevation(adapter)

    plan_annotations = curate_view_dimensions(
        adapter,
        plan,
        keep=_keep(adapter, plan, PLAN_KEEP_AT, _plan_point, label="plan keep"),
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=_keep(
            adapter, section, SECTION_KEEP_AT, _section_point, label="section keep"
        ),
        view_label="section D-D",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=_keep(adapter, detail, DETAIL_KEEP_AT, _plan_point, label="detail keep"),
        view_label="detail E",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    elevation_annotations = curate_view_dimensions(
        adapter,
        elevation,
        keep=_elevation_keep(adapter, elevation),
        view_label="end elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *plan_annotations,
        *section_annotations,
        *detail_annotations,
        *elevation_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    plan_edges = scan_view_edges(plan, label="plan")
    hold_down = HOLD_DOWN_POINTS[1]
    add_native_hole_callout(
        adapter,
        plan,
        edge=plan_edges.circle_at(
            (*hold_down, PLATE_TOP_Z),
            HOLD_DOWN_CBORE_DIA / 2.0,
            axis=(0, 0, 1),
            label="H2",
        ).edge,
        callout_xy=HOLD_DOWN_CALLOUT_XY,
        label="hold-down counterbore",
        process="DRILL, C'BORE",
    )
    stud = CLAMP_STUD_POINTS[3]
    add_native_hole_callout(
        adapter,
        plan,
        edge=plan_edges.circle_at(
            (*stud, PLATE_TOP_Z), CLAMP_STUD_DRILL_DIA / 2.0, axis=(0, 0, 1), label="S4"
        ).edge,
        callout_xy=STUD_CALLOUT_XY,
        label="clamp stud tap",
        process="TAP",
    )
    detail_edges = scan_view_edges(detail, label="detail E")
    add_native_hole_callout(
        adapter,
        detail,
        edge=detail_edges.circle_at(
            (0.0, 0.0, LOCATING_BORE_FLOOR_Z),
            PIVOT_TAP_DRILL_DIA / 2.0,
            axis=(0, 0, 1),
            label="pivot tap",
        ).edge,
        callout_xy=model_point_in_view(
            adapter,
            detail,
            _mm_to_m(_plan_point(PIVOT_CALLOUT_AT)),
            label="pivot tap callout",
        ),
        label="pivot screw tap",
        process="TAP",
    )
    if not auto_center_marks(adapter, plan, holes=True, size=0.0025):
        raise RuntimeError("failed to add center marks to the plan")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to return to the PLAN sheet")
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    # --- TAGS ------------------------------------------------------------------
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate the TAGS sheet")
    tag_plan = place_view(adapter, str(SOURCE), "*Front", *TAG_CENTER, scale=TAG_SCALE)
    set_hidden_lines_removed(adapter, tag_plan)
    _delete_thread_callouts(adapter, tag_plan, label="TAGS plan")
    _tags(adapter, tag_plan)
    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to return to the TAGS sheet")
    _schedule(
        adapter,
        PART_SCHEDULE_TITLE,
        PART_SCHEDULE_HEADER,
        PART_SCHEDULE,
        columns=PART_COLUMNS,
        top=PART_SCHEDULE_TOP,
    )

    # --- SCHEDULE --------------------------------------------------------------
    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate the SCHEDULE sheet")
    # finalize_drawing shades the pictorial isometric with edges. Set it HLR
    # first: shading the template's default view left high-quality cosmetic
    # threads off (run 20261007T183332487Z; the inspection box's d7ad8b4c4).
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, iso)
    _delete_thread_callouts(adapter, iso, label="isometric")
    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to return to the SCHEDULE sheet")
    _schedule(
        adapter,
        FEATURE_SCHEDULE_TITLE,
        FEATURE_SCHEDULE_HEADER,
        FEATURE_SCHEDULE,
        columns=FEATURE_COLUMNS,
        top=FEATURE_SCHEDULE_TOP,
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    for index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate sheet {sheet_name!r} for audit")
        if (
            add_note(adapter, f"SHEET {index} OF {len(SHEET_NAMES)}", *SHEET_COUNT_XY)
            is None
        ):
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name!r}")
        rebuild_drawing(adapter, label=f"profile fixture {sheet_name} layout")
        check_drawing_layout(adapter, layout=SPEC.layout, stem=sheet_name)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Profile Fixture Drawing",
        scale=SHEET_SCALES["PLAN"],
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
