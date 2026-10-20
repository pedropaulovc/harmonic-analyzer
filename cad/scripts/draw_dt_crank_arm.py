r"""Create the curated machinist drawing for crank arm MHA-DT-06.

Separate through hub MHA-DT-31 is a light press in the arm's seat bore, turned
to suit it.  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-DT-VN-59,
match-drilled with the hub; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-DT-32 shoulder screw.  The
principal view identifies the hub seat; the rotated top/profile view carries
the native far-side bore-mouth chamfer leg and its press lead-in intent.
The MHA-DT-09 taper-pin cross-hole belongs to the hub and shaft drawings.

The sheet remains deliberately plain: no datums, feature-control frames or
roughness symbols.  Every controlling value is imported from the part; matched
arm/hub and seam-pin operations are stated on their receiving feature/note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_arm.py dt-crank-arm
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import boxes_clear, callout_ink, sheet_region
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
    offset_dimension_text,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    dimension_text_points,
    distance_to_box,
    landing_distance,
    points_inside,
    segments_cross,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _hole_spec import blind_cut_dia_mm
from _layout_audit import display_box
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_arm_notes import (
    BORE_REAR_CHAMFER_CALLOUT,
    FIDUCIAL_CALLOUT,
    HUB_SEAT_CALLOUT,
    PIVOT_TAP_ROWS,
    PROFILE_VIEW_CAPTION,
    SEAM_CALLOUT,
)
from dt_crank_arm_spec import (
    ANCHOR_HOLE_SPEC,
    ANCHOR_SCREW_X,
    ANCHOR_SCREW_Y,
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    AXIAL_PIN_DIA,
    AXIAL_PIN_X,
    BORE_REAR_CHAMFER,
    BORE_REAR_CHAMFER_DEVIATIONS,
    BORE_REAR_CHAMFER_TOL_TYPE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FIDUCIAL_MODEL_DIA,
    FIDUCIAL_X,
    FIDUCIAL_Y,
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    HUB_SEAT_DIA,
    REFERENCE_DIMENSIONS,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_arm"]
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
_HANDLE_PIVOT_HOLE_DIA = blind_cut_dia_mm(HANDLE_PIVOT_HOLE_SPEC)
_ANCHOR_HOLE_DIA = blind_cut_dia_mm(ANCHOR_HOLE_SPEC)


SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  At 2:1 the 100.4-mm overall arm remains clear of the
# title block. The profile replaces the old stock end view: Top, turned 90
# degrees CCW at 1:1, shows the native chamfer in its proven XZ plane.
# The principal view sits so its lower edge keeps the dimension rows' height below
# it; the three callouts over the hub end (seat, seam, anchor tap) stand in a
# row above it so no leader crosses another.
FRONT_CENTER = (0.145, 0.142)
PROFILE_CENTER = (0.300, FRONT_CENTER[1])
ISO_CENTER = (0.360, 0.230)
PROFILE_SCALE = (1.0, 1.0)
PROFILE_ANGLE = math.pi / 2.0
PROFILE_CAPTION_XY = (0.316, 0.160)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the principal view (2:1, bbox-centred)."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


def _set_reference_precision(adapter: Any, display: Any, label: str) -> None:
    """Give the sheet-derived overall its PART-authored decimal places.

    The overall is a read-only sum with no model dimension to import, so its
    places come from the spec's ``DRAWING_REFERENCE_PRECISION``. ``SetPrecision3``
    reports rejection through its return status rather than by raising, so
    the side effect is read back.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places.  The subscript is written out again because
    # _drawing_contract only accepts a spec lookup here.
    adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


def _omit_title_block_thread_class(display: Any) -> None:
    """Remove only the redundant Hole Wizard thread-class field."""
    native = _early_bound(display, "IDisplayDimension")
    definition = str(native.GetText(5) or "")
    without_class = re.sub(
        r"\s*(?:-\s*)?<hw-threadclass>\s*", " ", definition, flags=re.IGNORECASE
    )
    without_class = re.sub(r" {2,}", " ", without_class)
    if without_class == definition:
        raise RuntimeError(
            f"anchor tap callout lacks its thread-class variable: {definition!r}"
        )
    # IDisplayDimension.SetText is void; the definition readback is the
    # authoritative persistence check.
    native.SetText(1, without_class)
    if str(native.GetText(5) or "") != without_class:
        raise RuntimeError("anchor tap callout retained its redundant thread class")


