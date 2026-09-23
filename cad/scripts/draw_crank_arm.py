r"""Create the curated machinist drawing for crank arm MHA-020.

The arm is match-fitted to separate through hub MHA-137.  Its outboard face
shows the simple punched alignment witness and the axial seam for MHA-138,
match-drilled with the hub; the seam's callout gives its nominal size and
depth.  The handle pivot is tapped for the MHA-139 shoulder screw.
The MHA-024 taper-pin cross-hole belongs to the hub and shaft drawings.

The sheet remains deliberately plain: no datums, feature-control frames or
roughness symbols.  Every controlling value is imported from the part; matched
arm/hub and seam-pin operations are stated on their receiving feature/note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_arm.py crank-arm
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from typing import Any

import _telemetry
from _hole_spec import blind_cut_dia_mm
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_arc_endpoints_to_max,
    set_reference_dimension,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_arm_spec import (
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
    HALF_WIDTH,
    HANDLE_PIVOT_HOLE_SPEC,
    HUB_SEAT_CALLOUT,
    SEAM_CALLOUT,
)
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


SPEC = DRAWINGS_BY_NAME["crank_arm"]
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

# Sheet layout (meters).  At 2:1 the 97.7-mm overall arm remains clear of the
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


# Per-view survivors of the marked-dimension import.
FRONT_KEEP = {
    "ArmEndX": (0.190, 0.085),
    "PivotStation": (_sheet_x(ARM_C2C / 2.0), 0.095),
    "AnchorStation": (_sheet_x(ANCHOR_SCREW_X / 2.0), 0.104),
    "AnchorOffset": (0.106, FRONT_CENTER[1] + 0.017),
    "AxisOffset": (0.252, FRONT_CENTER[1] + 0.013),
    "Width": (0.279, FRONT_CENTER[1]),
    "BossRadius": (0.030, FRONT_CENTER[1]),
    "HubSeatDia": (0.054, 0.225),
}
# The arm's half of the MHA-138 seam is the arc bulging from the seat edge
# toward the arm end; the callout attaches 45 degrees up its flank.
SEAM_EDGE_PICK = (
    _sheet_x(AXIAL_PIN_X + AXIAL_PIN_DIA / 2.0 * math.cos(math.pi / 4.0)),
    FRONT_CENTER[1]
    + AXIAL_PIN_DIA / 2.0 * math.sin(math.pi / 4.0) * SHEET_SCALE[0] / 1000.0,
)
SEAM_CALLOUT_XY = (0.104, 0.250)
ANCHOR_CALLOUT_XY = (0.195, 0.205)
RIGHT_KEEP = {"Depth": (0.300, 0.108)}
DIMENSION_CALLOUTS = {"HubSeatDia": HUB_SEAT_CALLOUT}


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
    # The part authored every displayed decimal place.  The match-fit hub seat
    # remains a one-place nominal because the assigned actual hub governs size.
    assert_imported_precision(adapter, imported_annotations, DRAWING_PRECISION_BY_NAME)

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
    # The true overall (boss extreme to arm end), as a reference below the
    # 85.0 centre-to-end chain so nobody saws the stock 8 mm short
    # (Harvey #25).  Picked at the boss arc's outer extreme so the default
    # tangent arc condition measures the far side, not the centre.
    overall = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(-HALF_WIDTH), FRONT_CENTER[1]),
        p1=(_sheet_x(ARM_END_X), FRONT_CENTER[1] - 0.004),
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

    # MHA-138's axial seam is match-drilled in the assembled arm and hub; its
    # callout names the mate, the fit and the pin's nominal size and depth.
    add_attached_note(
        adapter,
        front,
        text=SEAM_CALLOUT,
        entity_xy=SEAM_EDGE_PICK,
        note_xy=SEAM_CALLOUT_XY,
        label="MHA-138 seam callout",
    )
    # Handle pivot tap (MHA-139): above and just right of the arm, arrow on
    # the hole's top rim, clear of the full principal view.  Thread and tap
    # drill ride the native callout; the class is the title block's.
    pivot_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=(0.270, 0.180),
        label="handle pivot tap",
    )
    _omit_title_block_thread_class(pivot_callout)
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
