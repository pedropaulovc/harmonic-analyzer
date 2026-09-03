r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  This recipe supplies only the platform's
views, the wedge's native plan dimensions, the pivot-keyed hole stations and
the machining notes; every shared sheet/template, import, curation, and export
behavior lives in ``_drawing_common``.

The platform is machined from black-oxide 5/16 in minimum steel stock to a
6.35 mm finished plate: an asymmetric wedge (223.35 long, 24 -> 61 wide) with a
Ø6.76 pivot hole at the narrow tip, paired 1/4-20 post-mount taps, an open
lock notch through the west edge, and rounded plan corners. The main plan and
end views run 1:2; DETAIL A (the pivot end) runs 1:1; the isometric runs 1:3.

The print carries no datums, frames, roughness symbols or basic dimensions
(cad/docs/drawing-simplicity-policy.md).  The wedge is defined by its own
sketch dimensions from the pivot (the sketch origin): west taper run, axial
length and south edge; the lock notch by its closed-end cap (centre from the
pivot, full-radius diameter) plus the axis angle in the notes; the south
corners by their fillet radii; the post-mount taps by entity dimensions from
the pivot hole in the main plan view and a native callout.
DETAIL A retains the narrow pivot-end geometry; its unavailable
overhang, north widths and north radii are stated in a compact adjacent note
derived from the same build constants.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    create_detail_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    remove_notes_matching,
)
from _holes import blind_cut_dia_mm
from build_cone_swing_platform import (
    EAST_HALF_S,
    HALF_WIDTH_N,
    NORTH_OVERHANG,
    PIVOT_HOLE_SPEC,
    PLATE_LEN,
    POST_MOUNT_EAST_XZ,
    POST_MOUNT_SPEC,
    POST_MOUNT_WEST_XZ,
    WEST_HALF_N,
    WEST_HALF_S,
    _CORNERS,
)
from cone_swing_platform_spec import LOCK_NOTCH_SEAT_X, LOCK_NOTCH_SEAT_Z


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 3.0)  # 1:2 plan keeps the 266 mm envelope in-zone
_P = 0.5 / 1000.0  # sheet metres per model mm in the 1:2 plan

# Sheet layout (meters).  The 1:2 plan is the main definition view, low
# enough that four stacked dimensions above its south end stay under the top
# border; DETAIL A (the pivot end at 1:1) stands right of it; the isometric
# and the end view occupy the open right-hand field above the title block.
TOP_CENTER = (0.115, 0.172)
DETAIL_CENTER = (0.240, 0.150)
DETAIL_SCALE = (1, 1)
ISO_CENTER = (0.355, 0.225)
END_CENTER = (0.340, 0.095)

# The plan view centres on the plate's bounding box; +X (west) is to the
# right, +Z (north) is DOWN (the SolidWorks Top view), so the pivot end is at
# the bottom of the sheet.
_PLAN_CX = (WEST_HALF_S - EAST_HALF_S) / 2.0
_PLAN_CZ = NORTH_OVERHANG - PLATE_LEN / 2.0