def _append_callout_rows(display: Any, rows: str) -> None:
    """Add ``rows`` under a native hole callout's thread row.

    The definition (``GetText(5)``) carries the thread row; appending keeps
    the tap-drill and thread rows together, with the rows below them (#984
    review r3: a prefix split the callout between the two).
    """
    native = _early_bound(display, "IDisplayDimension")
    definition = str(native.GetText(5) or "")
    if not definition.strip():
        raise RuntimeError("hole callout has no definition to extend")
    extended = definition.rstrip() + "\n" + rows
    native.SetText(1, extended)
    if str(native.GetText(5) or "") != extended:
        raise RuntimeError(f"hole callout rows did not persist: {native.GetText(5)!r}")


# Per-view survivors of the marked-dimension import.
FRONT_KEEP = {
    "PivotStation": (_sheet_x(ARM_C2C / 2.0), 0.095),
    "AnchorStation": (_sheet_x(ANCHOR_SCREW_X / 2.0), 0.104),
    "AnchorOffset": (0.108, FRONT_CENTER[1] + HALF_WIDTH * SHEET_SCALE[0] / 1000.0 + 0.008),
    "Width": (0.279, FRONT_CENTER[1]),
    "BossRadius": (0.030, FRONT_CENTER[1]),
    # Below the front view and left of the profile's chamfer text lane.
    "EndRadius": (0.248, 0.087),
    "HubSeatDia": (0.048, 0.225),
}
# The hub seat's leader lands on the near rim, upper left of the bore: at
# 0.054 with both arrows it ran down through the bore centre to the far
# rim and crossed R12.7's leader there (eye pass of w15-301f4bf4e; the
# 2026-09-23 review had flagged the far-side landing). Nothing but R12.7
# itself may come within half the seat radius of the centre.
BORE_CENTER = (_sheet_x(0.0), FRONT_CENTER[1])
HUB_SEAT_KEEP_OUT = HUB_SEAT_DIA * SHEET_SCALE[0] / 4000.0
# Where each leader must END, from the bore centre (sheet metres): the hub
# seat on its rim, R12.7 at the centre or on its arc. A reading outside the
# band means the segments are not sheet metres, and the clear check fails.
HUB_SEAT_LANDING = (HUB_SEAT_KEEP_OUT, 3.0 * HUB_SEAT_KEEP_OUT)
BOSS_RADIUS_LANDING = (0.0, 1.2 * HALF_WIDTH * SHEET_SCALE[0] / 1000.0)
# Every front-view dimension text stands outside the arm's silhouette
# (2026-09-23 review: 8.2 sat on the part, between the top edge and the tap).
ARM_SILHOUETTE = (
    _sheet_x(-HALF_WIDTH),
    FRONT_CENTER[1] - HALF_WIDTH * SHEET_SCALE[0] / 1000.0,
    _sheet_x(ARM_END_X),
    FRONT_CENTER[1] + HALF_WIDTH * SHEET_SCALE[0] / 1000.0,
)
# The arm's half of the MHA-DT-VN-59 seam is the arc bulging from the seat edge
# toward the arm end; the callout attaches 45 degrees up its flank.
SEAM_EDGE_PICK = (
    _sheet_x(AXIAL_PIN_X + AXIAL_PIN_DIA / 2.0 * math.cos(math.pi / 4.0)),
    FRONT_CENTER[1]
    + AXIAL_PIN_DIA / 2.0 * math.sin(math.pi / 4.0) * SHEET_SCALE[0] / 1000.0,
)
SEAM_CALLOUT_XY = (0.104, 0.250)
# The punched fiducial's rim, picked on its upper-left flank toward the
# callout standing above the boss end, clear of the hub seat's leader.
FIDUCIAL_EDGE_PICK = (
    _sheet_x(FIDUCIAL_X - FIDUCIAL_MODEL_DIA / 2.0 * math.cos(math.pi / 4.0)),
    FRONT_CENTER[1]
    + (FIDUCIAL_Y + FIDUCIAL_MODEL_DIA / 2.0 * math.sin(math.pi / 4.0))
    * SHEET_SCALE[0]
    / 1000.0,
)
FIDUCIAL_CALLOUT_XY = (0.016, 0.196)
# The overall's pick on the handle-end arc: 2 mm below the axis, on the arc.
_END_PICK_DY_SHEET = 0.004
_END_PICK_DX = math.sqrt(HALF_WIDTH**2 - (_END_PICK_DY_SHEET * 1000.0 / SHEET_SCALE[0]) ** 2)
ANCHOR_CALLOUT_XY = (0.195, 0.205)
# Centre of the four-line pivot callout: its bottom row stays clear above
# the arm's top edge, its right end left of the isometric view.
PIVOT_CALLOUT_XY = (0.270, 0.190)
PROFILE_KEEP = {
    "Depth": (0.300, 0.082),
    "BoreRearChamferSize": (0.263, 0.112),
}
# The seven-row native block (two LIMIT rows plus the five short suffix rows)
# stands between the front and profile silhouettes, below Width and the pivot
# callout. These are lane limits, not a substitute for whole-ink readback.
CHAMFER_TEXT_LANE = (0.2498, 0.091, 0.277, 0.133)
DIMENSION_CALLOUTS = {
    "HubSeatDia": HUB_SEAT_CALLOUT,
    "BoreRearChamferSize": BORE_REAR_CHAMFER_CALLOUT,
}


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _assert_chamfer_limits(annotation: Any) -> None:
    """Verify the saved part's native leg and limits, never rewrite them."""
    native = _early_bound(annotation, "IAnnotation")
    display = _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    if (
        str(dimension.FullName or "").split("@")[:2]
        != ["BoreRearChamferSize", "BoreRearChamfer"]
        or int(dimension.GetType()) != 0  # swDimensionParamTypeDoubleLinear
    ):
        raise RuntimeError("imported bore-mouth chamfer has the wrong model identity/type")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if not math.isclose(
        float(dimension.SystemValue) * 1000.0, BORE_REAR_CHAMFER, abs_tol=1e-7
    ):
        raise RuntimeError("imported bore-mouth chamfer changed its model leg")
    lower, upper = BORE_REAR_CHAMFER_DEVIATIONS
    if (
        int(tolerance.Type) != BORE_REAR_CHAMFER_TOL_TYPE
        or not math.isclose(float(tolerance.GetMinValue()) * 1000.0, lower, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()) * 1000.0, upper, abs_tol=1e-9)
    ):
        raise RuntimeError("imported bore-mouth chamfer lost its native LIMIT band")


