r"""Create the curated machinist drawing for the pen v-block.

The SLDPRT remains authoritative.  This recipe supplies only the pen-v-block
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 4:1 (the block is 32 mm end to end); the isometric carries an
explicit 2:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_v_block.py pen-v-block
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from pen_v_block_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_basic_dimension,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pen_v_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_LENGTH,
    BORE_X,
    CHAMFER,
    SCREW_HOLE_XY,
    GROOVE_DEPTH,
    GROOVE_WIDTH,
    GROOVE_Z0,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pen_v_block"]
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

SHEET_SCALE = (4.0, 1.0)

# Sheet layout (meters).  The front view's model bbox is 32 x 18 mm; at 4:1 the
# view is 128 x 72 mm.  Third angle: the top view (block seen from above,
# carrying the two pen bores) sits ABOVE the front view; the right view (16 x 18
# stock section) sits to its right.
FRONT_CENTER = (0.130, 0.115)
TOP_CENTER = (0.130, 0.215)
RIGHT_CENTER = (0.265, 0.115)
ISO_CENTER = (0.360, 0.225)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - BLOCK_LENGTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - BLOCK_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  The linear chain stacks below the front view, smallest span nearest
# the geometry; the slit band dims sit left of the view; the screw-hole group
# sits right, between the front and right views.
FRONT_KEEP = {
    "Length": (_sheet_x(BLOCK_LENGTH / 2.0), 0.058),
    "Chamfer2dx": (
        _sheet_x(BLOCK_LENGTH - CHAMFER / 2.0),
        _front_y(BLOCK_HEIGHT) + 0.012,
    ),
    "ScrewHoleCx": (_sheet_x(SCREW_HOLE_XY[0] - 5.0), _front_y(BLOCK_HEIGHT) + 0.026),
    # +0.012 keeps this vertical dimension's line (drawn at the text's x, from the
    # block bottom up to the hole centre) out of datum C's box in the crowded
    # corridor between the front and right views; its text still clears the front
    # view's right edge (x=0.194) by ~3 mm.
    "ScrewHoleCz": (_sheet_x(BLOCK_LENGTH) + 0.012, _front_y(SCREW_HOLE_XY[1])),
    "ScrewHoleDiaDim": (_sheet_x(BLOCK_LENGTH) + 0.024, _front_y(16.0)),
}
TOP_KEEP = {
    "Bore0X": (_sheet_x(BORE_X[0] / 2.0), TOP_CENTER[1] - 0.042),
    "Bore1X": (_sheet_x(BORE_X[1] / 2.0), TOP_CENTER[1] - 0.052),
    "Bore0Dia": (_sheet_x(BORE_X[0]) + 0.030, TOP_CENTER[1] + 0.042),
    # Bottom groove band (a Top-plane sketch, so its Z dims project into the
    # top view): the width and its offset from the front depth face, stacked
    # right of the view.
    "GrooveWidth": (_sheet_x(BLOCK_LENGTH) + 0.014, TOP_CENTER[1]),
    "GrooveZ0": (_sheet_x(BLOCK_LENGTH) + 0.026, TOP_CENTER[1] - 0.024),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], 0.068),
    # The groove rise, seen in the end section left of the right view.
    "GrooveDepth": (RIGHT_CENTER[0] - 0.046, 0.088),
}

# Right-view half extents at 4:1: the 16 (Z) x 18 (Y) stock section.
RIGHT_HALF_Z = BLOCK_DEPTH / 2.0 * SHEET_SCALE[0] / 1000.0
RIGHT_HALF_Y = BLOCK_HEIGHT / 2.0 * SHEET_SCALE[0] / 1000.0
DIMENSION_CALLOUTS = {
    "Bore0Dia": "2X THRU",
    "ScrewHoleDiaDim": "THRU",
    "Chamfer2dx": "X 45 DEG, 2 PLACES",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-v-block source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen V-Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen v-block; brass; marker groove; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # The front view carries the vertical pen bores as hidden lines; the top
    # view exposes the slit band and the screw hole crossing the depth.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    # Right view: the 16 x 18 stock section.  Depth is the model extrusion dim;
    # the 18 height is added as an explicit overall across the view's extremes.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # The two bore stations from datum B are the nominal locations the A-B-C
    # position FCF controls, so they must be BASIC -- leaving them under the
    # general/title-block tolerance would double-tolerance the bore positions.
    # curate_view_dimensions yields IAnnotation; set_basic_dimension wants the
    # IDisplayDimension, so resolve it via GetSpecificAnnotation.
    top_by_name = {dimension_name(adapter, a): a for a in top_annotations}
    for station in ("Bore0X", "Bore1X"):
        annotation = top_by_name[station]
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{station} station has no display dimension to box")
        set_basic_dimension(adapter, display, label=f"{station} basic bore station")
    # Block height (18): dimension the right view's flat top/bottom silhouette
    # edges.  At 4:1 the 16 x 18 section spans +/-0.032 (Z) x +/-0.036 (Y)
    # around the view center.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - RIGHT_HALF_Y),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y),
        text_xy=(RIGHT_CENTER[0] + RIGHT_HALF_Z + 0.014, RIGHT_CENTER[1]),
        label="block-height overall",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    # Native datum/GD&T/surface annotations.  A = the bottom face the block
    # seats on; B = the left end the slit and both bore stations run from;
    # C = the broad front face.
    # Hangs below the bottom edge (a perpendicular standoff -- an X offset would
    # run along the edge and leave the attachment triangle no room). x=30 mm is
    # the one pocket in the band below the view: the 26.00 dimension line stops
    # at x=0.170 and the 32.00 sits down at y=0.058, so x 0.175..0.194 is clear
    # between the edge and the 32.00 line. The 7.1 mm box lands at y 0.0639..0.071
    # on an 8 mm leader, clearing the 32.00 line by 5.9 mm and the 32.00's right
    # extension line (x=0.194) by 4.5 mm.
    add_datum_feature(
        adapter,
        front,
        edge_xy=(_sheet_x(30.0), _front_y(0.0)),
        symbol_xy=(_sheet_x(30.0), _front_y(0.0) - 0.008),
        datum="A",
        label="block bottom face",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=(_sheet_x(0.0), TOP_CENTER[1]),
        symbol_xy=(_sheet_x(0.0) - 0.018, TOP_CENTER[1]),
        datum="B",
        label="block left end",
    )
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - RIGHT_HALF_Z, RIGHT_CENTER[1]),
        # -0.010, not -0.016: symbol_xy is the box's RIGHT edge here (the leader
        # arrives from the right), so the 7.1 mm box grows LEFT -- at -0.016 it
        # spanned x 0.2097..0.2168 and the ScrewHoleCz dimension line, vertical at
        # x=0.214, ran straight through it and struck out the "C". Pairs with the
        # ScrewHoleCz move to x=0.206: box left edge 0.2157 now clears it by 9.7 mm.
        symbol_xy=(RIGHT_CENTER[0] - RIGHT_HALF_Z - 0.010, RIGHT_CENTER[1] - 0.020),
        datum="C",
        label="block broad face",
    )
    bore0_edge = (_sheet_x(BORE_X[0]) + 0.016, TOP_CENTER[1])
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=bore0_edge,
        frame_xy=(0.198, 0.196),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["pen bore position"],
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2X",
        label="pen bore position",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + RIGHT_HALF_Y),
        frame_xy=(0.300, 0.165),
        characteristic="parallelism",
        tolerance=GEOMETRIC_TOLERANCES_MM["block top-face parallelism"],
        datums=("A",),
        label="block top-face parallelism",
    )
    # Ra 1.6 on BOTH pen bores (the 2X functional pair) -- add_surface_finish
    # attaches to one edge, so each bore carries its own symbol; a single symbol
    # would leave the other Ø8 bore without the finish requirement.
    #
    # Both symbols stack in the empty space RIGHT of the top view. The ▽ tip sits
    # AT the anchor and the body draws up-right from there (~46 x 19 mm), so the
    # old shared y=0.240 dropped both glyphs onto the view, whose top edge is
    # y=0.248; there is no room to lift them (the border cuts in) and the band
    # under the view is full of bore stations and chamfer/screw callouts.
    #
    # The LEFT column cannot take bore 0 either, though it looks empty: the body
    # would have to clear the left frame bound at ~0.0127 (ink >= 0.020, so
    # ax >= 0.026) AND stop before the view at 0.0658 (ax <= 0.0248) -- an empty
    # window. Dropping it lower-left instead puts its bore up-RIGHT of the anchor,
    # the one direction that makes the leader strike through its own text.
    #
    # So bore 0 is picked at its TOP rather than a side: from the right, a leader
    # to its top edge passes ~5 mm ABOVE bore 1 (y=0.2365 vs bore 1's 0.231),
    # whereas a leader to either of its side edges would run straight through
    # bore 1. y=0.244 keeps this leader off bore 1's Ra body below (top 0.239).
    add_surface_finish(
        adapter,
        top,
        edge_xy=(_sheet_x(BORE_X[0]), TOP_CENTER[1] + 0.016),  # bore 0, top edge
        symbol_xy=(0.205, 0.244),
        control=surface_finish_by_key(SURFACE_FINISHES, "pen_bore_0"),
        label="pen bore finish (bore 0)",
    )
    bore1_edge = (_sheet_x(BORE_X[1]) + 0.016, TOP_CENTER[1])
    add_surface_finish(
        adapter,
        top,
        edge_xy=bore1_edge,
        symbol_xy=(0.205, 0.220),
        control=surface_finish_by_key(SURFACE_FINISHES, "pen_bore_1"),
        label="pen bore finish (bore 1)",
    )

    # x=0.020: the anchor is the text's left edge, so the ink starts here. The
    # sheet's 0.0127 zone margin and the re-centred border rule (~0.0126) now
    # agree, so 0.020 clears the rule and the audit enforces the same bound.
    # y=0.046, not 0.070: this block is SIX lines (26.6 mm tall, anchored at its
    # top line) and the front view's bottom edge is only at y=0.079, so anchoring
    # it at 0.070 overlapped the whole 32.00/26.00 locator chain -- both dimension
    # lines span the view's full width and printed through the note text like
    # strikethrough. Dimensions are CollisionScope.NONE, so no gate sees this.
    # 0.046 drops the block clear below the 32.00 text (bottom y 0.055) while
    # keeping its own bottom at 0.0194 -- ~6.8 mm above the drawn bottom rule
    # (~0.0126, now on the declared 12.7 mm margin).
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.046)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.180)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen V-Block Manufacturing Drawing",
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
