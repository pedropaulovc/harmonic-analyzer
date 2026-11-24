r"""Create the curated machinist drawing for crank arm MHA-DT-06.

Separate through hub MHA-DT-31 is a bonded slip fit in the arm's seat bore,
turned to it (fit audit question 21).  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-DT-VN-59,
drilled with the hub at assembly; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-DT-32 shoulder screw.
The MHA-DT-09 taper-pin cross-hole belongs to the hub and shaft drawings.

The sheet remains deliberately plain: no datums, feature-control frames or
roughness symbols.  Every controlling value is imported from the part; matched
arm/hub and seam-pin operations are stated on their receiving feature/note.
The pivot callout uses a single near-rim arrow, so its leader stops before the
hole centre and does not cross the concentric end-radius leader.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_arm.py dt-crank-arm
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
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
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_leader_notes import add_attached_note
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    dimension_text_points,
    points_inside,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _part_properties import part_drawing_unit
from _printed_limits import drilled_limits, limits
from _supplier_dimensions import supplier_reference_dimension
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_arm_notes import (
    ANCHOR_TAP_ROWS,
    FIDUCIAL_CALLOUT,
    HUB_SEAT_CALLOUT,
    PIVOT_TAP_ROWS,
    SEAM_CALLOUT,
)
from dt_crank_arm_spec import (
    ANCHOR_EDGE_DIST,
    ANCHOR_HOLE_SPEC,
    ANCHOR_SCREW_X,
    ANCHOR_SCREW_Y,
    ANCHOR_TAP_WALL_MIN,
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    AXIAL_PIN_DIA,
    AXIAL_PIN_X,
    AXIS_FROM_EDGE_STATION_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FIDUCIAL_MODEL_DIA,
    FIDUCIAL_X,
    FIDUCIAL_Y,
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    HUB_SEAT_DIA,
    SEAT_PRESS_NOTE,
    STOCK_FRACTION_DENOMINATOR,
    STOCK_FRACTION_DIMENSIONS,
    UNIT,
)
from dt_crank_hub_geometry import SEAM_DEPTH
from dt_crank_handle_pivot_screw_spec import TAPPED_MOUTH_DIA_MAX


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

# Sheet layout (meters).  At 2:1 the 3.95-in overall arm remains clear of the
# title block, and the side view shows the 1 x 5/16 stock section.  The
# principal view sits so its lower edge keeps the dimension rows' height below
# it; the three callouts over the hub end (seat, seam, anchor tap) stand in a
# row above it so no leader crosses another.
FRONT_CENTER = (0.145, 0.142)
RIGHT_CENTER = (0.300, FRONT_CENTER[1])
ISO_CENTER = (0.360, 0.230)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the principal view (2:1, bbox-centred)."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


def _set_reference_precision(adapter: Any, display: Any, label: str) -> None:
    """Give the one SHEET-derived dimension its PART-authored decimal places.

    Every controlling dimension on this print is a model dimension whose
    places the part authored and ``assert_imported_precision`` reads back.
    The parenthesised overall (boss extreme to arm end) is the single
    exception: a read-only sum with no model dimension to import, so its
    places come from the spec's ``DRAWING_REFERENCE_PRECISION`` -- never a
    literal typed here.  ``SetPrecision3`` reports rejection through its
    return status rather than by raising, so the side effect is read back.
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


