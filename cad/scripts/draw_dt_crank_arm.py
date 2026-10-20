r"""Create the curated machinist drawing for crank arm MHA-DT-06.

Separate through hub MHA-DT-31 is a light press in the arm's seat bore, turned
to suit it.  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-DT-VN-59,
match-drilled with the hub; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-DT-32 shoulder screw.  The
principal view identifies the hub seat; the existing rotated Top/profile gets
one local breakout to the bore axis, exposing the far-side chamfer in solid
HLR ink while retaining its imported model leg and press lead-in intent.
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

from solidworks_mcp.adapters.com_variant import double_array
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
    distance_to_point,
    landing_distance,
    points_inside,
    segments_cross,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_selection import _activate_and_select_view
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _hole_spec import blind_cut_dia_mm
from _layout_geometry import estimate_text_box, union_boxes
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


def _native_text(value: Any) -> str:
    """Canonicalise native line endings only; every other character is exact."""
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def _omit_title_block_thread_class(display: Any) -> None:
    """Remove only the redundant Hole Wizard thread-class field."""
    native = _early_bound(display, "IDisplayDimension")
    definition = _native_text(native.GetText(5))
    without_class = re.sub(
        r"[ \t]*(?:-[ \t]*)?<hw-threadclass>[ \t]*", " ", definition, flags=re.IGNORECASE
    )
    if without_class == definition:
        raise RuntimeError(
            f"anchor tap callout lacks its thread-class variable: {definition!r}"
        )
    # IDisplayDimension.SetText is void; the definition readback is the
    # authoritative persistence check.
    native.SetText(1, without_class)
    if _native_text(native.GetText(5)) != without_class:
        raise RuntimeError("anchor tap callout retained its redundant thread class")


def _append_callout_rows(display: Any, rows: str) -> None:
    """Add ``rows`` under a native hole callout's thread row.

    The definition (``GetText(5)``) carries the thread row; appending keeps
    the tap-drill and thread rows together, with the rows below them (#984
    review r3: a prefix split the callout between the two).
    """
    native = _early_bound(display, "IDisplayDimension")
    definition = _native_text(native.GetText(5))
    if not definition.strip():
        raise RuntimeError("hole callout has no definition to extend")
    extended = definition.rstrip("\n") + "\n" + _native_text(rows)
    native.SetText(1, extended)
    actual = _native_text(native.GetText(5))
    if actual != extended:
        raise RuntimeError(f"hole callout rows did not persist: {actual!r}")


# Per-view survivors of the marked-dimension import.
FRONT_KEEP = {
    "PivotStation": (_sheet_x(ARM_C2C / 2.0), 0.095),
    "AnchorStation": (_sheet_x(ANCHOR_SCREW_X / 2.0), 0.104),
    "AnchorOffset": (0.108, FRONT_CENTER[1] + HALF_WIDTH * SHEET_SCALE[0] / 1000.0 + 0.008),
    "Width": (0.279, FRONT_CENTER[1]),
    "BossRadius": (0.030, FRONT_CENTER[1]),
    # Below the front view and left of the profile's chamfer text lane.
    "EndRadius": (0.242, 0.087),
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
PIVOT_CALLOUT_XY = (0.270, 0.225)
PROFILE_KEEP = {
    "Depth": (0.300, 0.210),
    "BoreRearChamferSize": (0.2645, 0.095),
}
# The seven-row native block (two LIMIT rows plus the five short suffix rows)
# stands between the front and profile silhouettes, below Width and the pivot
# callout. These are lane limits, not a substitute for whole-ink readback.
CHAMFER_TEXT_LANE = (0.2498, 0.074, 0.277, 0.1146)
DIMENSION_CALLOUTS = {
    "HubSeatDia": HUB_SEAT_CALLOUT,
    "BoreRearChamferSize": BORE_REAR_CHAMFER_CALLOUT,
}


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _arm_read(errors: list[str], label: str, read: Any, *, required: bool = False) -> Any:
    """Keep failed native measurements distinct from valid empty readbacks.

    Only this arm's new guards use the collection. Source/drawing creation and
    the pre-existing front-view guards retain their fatal failure semantics.
    """
    try:
        value = read()
        if required and value is None:
            raise RuntimeError("required native object/readback is absent")
        return value
    except Exception as exc:
        failure = f"UNMEASURED {label}: {type(exc).__name__}: {str(exc)[:512]}"
        _telemetry.info(failure)
        errors.append(failure)
        return None


def _arm_check(
    errors: list[str], label: str, actual: Any, expected: Any, valid: bool,
) -> None:
    """Log bounded primitive readbacks, never native object representations."""
    _telemetry.info(f"crank arm native {label}: actual={actual!r}, expected={expected!r}")
    if not valid:
        errors.append(label)


def _raise_arm_errors(errors: list[str]) -> None:
    if errors:
        raise RuntimeError("crank arm native guard violations:\n- " + "\n- ".join(errors))


def _finite_tuple(values: Any, size: int) -> bool:
    return (
        isinstance(values, tuple) and len(values) == size
        and all(math.isfinite(value) for value in values)
    )


def _assert_chamfer_limits(annotation: Any, *, errors: list[str]) -> None:
    """Measure every part-authored identity, leg and LIMIT field independently."""
    native = _arm_read(errors, "chamfer annotation", lambda: _early_bound(annotation, "IAnnotation"), required=True)
    display = _arm_read(errors, "chamfer display", lambda: _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension"), required=True)
    dimension = _arm_read(errors, "chamfer dimension", lambda: _early_bound(display.GetDimension2(0), "IDimension"), required=True)
    name = _arm_read(errors, "chamfer FullName", lambda: str(dimension.FullName))
    kind = _arm_read(errors, "chamfer dimension type", lambda: int(dimension.GetType()))
    leg = _arm_read(errors, "chamfer model leg", lambda: float(dimension.SystemValue) * 1000.0)
    tolerance = _arm_read(errors, "chamfer tolerance", lambda: _early_bound(dimension.Tolerance, "IDimensionTolerance"), required=True)
    tol_type = _arm_read(errors, "chamfer tolerance type", lambda: int(tolerance.Type))
    lower = _arm_read(errors, "chamfer lower deviation", lambda: float(tolerance.GetMinValue()) * 1000.0)
    upper = _arm_read(errors, "chamfer upper deviation", lambda: float(tolerance.GetMaxValue()) * 1000.0)
    identity = ["BoreRearChamferSize", "BoreRearChamfer"]
    _arm_check(errors, "imported bore-mouth chamfer has the wrong model identity/type (identity)", name, identity,
               name is not None and name.split("@")[:2] == identity)
    _arm_check(errors, "imported bore-mouth chamfer has the wrong model identity/type (type)", kind, 0, kind == 0)
    _arm_check(errors, "imported bore-mouth chamfer changed its model leg", leg, BORE_REAR_CHAMFER,
               leg is not None and math.isclose(leg, BORE_REAR_CHAMFER, abs_tol=1e-7))
    wanted_lower, wanted_upper = BORE_REAR_CHAMFER_DEVIATIONS
    for field, actual, wanted in (
        ("type", tol_type, BORE_REAR_CHAMFER_TOL_TYPE),
        ("lower", lower, wanted_lower), ("upper", upper, wanted_upper),
    ):
        _arm_check(errors, f"imported bore-mouth chamfer lost its native LIMIT band ({field})",
                   actual, wanted, actual is not None and math.isclose(actual, wanted, abs_tol=1e-9))


def _assert_profile_dimension(
    adapter: Any, profile: Any, annotation: Any, parameter: str, *, errors: list[str],
) -> Any:
    """Read every ownership/display field even when another field already failed."""
    native = _arm_read(errors, f"{parameter} annotation", lambda: _early_bound(annotation, "IAnnotation"), required=True)
    view = _arm_read(errors, f"{parameter} view", lambda: _early_bound(profile, "IView"), required=True)
    app = _arm_read(errors, f"{parameter} application", lambda: _early_bound(adapter.swApp, "ISldWorks"), required=True)
    kind = _arm_read(errors, f"{parameter} annotation type", lambda: int(native.GetType()))
    visible = _arm_read(errors, f"{parameter} visibility", lambda: int(native.Visible))
    owner_type = _arm_read(errors, f"{parameter} owner type", lambda: int(native.OwnerType))
    owner_object = _arm_read(errors, f"{parameter} owner object", lambda: native.Owner, required=True)
    owner = _arm_read(errors, f"{parameter} owner identity",
                      lambda: int(app.IsSame(owner_object, view)) if owner_object is not None and view is not None else None, required=True)
    dangling = _arm_read(errors, f"{parameter} dangling", lambda: native.IsDangling())
    for field, actual, wanted in (
        ("type", kind, 4), ("visible", visible, 1), ("owner type", owner_type, 0),
        ("owner IsSame", owner, 1), ("dangling", dangling, False),
    ):
        _arm_check(errors, f"{parameter}: dimension is not visible and attached in the profile view ({field})",
                   actual, wanted, actual is not None and actual == wanted)
    display = _arm_read(errors, f"{parameter} display", lambda: _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension"), required=True)
    dimension = _arm_read(errors, f"{parameter} dimension", lambda: _early_bound(display.GetDimension2(0), "IDimension"), required=True)
    source = _arm_read(errors, f"{parameter} source document", lambda: _early_bound(view.ReferencedDocument, "IModelDoc2"), required=True)
    expected = _arm_read(errors, f"{parameter} source Parameter", lambda: source.Parameter(parameter), required=True)
    same = _arm_read(errors, f"{parameter} source Parameter IsSame", lambda: int(app.IsSame(dimension, expected)) if dimension is not None and expected is not None else None, required=True)
    _arm_check(errors, f"{parameter}: dimension is not the source model dimension",
               (dimension is not None, expected is not None, same), (True, True, 1), same == 1)
    override = _arm_read(errors, f"{parameter} override", lambda: display.GetOverride())
    shown = _arm_read(errors, f"{parameter} displayed value", lambda: display.ShowDimensionValue)
    _arm_check(errors, f"{parameter}: dimension lost its native displayed value (override)", override, False, override is False)
    _arm_check(errors, f"{parameter}: dimension lost its native displayed value (shown)", shown, True, shown is True)
    return display


def _assert_profile_chamfer(
    adapter: Any, profile: Any, annotation: Any, *, errors: list[str],
) -> None:
    """Preserve the model's identity, LIMIT band, precision and exact suffix."""
    display = _assert_profile_dimension(
        adapter, profile, annotation, "BoreRearChamferSize@BoreRearChamfer", errors=errors,
    )
    _assert_chamfer_limits(annotation, errors=errors)
    reference = _arm_read(errors, "chamfer reference", lambda: display.IsReferenceDim())
    precision = _arm_read(errors, "chamfer primary precision", lambda: int(display.GetPrimaryPrecision2()))
    tol_precision = _arm_read(errors, "chamfer tolerance precision", lambda: int(display.GetPrimaryTolPrecision2()))
    raw_suffix = _arm_read(errors, "chamfer raw suffix", lambda: display.GetText(4), required=True)
    suffix = _native_text(raw_suffix) if raw_suffix is not None else None
    places = DRAWING_PRECISION_BY_NAME["BoreRearChamferSize"]
    for field, actual, wanted, valid in (
        ("reference", reference, False, reference is False),
        ("primary precision", precision, places, precision == places),
        ("tolerance precision", tol_precision, places, tol_precision == places),
        ("suffix", (raw_suffix, suffix), _native_text(BORE_REAR_CHAMFER_CALLOUT),
         suffix == _native_text(BORE_REAR_CHAMFER_CALLOUT)),
    ):
        _arm_check(errors, f"bore-mouth chamfer lost its native value, LIMIT precision or callout ({field})",
                   actual, wanted, valid)


