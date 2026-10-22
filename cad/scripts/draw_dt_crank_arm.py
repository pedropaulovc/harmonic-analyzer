r"""Create the curated machinist drawing for crank arm MHA-DT-06.

Separate through hub MHA-DT-31 is a light press in the arm's seat bore, turned
to suit it.  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-DT-VN-59,
match-drilled with the hub; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-DT-32 shoulder screw.
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

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_annotation_extent import (
    CalloutInk,
    callout_ink,
    require_clear,
    require_inside,
    require_leader_clear,
    sheet_region,
)
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
from _drawing_layout_audit import annotation_display
from _drawing_layout_collect import _leader_segments_of, _note_element
from _drawing_leaders import (
    assert_leaders_clear,
    dimension_segments,
    dimension_text_points,
    leader_crossings,
    points_inside,
    set_near_side_diameter,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from dt_crank_arm_notes import (
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
    AXIAL_PIN_DIA,
    AXIAL_PIN_X,
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
    centreline through their centre marks states that relationship without an
    invented cross-width dimension.
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
# The punched fiducial's rim, picked on its upper-left flank.
# Its purpose note stays west of the hub-seat leader and AnchorOffset text.
FIDUCIAL_EDGE_PICK = (
    _sheet_x(FIDUCIAL_X - FIDUCIAL_MODEL_DIA / 2.0 * math.cos(math.pi / 4.0)),
    FRONT_CENTER[1]
    + (FIDUCIAL_Y + FIDUCIAL_MODEL_DIA / 2.0 * math.sin(math.pi / 4.0))
    * SHEET_SCALE[0]
    / 1000.0,
)
# Keep the short purpose note in the west lane below the hub-seat shoulder
# at y=0.2111. INote.GetExtent includes the attached leader's landing here;
# measure text runs separately rather than mistaking that union for text height.
FIDUCIAL_CALLOUT_XY = (0.016, 0.202)
# The overall's pick on the handle-end arc: 2 mm below the axis, on the arc.
_END_PICK_DY_SHEET = 0.004
_END_PICK_DX = math.sqrt(HALF_WIDTH**2 - (_END_PICK_DY_SHEET * 1000.0 / SHEET_SCALE[0]) ** 2)
ANCHOR_CALLOUT_XY = (0.195, 0.205)
# Centre of the four-line pivot callout: its bottom row stays clear above
# the arm's top edge, its right end left of the isometric view.
PIVOT_CALLOUT_XY = (0.270, 0.190)
RIGHT_KEEP = {"Depth": (0.300, 0.108)}
DIMENSION_CALLOUTS = {"HubSeatDia": HUB_SEAT_CALLOUT}


def _named(adapter: Any, annotations: list[Any], name: str) -> Any:
    matches = [a for a in annotations if dimension_name(adapter, a) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} dimension, found {len(matches)}")
    return matches[0]


def _hub_seat_leader_clear(adapter: Any, annotations: list[Any]) -> None:
    """Land the hub seat bore on its near rim, clear of R12.7.

    The bore is made first and keeps the title block's .X band: its limits
    are the U29 cheek's real limits (crank_hub_geometry).  MHA-DT-31 is turned
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