def _assert_profile_dimension(
    adapter: Any, profile: Any, annotation: Any, parameter: str
) -> Any:
    """Require the visible, live source dimension in this particular view."""
    native = _early_bound(annotation, "IAnnotation")
    view = _early_bound(profile, "IView")
    app = _early_bound(adapter.swApp, "ISldWorks")
    if (
        int(native.GetType()) != 4  # swDisplayDimension
        or int(native.Visible) != 1  # swAnnotationVisible
        or int(native.OwnerType) != 0  # swAnnotationOwner_DrawingView
        or int(app.IsSame(native.Owner, view)) != 1  # swObjectSame
        or native.IsDangling()
    ):
        raise RuntimeError(f"{parameter}: dimension is not visible and attached in the profile view")
    display = _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    source = _early_bound(view.ReferencedDocument, "IModelDoc2")
    expected = source.Parameter(parameter)
    if expected is None or int(app.IsSame(dimension, expected)) != 1:
        raise RuntimeError(f"{parameter}: dimension is not the source model dimension")
    if display.GetOverride() is not False or display.ShowDimensionValue is not True:
        raise RuntimeError(f"{parameter}: dimension lost its native displayed value")
    return display


def _assert_profile_chamfer(adapter: Any, profile: Any, annotation: Any) -> None:
    """Preserve the model's identity, LIMIT band, precision and short suffix."""
    display = _assert_profile_dimension(
        adapter, profile, annotation, "BoreRearChamferSize@BoreRearChamfer"
    )
    _assert_chamfer_limits(annotation)
    if (
        display.IsReferenceDim() is not False
        or int(display.GetPrimaryPrecision2())
        != DRAWING_PRECISION_BY_NAME["BoreRearChamferSize"]
        or int(display.GetPrimaryTolPrecision2())
        != DRAWING_PRECISION_BY_NAME["BoreRearChamferSize"]
        or str(display.GetText(4) or "") != BORE_REAR_CHAMFER_CALLOUT
    ):
        raise RuntimeError("bore-mouth chamfer lost its native value, LIMIT precision or callout")


