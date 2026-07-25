r"""Create the curated machinist drawing for the crank arm.

The SLDPRT remains authoritative.  This recipe supplies only the crank-arm
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arm is 84 mm end to end); the isometric carries an
explicit 1:1 override so it stays clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_arm.py crank-arm
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    auto_center_marks,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from crank_arm_spec import (
    ARM_C2C,
    ARM_END_X,
    ARM_THICKNESS,
    DIMPLE_DIA,
    DIMPLE_X,
    HALF_WIDTH,
    PIN_HOLE_DIA,
    SHAFT_BORE_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    place_view,
)


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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The front view's model bbox runs -boss..arm-end in X
# (84 mm) and +/-8 in Y; at 2:1 the view is 168 x 32 mm.  Third angle: the top
# view (arm seen edge-on, carrying the cross-pin hole) sits ABOVE the front
# view; the right view (16 x 8 stock section) sits to its right.
FRONT_CENTER = (0.145, 0.135)
TOP_CENTER = (0.145, 0.205)
RIGHT_CENTER = (0.300, 0.135)
ISO_CENTER = (0.360, 0.230)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front/top views (2:1, bbox-centred)."""
    bbox_center = (ARM_END_X - HALF_WIDTH) / 2.0
    return FRONT_CENTER[0] + (model_x_mm - bbox_center) * SHEET_SCALE[0] / 1000.0


