r"""Create the curated machinist drawing for the rocker-arm support.

The SLDPRT remains authoritative.  This recipe supplies only the support's
views, dimension layout, hole table, and casting/machining notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The support is a green-painted gray-iron casting: a trapezoidal wall with a
square window cut from both faces (leaving a central web), a rounded/chamfered
window rim, and four 9/16-12 UNC tapped holes up through the foot.  The whole
sheet runs 1:2 and shows the window face (front), the taper (right), the foot
(bottom, carrying the hole table), SECTION A-A through the web ring, and an
isometric.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
bracket casting carries no datums, no feature-control frames, no roughness
symbols and no basic dimensions; the hole table's origin corner and the block
tolerances locate the four taps, the window and cavity are located from the
outside faces, and the web (only ever a hidden line in the orthographic
views) is dimensioned on the section.

Run with SolidWorks open::

    uv run python cad\scripts\draw_rocker_arm_support.py rocker-arm-support
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    insert_hole_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_rocker_arm_support import (
    BIG,
    BOSS_DEPTH,
    CAV,
    CHAMFER,
    FILLET_R,
    HALF_Y,
    HOLES,
    NARROW,
    WEB,
    WIDE,
)
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["rocker_arm_support"]
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

SHEET_SCALE = (1.0, 2.0)

# Sheet layout (meters).  A 177.8 mm casting with four views does not fit an
# ASME B sheet at 1:1 (measured: the notes column and the trapezoid view
# collided and the hole table clipped the border), so the whole sheet runs
# 1:2.  Third angle: taper (right view) beside the window face, foot (bottom
# view, the tapping setup) below it, aligned in X; SECTION A-A (cut through
# the web ring) between the taper and the isometric.
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.075, 0.200)
# Moved right from 0.155 to make room for the front view's vertical lanes.
RIGHT_CENTER = (0.165, 0.200)
# Dropped from 0.115 to make room for the front view's four horizontal lanes.
BOTTOM_CENTER = (0.075, 0.100)
SECTION_CENTER = (0.235, 0.205)
# Dropped from 0.210: the isometric's outline ran 6.8 mm into the top zone band.
# It cannot shrink to buy the room -- it already runs at the 1:2 sheet scale, and
# a view at any other scale would need a label this part declares no property for.
ISO_CENTER = (0.360, 0.201)

# SECTION A-A: a vertical cut through the front view at model X = +75, inside
# the web ring (63.5 < |X| < 82.55) and clear of the cavity fillets (|X| <
# 63.5), so the cut face is the full-height web slab between the foot and top
# bars -- the web's thickness and its location from the foot's outside corner
# become visible section edges instead of hidden lines (policy rule 7).  On
# the sheet the cut line sits right of every horizontal dimension text (all
# centred on x=0.075) and its end letters land beyond the outline where no
# lane runs.
SECTION_CUT_X = 75.0
_SECTION_LINE_X = FRONT_CENTER[0] + SECTION_CUT_X * VIEW_SCALE / 1000.0  # 0.1125
SECTION_LINE = ((_SECTION_LINE_X, 0.152), (_SECTION_LINE_X, 0.248))

# Front-view lanes.  Horizontal dimensions stack BELOW the view (shortest
# nearest), vertical ones stand to the RIGHT, so no horizontal crosses a
# vertical; nothing sits inside the window any more.  The window and cavity
# are each located from the outside faces (left edge for X, foot face for Y).
FRONT_LANE_Y = {
    "locate_window": 0.150,  # 6.35 window X off the left face (+ 127 cavity width)
    "locate_cavity": 0.143,  # 25.40 cavity X off the left face
    "window": 0.136,  # 165.10 window width
    "overall": 0.129,  # 177.80 overall width
}
FRONT_LANE_X = {
    "cavity": 0.127,  # 25.40 cavity Y off the foot face, chained with 127.00
    "window": 0.136,  # 165.10 window height
}

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position (meters).
FRONT_KEEP = {
    "Depth": (0.075, FRONT_LANE_Y["overall"]),  # 177.8 overall width
    "WinWidth": (0.075, FRONT_LANE_Y["window"]),  # 165.1 window square
    "CavWidth": (0.075, FRONT_LANE_Y["locate_window"]),  # 127 cavity square
    "CavDepth": (FRONT_LANE_X["cavity"], 0.195),
    "WinHeight": (FRONT_LANE_X["window"], 0.212),
}
RIGHT_KEEP = {
    "WallHeight": (RIGHT_CENTER[0] + 0.027, 0.200),  # 177.8, right of the taper
    "FootSpan": (RIGHT_CENTER[0], 0.147),  # 63.5 foot section, below the view
    "TopSpan": (RIGHT_CENTER[0], 0.252),  # 16.93 top section, above the view
}

# Top-left anchor (meters); the table grows down and RIGHT. It is ~145 mm wide,
# so x=0.284 ran its right edge 9.7 mm past the 0.4191 margin -- 0.270 leaves
# ~4 mm there while still clearing the notes block (which ends at x~0.246).
# y drops with the isometric above it (see ISO_CENTER): the table top must stay
# below the iso's lower edge, and its bottom (~74 mm) clears both the audit's
# title-block keep-out (64 mm) and the block's drawn top rule (~68 mm).
HOLE_TABLE_ANCHOR = (0.270, 0.130)

# The window-rim chamfer, flagged from its edge on the section (both slant
# faces carry it; the cavity rim and the end-face perimeters share the size,
# which the notes say).
CHAMFER_CALLOUT_TEXT = f"CHAMFER {CHAMFER:.2f} X 45 DEG\nWINDOW RIM, BOTH SIDES"

# 9/16-12 tap drill (the modeled hole) — the edge pick must land ON the rim.
_TAP_DRILL_DIA_MM = 12.30376


def _front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (X, Y) in the 1:2 front view (bbox on the origin)."""
    return (
        FRONT_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        FRONT_CENTER[1] + y_mm * VIEW_SCALE / 1000.0,
    )