def _profile_geometry(adapter: Any, profile: Any) -> tuple[float, float]:
    """Read the turned XZ projection, including rear-mouth and stock directions.

    The successful native XZ import (20261020T042443087Z) and failed Front
    import rule out repeating the plan-view prototype. The original Right
    projection is YZ, not this chamfer's annotation plane. One Top view replaces
    it; the angle, scale and actual projected axes must agree with its caption.
    """
    view = _early_bound(profile, "IView")
    if (
        str(view.GetOrientationName()).lstrip("*").casefold() != "top"
        or not math.isclose(math.remainder(float(view.Angle) - PROFILE_ANGLE, math.tau), 0.0, abs_tol=1e-8)
        or tuple(float(value) for value in view.ScaleRatio) != PROFILE_SCALE
        or int(view.GetDisplayMode2()) != 1  # swHIDDEN_GREYED: HLV
    ):
        raise RuntimeError("profile lost its Top/90 DEG CCW/1:1/HLV projection")
    radius = HUB_SEAT_DIA / 2.0 + BORE_REAR_CHAMFER
    origin, x_axis, y_axis, z_axis, low, high, mouth = model_points_in_view(
        adapter,
        view,
        (
            (0.0, 0.0, 0.0),
            (0.001, 0.0, 0.0),
            (0.0, 0.001, 0.0),
            (0.0, 0.0, 0.001),
            (-HALF_WIDTH / 1000.0, 0.0, 0.0),
            (ARM_END_X / 1000.0, 0.0, ARM_THICKNESS / 1000.0),
            (-radius / 1000.0, 0.0, 0.0),
        ),
        label="crank arm turned top profile",
    )
    axes = [
        (point[0] - origin[0], point[1] - origin[1])
        for point in (x_axis, y_axis, z_axis)
    ]
    expected = ((0.0, 0.001), (0.0, 0.0), (0.001, 0.0))
    cx, cy = PROFILE_CENTER
    half_length = (ARM_END_X + HALF_WIDTH) / 2000.0
    half_thickness = ARM_THICKNESS / 2000.0
    if (
        any(not math.isfinite(value) for point in (origin, *axes, low, high, mouth) for value in point)
        or any(math.dist(actual, wanted) > 1e-8 for actual, wanted in zip(axes, expected))
        or math.dist(low, (cx - half_thickness, cy - half_length)) > 1e-6
        or math.dist(high, (cx + half_thickness, cy + half_length)) > 1e-6
        or math.dist(
            mouth, (cx - half_thickness, cy - (ARM_C2C / 2.0 + radius) / 1000.0)
        ) > 1e-6
    ):
        raise RuntimeError("profile does not show the 8 mm stock and rear-Z mouth in the labelled direction")
    return mouth


@_telemetry.traced("drawing.crank_arm_profile_turn")
def _turn_profile(adapter: Any, profile: Any) -> None:
    view = _early_bound(profile, "IView")
    if not math.isclose(float(view.Angle), 0.0, abs_tol=1e-8):
        raise RuntimeError("Top profile is already rotated; its CCW caption would be false")
    view.Angle = PROFILE_ANGLE
    rebuild_drawing(adapter, label="turn crank arm Top profile 90 DEG CCW")
    _profile_geometry(adapter, view)


@_telemetry.traced("drawing.crank_arm_profile_caption")
def _profile_caption(adapter: Any, profile: Any) -> Any:
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(view_name(adapter, profile)):
        raise RuntimeError("failed to activate the profile for its rotation caption")
    note = add_note(adapter, PROFILE_VIEW_CAPTION, *PROFILE_CAPTION_XY)
    if note is None:
        raise RuntimeError("failed to insert the rotated Top profile caption")
    return note