DATUM_B_OFFSET = (0.022, 0.035)
DATUM_B_ANGLE = math.atan2(DATUM_B_OFFSET[1], DATUM_B_OFFSET[0])
DATUM_B_RADIUS = SHAFT_BORE_DIA * SHEET_SCALE[0] / 2000.0
DATUM_B_RIM = (
    _sheet_x(0.0) + DATUM_B_RADIUS * math.cos(DATUM_B_ANGLE),
    FRONT_CENTER[1] + DATUM_B_RADIUS * math.sin(DATUM_B_ANGLE),
)
DATUM_B_SYMBOL = (
    _sheet_x(0.0) + DATUM_B_OFFSET[0],
    FRONT_CENTER[1] + DATUM_B_OFFSET[1],
)


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Leadered diameters sit above the arm at each feature's station;
# the linear chain stacks below the view, smallest span nearest the geometry.
FRONT_KEEP = (
    "ArmEndX",
    "DimpleX",
    "BossRadius",
    "ShaftBoreDia",
    "DimpleDia",
)
RIGHT_KEEP = ("Depth",)
TOP_KEEP = ()
DIMENSION_CALLOUTS = {
    "ShaftBoreDia": "THRU - REAM 3/8 IN\n+0.05/-0.00",
    "DimpleDia": "0.5 DEEP",
}


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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Arm Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank arm; manufacturing drawing; straight cross-hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # Right view: the 16 x 8 stock section.  Thickness is the model Depth dim;
    # the 16 width is added as an explicit overall across the view's extremes.
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    # Top view: cross-drill geometry is visible; its size is a native hole callout.
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    # The shaft bore is an exact 3/8 in (Ø9.525) reamed bore; its native
    # dimension callout cites that conversion, so preserve three decimals.
    set_dimension_precision(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        {"ShaftBoreDia": 3},
    )
    # Arm width (16): dimension the right view's flat top/bottom faces. At 2:1
    # the 16 x 8 stock section spans +/-0.016 (Y) x +/-0.008 (Z) around the view
    # center. Place the dimension to the right of the section: its former left
    # position collided with the handle pivot's new basic 8.00 coordinate, while
    # the right-side band is clear at this height.
    add_edge_dimension(
        adapter,
        right,
        p0=(RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.016),
        p1=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.016),
        text_xy=(RIGHT_CENTER[0] + 0.050, RIGHT_CENTER[1]),
        label="arm-width overall",
    )

    for view, label in ((front, "front"), (top, "top")):
        if not auto_center_marks(adapter, view, holes=True):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    handle_edge = (
        _sheet_x(ARM_C2C),
        FRONT_CENTER[1] + (15.0 / 64.0 * 25.4) * SHEET_SCALE[0] / 2000.0,
    )
    pivot_location = add_edge_dimension(
        adapter,
        front,
        p0=(_sheet_x(0.0), FRONT_CENTER[1] + SHAFT_BORE_DIA / 1000.0),
        p1=(_sheet_x(ARM_C2C), FRONT_CENTER[1] + 15.0 / 64.0 * 25.4 / 1000.0),
        text_xy=(_sheet_x(ARM_C2C / 2.0), 0.102),
        label="shaft-to-handle-pivot location",
    )
    set_basic_dimension(adapter, pivot_location, label="handle-pivot location")
    handle_transverse = add_edge_dimension(
        adapter,
        front,
        p0=(
            _sheet_x(ARM_C2C),
            FRONT_CENTER[1] - HALF_WIDTH * SHEET_SCALE[0] / 1000.0,
        ),
        p1=handle_edge,
        text_xy=(0.240, FRONT_CENTER[1]),
        label="handle-pivot transverse location",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, handle_transverse, label="handle-pivot transverse location"
    )
    set_basic_dimension(
        adapter, handle_transverse, label="handle-pivot transverse location"
    )

    # The horizontal 30.00 marked dimension locates the dimple from datum B.
    # Add the other nominal coordinate explicitly: centre height from datum C.
    dimple_edge = (
        _sheet_x(DIMPLE_X),
        FRONT_CENTER[1] - DIMPLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    dimple_transverse = add_edge_dimension(
        adapter,
        front,
        p0=(
            _sheet_x(DIMPLE_X),
            FRONT_CENTER[1] - HALF_WIDTH * SHEET_SCALE[0] / 1000.0,
        ),
        p1=dimple_edge,
        text_xy=(0.158, FRONT_CENTER[1]),
        label="dimple transverse location from datum C",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter,
        dimple_transverse,
        label="dimple transverse location from datum C",
    )

    # The straight #14 cross-hole is the released MHA-020 condition. Locate its
    # axis from datum A on the top view; the manufacturing note explicitly makes
    # its nominal longitudinal location the intersection with datum axis B.
    pin_edge = (
        _sheet_x(0.0),
        TOP_CENTER[1] + PIN_HOLE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    pin_station = add_edge_dimension(
        adapter,
        top,
        p0=(
            _sheet_x(0.0),
            TOP_CENTER[1] + ARM_THICKNESS * SHEET_SCALE[0] / 2000.0,
        ),
        p1=pin_edge,
        text_xy=(0.045, TOP_CENTER[1] + 0.004),
        label="cross-hole station from datum A",
        orientation="vertical",
    )
    set_arc_endpoints_to_center(
        adapter, pin_station, label="cross-hole station from datum A"
    )
    set_basic_dimension(
        adapter, pin_station, label="cross-hole station from datum A"
    )
    add_feature_control_frame(
        adapter,
        top,
        edge_xy=pin_edge,
        frame_xy=(0.100, 0.230),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B"),
        diameter=True,
        label="cross-hole true position",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=pin_edge,
        callout_xy=(0.170, 0.230),
        label="crank-arm cross-hole",
    )

    # Native datum/GD&T/surface annotations replace the former prose notes 5/8/9.
    # Right view is the 16 x 8 stock section: its left broad face is datum A.
    #
    # The symbol sits LEFT of the section (-0.022), on the same side as the face
    # it tags.  The left face's outward normal is -X, so the old +0.030 scored
    # dot(symbol_xy - edge_xy, normal) = (+0.038)*(-1) = -0.038: the tag was on
    # the far side and its leader crossed the whole 16 mm section to get there.
    # Measured on the 2026-07-16 render as one unbroken black run at y=0.135 from
    # x=0.2918 (the triangle on the left face) to x=0.3300 (the box) -- 38.2 mm
    # straight through the part.  It also put that crossing 1.3 mm from the
    # parallelism frame's arrowhead on the RIGHT face at (0.3082, 0.1337), the
    # stacked-arrowhead tell.  Both symptoms are the same wrong-side offset.
    #
    # -0.022 rather than a symmetric -0.030: the box is drawn ~8 mm wide ending at
    # symbol_xy, so -0.022 spans 0.270..0.278 and leaves a 14 mm leader to the
    # face at 0.2918 -- entirely outside the section, crossing nothing.  -0.030
    # would reach x=0.262..0.270, which is clear only because the 16.00 dimension
    # was moved outboard above; 0.278 keeps the tag close to the face it names.
    add_datum_feature(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] - 0.008, RIGHT_CENTER[1]),
        symbol_xy=(RIGHT_CENTER[0] - 0.022, RIGHT_CENTER[1]),
        datum="A",
        label="crank broad face",
    )
    # Same bore circle, picked at its BOTTOM. The Ra below uses this instead of
    # DATUM_B_RIM so its leader runs level to the bore rather than climbing
    # through its own "Ra 1.6" text -- see the note at add_surface_finish.
    # In the front view the bore projects as ONE circular edge, so picking it at
    # 6 o'clock rather than 12 selects the same edge and specifies the same
    # surface: this is a routing change, not a respec of which face is finished.
    shaft_edge_lower = (
        _sheet_x(0.0),
        FRONT_CENTER[1] - SHAFT_BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=DATUM_B_RIM,
        symbol_xy=DATUM_B_SYMBOL,
        datum="B",
        label="crank shaft axis",
        shoulder=True,
        position_tolerance_m=0.0001,
    )
    # Station moved off ARM_C2C*0.75 (sheet x=0.176) to the flat stretch between
    # the pivot centre and the arm end.  A datum feature symbol may be tagged
    # anywhere along its face, and 0.176 is the one place it CANNOT go once the
    # symbol drops below the edge (see the sign note below): the 66.00 basic
    # dimension's line is a gray rule at y=0.0991 spanning x=0.0777..0.2073
    # (measured 2026-07-16 -- gray, so invisible below an ink threshold of 200),
    # and a leader from the edge at y=0.119 down to the symbol would cross it.
    # At x=0.219 the 66.00 line has ended (11.7 mm clear) and the band from the
    # arm's bottom edge (0.1190) to the 76.00 dimension line (0.0832) is 35.7 mm
    # of empty sheet, so the tag drops straight down into open space.
    datum_c_edge = (
        _sheet_x((ARM_C2C + ARM_END_X) / 2.0),
        FRONT_CENTER[1] - HALF_WIDTH * SHEET_SCALE[0] / 1000.0,
    )
    # MINUS 0.022, not plus: `datum_c_edge` is the front view's BOTTOM edge, whose
    # outward normal is -Y, so the symbol has to sit BELOW it.  The rule is
    # dot(symbol_xy - edge_xy, outward_normal_at(edge_xy)) > 0; +0.022 scored
    # (+0.022)*(-1) = -0.022 and printed the whole tag INSIDE the part -- measured
    # on the 2026-07-16 render, the arm spans y=0.1190..0.1510 and the "C" box sat
    # at y=0.1408..0.1480, interior, with a 22 mm leader running down through the
    # body to the triangle.  Not the collapsed variant (the standoff existed, it
    # just pointed the wrong way), and invisible to the audit either way: datum
    # boxes carry CollisionScope.NONE, so the eye pass is the only gate here.
    add_datum_feature(
        adapter,
        front,
        edge_xy=datum_c_edge,
        symbol_xy=(datum_c_edge[0], datum_c_edge[1] - 0.022),
        datum="C",
        label="crank width side",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=handle_edge,
        frame_xy=(0.222, 0.158),
        characteristic="position",
        tolerance="0.20",
        datums=("A", "B", "C"),
        diameter=True,
        label="handle pivot position",
    )
    # BELOW the front view, not beside it.  (0.235, 0.128) put the text at
    # y=0.1258..0.1297 -- inside the view's own y-band (0.1190..0.1510) -- and
    # centred it on x=0.235, only 6 mm right of the view's right edge, so its left
    # third printed inside the outline.  Measured 2026-07-16 at y=0.1278: the gray
    # callout text spans x=0.2129..0.2521 and the view's BLACK outline edge cuts
    # through it at x=0.2274..0.2290, between the "5." and the "95".  (The text is
    # gray = level 128, so an ink threshold of 128 reports this region as empty --
    # the strikethrough is invisible to any check that does not measure at 200.)
    #
    # Sideways does not fit: in that y-band the free window is only the 46.9 mm
    # between the view's edge (0.2289) and the 16.00 dim line (0.2758), and the
    # text is 39.2 mm wide.  The band at y=0.164..0.172 is empty for 90 mm but is
    # unusable for THIS callout -- the position frame already anchors above the
    # same hole, so a callout up there would re-attach to the hole's top edge and
    # stack with it.  y=0.110 is clear from x=0.2290 to 0.2918 (probed), keeps the
    # arrow on the hole's BOTTOM (the frame owns the top), and centring at x=0.258
    # puts the text at ~0.2355..0.2747: 6.6 mm clear of the 76.00 extension line,
    # 17 mm clear of the right view, 7.3 mm below the arm.  The leader re-enters
    # the outline to reach its hole, which is what a hole callout is supposed to
    # do -- draw_column_clamp_front.py's 2X O4.98 reads the same way.
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=handle_edge,
        callout_xy=(0.258, 0.110),
        label="handle pivot hole",
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.008, RIGHT_CENTER[1]),
        frame_xy=(0.316, 0.118),
        characteristic="parallelism",
        tolerance="0.10",
        datums=("A",),
        label="crank broad-face parallelism",
    )
    # Sits LEFT of the boss and BELOW bore height. Three constraints pin it:
    #   * not above the top view (its old (0.140, 0.235) spot) -- the leader
    #     then ran as one long diagonal down across the whole top view;
    #   * not in the 0.151..0.189 band between the two views -- that is full
    #     (BossRadius / ShaftBoreDia / DimpleDia), and ShaftBoreDia's callout is
    #     ~48 mm wide now that dimension text renders horizontally instead of
    #     stacked vertically; and
    #   * low enough that the symbol's body clears BossRadius's R8.00 at
    #     y=0.162; and far enough left that its text ends before the boss
    #     circle's left edge (x=0.061) instead of printing over the arc.
    #
    # symbol_xy is the LEADER'S ATTACHMENT POINT -- the bottom vertex of the
    # triangle -- not the symbol's centre. The whole body draws UP and RIGHT of
    # it, ~46 x 19 mm: triangle x [ax-0.006, ax+0.006] y [ay, ay+0.011], the
    # "Ra 1.6" text x [ax+0.013, ax+0.039] y [ay+0.010, ay+0.017], arm at
    # y ~= ay+0.018. So an anchor at y=0.145 pushed text into R8.00 15 mm above
    # it, and the arm sets the left edge against the 12.7 mm zone margin.
    # (Measured across three sheets; an earlier note here claimed the text sits
    # ABOVE the arm -- it sits just under it. The prediction was right for the
    # wrong reason.)
    # Targets shaft_edge_LOWER (the bore at 6 o'clock), not shaft_edge (12
    # o'clock). Measured on the 2026-07-16 render: aimed at the bore's top the
    # leader climbs from the anchor (0.022, 0.125) to (0.077, 0.1445) at slope
    # 0.355, enters the text box (x 0.0350..0.0610, y 0.1350..0.1420) at x=0.0502
    # and exits its right edge at y=0.1388 -- straight through the "6" glyph
    # (x 0.0552..0.0598). Ink-on-ink at 8:1, not a graze.
    #
    # The body draws UP-RIGHT of the anchor and the bore's top is ALSO up-right,
    # so text and leader share one corridor. Cross-free needs slope <0.256 (under
    # the text) or >1.308 (over it); 0.355 sits between. The levers, all measured:
    #   - move the anchor LEFT: at the frame rule the slope is still 0.291. Dead.
    #   - raise the anchor to flatten it: ay=0.134 gives slope 0.191, but puts the
    #     text at y 0.144..0.151 straight into R8.00's LEADER, which descends
    #     diagonally through x 0.056..0.071 / y 0.143..0.160. Trades a
    #     strikethrough for a collision.
    #   - aim at the bore's BOTTOM: slope 0.009, level, passing 9.7..9.9 mm under
    #     the text. Costs nothing -- same edge, same specified surface.
    add_surface_finish(
        adapter,
        front,
        edge_xy=shaft_edge_lower,
        symbol_xy=(0.022, 0.125),
        roughness_ra="1.6",
        label="shaft bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.185)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Arm Manufacturing Drawing",
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