def _add_arm_centerline(adapter: Any, view: Any) -> None:
    """Draw the arm's longitudinal centreline between its two long edges.

    The through-hub seat and handle pivot lie on the arm mid-width axis.  A
    centreline through their centre marks draws that axis; the AxisFromEdge
    station locates it from the top edge, where a machinist sets the bore.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the front view for its centreline")
    draw.ClearSelection2(True)
    x = _sheet_x((ANCHOR_SCREW_X + ARM_C2C) / 2.0)
    for index, side in enumerate((-1.0, 1.0)):
        y = FRONT_CENTER[1] + side * HALF_WIDTH * SHEET_SCALE[0] / 1000.0
        if not draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        ):
            raise RuntimeError("failed to select an arm long edge for its centreline")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if centerline is None:
        raise RuntimeError("failed to insert the arm centreline between its edges")
    count = int(_early_bound(view, "IView").GetCenterLineCount())
    if count != 1:
        raise RuntimeError(f"front view carries {count} centrelines, expected 1")

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
    # The bore/pivot axis from the top edge, on its own construction line in
    # the empty span between the anchor and pivot callouts' leaders; its text
    # stands above the edge on the AnchorOffset row (fan-out round 5).
    "AxisFromEdge": (
        _sheet_x(AXIS_FROM_EDGE_STATION_X),
        FRONT_CENTER[1] + HALF_WIDTH * SHEET_SCALE[0] / 1000.0 + 0.008,
    ),
    "Width": (0.279, FRONT_CENTER[1]),
    # The punch witness's ordinates from the hub-seat axis: the X above the
    # boss end, under the witness's callout; the Y left of the boss.
    "FiducialX": (_sheet_x(FIDUCIAL_X / 2.0), 0.178),
    "FiducialY": (0.034, FRONT_CENTER[1] + FIDUCIAL_Y / 2.0 * SHEET_SCALE[0] / 1000.0),
    # Below the boss end, inboard of the overall's extension line: on the axis
    # its leader would run along the witness Y's extension line from the centre.
    "BossRadius": (0.057, 0.106),
    # Below and right of the handle end, clear of the Width row and the
    # pivot station row; its leader lands on the lower-right quarter of the arc.
    "EndRadius": (0.268, 0.100),
    "HubSeatDia": (0.048, 0.225),
}
# The hub seat's leader lands on the near rim, upper left of the bore: at
# 0.054 with both arrows it ran down through the bore centre to the far
# rim and crossed R.50's leader there (eye pass of w15-301f4bf4e; the
# 2026-09-23 review had flagged the far-side landing). Nothing but R.50
# itself may come within half the seat radius of the centre.
BORE_CENTER = (_sheet_x(0.0), FRONT_CENTER[1])
HUB_SEAT_KEEP_OUT = HUB_SEAT_DIA * SHEET_SCALE[0] / 4000.0
# Where each leader must END, from the bore centre (sheet metres): the hub
# seat on its rim, R.50 at the centre or on its arc. A reading outside the
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
# The seam's station from the bore axis, a horizontal reference between the
# bore rim (picked lower left, clear of every leader) and the seam arc
# (lower flank): SolidWorks measures circle to arc centre to centre.  Its
# text stands under the arm, above the .79 anchor station's row.
_DIAG = math.cos(math.pi / 4.0)
SEAM_STATION_PICKS = (
    (
        _sheet_x(-HUB_SEAT_DIA / 2.0 * _DIAG),
        FRONT_CENTER[1] - HUB_SEAT_DIA / 2.0 * _DIAG * SHEET_SCALE[0] / 1000.0,
    ),
    (
        _sheet_x(AXIAL_PIN_X + AXIAL_PIN_DIA / 2.0 * _DIAG),
        FRONT_CENTER[1] - AXIAL_PIN_DIA / 2.0 * _DIAG * SHEET_SCALE[0] / 1000.0,
    ),
)
SEAM_STATION_TEXT_XY = (_sheet_x(AXIAL_PIN_X / 2.0), 0.111)
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
# Under the hub-seat block, its right end left of the mark: the leader runs
# down and right to the rim, outside the FiducialX ordinate's lines and text
# (iter 1 of the 2026-10-27 fix: from right of the mark it ran through its text).
FIDUCIAL_CALLOUT_XY = (0.016, 0.205)
# The overall's pick on the handle-end arc: 2 mm below the axis, on the arc.
_END_PICK_DY_SHEET = 0.004
_END_PICK_DX = math.sqrt(HALF_WIDTH**2 - (_END_PICK_DY_SHEET * 1000.0 / SHEET_SCALE[0]) ** 2)
ANCHOR_CALLOUT_XY = (0.195, 0.205)
# Centre of the four-line pivot callout: its bottom row stays clear above
# the arm's top edge, its right end left of the isometric view.
PIVOT_CALLOUT_XY = (0.270, 0.190)
# The side view's stock thickness, dimensioned across its two faces.
_HALF_THICKNESS_SHEET = ARM_THICKNESS * SHEET_SCALE[0] / 2000.0
THICKNESS_PICKS = (
    (RIGHT_CENTER[0] - _HALF_THICKNESS_SHEET, RIGHT_CENTER[1]),
    (RIGHT_CENTER[0] + _HALF_THICKNESS_SHEET, RIGHT_CENTER[1]),
)
THICKNESS_TEXT_XY = (RIGHT_CENTER[0], 0.108)
DIMENSION_CALLOUTS = {"HubSeatDia": HUB_SEAT_CALLOUT}
# swDimensionArrowsSide_e.swDimArrowsInside, set rather than left to the
# document's smart arrows (draw_dt_pinion_arbor's form): left smart, the two
# ordinates drew their arrows outside, and the X's tails ran under the
# punch-mark and hub-seat leaders (machinist review of the 2026-10-27 fix's
# farm iter 2, rule 14).
ARROWS_INSIDE = ("FiducialX", "FiducialY")
_DIM_ARROWS_INSIDE = 0
# Both taps print their drill size .XXX.  The native variable is
# <hw-tapdrldia>, or <hw-thrutapdrldia> on a THRU tap (draw_pn_pen_v_block).
_TAP_DRILL_VARIABLES = ("hw-tapdrldia", "hw-thrutapdrldia")


def _tap_drill_precision(display: Any, label: str) -> None:
    """Print the tap callout's drill diameter at three places."""
    native = _early_bound(display, "IDisplayDimension")
    # swDimensionTextParts_e 5..8: the four definition parts; the drill row
    # is not in the thread row's part.
    definition = "\n".join(str(native.GetText(part) or "") for part in (5, 6, 7, 8))
    names = [name for name in _TAP_DRILL_VARIABLES if f"<{name}>" in definition]
    if len(names) != 1:
        raise RuntimeError(f"{label}: no single tap drill variable in {definition!r}")
    set_hole_callout_precision(display, {names[0]: 3}, label=label)


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    """Draw each ``ARROWS_INSIDE`` dimension's arrows inside its witnesses."""
    for name in ARROWS_INSIDE:
        annotation = _early_bound(_named(adapter, annotations, name), "IAnnotation")
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside its witnesses")