def _rendered_chamfer_edges(adapter: Any, profile: Any, annotation: Any) -> None:
    """Require the actual rear chamfer boundaries in the native rendered set.

    GetVisibleEntities2 excludes completely obscured entities, including an
    internal mouth; a positive count cannot prove this HLV edge prints.
    GetPolylines7(1) instead pairs each rendered polyline with its model edge.
    Its XYZs are used ONLY to reject empty/degenerate rendering, never treated
    as sheet coordinates. Model geometry is projected by SolidWorks separately.
    """
    view = _early_bound(profile, "IView")
    app = _early_bound(adapter.swApp, "ISldWorks")
    part = _early_bound(view.ReferencedDocument, "IPartDoc")
    raw_feature = part.FeatureByName("BoreRearChamfer")
    if raw_feature is None:
        raise RuntimeError("profile has no source BoreRearChamfer feature")
    faces = list(_early_bound(raw_feature, "IFeature").GetFaces() or ())
    expected = (
        (0.0, HUB_SEAT_DIA / 2.0 + BORE_REAR_CHAMFER),
        (BORE_REAR_CHAMFER, HUB_SEAT_DIA / 2.0),
    )
    boundaries: list[Any] = []
    for z_mm, radius_mm in expected:
        matches = []
        for face in faces:
            for raw_edge in _early_bound(face, "IFace2").GetEdges() or ():
                edge = _early_bound(raw_edge, "IEdge")
                curve = _early_bound(edge.GetCurve(), "ICurve")
                if not curve.IsCircle():
                    continue
                values = tuple(float(value) for value in curve.CircleParams)
                if (
                    len(values) == 7
                    and all(math.isfinite(value) for value in values)
                    and math.dist(values[:3], (0.0, 0.0, z_mm / 1000.0)) < 1e-8
                    and abs(abs(values[5]) - 1.0) < 1e-8
                    and math.hypot(values[3], values[4]) < 1e-8
                    and abs(values[6] - radius_mm / 1000.0) < 1e-8
                    and not any(int(app.IsSame(edge, other)) == 1 for other in matches)
                ):
                    matches.append(edge)
        if len(matches) != 1:
            raise RuntimeError("profile cannot identify both actual rear bore-chamfer boundary edges")
        boundaries.append(matches[0])
    native = _early_bound(annotation, "IAnnotation")
    attached = tuple(native.GetAttachedEntities3() or ())
    kinds = tuple(int(value) for value in (native.GetAttachedEntityTypes() or ()))
    if (
        len(attached) != len(kinds)
        or len(attached) != int(native.GetAttachedEntityCount3())
        or not attached
        or any(item is None for item in attached)
        or not any(
            int(app.IsSame(item, receiver)) == 1
            for item, kind in zip(attached, kinds)
            for receiver in (boundaries if kind == 1 else faces if kind == 2 else ())
        )
    ):
        raise RuntimeError("native chamfer leg is not attached to its actual rear-mouth feature")
    # Generated IView binding returns (model edges, out polyline buffer).
    result = view.GetPolylines7(1)
    if not isinstance(result, (list, tuple)) or len(result) != 2:
        raise RuntimeError("profile chamfer rendered-edge readback is unavailable")
    edges, raw = result
    data = tuple(float(value) for value in (raw or ()))
    if not all(math.isfinite(value) for value in data):
        raise RuntimeError("profile chamfer rendered-edge data is non-finite")
    rendered = [False, False]
    cursor = 0
    for edge in edges or ():
        if cursor + 2 > len(data):
            raise RuntimeError("profile rendered-edge buffer is truncated")
        kind, size = data[cursor:cursor + 2]
        if (kind, size) not in ((0.0, 0.0), (1.0, 12.0)):
            raise RuntimeError("profile rendered-edge geometry has an unsupported native shape")
        count_at = cursor + 2 + int(size) + 6
        if count_at >= len(data):
            raise RuntimeError("profile rendered-edge buffer lacks its point count")
        count = int(data[count_at])
        end = count_at + 1 + 3 * count
        if count < 0 or count != data[count_at] or end > len(data):
            raise RuntimeError("profile rendered-edge buffer has an invalid point count")
        points = [data[index:index + 3] for index in range(count_at + 1, end, 3)]
        if edge is not None and any(math.dist(a, b) > 1e-9 for a, b in zip(points, points[1:])):
            for index, boundary in enumerate(boundaries):
                if int(app.IsSame(edge, boundary)) == 1:
                    rendered[index] = True
        cursor = end
    if cursor != len(data) or not all(rendered):
        raise RuntimeError("profile does not render both actual rear bore-chamfer edges")


@_telemetry.traced("drawing.crank_arm_profile_chamfer")
def _place_profile_chamfer(adapter: Any, profile: Any, annotations: list[Any]) -> None:
    """Offset the imported native leg, never replace it with a note/dimension."""
    annotation = _early_bound(_named(adapter, annotations, "BoreRearChamferSize"), "IAnnotation")
    _assert_profile_chamfer(adapter, profile, annotation)
    mouth = _profile_geometry(adapter, profile)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.OffsetText = False
    if bool(display.OffsetText) or not annotation.SetPosition2(*mouth, 0.0):
        raise RuntimeError("failed to place the native bore-mouth dimension line")
    offset_dimension_text(
        adapter, [annotation], {"BoreRearChamferSize": PROFILE_KEEP["BoreRearChamferSize"]}
    )
    _assert_chamfer_offset(annotation)