def _section_xy(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a model (Z, Y) in the 1:2 SECTION A-A.

    The cut face (trapezoid Z +-31.75 at the foot, Y +-88.9) is symmetric in
    both axes, so the section's bounding box is centred on the pivot of the
    trapezoid and a mirrored Z cannot move a pick.
    """
    return (
        SECTION_CENTER[0] + z_mm * VIEW_SCALE / 1000.0,
        SECTION_CENTER[1] + y_mm * VIEW_SCALE / 1000.0,
    )


def _bottom_sheet_xy(hole_xz: tuple[float, float]) -> tuple[float, float]:
    """Sheet pick point ON a foot hole's rim (model X, Z in mm), bottom view."""
    x_mm, z_mm = hole_xz
    return (
        BOTTOM_CENTER[0] + x_mm * VIEW_SCALE / 1000.0,
        BOTTOM_CENTER[1] + (z_mm + _TAP_DRILL_DIA_MM / 2.0) * VIEW_SCALE / 1000.0,
    )


def _slant_z_at(y_mm: float) -> float:
    """Half-width (Z) of the trapezoid wall at height ``y_mm``."""
    return WIDE + (NARROW - WIDE) * (y_mm + HALF_Y) / (2.0 * HALF_Y)


def _add_radial_dimension(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    text_xy: tuple[float, float],
    prefix: str,
    label: str,
) -> Any:
    """Radius-dimension one arc edge picked at a sheet point, with a prefix.

    ``IModelDoc2.AddRadialDimension2`` only works inside an active sketch, so
    a drawing radius is the smart dimension (``AddDimension2``) with a single
    arc edge selected -- SolidWorks emits ``R<value>``; ``prefix`` ("4X ")
    goes in front of it.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    name = view_name(adapter, view)
    if not ddoc.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r} ({label})")
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        "", "EDGE", edge_xy[0], edge_xy[1], 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(
            f"failed to select {label} arc at sheet ({edge_xy[0]:g}, {edge_xy[1]:g})"
        )
    dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} radius dimension")
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "SetText", "GetText"
    )
    display.SetText(1, prefix)  # swDimensionTextPrefix
    if str(display.GetText(1) or "") != prefix:
        raise RuntimeError(f"{label} radius prefix did not persist: {display.GetText(1)!r}")
    draw.EditRebuild3()
    return dimension


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rocker-arm-support source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker-Arm Support Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker-arm support; manufacturing drawing; casting",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 2))
    bottom = place_view(adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    # Hidden lines on in every orthographic view: the taper view's greyed web
    # band and cavity floor make "window cut from both faces, leaving the web"
    # visible rather than prose-only.
    for view in (front, right, bottom):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, iso)
    removed_thread_notes = remove_notes_matching(adapter, "9/16-12")
    _telemetry.info(
        f"removed {removed_thread_notes} redundant automatic thread note(s)"
    )

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    if not auto_center_marks(adapter, bottom, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to bottom view")

    # --- Front view: window and cavity located from the OUTSIDE faces with
    # ordinary two-place dimensions (the block tolerance is the centring
    # tolerance).  X off the left end face on the lower lanes, Y off the foot
    # face chained under the marked cavity height on the right.  Each pick is
    # on the feature's WALL edge, 0.635 mm on the sheet from the parallel
    # chamfer edge, so the nearest-edge selection lands on the wall.
    outer_left = _front_xy(-BOSS_DEPTH / 2.0, -20.0)
    add_edge_dimension(
        adapter,
        front,
        p0=outer_left,
        p1=_front_xy(-BIG, -20.0),
        text_xy=(0.024, FRONT_LANE_Y["locate_window"]),
        label="window X off left face",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(-BOSS_DEPTH / 2.0, -35.0),
        p1=_front_xy(-CAV, -35.0),
        text_xy=(0.024, FRONT_LANE_Y["locate_cavity"]),
        label="cavity X off left face",
        orientation="horizontal",
    )
    add_edge_dimension(
        adapter,
        front,
        p0=_front_xy(0.0, -HALF_Y),
        p1=_front_xy(0.0, -CAV),
        text_xy=(FRONT_LANE_X["cavity"], 0.162),
        label="cavity Y off foot face",
        orientation="vertical",
    )
    # Cavity corner fillets: a radius on the upper-LEFT arc (its mid-point,
    # 0.635 mm inside the parallel chamfer arc), "4X" prefixed, text above
    # the view on the arc's own radial (so the leader meets the arc, not its
    # extension) and clear of the cutting-plane line's top letter at x=0.1125.
    fillet_mid = FILLET_R * (1.0 - 1.0 / 2.0**0.5)
    _add_radial_dimension(
        adapter,
        front,
        edge_xy=_front_xy(-(CAV - fillet_mid), CAV - fillet_mid),
        text_xy=(0.045, 0.252),
        prefix="4X ",
        label="cavity corner fillet",
    )

    # --- SECTION A-A through the web ring.
    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(1, 2),
        label="web ring section",
    )
    add_edge_dimension(
        adapter,
        section,
        p0=_section_xy(-WEB, 70.0),
        p1=_section_xy(WEB, 70.0),
        text_xy=(SECTION_CENTER[0], 0.257),
        label="web thickness",
        orientation="horizontal",
    )
    # Web face off the end of the flat foot face: the slant faces are
    # whole-face chamfered (RimChamfer), so the nominal foot corner is broken
    # 1.27 inboard and the cut face's outside vertex is where the flat foot
    # bottom ends (Z = -(WIDE - CHAMFER)) -- a checkable outside reference
    # (27.31); the web face is a section edge.
    add_edge_dimension(
        adapter,
        section,
        p0=_section_xy(-(WIDE - CHAMFER), -HALF_Y),
        p1=_section_xy(-WEB, -70.0),
        text_xy=(0.207, 0.152),
        label="web face off foot flat end",
        orientation="horizontal",
        entity_types=("VERTEX", "EDGE"),
    )
    add_edge_dimension(
        adapter,
        section,
        p0=_section_xy(-20.0, -HALF_Y),
        p1=_section_xy(-20.0, -BIG),
        text_xy=(0.211, 0.1622),
        label="window Y off foot face",
        orientation="vertical",
    )
    # The window-rim chamfer at the +Z foot-bar corner of the cut face; the
    # pick is the chamfer's mid-point (0.6 mm long on the sheet -- a pick
    # that lands on the neighbouring window-face edge still flags the same
    # corner, and the text names the feature either way).
    chamfer_z = _slant_z_at(-BIG) - CHAMFER * 0.35
    add_attached_note(
        adapter,
        section,
        text=CHAMFER_CALLOUT_TEXT,
        entity_xy=_section_xy(chamfer_z, -BIG - CHAMFER * 0.35),
        note_xy=(0.256, 0.185),
        label="window rim chamfer",
    )

    # Foot corner datum + the four tapped holes: the native hole table carries
    # every X/Y station and the 9/16-12 tap callout.  Locations are ORDINARY
    # (two-place, block tolerance): a bracket casting carries no frame for a
    # BASIC to feed (policy rule 4).
    insert_hole_table(
        adapter,
        bottom,
        datum_xy=(
            BOTTOM_CENTER[0] - BOSS_DEPTH / 2.0 * VIEW_SCALE / 1000.0,
            BOTTOM_CENTER[1] - WIDE * VIEW_SCALE / 1000.0,
        ),
        hole_points=tuple(_bottom_sheet_xy(hole) for hole in HOLES),
        # The nominal foot corner (-BossDepth/2, -Wide) is broken by the 1.27
        # RimChamfer, so the vertex SolidWorks anchors the table on is the
        # chamfer-edge vertex 1.27 INBOARD on both axes -- the shipped table's
        # LOCs (27.31/147.95, 13.02/47.94) are pinned here verbatim. The B/C
        # datum planes sit 1.27 outside this origin; follow-up: anchor via
        # datum_axes on the virtual B-C intersection like the harmonic base.
        expected_locations_mm=tuple(
            (x + BOSS_DEPTH / 2.0 - CHAMFER, z + WIDE - CHAMFER) for x, z in HOLES
        ),
        anchor_xy=HOLE_TABLE_ANCHOR,
        basic_locations=False,
        label="rocker-arm-support",
    )

    # x=0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker-Arm Support Manufacturing Drawing",
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