def _plan_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet (x, y) of a part-local plan point (x west, z north) in the plan."""
    return (
        TOP_CENTER[0] + (x_mm - _PLAN_CX) * _P,
        TOP_CENTER[1] - (z_mm - _PLAN_CZ) * _P,
    )


_PIVOT = _plan_xy(0.0, 0.0)
_AXIS_X = _PIVOT[0]
_NE = _plan_xy(-HALF_WIDTH_N, NORTH_OVERHANG)
_NW = _plan_xy(WEST_HALF_N, NORTH_OVERHANG)
_SW = _plan_xy(WEST_HALF_S, NORTH_OVERHANG - PLATE_LEN)
_SE = _plan_xy(-EAST_HALF_S, NORTH_OVERHANG - PLATE_LEN)
_SOUTH_Y = _SW[1]
_NORTH_Y = _NE[1]
_W_HOLE = _plan_xy(*POST_MOUNT_WEST_XZ)
_E_HOLE = _plan_xy(*POST_MOUNT_EAST_XZ)
_CAP = _plan_xy(LOCK_NOTCH_SEAT_X, LOCK_NOTCH_SEAT_Z)

# DETAIL A boundary on the plan: centred on the axis 12 mm south of the pivot,
# 26 mm (model) radius, so the whole 24 mm north end, the pivot hole and both
# north corner radii are inside it.
DETAIL_MODEL_CENTER_Z = -12.0
DETAIL_MODEL_RADIUS = 26.0
DETAIL_BOUNDARY = (
    _plan_xy(0.0, DETAIL_MODEL_CENTER_Z),
    DETAIL_MODEL_RADIUS * _P,
)

# Plan dimensions.  Left: the axial length outermost, the east mount's
# station from the pivot nearer.  Right: the notch closed-end station and the
# west mount's station from the pivot (shorter nearer).  Above the south end,
# nearest first: the east mount's offset from the axis, the mount pitch across
# the axis, the notch closed-end offset, and the south edge.  The notch-width
# leader and east corner radius occupy separate rows to the right; the native
# two-line tap callout has its own row nearest the top border.
TOP_KEEP = {
    "PlateLenDim": (0.035, (_NORTH_Y + _SOUTH_Y) / 2.0),
    "WestTaperDx": ((_NW[0] + _SW[0]) / 2.0, _NORTH_Y - 0.012),
    "SouthEdge": ((_SE[0] + _SW[0]) / 2.0, _SOUTH_Y + 0.033),
    "CapECx": (_AXIS_X + (LOCK_NOTCH_SEAT_X / 2.0) * _P, _SOUTH_Y + 0.024),
    "CapECz": (_SW[0] + 0.016, (_PIVOT[1] + _CAP[1]) / 2.0),
    "CapEDia": (0.220, _SOUTH_Y - 0.006),
    "CornerSWR": (_SW[0] + 0.024, _SOUTH_Y + 0.0065),
    "CornerSER": (_SE[0] - 0.022, _SOUTH_Y + 0.014),
}
# The five marked sketch/fillet dimensions are unavailable from the derived
# detail. State the same values from build constants beside the retained
# pivot-end geometry instead of introducing fresh selection coordinates.
_NORTH_CORNER_RADII = {
    label: radius for label, _x, _z, radius in _CORNERS if label in {"NE", "NW"}
}
PIVOT_END_GEOMETRY_NOTE = "\n".join(
    (
        "DETAIL A PIVOT-END PROFILE",
        (f"FROM PIVOT C/L: EAST {HALF_WIDTH_N:.2f}; NORTH {NORTH_OVERHANG:.2f}"),
        (
            f"NORTH EDGE {HALF_WIDTH_N + WEST_HALF_N:.2f}; "
            f"NE R{_NORTH_CORNER_RADII['NE']:.1f}; "
            f"NW R{_NORTH_CORNER_RADII['NW']:.1f}"
        ),
    )
)
PIVOT_END_GEOMETRY_NOTE_XY = (
    DETAIL_CENTER[0] + DETAIL_MODEL_RADIUS / 1000.0 + 0.008,
    DETAIL_CENTER[1] - 0.010,
)
PIVOT_CALLOUT_XY = (_PIVOT[0] + 0.035, _PIVOT[1] + 0.015)
END_KEEP = {
    "PlateT": (END_CENTER[0] + 0.026, END_CENTER[1]),
}
DIMENSION_CALLOUTS = {
    "CapEDia": "NOTCH WIDTH",
}
# Only the south radii remain imported; the north pair is explicit in the note.
DIMENSION_PRECISION = {name: 1 for name in ("CornerSWR", "CornerSER")}
# Post-mount stations from the pivot: the east hole's offset across the axis
# (text left of its span), the pair's pitch across the axis, and each hole's
# station along the axis on its own side of the plate.
EAST_OFFSET_TEXT_XY = (_AXIS_X - 0.017, _SOUTH_Y + 0.009)
PITCH_TEXT_XY = (_AXIS_X, _SOUTH_Y + 0.016)
WEST_STATION_TEXT_XY = (_SW[0] + 0.030, (_PIVOT[1] + _W_HOLE[1]) / 2.0)
EAST_STATION_TEXT_XY = (_SE[0] - 0.016, (_PIVOT[1] + _E_HOLE[1]) / 2.0)
MOUNT_CALLOUT_XY = (0.225, _SOUTH_Y + 0.030)
NOTES_XY = (0.016, 0.088)
PLAN_NOTE_XY = (0.030, 0.258)
ISO_NOTE_XY = (0.325, 0.190)
END_NOTE_XY = (0.310, 0.112)


def _plan_circles(
    adapter: Any, view: Any
) -> list[tuple[float, tuple[float, float, float], Any]]:
    """Every visible circular edge in a plan-family view: (radius m, centre m, edge)."""
    circles: list[tuple[float, tuple[float, float, float], Any]] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            circles.append((values[6], values[:3], edge))
    return circles


def _pivot_rim(adapter: Any, view: Any) -> Any:
    """The pivot hole's rim in a plan-family view (the plan or its detail)."""
    expected_radius_m = blind_cut_dia_mm(PIVOT_HOLE_SPEC) / 2000.0
    rims = [
        edge
        for radius, _center, edge in _plan_circles(adapter, view)
        if abs(radius - expected_radius_m) <= 1e-6
    ]
    if not rims:
        raise RuntimeError(f"{view_name(adapter, view)} shows no pivot-hole rim")
    return rims[0]


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any, Any]:
    """Return the pivot rim and the west and east post-mount rims.

    Rims are matched by radius; the two mount rims are told apart by model X
    (part-local +x is west).
    """
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    mount_edges: list[tuple[float, Any]] = [
        (center[0], edge)
        for radius, center, edge in _plan_circles(adapter, view)
        if abs(radius - expected_mount_radius_m) <= 1e-6
    ]
    if len(mount_edges) < 2:
        raise RuntimeError(
            f"cone-platform plan view shows {len(mount_edges)} post-mount rims, expected 2"
        )
    mount_edges.sort(key=lambda item: item[0], reverse=True)  # west (+x) first
    return _pivot_rim(adapter, view), mount_edges[0][1], mount_edges[-1][1]