def _assert_chamfer_offset(annotation: Any) -> None:
    native = _early_bound(annotation, "IAnnotation")
    display = _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension")
    position = tuple(float(value) for value in (native.GetPosition() or ()))
    if (
        not bool(display.OffsetText)
        or len(position) != 3
        or not all(math.isfinite(value) for value in position)
        or math.dist(position[:2], PROFILE_KEEP["BoreRearChamferSize"]) > 1e-5
    ):
        raise RuntimeError("native bore-mouth chamfer lost its final offset leader position")


def _dimension_text_bounds(annotation: Any, *, label: str) -> tuple[float, float, float, float]:
    """Whole native text runs, not requested anchors or estimated glyph widths."""
    native = _early_bound(annotation, "IAnnotation")
    display = _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    texts = []
    for index in range(int(data.GetTextCount())):
        text = str(data.GetTextAtIndex(index) or "")
        if not text.strip():
            continue
        position = tuple(float(value) for value in (data.GetTextPositionAtIndex(index) or ()))
        width = float(data.GetTextInBoxWidthAtIndex(index))
        height = float(data.GetTextHeightAtIndex(index))
        angle = float(data.GetTextAngleAtIndex(index))
        if (
            len(position) != 3 or width <= 0.0 or height <= 0.0
            or not all(math.isfinite(value) for value in (*position, width, height, angle))
        ):
            raise RuntimeError(f"{label}: native dimension text has no measurable whole bounds")
        texts.append({"t": text, "pos": position, "w": width, "h": height, "ang": angle})
    box = display_box({"texts": texts})
    if box is None:
        raise RuntimeError(f"{label}: native dimension has no rendered text")
    return (box.xmin, box.ymin, box.xmax, box.ymax)


@_telemetry.traced("drawing.crank_arm_profile_readback")
def _profile_chamfer_clear(
    adapter: Any, front: Any, profile: Any, front_annotations: list[Any],
    profile_annotations: list[Any], callouts: dict[str, Any], caption: Any,
) -> None:
    """Fail before review unless the native import, receiver and whole ink survive."""
    annotation = _named(adapter, profile_annotations, "BoreRearChamferSize")
    _assert_profile_chamfer(adapter, profile, annotation)
    _assert_chamfer_offset(annotation)
    mouth = _profile_geometry(adapter, profile)
    _rendered_chamfer_edges(adapter, profile, annotation)
    depth = _named(adapter, profile_annotations, "Depth")
    stock = _assert_profile_dimension(adapter, profile, depth, "Depth@Arm")
    stock_dimension = _early_bound(stock.GetDimension2(0), "IDimension")
    if (
        stock.IsReferenceDim() is not True
        or int(stock_dimension.GetType()) != 0
        or not math.isclose(float(stock_dimension.SystemValue) * 1000.0, ARM_THICKNESS, abs_tol=1e-7)
        or int(stock.GetPrimaryPrecision2()) != DRAWING_PRECISION_BY_NAME["Depth"]
    ):
        raise RuntimeError("profile stock thickness lost its native 8 mm reference")
    ink = callout_ink(adapter, annotation, label="far-side bore-mouth chamfer")
    x0, y0, x1, y1 = ink.text
    left, bottom, right, top = CHAMFER_TEXT_LANE
    front_box = tuple(float(value) for value in _early_bound(front, "IView").GetOutline())
    profile_box = tuple(float(value) for value in _early_bound(profile, "IView").GetOutline())
    region = sheet_region(adapter)
    if (
        len(front_box) != 4 or len(profile_box) != 4
        or not all(math.isfinite(value) for value in (*ink.text, *front_box, *profile_box))
        or not (
            max(left, front_box[2] + 0.002, region.xmin + 0.003) <= x0 < x1
            <= min(right, profile_box[0] - 0.002, region.xmax - 0.003)
            and max(bottom, region.ymin + 0.003) <= y0 < y1
            <= min(top, region.ymax - 0.003)
        )
    ):
        raise RuntimeError(f"bore-mouth chamfer text leaves its clear profile lane: {ink.text}")
    chamfer = dimension_segments(annotation)
    if not chamfer or landing_distance(chamfer, mouth) > 0.001:
        raise RuntimeError("native bore-mouth chamfer leader does not land on the rear-Z mouth")
    others = {
        name: _named(adapter, front_annotations, name)
        for name in ("Width", "EndRadius")
    }
    others.update(callouts)
    others["stock thickness"] = depth
    other_boxes = {}
    collisions = []
    for name, other in others.items():
        segments = dimension_segments(other)
        box = _dimension_text_bounds(other, label=name)
        other_boxes[name] = box
        if (
            not segments or not boxes_clear(ink.text, box, 0.002)
            or any(distance_to_box(segment, ink.text) < 0.002 for segment in segments)
            or any(distance_to_box(segment, box) < 0.002 for segment in chamfer)
            or any(segments_cross(first, second) for first in chamfer for second in segments)
        ):
            collisions.append(name)
    note = _early_bound(caption, "INote")
    note_annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    extent = tuple(float(value) for value in (note.GetExtent() or ()))
    position = tuple(float(value) for value in (note_annotation.GetPosition() or ()))
    if (
        str(note.GetText() or "") != PROFILE_VIEW_CAPTION
        or int(note_annotation.Visible) != 1 or int(note_annotation.OwnerType) != 0
        or int(_early_bound(adapter.swApp, "ISldWorks").IsSame(note_annotation.Owner, profile)) != 1
        or len(position) != 3 or not all(math.isfinite(value) for value in position)
        or math.dist(position[:2], PROFILE_CAPTION_XY) > 1e-5
        or len(extent) != 6 or not all(math.isfinite(value) for value in extent)
    ):
        raise RuntimeError("rotated Top profile caption did not persist with its view")
    caption_box = (extent[0], extent[1], extent[3], extent[4])
    if (
        caption_box[0] >= caption_box[2] or caption_box[1] >= caption_box[3]
        or not boxes_clear(ink.text, caption_box, 0.002)
        or any(not boxes_clear(caption_box, box, 0.002) for box in other_boxes.values())
        or not boxes_clear(profile_box, caption_box, 0.002)
        or not (
            region.xmin + 0.003 <= caption_box[0] < caption_box[2] <= region.xmax - 0.003
            and region.ymin + 0.003 <= caption_box[1] < caption_box[3] <= region.ymax - 0.003
        )
    ):
        collisions.append("profile caption")
    if collisions:
        raise RuntimeError(f"bore-mouth chamfer crowds existing callouts: {collisions}")