def _hub_seat_leader_clear(adapter: Any, annotations: list[Any]) -> None:
    """Land the hub seat bore on its near rim, clear of R.50.

    The bore is made first and keeps the title block's .XX band: its limits
    are the U29 cheek's real limits (crank_hub_geometry).  MHA-DT-31 is turned
    to it for a bonded slip fit, and the note under the value states that
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


# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame (the build
# docstring's layout: the hub seat's axis on Z at the origin, the arm along +X,
# its width across Y, the inboard face at Z0 and the outboard face, the one the
# front view shows, at +Z). A band is the dimension's own native band, else the
# title block's row for its printed places. The declarations print nothing.
_P = DRAWING_PRECISION_BY_NAME
_SELF = "draw_dt_crank_arm"
_SPEC = "dt_crank_arm_spec"
_NOTES = "dt_crank_arm_notes"
_HUB = "dt_crank_hub_geometry"
_FRAME = (_SPEC, "__frame__")
_UNIT = (_SPEC, "UNIT")
_Z = (0.0, 0.0, 1.0)


def _plane(axis: str, value: float) -> dict[str, Any]:
    return {"frame": "model", "axis": axis, "value": value}


part_metadata(
    fields={"material.thickness": (ARM_THICKNESS, ((_HUB, "ARM_THICKNESS"),))},
    model_sources=((_SPEC, "__frame__"), (_HUB, "ARM_THICKNESS"), (_HUB, "ARM_WIDTH")),
    precision_sources=(
        (_SPEC, "DRAWING_PRECISION"),
        (_SPEC, "DRAWING_PRECISION_BY_NAME"),
        (_SPEC, "DRAWING_REFERENCE_PRECISION"),
        (_SELF, "_tap_drill_precision"),
    ),
)
# The bar's two faces and two long edges, as supplied (note 1, the side
# view's (5/16") and the front view's (1")): the inboard face at Z0, the
# outboard face the front view shows; the top edge the bore axis, the anchor
# tap and the pivot are set from (AxisFromEdge, AnchorOffset).
requirement(
    "inboard_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={"plane": (_plane("z", 0.0), (_FRAME,))},
)
requirement(
    "outboard_face",
    kind="face",
    faces=(PlanarFace(_Z, ARM_THICKNESS),),
    requirements=("thickness_as_supplied",),
    fields={
        "plane": (_plane("z", ARM_THICKNESS), (_FRAME, (_HUB, "ARM_THICKNESS"))),
        "thickness_as_supplied": (
            ARM_THICKNESS,
            ((_HUB, "ARM_THICKNESS"), "STOCK_FRACTION_DIMENSIONS", "STOCK_NOTE"),
        ),
        "thickness_from": ("inboard_face", ((_SELF, "THICKNESS_PICKS"),)),
        "callout": ("(5/16\")", ("STOCK_FRACTION_DIMENSIONS",)),
    },
)
requirement(
    "top_edge",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), HALF_WIDTH),),
    requirements=("plane",),
    fields={"plane": (_plane("y", HALF_WIDTH), (_FRAME, (_HUB, "ARM_WIDTH")))},
)
requirement(
    "bottom_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), HALF_WIDTH),),
    requirements=("width_as_supplied",),
    fields={
        "plane": (_plane("y", -HALF_WIDTH), (_FRAME, (_HUB, "ARM_WIDTH"))),
        "width_as_supplied": (
            2.0 * HALF_WIDTH,
            ((_HUB, "ARM_WIDTH"), "STOCK_FRACTION_DIMENSIONS", "STOCK_NOTE"),
        ),
        "width_from": ("top_edge", ((_SELF, "FRONT_KEEP"),)),
        "callout": ("(1\")", ("STOCK_FRACTION_DIMENSIONS",)),
    },
)
# The two full-round ends, R.50 each at .XX (FRONT_KEEP "BossRadius",
# "EndRadius"), concentric with the hub seat and the handle pivot; the
# overall over both is the sheet's (3.95) reference.
requirement(
    "boss_end",
    kind="profile",
    faces=(CylinderFace(2.0 * HALF_WIDTH, contains_x_mm=-HALF_WIDTH / 2.0),),
    requirements=("radius",),
    fields={
        "radius": (
            limits(HALF_WIDTH, _P["BossRadius"], unit=UNIT),
            ("END_RADIUS", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "radius_nominal": (HALF_WIDTH, ("END_RADIUS",)),
        "centre_at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "extent_x": ([-HALF_WIDTH, 0.0], ("END_RADIUS",)),
        "extent_y": ([-HALF_WIDTH, HALF_WIDTH], ((_HUB, "ARM_WIDTH"),)),
    },
    precision={"radius": _P["BossRadius"]},
)
requirement(
    "handle_end",
    kind="profile",
    faces=(CylinderFace(2.0 * HALF_WIDTH, contains_x_mm=ARM_C2C + HALF_WIDTH / 2.0),),
    requirements=("radius",),
    fields={
        "radius": (
            limits(HALF_WIDTH, _P["EndRadius"], unit=UNIT),
            ("END_RADIUS", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "radius_nominal": (HALF_WIDTH, ("END_RADIUS",)),
        "centre_at": ([ARM_C2C, 0.0, 0.0], ("ARM_C2C",)),
        "overall_length_ref": (
            ARM_END_X + HALF_WIDTH,
            ("ARM_END_X", "HALF_WIDTH", "DRAWING_REFERENCE_PRECISION"),
        ),
        "extent_x": ([0.0, ARM_END_X], ("ARM_END_X",)),
        "extent_y": ([-HALF_WIDTH, HALF_WIDTH], ((_HUB, "ARM_WIDTH"),)),
    },
    precision={"radius": _P["EndRadius"]},
)
# The hub seat: .76 at the title block's .XX (FRONT_KEEP "HubSeatDia"), made
# first; MHA-DT-31 is turned to suit it (note 2). Its axis stands .50 from
# the top edge at .XX (FRONT_KEEP "AxisFromEdge").
requirement(
    "hub_seat",
    kind="hole",
    faces=(CylinderFace(HUB_SEAT_DIA),),
    requirements=("dia", "thru", "axis_from_edge"),
    fields={
        "at": ([0.0, 0.0, 0.0], (_FRAME,)),
        "axis": (_Z, (_FRAME,)),
        "dia": (
            limits(HUB_SEAT_DIA, _P["HubSeatDia"], unit=UNIT),
            ((_HUB, "HUB_SEAT_DIA"), _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "dia_nominal": (HUB_SEAT_DIA, ((_HUB, "HUB_SEAT_DIA"),)),
        "thru": (True, ((_SELF, "FRONT_KEEP"),)),
        "axis_from_edge": (
            limits(HALF_WIDTH, _P["AxisFromEdge"], unit=UNIT),
            ("HALF_WIDTH", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "axis_from_edge_nominal": (HALF_WIDTH, ("HALF_WIDTH",)),
        "axis_from_edge_from": ("top_edge", ((_SELF, "FRONT_KEEP"),)),
        "callout": (HUB_SEAT_CALLOUT, ((_NOTES, "HUB_SEAT_CALLOUT"),)),
        "fit_note": (SEAT_PRESS_NOTE, ("SEAT_PRESS_NOTE",)),
    },
    precision={"dia": _P["HubSeatDia"], "axis_from_edge": _P["AxisFromEdge"]},
)
# The MHA-DT-VN-59 seam: drilled 5/32 with the hub at assembly (note 3), so this
# part's traveler does not make it; the callout's (.156) is a reference, its
# .17 depth from the outboard face at .XX.
requirement(
    "seam",
    kind="hole",
    faces=(CylinderFace(AXIAL_PIN_DIA),),
    requirements=("depth",),
    fields={
        "at": ([AXIAL_PIN_X, 0.0, ARM_THICKNESS], ("AXIAL_PIN_X", (_HUB, "ARM_THICKNESS"))),
        "axis": ((0.0, 0.0, -1.0), (_FRAME,)),
        "dia_ref": (AXIAL_PIN_DIA, ((_HUB, "AXIAL_PIN_DIA"), (_NOTES, "SEAM_CALLOUT"))),
        "depth": (
            limits(SEAM_DEPTH, 2, unit=UNIT),
            ((_HUB, "SEAM_DEPTH"), _UNIT, (_NOTES, "SEAM_CALLOUT")),
        ),
        "depth_nominal": (SEAM_DEPTH, ((_HUB, "SEAM_DEPTH"),)),
        "depth_from": ("outboard_face", ((_NOTES, "SEAM_CALLOUT"),)),
        "made_at": ("assembly", ("SEAM_NOTE",)),
        "callout": (SEAM_CALLOUT, ((_NOTES, "SEAM_CALLOUT"),)),
    },
    precision={"depth": 2},
)
# The punched match mark on the outboard face: its centre two ordinates from
# the hub seat's axis at .XX (FRONT_KEEP "FiducialX", "FiducialY"); its size
# is the callout's, its process a punch.
requirement(
    "match_mark",
    kind="hole",
    faces=(CylinderFace(FIDUCIAL_MODEL_DIA),),
    requirements=("x_from_seat", "y_from_seat", "process"),
    fields={
        "at": ([FIDUCIAL_X, FIDUCIAL_Y, ARM_THICKNESS], ("FIDUCIAL_X", "FIDUCIAL_Y", (_HUB, "ARM_THICKNESS"))),
        "axis": ((0.0, 0.0, -1.0), (_FRAME,)),
        "x_from_seat": (
            limits(FIDUCIAL_X, _P["FiducialX"], unit=UNIT),
            ("FIDUCIAL_X", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "x_from_seat_nominal": (FIDUCIAL_X, ("FIDUCIAL_X",)),
        "y_from_seat": (
            limits(FIDUCIAL_Y, _P["FiducialY"], unit=UNIT),
            ("FIDUCIAL_Y", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "y_from_seat_nominal": (FIDUCIAL_Y, ("FIDUCIAL_Y",)),
        "x_from_seat_from": ("hub_seat", ((_SELF, "FRONT_KEEP"),)),
        "y_from_seat_from": ("hub_seat", ((_SELF, "FRONT_KEEP"),)),
        "process": ("punch", ((_NOTES, "FIDUCIAL_CALLOUT"),)),
        "face": ("outboard_face", ((_NOTES, "FIDUCIAL_CALLOUT"),)),
        "callout": (FIDUCIAL_CALLOUT, ((_NOTES, "FIDUCIAL_CALLOUT"),)),
    },
    precision={"x_from_seat": _P["FiducialX"], "y_from_seat": _P["FiducialY"]},
)
# The two taps, each THRU with its native Hole Wizard callout and drill
# (three places, _tap_drill_precision, the title block's DRILLED HOLES row):
# the #2-56 keeper-chain anchor .79 from the seat (FRONT_KEEP "AnchorStation")
# and .110 from the top edge (FRONT_KEEP "AnchorOffset", .XXX), its wall
# under the callout; the #4-40 handle pivot 2.95 from the seat (FRONT_KEEP
# "PivotStation") on the seat's axis, its mouth countersink on the outboard
# face (the near side) at most .122.
requirement(
    "anchor_tap",
    kind="threaded_hole",
    faces=(CylinderFace(_ANCHOR_HOLE_DIA),),
    requirements=("thread", "dia", "thru", "station", "edge_offset"),
    fields={
        "at": ([ANCHOR_SCREW_X, ANCHOR_SCREW_Y, 0.0], ("ANCHOR_SCREW_X", "ANCHOR_SCREW_Y")),
        "axis": (_Z, (_FRAME,)),
        "thread": (ANCHOR_HOLE_SPEC.size, ("ANCHOR_HOLE_SPEC",)),
        "dia": (
            drilled_limits(_ANCHOR_HOLE_DIA, 3, unit=UNIT),
            ("ANCHOR_HOLE_SPEC", _UNIT, (_SELF, "_tap_drill_precision")),
        ),
        "nominal_dia": (_ANCHOR_HOLE_DIA, ("ANCHOR_HOLE_SPEC",)),
        "thru": (True, ((_SELF, "ANCHOR_CALLOUT_XY"),)),
        "station": (
            limits(ANCHOR_SCREW_X, _P["AnchorStation"], unit=UNIT),
            ("ANCHOR_SCREW_X", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "station_nominal": (ANCHOR_SCREW_X, ("ANCHOR_SCREW_X",)),
        "station_from": ("hub_seat", ((_SELF, "FRONT_KEEP"),)),
        "edge_offset": (
            limits(ANCHOR_EDGE_DIST, _P["AnchorOffset"], unit=UNIT),
            ("ANCHOR_EDGE_DIST", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "edge_offset_nominal": (ANCHOR_EDGE_DIST, ("ANCHOR_EDGE_DIST",)),
        "edge_offset_from": ("top_edge", ((_SELF, "FRONT_KEEP"),)),
        "wall_min": (ANCHOR_TAP_WALL_MIN, ("ANCHOR_TAP_WALL_MIN", (_NOTES, "ANCHOR_TAP_ROWS"))),
        "callout_rows": (ANCHOR_TAP_ROWS, ((_NOTES, "ANCHOR_TAP_ROWS"),)),
    },
    precision={"dia": 3, "station": _P["AnchorStation"], "edge_offset": _P["AnchorOffset"]},
)
requirement(
    "pivot_tap",
    kind="threaded_hole",
    faces=(CylinderFace(_HANDLE_PIVOT_HOLE_DIA),),
    requirements=("thread", "dia", "thru", "station", "countersink_dia_max"),
    fields={
        "at": ([ARM_C2C, 0.0, 0.0], ("ARM_C2C",)),
        "axis": (_Z, (_FRAME,)),
        "thread": (HANDLE_PIVOT_HOLE_SPEC.size, ("HANDLE_PIVOT_HOLE_SPEC",)),
        # The band runs from the printed .089 (the #43), not from the Hole
        # Wizard's 2.261 mm, which reads .0002 mm over the drill.
        "dia": (
            drilled_limits(round(_HANDLE_PIVOT_HOLE_DIA / 25.4, 3) * 25.4, 3, unit=UNIT),
            ("HANDLE_PIVOT_HOLE_SPEC", _UNIT, (_SELF, "_tap_drill_precision")),
        ),
        "nominal_dia": (_HANDLE_PIVOT_HOLE_DIA, ("HANDLE_PIVOT_HOLE_SPEC",)),
        "thru": (True, ((_SELF, "PIVOT_CALLOUT_XY"),)),
        "station": (
            limits(ARM_C2C, _P["PivotStation"], unit=UNIT),
            ("ARM_C2C", _UNIT, (_SELF, "FRONT_KEEP")),
        ),
        "station_nominal": (ARM_C2C, ("ARM_C2C",)),
        "station_from": ("hub_seat", ((_SELF, "FRONT_KEEP"),)),
        "countersink_dia_max": (
            TAPPED_MOUTH_DIA_MAX,
            (("dt_crank_handle_pivot_screw_spec", "TAPPED_MOUTH_DIA_MAX"), (_NOTES, "PIVOT_TAP_ROWS")),
        ),
        "countersink_angle_deg": (90.0, ((_NOTES, "PIVOT_TAP_ROWS"),)),
        "countersink_face": ("outboard_face", ((_NOTES, "PIVOT_TAP_ROWS"),)),
        "callout_rows": (PIVOT_TAP_ROWS, ((_NOTES, "PIVOT_TAP_ROWS"),)),
    },
    precision={"dia": 3, "station": _P["PivotStation"]},
)


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-arm source", adapter.open_model(str(SOURCE)))
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The part authored every displayed decimal place.  The hub seat bore
    # is a two-place .XX size: MHA-DT-31 is turned to suit it.
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    thickness = add_edge_dimension(
        adapter,
        right,
        p0=THICKNESS_PICKS[0],
        p1=THICKNESS_PICKS[1],
        text_xy=THICKNESS_TEXT_XY,
        label="arm stock thickness",
        orientation="horizontal",
    )
    # The bar's as-rolled width and thickness: the supplier's fractions, its
    # tolerance governs (the stock note).
    stock_displays = {
        "Width": _early_bound(
            _named(adapter, front_annotations, "Width"), "IAnnotation"
        ).GetSpecificAnnotation(),
        "Thickness": thickness,
    }
    for name, value_mm in STOCK_FRACTION_DIMENSIONS.items():
        supplier_reference_dimension(
            adapter,
            stock_displays[name],
            label=f"arm stock {name}",
            units="in",
            precision=0,
            expected_mm=value_mm,
            fraction_denominator=STOCK_FRACTION_DENOMINATOR,
        )
    _arrows_inside(adapter, front_annotations)
    _hub_seat_leader_clear(adapter, front_annotations)
    _texts_off_the_part(adapter, front_annotations)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")
    _add_arm_centerline(adapter, front)

    # Handle-pivot callout attaches at the hole's top rim; the pivot's station
    # from the bore axis is the part's PivotStation dim imported above.
    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + _HANDLE_PIVOT_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    # Anchor tap (#2-56, MHA-DT-VN-70): size and THRU on a native Hole Wizard
    # callout, its edge wall under them (rule 20); its station from the bore
    # axis and its .XXX offset from the top long edge are the part's
    # StationReference dims imported above.
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
    _tap_drill_precision(anchor_callout, "anchor tap")
    _append_callout_rows(anchor_callout, ANCHOR_TAP_ROWS)
    # The true overall (boss extreme to handle-end extreme), as a reference
    # below the pivot station so nobody saws the stock a radius short
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

    seam_station = add_edge_dimension(
        adapter,
        front,
        p0=SEAM_STATION_PICKS[0],
        p1=SEAM_STATION_PICKS[1],
        text_xy=SEAM_STATION_TEXT_XY,
        label="seam station reference",
        orientation="horizontal",
    )
    assert_dimension_measures(
        adapter,
        seam_station,
        expected_mm=AXIAL_PIN_X,
        label="seam station reference",
    )
    set_reference_dimension(
        adapter,
        _early_bound(seam_station, "IDisplayDimension").GetAnnotation(),
        label="seam station reference",
    )
    _set_reference_precision(adapter, seam_station, "seam station reference")
    # Its arrows inside its witnesses too: drawn outside, the left tail ran
    # past the bore-axis witness under the boss R.50's leader (fan-out round
    # 4, rule 14).
    seam_display = _early_bound(seam_station, "IDisplayDimension")
    seam_display.ArrowSide = _DIM_ARROWS_INSIDE
    if int(seam_display.ArrowSide) != _DIM_ARROWS_INSIDE:
        raise RuntimeError("seam station reference did not keep its arrows inside")

    # MHA-DT-VN-59's axial seam is drilled with the hub at assembly; its callout
    # names the mate, the fit and the pin's nominal size and depth.
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
    # tap and its face.
    pivot_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=PIVOT_CALLOUT_XY,
        label="handle pivot tap",
    )
    _omit_title_block_thread_class(pivot_callout)
    _tap_drill_precision(pivot_callout, "handle pivot tap")
    _append_callout_rows(pivot_callout, PIVOT_TAP_ROWS)
    pivot_annotation = _early_bound(pivot_callout, "IDisplayDimension").GetAnnotation()
    set_near_side_diameter(pivot_annotation, "handle pivot tap")
    rebuild_drawing(adapter, label="handle pivot near-side leader")
    pivot_keep_out = _HANDLE_PIVOT_HOLE_DIA * SHEET_SCALE[0] / 4000.0
    assert_leaders_clear(
        {
            "HandlePivotTap": dimension_segments(pivot_annotation),
            "EndRadius": dimension_segments(_named(adapter, front_annotations, "EndRadius")),
        },
        centre=(_sheet_x(ARM_C2C), FRONT_CENTER[1]),
        keep_out={"HandlePivotTap": pivot_keep_out},
        lands_within={
            "HandlePivotTap": (pivot_keep_out, 3.0 * pivot_keep_out),
            "EndRadius": BOSS_RADIUS_LANDING,
        },
        label="crank arm handle pivot",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)

    return finalize_drawing(
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
