r"""Create the curated machinist drawing for crank arm MHA-DT-06.

Separate through hub MHA-DT-31 is a light press in the arm's seat bore, turned
to suit it.  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-DT-VN-59,
match-drilled with the hub; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-DT-32 shoulder screw.  Partial
XZ section A-A cuts only the seat's -X wall and shows the far-side mouth
chamfer on the MHA-DT-31 hub side, clearing its seat-root radius.
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
    auto_center_marks,
    curate_dimensions,
    dimension_name,
    place_view,
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
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_hole_callout import add_native_hole_callout
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
from _drawing_projection import model_point_in_view
from _drawing_sections import create_section_view
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _section_axis import position_section_caption
import _telemetry
from dt_crank_arm_notes import (
    BORE_REAR_CHAMFER_CALLOUT,
    FIDUCIAL_CALLOUT,
    HUB_SEAT_CALLOUT,
    PIVOT_TAP_ROWS,
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
# title block, and the side view shows the 25.4 x 8 stock section.  The
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
    # Below and right of the handle end, clear of the Width row and the
    # 75.0 station row; its leader lands on the lower-right quarter of the arc.
    "EndRadius": (0.268, 0.100),
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
RIGHT_KEEP = {"Depth": (0.300, 0.108)}

# The short horizontal cut crosses only the -X bore wall in the XZ plane
# containing the chamfer's native model dimension. The prior partial YZ cut
# used the wrong annotation plane. Keep native radial X across / axial Z
# vertical, with a genuine partial section rather than a full-cut crop.
SECTION_SCALE = (4, 1)
# Armfix1 measured the left A glyph ending 2.94 mm right of its endpoint.
# Extend that end into air so it clears the overall's outer witness line;
# the right end stays 1 mm into the bore at the front view's 2:1 scale.
SECTION_LINE_LEFT_OVERRUN = 0.005
SECTION_LINE_RIGHT_OVERRUN = 0.002
SECTION_LINE = (
    (_sheet_x(-HALF_WIDTH) - SECTION_LINE_LEFT_OVERRUN, BORE_CENTER[1]),
    (_sheet_x(-HUB_SEAT_DIA / 2.0) + SECTION_LINE_RIGHT_OVERRUN, BORE_CENTER[1]),
)
SECTION_CENTER = (0.368, 0.150)
SECTION_ANCHOR_MM = (
    -(HUB_SEAT_DIA / 2.0 + HALF_WIDTH) / 2.0,
    0.0,
    ARM_THICKNESS / 2.0,
)
# Sol6 proved that the native block flips to the RIGHT outside the cheek.
# Compact rows measured from the actual Century Gothic PDF glyphs need at
# most 29.864 mm including padding. At x=385 this leaves 4.236 mm to the inner
# border and 4.212 mm to the section's audited outline; neither side is guessed.
CHAMFER_CALLOUT_WIDTH = 0.029864
SECTION_KEEP = {"BoreRearChamferSize": (0.385, 0.118)}
SECTION_CAPTION_XY = (SECTION_CENTER[0], 0.091)
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
    """Verify the saved part's native limits after importing into the section."""
    native = _early_bound(annotation, "IAnnotation")
    display = _early_bound(native.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
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


def _assert_cheek_section_display(section: Any) -> None:
    """Require the native short-span cut, not a full cut with a cropped outline."""
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    if cut.GetPartialSection() is not True:
        raise RuntimeError("section A-A did not retain its partial wall cut")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("section A-A retained geometry beyond the cutting plane")


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _cheek_section(adapter: Any, front: Any) -> Any:
    """Create a partial XZ wall cut for the native chamfer dimension."""
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SECTION_SCALE,
        partial=True,
        label="hub seat cheek section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section A-A cut face only")
    _assert_cheek_section_display(native)
    set_hidden_lines_removed(adapter, native)
    return native


def _position_cheek_section(adapter: Any, section: Any) -> None:
    """Centre the wall's native projected anchor and retain its XZ orientation."""
    native = _early_bound(section, "IView")
    anchor = _metres(SECTION_ANCHOR_MM)
    origin = model_point_in_view(adapter, native, anchor, label="A-A anchor")
    radial = model_point_in_view(
        adapter,
        native,
        _metres((SECTION_ANCHOR_MM[0] + 1.0, 0.0, SECTION_ANCHOR_MM[2])),
        label="A-A radial X",
    )
    axial = model_point_in_view(
        adapter,
        native,
        _metres((SECTION_ANCHOR_MM[0], 0.0, SECTION_ANCHOR_MM[2] + 1.0)),
        label="A-A axial Z",
    )
    if abs(radial[1] - origin[1]) > 1e-7 or abs(axial[0] - origin[0]) > 1e-7:
        raise RuntimeError("cheek section is not radial-across, axial-vertical")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"A-A centre, pass {attempt}"
        )
        if math.dist(projected, SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + SECTION_CENTER[axis] - projected[axis] for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre section A-A")
        rebuild_drawing(adapter, label=f"section A-A re-centred, pass {attempt}")
    else:
        raise RuntimeError(
            f"section A-A centre stands at {projected}, not {SECTION_CENTER}"
        )
    position_section_caption(
        adapter, native, SECTION_CAPTION_XY, label="cheek section A-A"
    )


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
    # Right view: stock width by thickness.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section = _cheek_section(adapter, front)
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="section A-A",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _position_cheek_section(adapter, section)
    section_annotations = curate_dimensions(
        adapter, section_annotations, reposition=SECTION_KEEP
    )
    if any(
        int(_early_bound(item, "IAnnotation").Visible) != 1
        for item in section_annotations
    ):
        raise RuntimeError("cheek section hid its native chamfer dimension")
    _assert_chamfer_limits(_named(adapter, section_annotations, "BoreRearChamferSize"))
    imported_annotations = [
        *front_annotations,
        *right_annotations,
        *section_annotations,
    ]
    set_dimension_callouts(adapter, imported_annotations, DIMENSION_CALLOUTS)
    # The part authored every displayed decimal place.  The hub seat bore
    # is a one-place .X size: MHA-DT-31 is turned to suit it.
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)
    # The thickness is the supplied stock's (the stock note governs it).
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, _named(adapter, right_annotations, name), label="arm stock thickness"
        )
    _hub_seat_leader_clear(adapter, front_annotations)

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