@_telemetry.traced("drawing.entity_dimension", label_param="label")
def _entity_dimension(
    adapter: Any,
    view: Any,
    base_entity: Any,
    circle_entity: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
) -> Any:
    """Entity-selected circle-centre-to-circle-centre dimension (the arbor recipe).

    A sheet-picked dimension re-anchored to a circle centre was found to
    DANGLE on the tip-block sheet (rendered gray on the eye pass); entity
    selection does not.  Both picks are circular rims, so both endpoints are
    re-anchored to their centres.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, base_entity), (True, circle_entity)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError(f"failed to select {label} entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    set_arc_endpoints_to_center(adapter, display, label=label)
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
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
            "Plan View Note",
            "Isometric View Note",
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Plan View Note",
            "Isometric View Note",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # DETAIL A: the pivot end at 1:1, where the pivot hole, the 7 overhang,
    # the 16/24 north widths and the two north radii have room (rule 7).
    detail = create_detail_view(
        adapter,
        top,
        center=DETAIL_BOUNDARY[0],
        radius=DETAIL_BOUNDARY[1],
        view_xy=DETAIL_CENTER,
        detail_label="A",
        scale=DETAIL_SCALE,
        label="pivot-end detail",
    )
    # Hidden lines stay ON in every orthographic view (policy rule 7).
    for view in (top, end, detail):
        set_hidden_lines_visible(adapter, view)

    pivot_edge, west_edge, east_edge = _visible_plan_controls(adapter, top)
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="end"
    )
    set_dimension_callouts(
        adapter, [*top_annotations, *end_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, top_annotations, DIMENSION_PRECISION)
    if add_note(adapter, PIVOT_END_GEOMETRY_NOTE, *PIVOT_END_GEOMETRY_NOTE_XY) is None:
        raise RuntimeError("failed to add pivot-end geometry note")
    for label, view in (("plan", top), ("detail", detail)):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to the {label} view")

    # The derived detail does not expose the pivot-hole rim reliably. Keep
    # DETAIL A for the end profile, and attach the native hole callout to the
    # model rim in the main plan view.
    add_native_hole_callout(
        adapter,
        top,
        callout_xy=PIVOT_CALLOUT_XY,
        label="pivot-hole size",
        edge=pivot_edge,
        # 1/4 close clearance (6.756 = 0.266 in) is exactly the H drill.
        process="H DRILL",
    )

    # Post-mount taps from the pivot hole (the coordinate frame the notes
    # name): the east hole's offset across the axis, the pair's pitch across
    # the axis, and each hole's station along the axis -- every one an
    # entity dimension between rim centres -- plus the native 2X callout.
    _entity_dimension(
        adapter,
        top,
        pivot_edge,
        east_edge,
        orientation="horizontal",
        position=EAST_OFFSET_TEXT_XY,
        label="east mount offset from the axis",
    )
    _entity_dimension(
        adapter,
        top,
        west_edge,
        east_edge,
        orientation="horizontal",
        position=PITCH_TEXT_XY,
        label="mount pitch across the axis",
    )
    _entity_dimension(
        adapter,
        top,
        pivot_edge,
        west_edge,
        orientation="vertical",
        position=WEST_STATION_TEXT_XY,
        label="west mount station from the pivot",
    )
    _entity_dimension(
        adapter,
        top,
        pivot_edge,
        east_edge,
        orientation="vertical",
        position=EAST_STATION_TEXT_XY,
        label="east mount station from the pivot",
    )
    # The imported model items also materialize a generic note matching the
    # post-mount thread size. The associative 2X Hole Wizard callout is
    # authoritative for thread, depth and quantity, while the four dimensions
    # above own both hole locations.  Create and read back that replacement
    # before deleting exactly the duplicate note.
    mount_callout = add_native_hole_callout(
        adapter,
        top,
        callout_xy=MOUNT_CALLOUT_XY,
        label="v2 post-mount tapped holes",
        edge=west_edge,
    )
    if not bool(mount_callout.IsHoleCallout()):
        raise RuntimeError("post-mount replacement is not a native hole callout")
    redundant_tap_note = f"{POST_MOUNT_SPEC.size} Tapped Hole"
    removed_tap_notes = remove_notes_matching(adapter, redundant_tap_note)
    if removed_tap_notes != 1:
        raise RuntimeError(
            "cone-swing-platform tap cleanup mismatch: "
            f"removed={removed_tap_notes}, expected=1"
        )
    if remove_notes_matching(adapter, redundant_tap_note) != 0:
        raise RuntimeError("redundant post-mount tap note remained after deletion")
    if not bool(mount_callout.IsHoleCallout()):
        raise RuntimeError("native post-mount hole callout was lost during cleanup")
    _telemetry.info("removed the redundant cone-swing-platform tap note")

    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.0025
    )
    add_property_linked_note(adapter, "Plan View Note", *PLAN_NOTE_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "End View Note", *END_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