def _hub_seat_leader_clear(adapter: Any, annotations: list[Any]) -> None:
    """Land the hub seat bore on its near rim, clear of R12.7.

    The bore is made first and keeps the title block's .X band: its limits
    are the U29 cheek's real limits (dt_crank_hub_geometry).  MHA-DT-31 is turned
    to suit it for a light press, and the note under the value states that
    fit; the band bounds the bore, the note the fit (drawing-guidelines.md rule 4 (tighten only for function, and name the mate): "any
    retained dimensional limits still apply").
    """
    hub_seat = _named(adapter, annotations, "HubSeatDia")
    set_near_side_diameter(hub_seat, "hub seat diameter")
    rebuild_drawing(adapter, label="hub seat near-side leader")
    assert_leaders_clear(
        {
            "HubSeatDia": dimension_segments(hub_seat),
            "BossRadius": dimension_segments(_named(adapter, annotations, "BossRadius")),
        },
        centre=BORE_CENTER,
        keep_out={"HubSeatDia": HUB_SEAT_KEEP_OUT},
        lands_within={"HubSeatDia": HUB_SEAT_LANDING, "BossRadius": BOSS_RADIUS_LANDING},
        label="crank arm hub seat",
    )


def _texts_off_the_part(adapter: Any, annotations: list[Any]) -> None:
    """Fail when a front-view dimension's text sits inside the arm's silhouette."""
    inside = {
        dimension_name(adapter, annotation): points
        for annotation in annotations
        if (points := points_inside(dimension_text_points(annotation), ARM_SILHOUETTE))
    }
    _telemetry.event("drawing.texts_off_part", inside=str(inside))
    if inside:
        raise RuntimeError(f"dimension text inside the arm silhouette {ARM_SILHOUETTE}: {inside}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-arm source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank arm; separate through hub; axial seam key",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    profile = place_view(adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=PROFILE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, profile, iso):
        set_hidden_lines_removed(adapter, view)
    # Only the profile exposes the internal rear mouth. Front and isometric
    # retain HLR; the replacement profile carries both native chamfer and stock.
    set_hidden_lines_visible(adapter, profile)
    _turn_profile(adapter, profile)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="rotated Top profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    imported_annotations = [*front_annotations, *profile_annotations]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    # The part authored every displayed decimal place.  The hub seat bore
    # is a one-place .X size: MHA-DT-31 is turned to suit it.
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)
    # The thickness is the supplied stock's (the stock note governs it).
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, _named(adapter, profile_annotations, name), label="arm stock thickness"
        )
    _hub_seat_leader_clear(adapter, front_annotations)
    _place_profile_chamfer(adapter, profile, profile_annotations)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    _texts_off_the_part(adapter, front_annotations)

    # Handle-pivot callout attaches at the hole's top rim; the pivot's station
    # from the bore axis is the part's PivotStation dim imported above.
    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + _HANDLE_PIVOT_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    # Anchor tap: size and THRU on a native Hole Wizard callout; its
    # station from the bore axis and its offset from the top long edge are the
    # part's StationReference dims imported above.
    anchor_edge = (
        _sheet_x(ANCHOR_SCREW_X),
        FRONT_CENTER[1]
        + (ANCHOR_SCREW_Y + _ANCHOR_HOLE_DIA / 2.0) * SHEET_SCALE[0] / 1000.0,
    )
    anchor_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=anchor_edge,
        callout_xy=ANCHOR_CALLOUT_XY,
        label="anchor tap",
    )
    _omit_title_block_thread_class(anchor_callout)
    # The true overall (boss extreme to handle-end extreme), as a reference
    # below the 75.0 station so nobody saws the stock a radius short
    # (Harvey #25).  Both ends are arcs, each picked on its outer flank and
    # re-anchored to its far extreme below.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(-HALF_WIDTH), FRONT_CENTER[1]),
        p1=(_sheet_x(ARM_C2C + _END_PICK_DX), FRONT_CENTER[1] - _END_PICK_DY_SHEET),
        text_xy=(_sheet_x(ARM_C2C / 2.0), 0.073),
        label="overall length reference",
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label="overall length reference")
    # add_edge_dimension hands back the IDisplayDimension (late-bound); bind
    # it before reading the IAnnotation the reference helper wants.
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length reference",
    )
    _set_reference_precision(adapter, overall, "overall length reference")

    # MHA-DT-VN-59's axial seam is match-drilled in the assembled arm and hub; its
    # callout names the mate, the fit and the pin's nominal size and depth.
    add_attached_note(
        adapter,
        front,
        text=SEAM_CALLOUT,
        entity_xy=SEAM_EDGE_PICK,
        note_xy=SEAM_CALLOUT_XY,
        label="MHA-DT-VN-59 seam callout",
    )
    # The punched fiducial is flagged at the mark itself, from the clear
    # band above the boss end.
    add_attached_note(
        adapter,
        front,
        text=FIDUCIAL_CALLOUT,
        entity_xy=FIDUCIAL_EDGE_PICK,
        note_xy=FIDUCIAL_CALLOUT_XY,
        label="punched fiducial callout",
    )
    # Handle pivot tap (MHA-DT-32): above and just right of the arm, arrow on
    # the hole's top rim, clear of the full principal view.  Thread and tap
    # drill ride the native callout; the class is the title block's.  The
    # mate and mouth limit follow the thread row, so the callout names this
    # tap, not the identical anchor.
    pivot_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=PIVOT_CALLOUT_XY,
        label="handle pivot tap",
    )
    _omit_title_block_thread_class(pivot_callout)
    _append_callout_rows(pivot_callout, PIVOT_TAP_ROWS)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)
    caption = _profile_caption(adapter, profile)
    rebuild_drawing(adapter, label="final crank arm profile annotations")
    # A real HLR/HLV toggle regenerates the internal edge set after insertion.
    # Missing imports, receivers, edge ink or text bounds fail BEFORE review.
    set_hidden_lines_visible(adapter, profile)
    _profile_chamfer_clear(
        adapter, front, profile, front_annotations, profile_annotations,
        {
            "handle pivot": _early_bound(pivot_callout, "IDisplayDimension").GetAnnotation(),
            "anchor tap": _early_bound(anchor_callout, "IDisplayDimension").GetAnnotation(),
            "overall length": _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        },
        caption,
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Arm Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks pins its own "... Tapped Hole" note to the front view
        # once a tap carries a hole callout; the anchor and pivot callouts
        # already state each thread and drill (iter3 printed both).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