def _fiducial_note_clear(
    adapter: Any, note: Any, front_annotations: list[Any], anchor_callout: Any
) -> None:
    """Prove the expanded purpose note clears the arm and adjacent native ink."""
    annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
    element = _note_element(adapter, annotation, "punched fiducial callout")
    if element is None:
        raise RuntimeError("punched fiducial callout has no measurable native extent")
    extent = (element.xmin, element.ymin, element.xmax, element.ymax)
    require_inside("punched fiducial callout and leader", extent, sheet_region(adapter))
    required_reads = (
        "GetTextCount", "GetTextAtIndex", "GetTextPositionAtIndex",
        "GetTextHeightAtIndex", "GetTextRefPositionAtIndex", "GetTextAngleAtIndex",
    )
    display, read_errors = annotation_display(adapter, annotation)
    runs = [run for run in display.get("texts", ()) if str(run.get("t", "")).strip()]
    _telemetry.info(
        f"punched fiducial native extent={extent}, text runs={runs}, "
        f"display read errors={read_errors}"
    )
    if any(
        accessor in name for name in read_errors for accessor in required_reads
    ):
        raise RuntimeError(f"fiducial text geometry readback refused: {read_errors}")
    if not runs:
        raise RuntimeError("punched fiducial callout has no rendered text runs")
    vertical = []
    for run in runs:
        position = run.get("pos", ())
        height = float(run.get("h") or 0.0)
        reference = int(run.get("ref", -1))
        angle = float(run.get("ang") or 0.0)
        if (
            len(position) != 3
            or not all(math.isfinite(float(value)) for value in position)
            or not math.isfinite(height)
            or height <= 0.0
            or not math.isfinite(angle)
            or abs(angle) > 1e-6
            or reference not in range(6)
            or "\n" in str(run["t"])
        ):
            raise RuntimeError(f"unsupported fiducial text-run geometry: {run}")
        # swTextPosition_e: upper left/right/centre = 0/3/5,
        # lower left/right = 1/4, centre = 2. Heights are native metres.
        y = float(position[1])
        bottom = y - height if reference in (0, 3, 5) else (
            y - height / 2.0 if reference == 2 else y
        )
        vertical.append((bottom, bottom + height))
    # Retain GetExtent's entire X span conservatively: no font-width estimate
    # or dependence on unproven text-only width semantics for this note.
    box = (
        extent[0], min(bottom for bottom, _top in vertical),
        extent[2], max(top for _bottom, top in vertical),
    )
    if box[1] < extent[1] - 0.001 or box[3] > extent[3] + 0.001:
        raise RuntimeError(f"fiducial text runs are not in sheet space: {box}, {extent}")
    _telemetry.info(f"punched fiducial text-only vertical bounds={box}")
    neighbours = [
        callout_ink(
            adapter, _named(adapter, front_annotations, "HubSeatDia"),
            label="hub seat callout",
        ),
        callout_ink(
            adapter, _early_bound(anchor_callout, "IDisplayDimension").GetAnnotation(),
            label="anchor tap callout",
        ),
    ]
    require_clear(
        "punched fiducial callout",
        box,
        {"arm silhouette": ARM_SILHOUETTE, **{ink.label: ink.text for ink in neighbours}},
    )
    # Include 2 mm of air around the measured note,
    # rather than merely proving that adjacent leaders miss its ink.
    leader_keep_out = (
        box[0] - 0.002, box[1] - 0.002, box[2] + 0.002, box[3] + 0.002
    )
    for ink in neighbours:
        require_leader_clear(ink, {"punched fiducial callout": leader_keep_out})
    leader = _leader_segments_of(
        adapter, annotation, label="punched fiducial callout", kind="note", owner="front"
    )
    if not leader:
        raise RuntimeError("punched fiducial callout has no measurable leader")
    require_leader_clear(
        CalloutInk("punched fiducial callout", box, tuple(leader)),
        {ink.label: ink.text for ink in neighbours},
    )
    crossings = leader_crossings(
        {
            "punched fiducial": [
                ((segment.x0, segment.y0), (segment.x1, segment.y1))
                for segment in leader
            ],
            "HubSeatDia": dimension_segments(
                _named(adapter, front_annotations, "HubSeatDia")
            ),
        }
    )
    if crossings:
        raise RuntimeError(f"punched fiducial and hub-seat leaders cross: {crossings}")


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
    imported_annotations = [*front_annotations, *right_annotations]
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
    # Retain the feature attachment and west-side note lane, with the expanded
    # rendered extent and neighbouring leaders proved clear below.
    fiducial_note = add_attached_note(
        adapter,
        front,
        text=FIDUCIAL_CALLOUT,
        entity_xy=FIDUCIAL_EDGE_PICK,
        note_xy=FIDUCIAL_CALLOUT_XY,
        label="punched fiducial callout",
    )
    _fiducial_note_clear(adapter, fiducial_note, front_annotations, anchor_callout)
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