def _profile_geometry(adapter: Any, profile: Any, *, errors: list[str], expected_mode: int = 2) -> Any:
    """Read the actual Top/90-CCW/1:1 XZ axes, stock and rear-mouth projection."""
    view = _arm_read(errors, "profile geometry view", lambda: _early_bound(profile, "IView"), required=True)
    orientation = _arm_read(errors, "profile orientation", lambda: str(view.GetOrientationName()))
    angle = _arm_read(errors, "profile angle", lambda: float(view.Angle))
    scale = _arm_read(errors, "profile scale", lambda: tuple(float(value) for value in view.ScaleRatio))
    mode = _arm_read(errors, "profile display mode", lambda: int(view.GetDisplayMode2()))
    for field, actual, wanted, valid in (
        ("orientation", orientation, "Top", orientation is not None and orientation.lstrip("*").casefold() == "top"),
        ("angle", angle, PROFILE_ANGLE, angle is not None and math.isfinite(angle)
         and math.isclose(math.remainder(angle - PROFILE_ANGLE, math.tau), 0.0, abs_tol=1e-8)),
        ("scale", scale, PROFILE_SCALE, scale == PROFILE_SCALE),
        ("mode", mode, expected_mode, mode == expected_mode),
    ):
        _arm_check(errors, f"profile lost its Top/90 DEG CCW/1:1/{'HLR' if expected_mode == 2 else 'temporary HLV import'} projection ({field})",
                   actual, wanted, valid)
    radius = HUB_SEAT_DIA / 2.0 + BORE_REAR_CHAMFER
    projected = _arm_read(
        errors, "profile projected axes/stock/rear-Z mouth",
        lambda: tuple(tuple(float(value) for value in point) for point in model_points_in_view(
            adapter, view,
            (
                (0.0, 0.0, 0.0), (0.001, 0.0, 0.0),
                (0.0, 0.001, 0.0), (0.0, 0.0, 0.001),
                (-HALF_WIDTH / 1000.0, 0.0, 0.0),
                (ARM_END_X / 1000.0, 0.0, ARM_THICKNESS / 1000.0),
                (-radius / 1000.0, 0.0, 0.0),
            ),
            label="crank arm turned top profile",
        )), required=True,
    )
    valid_points = projected is not None and len(projected) == 7 and all(_finite_tuple(point, 2) for point in projected)
    _arm_check(errors, "profile rear-Z mouth projection has invalid native points",
               projected, "seven finite XY points", valid_points)
    if not valid_points:
        errors.append("UNMEASURED profile projected axes/stock/rear-Z mouth: invalid projection dependency")
        return None
    origin, x_axis, y_axis, z_axis, low, high, mouth = projected
    axes = tuple((point[0] - origin[0], point[1] - origin[1]) for point in (x_axis, y_axis, z_axis))
    expected_axes = ((0.0, 0.001), (0.0, 0.0), (0.001, 0.0))
    cx, cy = PROFILE_CENTER
    half_length = (ARM_END_X + HALF_WIDTH) / 2000.0
    half_thickness = ARM_THICKNESS / 2000.0
    for index, (actual, wanted) in enumerate(zip(axes, expected_axes)):
        _arm_check(errors, f"profile does not show the rear-Z mouth in the labelled direction (axis {index})",
                   actual, wanted, math.dist(actual, wanted) <= 1e-8)
    for field, actual, wanted in (
        ("low stock", low, (cx - half_thickness, cy - half_length)),
        ("high stock", high, (cx + half_thickness, cy + half_length)),
        ("rear-Z mouth", mouth, (cx - half_thickness, cy - (ARM_C2C / 2.0 + radius) / 1000.0)),
    ):
        _arm_check(errors, f"profile does not show the 8 mm stock and rear-Z mouth in the labelled direction ({field})",
                   actual, wanted, math.dist(actual, wanted) <= 1e-6)
    return mouth


@_telemetry.traced("drawing.crank_arm_profile_turn")
def _turn_profile(adapter: Any, profile: Any, *, errors: list[str]) -> None:
    view = _arm_read(errors, "turn profile view", lambda: _early_bound(profile, "IView"), required=True)
    before = _arm_read(errors, "turn profile initial angle", lambda: float(view.Angle))
    can_turn = before is not None and math.isfinite(before) and math.isclose(before, 0.0, abs_tol=1e-8)
    _arm_check(errors, "Top profile is already rotated; its CCW caption would be false",
               before, 0.0, can_turn)
    if can_turn:
        _arm_read(errors, "turn profile Angle assignment", lambda: setattr(view, "Angle", PROFILE_ANGLE))
    _arm_read(errors, "turn profile rebuild", lambda: rebuild_drawing(adapter, label="turn crank arm Top profile 90 DEG CCW"))
    _profile_geometry(adapter, view, errors=errors, expected_mode=1)


@_telemetry.traced("drawing.crank_arm_profile_caption")
def _profile_caption(adapter: Any, profile: Any, *, errors: list[str]) -> Any:
    activated = _arm_read(errors, "activate caption profile", lambda: _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(view_name(adapter, profile)))
    _arm_check(errors, "failed to activate the profile for its rotation caption", activated, True, activated is True)
    return _arm_read(errors, "insert rotated Top profile caption",
                     lambda: add_note(adapter, PROFILE_VIEW_CAPTION, *PROFILE_CAPTION_XY), required=True)


def _chamfer_sources(adapter: Any, view: Any, *, errors: list[str]) -> list[list[Any]]:
    """Identify unique actual feature-owned outer and inner circles."""
    app = _arm_read(errors, "source chamfer application", lambda: _early_bound(adapter.swApp, "ISldWorks"), required=True)
    part = _arm_read(errors, "rendered chamfer source part", lambda: _early_bound(view.ReferencedDocument, "IPartDoc"), required=True)
    feature = _arm_read(errors, "source BoreRearChamfer feature", lambda: _early_bound(part.FeatureByName("BoreRearChamfer"), "IFeature"), required=True)
    faces = _arm_read(errors, "source chamfer faces", lambda: tuple(feature.GetFaces() or ()))
    expected = (
        (0.0, HUB_SEAT_DIA / 2.0 + BORE_REAR_CHAMFER),
        (BORE_REAR_CHAMFER, HUB_SEAT_DIA / 2.0),
    )
    matches: list[list[Any]] = [[], []]
    _telemetry.info(f"profile chamfer source faces={None if faces is None else len(faces)}, expected circles (z/r mm)={expected}")
    for face_index, face in enumerate(faces if faces is not None else ()):
        edges = _arm_read(errors, f"source chamfer face {face_index} edges",
                          lambda: tuple(_early_bound(face, "IFace2").GetEdges() or ()))
        for edge_index, raw_edge in enumerate(edges if edges is not None else ()):
            label = f"source chamfer face {face_index} edge {edge_index}"
            edge = _arm_read(errors, label, lambda: _early_bound(raw_edge, "IEdge"), required=True)
            curve = _arm_read(errors, f"{label} curve", lambda: _early_bound(edge.GetCurve(), "ICurve"), required=True)
            circle = _arm_read(errors, f"{label} IsCircle", lambda: curve.IsCircle())
            values = _arm_read(errors, f"{label} CircleParams",
                               lambda: tuple(float(value) for value in curve.CircleParams)) if circle is True else None
            _telemetry.info(f"{label}: IsCircle={circle!r}, CircleParams={values!r}, expected finite circle params=7")
            if circle is not True:
                continue
            valid = _finite_tuple(values, 7)
            _arm_check(errors, f"{label} has invalid source circle geometry", values, "seven finite values", valid)
            if not valid:
                continue
            for index, (z_mm, radius_mm) in enumerate(expected):
                actual = (
                    math.dist(values[:3], (0.0, 0.0, z_mm / 1000.0)),
                    abs(abs(values[5]) - 1.0), math.hypot(values[3], values[4]),
                    abs(values[6] - radius_mm / 1000.0),
                )
                same = tuple(_arm_read(errors, f"{label} boundary {index} duplicate IsSame",
                                       lambda other=other: int(app.IsSame(edge, other[0]))) for other in matches[index])
                _telemetry.info(f"{label} boundary {index}: center/axis/radius errors={actual!r}, expected each<1e-8; duplicate IsSame={same!r}, duplicate=1")
                if all(value < 1e-8 for value in actual) and 1 not in same:
                    matches[index].append((edge, values))
    for index, found in enumerate(matches):
        _arm_check(errors, f"profile cannot identify both actual rear bore-chamfer boundary edges (boundary {index})",
                   len(found), 1, len(found) == 1)
    return matches


def _project_native_points(adapter: Any, view: Any, points: Any, *, label: str, errors: list[str]) -> Any:
    projected = _arm_read(
        errors, f"{label} native projection",
        lambda: tuple(tuple(float(value) for value in point) for point in model_points_in_view(
            adapter, view, points, label=label,
        )), required=True,
    )
    valid = projected is not None and len(projected) == len(points) and all(_finite_tuple(point, 2) for point in projected)
    _arm_check(errors, f"{label} projection has invalid native points",
               projected, f"{len(points)} finite XY points", valid)
    return projected if valid else None


def _assert_profile_breakout(adapter: Any, profile: Any, *, errors: list[str]) -> None:
    """Read retained numeric depth without modifying the breakout definition."""
    view = _arm_read(errors, "retained breakout view", lambda: _early_bound(profile, "IView"), required=True)
    draw = _arm_read(errors, "retained breakout drawing", lambda: _early_bound(adapter.currentModel, "IModelDoc2"), required=True)
    _arm_read(errors, "clear breakout depth selections", lambda: draw.ClearSelection2(True))
    count = _arm_read(errors, "retained breakout count", lambda: int(view.GetBreakOutSectionCount()))
    features = _arm_read(errors, "retained breakout features", lambda: tuple(view.GetBreakOutSections() or ()))
    _arm_check(errors, "profile did not retain exactly one local breakout", (count, None if features is None else len(features)), (1, 1),
               count == 1 and features is not None and len(features) == 1)
    for index, feature in enumerate(features if features is not None else ()):
        data = _arm_read(errors, f"breakout {index} feature data",
                         lambda: _early_bound(_early_bound(feature, "IFeature").GetDefinition(), "IBrokenOutSectionFeatureData"), required=True)
        accessed = _arm_read(errors, f"breakout {index} AccessSelections", lambda: data.AccessSelections(draw, None))
        _arm_check(errors, f"breakout {index} definition selections unavailable", accessed, True, accessed is True)
        try:
            if accessed is True:
                reference = _arm_read(errors, f"breakout {index} DepthReference", lambda: data.DepthReference)
                _arm_check(errors, f"breakout {index} depth is not numeric", reference is not None, False, reference is None)
                # SDK: numeric Depth is valid only with no depth reference.
                depth = _arm_read(errors, f"breakout {index} retained Depth", lambda: float(data.Depth)) if reference is None else None
                _arm_check(errors, f"breakout {index} depth does not reach the bore axis",
                           depth, HALF_WIDTH / 1000.0,
                           depth is not None and math.isfinite(depth)
                           and math.isclose(depth, HALF_WIDTH / 1000.0, rel_tol=0.0, abs_tol=1e-8))
        finally:
            if accessed is True:
                _arm_read(errors, f"breakout {index} ReleaseSelectionAccess", data.ReleaseSelectionAccess)


@_telemetry.traced("drawing.crank_arm_local_breakout")
def _create_profile_breakout(adapter: Any, profile: Any, *, errors: list[str]) -> None:
    """One closed-spline cut on the existing Top, from +HALF_WIDTH to Y=0."""
    view = _arm_read(errors, "create breakout view", lambda: _early_bound(profile, "IView"), required=True)
    draw = _arm_read(errors, "create breakout model", lambda: _early_bound(adapter.currentModel, "IModelDoc2"), required=True)
    ddoc = _arm_read(errors, "create breakout drawing", lambda: _early_bound(adapter.currentModel, "IDrawingDoc"), required=True)
    before = _arm_read(errors, "initial breakout count", lambda: int(view.GetBreakOutSectionCount()))
    _arm_check(errors, "profile already has a breakout before its one creation attempt", before, 0, before == 0)
    sources = _chamfer_sources(adapter, view, errors=errors)
    mouths = tuple((found[0][1][0] - found[0][1][6], found[0][1][1], found[0][1][2])
                   for found in sources if len(found) == 1)
    projected = _project_native_points(adapter, view, mouths, label="breakout source mouth endpoints", errors=errors) if len(mouths) == 2 else None
    activated = _arm_read(errors, "activate/select breakout view",
                          lambda: _activate_and_select_view(adapter, view, label="crank arm local breakout"), required=True)
    sketch = _arm_read(errors, "breakout view sketch", lambda: _early_bound(view.GetSketch(), "ISketch"), required=True)
    transform = _arm_read(errors, "breakout ModelToSketchTransform", lambda: _early_bound(sketch.ModelToSketchTransform, "IMathTransform"), required=True)
    utility = _arm_read(errors, "breakout math utility", lambda: _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility"), required=True)
    manager = _arm_read(errors, "breakout sketch manager", lambda: _early_bound(draw.SketchManager, "ISketchManager"), required=True)
    sheet_points = ()
    sketch_points = []
    if projected is not None:
        cx = (projected[0][0] + projected[1][0]) / 2.0
        cy = (projected[0][1] + projected[1][1]) / 2.0
        rx = abs(projected[1][0] - projected[0][0]) / 2.0 + 0.001
        ry = abs(projected[1][1] - projected[0][1]) / 2.0 + 0.001
        sheet_points = ((cx - rx, cy, 0.0), (cx, cy + ry, 0.0), (cx + rx, cy, 0.0),
                        (cx, cy - ry, 0.0), (cx - rx, cy, 0.0))
        for index, point in enumerate(sheet_points):
            native = _arm_read(errors, f"breakout spline point {index}",
                               lambda point=point: _early_bound(utility.CreatePoint(double_array(list(point))), "IMathPoint"), required=True)
            transformed = _arm_read(errors, f"breakout spline point {index} transform",
                                    lambda: _early_bound(native.MultiplyTransform(transform), "IMathPoint"), required=True)
            coords = _arm_read(errors, f"breakout spline point {index} XYZ",
                               lambda: tuple(float(value) for value in transformed.ArrayData))
            _arm_check(errors, f"breakout spline point {index} is unmeasured", coords, "finite sketch XYZ", _finite_tuple(coords, 3))
            sketch_points.append(coords)
    valid_points = (
        len(sketch_points) == 5 and all(_finite_tuple(point, 3) for point in sketch_points)
        and sketch_points[0] == sketch_points[-1]
        and all(math.dist(a, b) > 1e-9 for a, b in zip(sketch_points, sketch_points[1:]))
    )
    _arm_check(errors, "breakout spline is not a measured nondegenerate closed profile",
               sketch_points, "five finite XYZs; first equals last; distinct adjacent points", valid_points)
    _telemetry.info(f"profile breakout requestedDepth={HALF_WIDTH / 1000.0!r}, source_mouths={mouths!r}, sheet_spline={sheet_points!r}, sketch_spline={sketch_points!r}, before_count={before!r}")
    ready = before == 0 and activated is not None and manager is not None and valid_points
    segment = None
    if ready:
        def insert_spline():
            previous = manager.AddToDB
            try:
                # CreateSpline always writes directly; restore the prior mode
                # regardless of insertion success, matching view-sketch hygiene.
                manager.AddToDB = True
                return _early_bound(manager.CreateSpline(double_array([value for point in sketch_points for value in point])), "ISketchSegment")
            finally:
                manager.AddToDB = previous
        segment = _arm_read(errors, "create breakout closed spline", insert_spline, required=True)
    else:
        errors.append("UNMEASURED breakout creation: source/count/view-sketch prerequisites unavailable")
    selected = _arm_read(errors, "breakout spline Select4", lambda: segment.Select4(True, None)) if segment is not None else None
    _arm_check(errors, "breakout spline selection failed", selected, True, selected is True)
    selection = _arm_read(errors, "breakout selection manager", lambda: _early_bound(draw.SelectionManager, "ISelectionMgr"), required=True)
    selected_count = _arm_read(errors, "pre-create breakout selection count", lambda: int(selection.GetSelectedObjectCount2(-1)))
    selected_types = tuple(_arm_read(errors, f"pre-create breakout selection type {index}",
                                     lambda index=index: int(selection.GetSelectedObjectType3(index, -1)))
                           for index in range(1, selected_count + 1)) if selected_count is not None else None
    _telemetry.info(f"profile breakout pre-Create selection count={selected_count!r}, types={selected_types!r}, splineSelect4={selected!r}; no arbitrary count gate")
    created = _arm_read(errors, "single CreateBreakOutSection", lambda: ddoc.CreateBreakOutSection(HALF_WIDTH / 1000.0)) if ready and selected is True else None
    _arm_check(errors, "native local breakout creation failed (no retry)", created, True, created is True)
    _arm_read(errors, "clear selections after breakout creation", lambda: draw.ClearSelection2(True))
    _arm_read(errors, "breakout final hidden lines removed", lambda: set_hidden_lines_removed(adapter, view))
    _arm_read(errors, "breakout rebuild", lambda: rebuild_drawing(adapter, label="crank arm local breakout"))
    after = _arm_read(errors, "post-create breakout count", lambda: int(view.GetBreakOutSectionCount()))
    _arm_check(errors, "profile breakout count did not change from zero to one", (before, after), (0, 1), (before, after) == (0, 1))
    _assert_profile_breakout(adapter, view, errors=errors)


def _solid_record(ddoc: Any, style: tuple[float, ...], cache: dict[tuple[str, int], Any], *, label: str, errors: list[str]) -> bool:
    """Use each record's documented decoder namespace; never retry another."""
    decoder = "GetLineFontInfo2" if style[1] == -1.0 else "GetLineFontInfo"
    raw_index = style[2] if style[1] == -1.0 else style[1]
    valid_index = math.isfinite(raw_index) and raw_index >= 0.0 and raw_index.is_integer()
    _arm_check(errors, f"{label} has no native font index", style, "nonnegative integral LineStyle, or LineFont when LineStyle=-1", valid_index)
    if not valid_index:
        return False
    index = int(raw_index)
    key = (decoder, index)
    if key not in cache:
        raw = _arm_read(errors, f"line font {index} {decoder} raw return",
                        lambda: getattr(ddoc, decoder)(index), required=True)
        # Keep unexpected legacy payloads diagnosable BEFORE any numeric or
        # shape interpretation. Only a flat segment-count/length array is valid.
        _telemetry.info(f"line font decoder={decoder!r}, index={index}, native_raw_return={raw!r}")
        cache[key] = _arm_read(
            errors, f"line font {index} {decoder} flat numeric pattern",
            lambda: tuple(float(value) for value in raw) if isinstance(raw, (list, tuple)) else None,
            required=True,
        )
    pattern = cache[key]
    valid = (
        isinstance(pattern, tuple) and len(pattern) >= 2 and all(math.isfinite(value) for value in pattern)
        and pattern[0] >= 1 and pattern[0].is_integer() and int(pattern[0]) == len(pattern) - 1
    )
    solid = valid and all(value > 0.0 for value in pattern[1:])
    _telemetry.info(f"{label} style fields (color/style/font/weight/layer/override)={style!r}, decoder={decoder!r}, effective_font={index}, native_pattern={pattern!r}, solid={solid!r}")
    _arm_check(errors, f"{label} does not have a measured continuous native line font",
               pattern, "integral positive segment count; matching finite positive lengths; no gaps", solid)
    return solid


def _circle_record(points: Any, circle: Any, *, label: str, errors: list[str]) -> bool:
    """Establish MODEL coordinates against the actual native circle, pointwise."""
    valid_circle = _finite_tuple(circle, 7)
    residuals = tuple((
        abs(sum((point[axis] - circle[axis]) * circle[axis + 3] for axis in range(3))),
        abs(math.dist(point, circle[:3]) - circle[6]),
    ) for point in points) if valid_circle else ()
    valid = valid_circle and len(points) >= 2 and all(plane <= 1e-8 and radial <= 1e-8 for plane, radial in residuals)
    maximum = tuple(max((pair[axis] for pair in residuals), default=math.inf) for axis in range(2))
    _telemetry.info(f"{label} MODEL circle frame: native_circle={circle!r}, raw_samples={points[:3]!r}/{points[-2:]!r}, measured_point_count={len(residuals)}, max_plane/radius_residual={maximum!r}, expected each<=1e-8m")
    _arm_check(errors, f"{label} raw polyline points are not measured MODEL-circle coordinates", (len(residuals), maximum), "every plane/radius residual <= 1e-8 m", valid)
    return valid


def _model_segment_distance(point: Any, first: Any, last: Any) -> float:
    delta = tuple(b - a for a, b in zip(first, last))
    length_sq = sum(value * value for value in delta)
    if length_sq == 0.0:
        return math.dist(point, first)
    fraction = max(0.0, min(1.0, sum((p - a) * d for p, a, d in zip(point, first, delta)) / length_sq))
    return math.dist(point, tuple(a + fraction * d for a, d in zip(first, delta)))


def _within_contour_tolerance(distance: float) -> bool:
    return distance <= 5e-5 or math.isclose(distance, 5e-5, rel_tol=0.0, abs_tol=1e-12)


def _rendered_chamfer_edges(
    adapter: Any, profile: Any, annotation: Any, *, errors: list[str],
) -> None:
    """Prove solid actual polyline coverage, never joining clipped records."""
    view = _arm_read(errors, "rendered chamfer view", lambda: _early_bound(profile, "IView"), required=True)
    app = _arm_read(errors, "rendered chamfer application", lambda: _early_bound(adapter.swApp, "ISldWorks"), required=True)
    ddoc = _arm_read(errors, "rendered chamfer drawing", lambda: _early_bound(adapter.currentModel, "IDrawingDoc"), required=True)
    matches = _chamfer_sources(adapter, view, errors=errors)
    boundaries = []
    for index, found in enumerate(matches):
        if len(found) == 1:
            if index == 0:
                try:
                    mapped = view.GetCorrespondingEntity(found[0][0])
                except Exception as exc:
                    mapped = None
                    _telemetry.info(f"profile chamfer outer mapping telemetry: UNMEASURED {type(exc).__name__}: {str(exc)[:512]}")
            else:
                mapped = _arm_read(errors, f"chamfer boundary {index} GetCorrespondingEntity part-to-view",
                                   lambda: view.GetCorrespondingEntity(found[0][0]), required=True)
        else:
            mapped = None
            errors.append(f"UNMEASURED chamfer boundary {index} mapping: source boundary is not unique")
        _telemetry.info(f"profile chamfer boundary {index} mapping: source_count={len(found)}, view_entity_present={mapped is not None}, expected source_count=1; inner mapping mandatory, outer telemetry only")
        boundaries.append(mapped)
    if all(boundary is not None for boundary in boundaries):
        same = _arm_read(errors, "mapped chamfer boundary pair IsSame", lambda: int(app.IsSame(*boundaries)))
        _arm_check(errors, "mapped rear chamfer boundaries are not distinct", same, 0, same == 0)

    # Attachment support varies for imported feature dimensions. Each field is
    # independent telemetry, including an exception; none contributes a gate.
    inventory = {}
    for member, read in (
        ("GetAttachedEntities3", lambda: len(tuple(_early_bound(annotation, "IAnnotation").GetAttachedEntities3() or ()))),
        ("GetAttachedEntityTypes", lambda: tuple(int(value) for value in (_early_bound(annotation, "IAnnotation").GetAttachedEntityTypes() or ()))),
        ("GetAttachedEntityCount3", lambda: int(_early_bound(annotation, "IAnnotation").GetAttachedEntityCount3())),
    ):
        try:
            inventory[member] = read()
        except Exception as exc:
            inventory[member] = None
            _telemetry.info(f"profile chamfer attachment telemetry {member}: UNMEASURED {type(exc).__name__}: {str(exc)[:512]}")
    _telemetry.info(
        f"profile chamfer native attachments: count={inventory['GetAttachedEntityCount3']}, "
        f"types={inventory['GetAttachedEntityTypes']}, entities={inventory['GetAttachedEntities3']}"
    )
    result = _arm_read(errors, "profile GetPolylines7(1)", lambda: view.GetPolylines7(1), required=True)
    valid_result = isinstance(result, (list, tuple)) and len(result) == 2
    _arm_check(errors, "profile chamfer rendered-edge readback is unavailable",
               (type(result).__name__, len(result) if isinstance(result, (list, tuple)) else None),
               "two-item (edges, raw) result", valid_result)
    edges = _arm_read(errors, "profile rendered edges", lambda: tuple(result[0] or ())) if valid_result else None
    data = _arm_read(errors, "profile rendered polyline data", lambda: tuple(float(value) for value in (result[1] or ()))) if valid_result else None
    finite = data is not None and all(math.isfinite(value) for value in data)
    _arm_check(errors, "profile chamfer rendered-edge data is non-finite or unavailable",
               (None if data is None else len(data), None if data is None else tuple(index for index, value in enumerate(data) if not math.isfinite(value))),
               "available, all finite", finite)
    rendered = [False, False]
    cursor = 0
    poly_count = 0
    offsets_known = finite
    candidates = []
    stock_rendered = False
    stock_records = []
    outer_circle = matches[0][0][1] if len(matches[0]) == 1 else None
    inner_circle = matches[1][0][1] if len(matches[1]) == 1 else None
    source_points = tuple((circle[0] - circle[6], circle[1], circle[2])
                          for circle in (outer_circle, inner_circle) if circle is not None)
    source_sheet = _project_native_points(adapter, view, source_points, label="rendered chamfer source endpoints", errors=errors) if len(source_points) == 2 else None
    bevel_rendered = False
    fonts: dict[tuple[str, int], Any] = {}
    for edge_index, edge in enumerate(edges if edges is not None else ()):
        signature = None
        # Circle signatures also identify the actual stock candidate below;
        # unreadable unrelated curves remain bounded diagnostic telemetry.
        try:
            if edge is None:
                signature = "silhouette"
            else:
                curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
                signature = tuple(float(value) for value in curve.CircleParams) if curve.IsCircle() else "not circle"
            if len(candidates) < 32:
                candidates.append((edge_index, signature))
        except Exception as exc:
            if len(candidates) < 32:
                candidates.append((edge_index, "UNMEASURED", type(exc).__name__, str(exc)[:160]))
        identities = tuple(
            _arm_read(errors, f"rendered edge {edge_index} / mapped boundary {index} IsSame",
                      lambda boundary=boundary: int(app.IsSame(edge, boundary)))
            if edge is not None and boundary is not None else None
            for index, boundary in enumerate(boundaries)
        )
        _telemetry.info(f"profile rendered edge {edge_index}: entity_present={edge is not None}, mapped_boundary_IsSame={identities!r}, expected match=1")
        if not offsets_known:
            errors.append(f"UNMEASURED rendered edge {edge_index} polyline: invalid preceding buffer dependency")
            continue
        header_ok = cursor + 2 <= len(data)
        _arm_check(errors, f"profile rendered-edge buffer is truncated (edge {edge_index})",
                   (cursor, len(data)), "cursor+2 <= rawlen", header_ok)
        if not header_ok:
            offsets_known = False
            continue  # Identities/signatures of subsequent edges remain measurable.
        kind, size = data[cursor:cursor + 2]
        shape_ok = (kind, size) in ((0.0, 0.0), (1.0, 12.0))
        _arm_check(errors, f"profile rendered-edge geometry has an unsupported native shape (edge {edge_index})",
                   (kind, size), ((0.0, 0.0), (1.0, 12.0)), shape_ok)
        if not shape_ok:
            offsets_known = False
            continue
        count_at = cursor + 2 + int(size) + 6
        count_ok = count_at < len(data)
        _arm_check(errors, f"profile rendered-edge buffer lacks its point count (edge {edge_index})",
                   (count_at, len(data)), "count_at < rawlen", count_ok)
        if not count_ok:
            offsets_known = False
            continue
        count = int(data[count_at])
        end = count_at + 1 + 3 * count
        valid_count = count >= 0 and count == data[count_at] and end <= len(data)
        _arm_check(errors, f"profile rendered-edge buffer has an invalid point count (edge {edge_index})",
                   (data[count_at], count, end, len(data)), "nonnegative integral count and end <= rawlen", valid_count)
        if not valid_count:
            offsets_known = False
            continue
        points = tuple(data[index:index + 3] for index in range(count_at + 1, end, 3))
        longest = max((math.dist(a, b) for a, b in zip(points, points[1:])), default=0.0)
        style = data[count_at - 6:count_at]
        _telemetry.info(f"profile rendered edge {edge_index}: cursor={cursor}, end={end}, point_count={count}, longest_segment={longest!r}, style={style!r}, raw_samples={points[:3]!r}/{points[-2:]!r}, expected>1e-9")
        stock_circle = (
            _finite_tuple(signature, 7)
            and math.dist(signature[:3], (0.0, 0.0, 0.0)) < 1e-8
            and abs(abs(signature[5]) - 1.0) < 1e-8
            and math.hypot(signature[3], signature[4]) < 1e-8
            and abs(signature[6] - HALF_WIDTH / 1000.0) < 1e-8
        )
        outer_match = identities[0] == 1
        inner_match = identities[1] == 1
        selected_circle = outer_match or inner_match
        if stock_circle:
            stock_records.append((edge_index, signature, points, style))
        projected = None
        solid = False
        if selected_circle:
            solid = _solid_record(ddoc, style, fonts, label=f"rendered edge {edge_index}", errors=errors)
            circle = outer_circle if outer_match else inner_circle
            if _circle_record(points, circle, label=f"rendered edge {edge_index}", errors=errors):
                projected = _project_native_points(adapter, view, points, label=f"rendered edge {edge_index} MODEL circle ink", errors=errors)
            segments = tuple((a, b) for a, b in zip(projected, projected[1:]) if math.dist(a, b) > 1e-9) if projected is not None else ()
            if inner_match and solid and segments:
                rendered[1] = True
            if outer_match:
                distances = tuple(distance_to_point(segment, source_sheet[0]) for segment in segments) if source_sheet is not None else ()
                distance = min(distances, default=math.inf)
                _telemetry.info(f"rendered edge {edge_index} direct outer boundary: projected_record={projected!r}, source_outer={None if source_sheet is None else source_sheet[0]!r}, adjacent_segment_distances={distances!r}, actual_distance={distance!r}, expected<=5e-5m (equality roundoff<=1e-12m)")
                rendered[0] = rendered[0] or (solid and bool(segments) and _within_contour_tolerance(distance))
        # A section-created bevel may have no original IEdge counterpart. Its
        # ACTUAL non-hatch ink must lie on the bounded source generatrix at Y=0.
        bevel_residuals = tuple(_model_segment_distance(point, *source_points) for point in points) if len(source_points) == 2 else ()
        bevel_candidate = longest > 1e-9 and bool(bevel_residuals) and all(value <= 1e-8 for value in bevel_residuals)
        if bevel_candidate:
            bevel_solid = _solid_record(ddoc, style, fonts, label=f"rendered bevel edge {edge_index}", errors=errors)
            bevel_points = _project_native_points(adapter, view, points, label=f"rendered bevel edge {edge_index} MODEL ink", errors=errors)
            segments = tuple((a, b) for a, b in zip(bevel_points, bevel_points[1:]) if math.dist(a, b) > 1e-9) if bevel_points is not None else ()
            coverage = tuple(min((distance_to_point(segment, endpoint) for segment in segments), default=math.inf) for endpoint in source_sheet) if source_sheet is not None else ()
            _telemetry.info(f"rendered bevel edge {edge_index}: source_endpoints={source_points!r}, raw_samples={points[:3]!r}/{points[-2:]!r}, model_residuals={bevel_residuals!r}, projected_record={bevel_points!r}, endpoint_distances={coverage!r}, expected both<=5e-5m on same solid record")
            bevel_rendered = bevel_rendered or (bevel_solid and bool(segments) and len(coverage) == 2 and all(_within_contour_tolerance(distance) for distance in coverage))
        cursor = end
        poly_count += 1
    # A local cut may expose the real outer rim while clipping away the old
    # stock contour. Prefer its authoritative mapped source identity; measure
    # the coincident stock representation only when no direct record proves it.
    stock_contours = len(stock_records)
    if not rendered[0]:
        for edge_index, circle, points, style in stock_records:
            solid = _solid_record(ddoc, style, fonts, label=f"rendered stock edge {edge_index}", errors=errors)
            projected = None
            if _circle_record(points, circle, label=f"rendered stock edge {edge_index}", errors=errors):
                projected = _project_native_points(adapter, view, points, label=f"rendered stock edge {edge_index} MODEL circle ink", errors=errors)
            segments = tuple((a, b) for a, b in zip(projected, projected[1:]) if math.dist(a, b) > 1e-9) if projected is not None else ()
            distances = tuple(distance_to_point(segment, source_sheet[0]) for segment in segments) if source_sheet is not None else ()
            distance = min(distances, default=math.inf)
            _telemetry.info(f"rendered edge {edge_index} actual stock contour: projected_record={projected!r}, source_outer={None if source_sheet is None else source_sheet[0]!r}, adjacent_segment_distances={distances!r}, actual_distance={distance!r}, expected<=5e-5m (equality roundoff<=1e-12m)")
            stock_rendered = stock_rendered or (solid and bool(segments) and _within_contour_tolerance(distance))
    representation = "direct mapped outer boundary" if rendered[0] else "coincident rendered stock contour" if stock_rendered else "UNPROVEN"
    _telemetry.info(f"profile chamfer outer representation={representation!r}, direct_proven={rendered[0]!r}, stock_record_count={stock_contours}, stock_proven={stock_rendered!r}")
    _telemetry.info(f"profile chamfer rendered candidate circle signatures (first 32): {candidates!r}; edge_count={None if edges is None else len(edges)}")
    _telemetry.info(f"profile chamfer rendered proof: flags={tuple(rendered)}, cursor={cursor}, rawlen={None if data is None else len(data)}, edge_count={None if edges is None else len(edges)}, poly_count={poly_count}")
    _arm_check(errors, "profile rendered-edge buffer was not fully measured",
               (cursor, None if data is None else len(data), poly_count, None if edges is None else len(edges)),
               "cursor=rawlen and poly_count=edge_count",
               data is not None and edges is not None and cursor == len(data) and poly_count == len(edges))
    _arm_check(errors, "profile does not render the actual inner rear bore-chamfer edge (boundary 1)",
               rendered[1], True, rendered[1])
    _arm_check(errors, "profile lacks a solid directly rendered outer boundary or actual rendered stock-face contour for the outer chamfer mouth",
               (rendered[0], stock_contours, stock_rendered), "solid MODEL-validated mapped outer or stock record; adjacent segment distance <= 0.05 mm",
               rendered[0] or stock_rendered)
    _arm_check(errors, "profile lacks a solid actual chamfer section stroke at the bore axis",
               bevel_rendered, "one MODEL-validated solid record covering both source chamfer endpoints", bevel_rendered)


@_telemetry.traced("drawing.crank_arm_profile_chamfer")
def _place_profile_chamfer(
    adapter: Any, profile: Any, annotations: list[Any], *, errors: list[str],
) -> None:
    """Attempt independent placement work, retaining every failure until export."""
    annotation = _arm_read(errors, "place expected one BoreRearChamferSize",
                           lambda: _early_bound(_named(adapter, annotations, "BoreRearChamferSize"), "IAnnotation"), required=True)
    _assert_profile_chamfer(adapter, profile, annotation, errors=errors)
    mouth = _profile_geometry(adapter, profile, errors=errors)
    display = _arm_read(errors, "place chamfer display", lambda: _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension"), required=True)
    _arm_read(errors, "clear chamfer OffsetText", lambda: setattr(display, "OffsetText", False))
    offset = _arm_read(errors, "initial chamfer OffsetText readback", lambda: display.OffsetText)
    _arm_check(errors, "failed to place the native bore-mouth dimension line (OffsetText)", offset, False, offset is False)
    if mouth is None:
        errors.append("UNMEASURED native bore-mouth dimension line placement: rear-Z mouth is unavailable")
    else:
        placed = _arm_read(errors, "native chamfer SetPosition2", lambda: annotation.SetPosition2(*mouth, 0.0))
        _arm_check(errors, "failed to place the native bore-mouth dimension line", (placed, mouth), (True, mouth), placed is True)
    if annotation is None:
        errors.append("UNMEASURED chamfer text offset: native annotation is unavailable")
    else:
        _arm_read(errors, "offset native chamfer text", lambda: offset_dimension_text(
            adapter, [annotation], {"BoreRearChamferSize": PROFILE_KEEP["BoreRearChamferSize"]},
        ))
    _assert_chamfer_offset(annotation, errors=errors)


def _assert_chamfer_offset(annotation: Any, *, errors: list[str]) -> None:
    native = _arm_read(errors, "offset chamfer annotation", lambda: _early_bound(annotation, "IAnnotation"), required=True)
    display = _arm_read(errors, "offset chamfer display", lambda: _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension"), required=True)
    offset = _arm_read(errors, "final chamfer OffsetText", lambda: display.OffsetText)
    position = _arm_read(errors, "final chamfer position", lambda: tuple(float(value) for value in (native.GetPosition() or ())))
    _arm_check(errors, "native bore-mouth chamfer lost its final offset leader (OffsetText)", offset, True, offset is True)
    _arm_check(errors, "native bore-mouth chamfer lost its final offset leader position",
               position, (*PROFILE_KEEP["BoreRearChamferSize"], 0.0),
               _finite_tuple(position, 3) and math.dist(position[:2], PROFILE_KEEP["BoreRearChamferSize"]) <= 1e-5)


def _dimension_text_bounds(
    annotation: Any, *, label: str, errors: list[str],
) -> Any:
    """Read ALL native runs; an invalid run never yields a partial passing box."""
    native = _arm_read(errors, f"{label} text annotation", lambda: _early_bound(annotation, "IAnnotation"), required=True)
    display = _arm_read(errors, f"{label} text display", lambda: _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension"), required=True)
    data = _arm_read(errors, f"{label} display data", lambda: _early_bound(display.GetDisplayData(), "IDisplayData"), required=True)
    count = _arm_read(errors, f"{label} text count", lambda: int(data.GetTextCount()))
    _arm_check(errors, f"{label}: native dimension has no rendered text", count, "positive text count",
               count is not None and count > 0)
    boxes = []
    invalid = count is None or count <= 0
    for index in range(count if count is not None and count > 0 else 0):
        run = f"{label} run {index}"
        raw_text = _arm_read(errors, f"{run} text", lambda: data.GetTextAtIndex(index), required=True)
        text = _native_text(raw_text) if raw_text is not None else None
        position = _arm_read(errors, f"{run} position", lambda: tuple(float(value) for value in (data.GetTextPositionAtIndex(index) or ())))
        width = _arm_read(errors, f"{run} width", lambda: float(data.GetTextInBoxWidthAtIndex(index)))
        height = _arm_read(errors, f"{run} height", lambda: float(data.GetTextHeightAtIndex(index)))
        angle = _arm_read(errors, f"{run} angle", lambda: float(data.GetTextAngleAtIndex(index)))
        reference = _arm_read(errors, f"{run} reference", lambda: data.GetTextRefPositionAtIndex(index))
        _telemetry.info(f"{run}: raw_text={raw_text!r}, text={text!r}, pos={position!r}, width={width!r}, height={height!r}, ref={reference!r}, angle={angle!r}; expected finite XYZ, positive width/height, ref=0..5, finite angle")
        if text is not None and not text.strip():
            continue
        fields = (
            ("text", text, "nonblank native text", text is not None),
            ("position", position, "finite XYZ", _finite_tuple(position, 3)),
            ("width", width, "finite width > 0", width is not None and math.isfinite(width) and width > 0.0),
            ("height", height, "finite height > 0", height is not None and math.isfinite(height) and height > 0.0),
            ("angle", angle, "finite angle", angle is not None and math.isfinite(angle)),
            ("reference", reference, "integer ref=0..5", type(reference) is int and reference in (0, 1, 2, 3, 4, 5)),
        )
        for field, actual, wanted, measured in fields:
            _arm_check(errors, f"{label}: native dimension text has no measurable whole bounds (run={index}) ({field})",
                       actual, wanted, measured)
        valid = all(measured for _field, _actual, _wanted, measured in fields)
        if not valid:
            invalid = True
            continue
        # This geometry is calibrated to the ACTUAL positive native width.
        # No zero-width fallback or estimated-width acceptance path exists.
        advance = _arm_read(errors, f"{run} measured width calibration",
                            lambda: width / (max(map(len, text.split("\n"))) * height))
        _arm_check(errors, f"{label}: native dimension text has no measurable whole bounds (run={index} calibration)",
                   advance, "finite positive native width/height ratio",
                   advance is not None and math.isfinite(advance) and advance > 0.0)
        if advance is None or not math.isfinite(advance) or advance <= 0.0:
            invalid = True
            continue
        box = _arm_read(errors, f"{run} whole bounds", lambda: estimate_text_box(
            text, anchor=position[:2], height=height, reference=reference,
            angle=angle, advance_ratio=advance,
        ), required=True)
        bounds = None if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)
        good_box = _finite_tuple(bounds, 4) and bounds[0] < bounds[2] and bounds[1] < bounds[3]
        _arm_check(errors, f"{label}: native dimension text has no measurable whole bounds (run={index} box)",
                   bounds, "finite positive-area measured bounds", good_box)
        if good_box:
            boxes.append(box)
        else:
            invalid = True
    box = union_boxes(boxes) if boxes and not invalid else None
    bounds = None if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)
    _arm_check(errors, f"{label}: native dimension has no rendered text / measurable whole bounds",
               bounds, "all nonblank runs measured", bounds is not None)
    return bounds


@_telemetry.traced("drawing.crank_arm_profile_readback")
def _profile_chamfer_clear(
    adapter: Any, front: Any, profile: Any, front_annotations: list[Any],
    profile_annotations: list[Any], callouts: dict[str, Any], caption: Any,
    *, errors: list[str],
) -> None:
    """Collect every independent final readback; build raises once before export."""
    annotation = _arm_read(errors, "final expected one BoreRearChamferSize",
                           lambda: _named(adapter, profile_annotations, "BoreRearChamferSize"), required=True)
    _assert_profile_chamfer(adapter, profile, annotation, errors=errors)
    _assert_chamfer_offset(annotation, errors=errors)
    mouth = _profile_geometry(adapter, profile, errors=errors)
    _rendered_chamfer_edges(adapter, profile, annotation, errors=errors)
    depth = _arm_read(errors, "final expected one Depth", lambda: _named(adapter, profile_annotations, "Depth"), required=True)
    stock = _assert_profile_dimension(adapter, profile, depth, "Depth@Arm", errors=errors)
    stock_dimension = _arm_read(errors, "stock dimension", lambda: _early_bound(stock.GetDimension2(0), "IDimension"), required=True)
    prefix = _arm_read(errors, "stock native reference prefix", lambda: stock.GetText(1), required=True)
    suffix = _arm_read(errors, "stock native reference suffix", lambda: stock.GetText(2), required=True)
    stock_data = _arm_read(errors, "stock native reference display data", lambda: _early_bound(stock.GetDisplayData(), "IDisplayData"), required=True)
    stock_runs = _arm_read(errors, "stock native reference displayed text",
                           lambda: tuple(stock_data.GetTextAtIndex(index) for index in range(stock_data.GetTextCount())), required=True)
    stock_text = "".join(stock_runs).strip() if stock_runs is not None and all(isinstance(run, str) for run in stock_runs) else None
    kind = _arm_read(errors, "stock dimension type", lambda: int(stock_dimension.GetType()))
    value = _arm_read(errors, "stock thickness mm", lambda: float(stock_dimension.SystemValue) * 1000.0)
    precision = _arm_read(errors, "stock primary precision", lambda: int(stock.GetPrimaryPrecision2()))
    for field, actual, wanted, valid in (
        ("prefix", prefix, "(", prefix == "("),
        ("suffix", suffix, ")", suffix == ")"),
        ("displayed text", stock_runs, "(8.0) with optional outer padding", stock_text == "(8.0)"),
        ("type", kind, 0, kind == 0),
        ("value mm", value, ARM_THICKNESS, value is not None and math.isclose(value, ARM_THICKNESS, abs_tol=1e-7)),
        ("precision", precision, DRAWING_PRECISION_BY_NAME["Depth"], precision == DRAWING_PRECISION_BY_NAME["Depth"]),
    ):
        _arm_check(errors, f"profile stock thickness lost its native 8 mm reference ({field})", actual, wanted, valid)

    ink = _arm_read(errors, "chamfer whole rendered callout ink",
                    lambda: callout_ink(adapter, annotation, label="far-side bore-mouth chamfer"), required=True)
    ink_box = _arm_read(errors, "chamfer whole ink box", lambda: tuple(float(value) for value in ink.text))
    front_box = _arm_read(errors, "front outline", lambda: tuple(float(value) for value in _early_bound(front, "IView").GetOutline()))
    profile_box = _arm_read(errors, "profile outline", lambda: tuple(float(value) for value in _early_bound(profile, "IView").GetOutline()))
    region = _arm_read(errors, "sheet region", lambda: sheet_region(adapter), required=True)
    region_box = _arm_read(errors, "sheet region bounds", lambda: (float(region.xmin), float(region.ymin), float(region.xmax), float(region.ymax)))
    for name, box in (("chamfer whole ink", ink_box), ("front", front_box), ("profile", profile_box), ("sheet", region_box)):
        _arm_check(errors, f"{name} has no finite positive whole bounds for the clear profile lane",
                   box, "four finite ordered bounds", _finite_tuple(box, 4) and box[0] < box[2] and box[1] < box[3])
    lane = None
    if all(_finite_tuple(box, 4) for box in (front_box, profile_box, region_box)):
        left, bottom, right, top = CHAMFER_TEXT_LANE
        lane = (
            max(left, front_box[2] + 0.002, region_box[0] + 0.003),
            max(bottom, region_box[1] + 0.003),
            min(right, profile_box[0] - 0.002, region_box[2] - 0.003),
            min(top, region_box[3] - 0.003),
        )
    else:
        errors.append("UNMEASURED clear profile lane: outline/sheet dependency is invalid")
    _arm_check(errors, "bore-mouth chamfer text leaves its clear profile lane",
               (ink_box, front_box, profile_box, region_box), lane,
               lane is not None and _finite_tuple(ink_box, 4)
               and lane[0] <= ink_box[0] < ink_box[2] <= lane[2]
               and lane[1] <= ink_box[1] < ink_box[3] <= lane[3])
    chamfer = _arm_read(errors, "chamfer leader segments", lambda: tuple(dimension_segments(annotation)))
    landing = _arm_read(errors, "chamfer rear-Z mouth landing distance",
                        lambda: landing_distance(chamfer, mouth) if chamfer and mouth is not None else None, required=True)
    _arm_check(errors, "native bore-mouth chamfer leader does not land on the rear-Z mouth",
               (chamfer, mouth, landing), "nonempty segments, numerical-zero landing distance (abs_tol=1e-8 m)",
               landing is not None and math.isfinite(landing)
               and math.isclose(landing, 0.0, rel_tol=0.0, abs_tol=1e-8))

    others = {
        name: _arm_read(errors, f"final expected one {name}", lambda name=name: _named(adapter, front_annotations, name), required=True)
        for name in ("Width", "EndRadius")
    }
    others.update(callouts)
    others["stock thickness"] = depth
    other_boxes = {}
    for name, other in others.items():
        segments = _arm_read(errors, f"{name} leader segments", lambda: tuple(dimension_segments(other)))
        box = _dimension_text_bounds(other, label=name, errors=errors)
        other_boxes[name] = box
        _arm_check(errors, f"bore-mouth chamfer crowds existing callouts: {name} has no native leader",
                   segments, "nonempty segments", bool(segments))
        text_clear = _arm_read(errors, f"{name} text-to-chamfer clearance",
                              lambda: boxes_clear(ink_box, box, 0.002) if _finite_tuple(ink_box, 4) and _finite_tuple(box, 4) else None, required=True)
        other_distances = _arm_read(errors, f"{name} leaders-to-chamfer ink distances",
                                   lambda: tuple(distance_to_box(segment, ink_box) for segment in segments)
                                   if segments and _finite_tuple(ink_box, 4) else None, required=True)
        chamfer_distances = _arm_read(errors, f"chamfer leaders-to-{name} text distances",
                                     lambda: tuple(distance_to_box(segment, box) for segment in chamfer)
                                     if chamfer and _finite_tuple(box, 4) else None, required=True)
        crossings = _arm_read(errors, f"{name} leader crossings",
                             lambda: tuple(segments_cross(first, second) for first in chamfer for second in segments)
                             if chamfer and segments else None, required=True)
        for field, actual, wanted, valid in (
            ("whole text boxes", (ink_box, box, text_clear), "boxes clear by 0.002 m", text_clear is True),
            ("other leaders to ink", other_distances, "each distance >= 0.002 m",
             other_distances is not None and all(math.isfinite(value) and value >= 0.002 for value in other_distances)),
            ("chamfer leaders to text", chamfer_distances, "each distance >= 0.002 m",
             chamfer_distances is not None and all(math.isfinite(value) and value >= 0.002 for value in chamfer_distances)),
            ("leader crossings", crossings, "all False", crossings is not None and not any(crossings)),
        ):
            _arm_check(errors, f"bore-mouth chamfer crowds existing callouts: {name} ({field})", actual, wanted, valid)

    note = _arm_read(errors, "caption note", lambda: _early_bound(caption, "INote"), required=True)
    note_annotation = _arm_read(errors, "caption annotation", lambda: _early_bound(note.GetAnnotation(), "IAnnotation"), required=True)
    raw_text = _arm_read(errors, "caption raw text", lambda: note.GetText(), required=True)
    text = _native_text(raw_text) if raw_text is not None else None
    extent = _arm_read(errors, "caption extent", lambda: tuple(float(value) for value in (note.GetExtent() or ())))
    position = _arm_read(errors, "caption position", lambda: tuple(float(value) for value in (note_annotation.GetPosition() or ())))
    visible = _arm_read(errors, "caption visibility", lambda: int(note_annotation.Visible))
    owner_type = _arm_read(errors, "caption owner type", lambda: int(note_annotation.OwnerType))
    owner_object = _arm_read(errors, "caption owner object", lambda: note_annotation.Owner, required=True)
    owner = _arm_read(errors, "caption owner IsSame",
                      lambda: int(_early_bound(adapter.swApp, "ISldWorks").IsSame(owner_object, profile))
                      if owner_object is not None and profile is not None else None, required=True)
    for field, actual, wanted, valid in (
        ("raw/normalized text", (raw_text, text), _native_text(PROFILE_VIEW_CAPTION), text == _native_text(PROFILE_VIEW_CAPTION)),
        ("visibility", visible, 1, visible == 1), ("owner type", owner_type, 0, owner_type == 0),
        ("owner IsSame", owner, 1, owner == 1),
        ("position", position, (*PROFILE_CAPTION_XY, 0.0), _finite_tuple(position, 3) and math.dist(position[:2], PROFILE_CAPTION_XY) <= 1e-5),
        ("extent", extent, "six finite values", _finite_tuple(extent, 6)),
    ):
        _arm_check(errors, f"rotated Top profile caption did not persist with its view ({field})", actual, wanted, valid)
    caption_box = (extent[0], extent[1], extent[3], extent[4]) if _finite_tuple(extent, 6) else None
    valid_caption_box = _finite_tuple(caption_box, 4) and caption_box[0] < caption_box[2] and caption_box[1] < caption_box[3]
    _arm_check(errors, "bore-mouth chamfer crowds existing callouts: profile caption whole bounds",
               caption_box, "finite positive-area box", valid_caption_box)
    for name, box in {"chamfer": ink_box, "profile": profile_box, **other_boxes}.items():
        clear = _arm_read(errors, f"caption clearance from {name}",
                          lambda box=box: boxes_clear(caption_box, box, 0.002)
                          if valid_caption_box and _finite_tuple(box, 4) else None, required=True)
        _arm_check(errors, f"bore-mouth chamfer crowds existing callouts: profile caption / {name}",
                   (caption_box, box, clear), "boxes clear by 0.002 m", clear is True)
    _arm_check(errors, "bore-mouth chamfer crowds existing callouts: profile caption border",
               (caption_box, region_box), "caption inside sheet with 0.003 m air",
               valid_caption_box and _finite_tuple(region_box, 4)
               and region_box[0] + 0.003 <= caption_box[0] < caption_box[2] <= region_box[2] - 0.003
               and region_box[1] + 0.003 <= caption_box[1] < caption_box[3] <= region_box[3] - 0.003)


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
    # Temporary HLV preserves the proven native dimension import. The existing
    # Top then gets one local breakout and remains HLR for placement/export.
    arm_errors: list[str] = []
    _arm_read(arm_errors, "initial profile hidden lines visible", lambda: set_hidden_lines_visible(adapter, profile))
    _turn_profile(adapter, profile, errors=arm_errors)

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
    _arm_read(arm_errors, "imported model precision", lambda: assert_imported_precision(
        adapter, imported_annotations, DRAWING_PRECISION_BY_NAME,
    ))
    # The thickness is the supplied stock's (the stock note governs it).
    for name in sorted(REFERENCE_DIMENSIONS):
        _arm_read(arm_errors, f"{name} stock reference placement", lambda name=name: set_reference_dimension(
            adapter, _named(adapter, profile_annotations, name), label="arm stock thickness",
        ))
    _hub_seat_leader_clear(adapter, front_annotations)
    _create_profile_breakout(adapter, profile, errors=arm_errors)
    _place_profile_chamfer(adapter, profile, profile_annotations, errors=arm_errors)

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
    caption = _profile_caption(adapter, profile, errors=arm_errors)
    _arm_read(arm_errors, "final profile annotation rebuild",
              lambda: rebuild_drawing(adapter, label="final crank arm profile annotations"))
    # Retain HLR: the breakout, not hidden-line ink, exposes the chamfer.
    # Collect every independent guard before the single no-export boundary.
    _arm_read(arm_errors, "final profile hidden lines removed", lambda: set_hidden_lines_removed(adapter, profile))
    _assert_profile_breakout(adapter, profile, errors=arm_errors)
    _profile_chamfer_clear(
        adapter, front, profile, front_annotations, profile_annotations,
        {
            name: _arm_read(arm_errors, f"{name} final annotation",
                            lambda display=display: _early_bound(display, "IDisplayDimension").GetAnnotation(), required=True)
            for name, display in (
                ("handle pivot", pivot_callout), ("anchor tap", anchor_callout),
                ("overall length", overall),
            )
        },
        caption, errors=arm_errors,
    )
    _raise_arm_errors(arm_errors)

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
