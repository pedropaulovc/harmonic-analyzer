r"""Reproduction script: platen rack bar (book ch. 22 pp. 54-55, teeth ch. 23).

Metric PA20 rack prototype using the SDP/SI A1B12MY08A300 tooth system and
12.7-high × 6.3-wide section, cut to 269.64 mm. The assembly mounts it
rotated 180 about Z so the +Y-authored teeth point down. It meshes the
shifted m0.8 12T feed pinion (build_pd_transgear_feed_pinion.py).

Rack tooth form: straight-flanked trapezoid at PA20. At PITCH_LINE_Y=11.9,
gap half-width is p/4; it flares toward the crest at y=12.7. The root lies
1.25 module below the pitch line; the cut overshoots the crest by 1 mm.
Gap count and first-gap position derive from the live pitch and bar length.

Layout: bar x = 0..269.64, y = 0..12.7, z = 0..6.3.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen_rack.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_polygon_chain,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_simplified import save_simplified_part

PART_NAME = "pd-platen-rack"
MATERIAL = "Brass"  # ch. 22/23 photos: brass

# SDP/SI A1B12MY08A300 metric PA20 rack, cut to the platen length.
# Keep this gear pair independent of the cone/cylinder drive train.
CATALOG_SKU = "A1B12MY08A300"
MODULE_MM = 0.8
DP = IN / MODULE_MM
PA_DEG = 20.0
BAR_LENGTH = 269.64
BAR_HEIGHT = 12.7
BAR_THICKNESS = 6.3
PITCH_LINE_Y = 11.9
PITCH_HEIGHT = PITCH_LINE_Y

PITCH = math.pi * MODULE_MM
ADDENDUM = MODULE_MM
DEDENDUM = 1.25 * MODULE_MM
ROOT_Y = PITCH_LINE_Y - DEDENDUM
CUT_TOP_Y = BAR_HEIGHT + 1.0  # opens past the top edge
TAN_PA = math.tan(math.radians(PA_DEG))

GAP_COUNT = int(BAR_LENGTH / PITCH)
FIRST_GAP_X = PITCH / 2.0


def half_width(y: float) -> float:
    """Gap half-width (mm) at height y: p/4 at the pitch line, PA20 flanks."""
    return PITCH / 4.0 + (y - PITCH_LINE_Y) * TAN_PA


# Exact per-gap cross-section inside the bar (trapezoid clipped at the top).
GAP_AREA = (half_width(ROOT_Y) + half_width(BAR_HEIGHT)) * (BAR_HEIGHT - ROOT_Y)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        LinearPatternParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the ordinary bar section is driven by
    # these. The tooth GAP geometry is deliberately left undriven -- its flank
    # angle and pitch-line offsets must MESH with the DP-30 rack pinion, so the
    # gap sketch is named (for the namer/pattern) but its dims are NOT recorded
    # or driven; touching them would risk silently breaking the mesh.
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 269.64 is inches,
    # blowing the part up 25.4x).
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarThickness", f"{BAR_THICKNESS}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar blank: origin-cornered rectangle (the ORDINARY sketch -- fully driven).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (0.0, 0.0),
        (BAR_LENGTH, 0.0),
        (BAR_LENGTH, BAR_HEIGHT),
        (0.0, BAR_HEIGHT),
    ]
    bar_lines = await add_line_chain(adapter, bar_rect)
    # Emission order (anchor vertex 0 at origin = 0 anchor dims; then the kept
    # per-segment distance dims in line order, skipping the last of each
    # direction): line0 horizontal span = BarLength, line1 vertical span =
    # BarHeight; lines 2/3 close.
    await define_rectilinear_chain(
        adapter, bar_lines, bar_rect, label="bar", dims=bar,
        names=["Length", "Height"],
        drives=['"BarLength"', '"BarHeight"'],
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_THICKNESS)),
    )
    name_last_feature(adapter, "Bar")
    v_bar = BAR_LENGTH * BAR_HEIGHT * BAR_THICKNESS
    volume = await volume_check(adapter, "bar blank", v_bar, 0.005 * v_bar)

    # Seed tooth gap at the left end (AddToDB: corners sit near the top edge,
    # where inferencing would snap them onto model vertices -- see the
    # cylinder-gear notch finding).
    check("create_sketch gap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    gap_pts = [
        (FIRST_GAP_X - half_width(ROOT_Y), ROOT_Y),
        (FIRST_GAP_X - half_width(CUT_TOP_Y), CUT_TOP_Y),
        (FIRST_GAP_X + half_width(CUT_TOP_Y), CUT_TOP_Y),
        (FIRST_GAP_X + half_width(ROOT_Y), ROOT_Y),
    ]
    gap = await add_line_chain(adapter, gap_pts)
    set_sketch_direct_db(adapter, False)
    # RACK MESH: the tooth-gap profile (flank angle, pitch-line offsets) MUST
    # mesh with the DP-30 rack pinion -- do NOT record/drive its dims. Name the
    # sketch+cut features only so the pattern can reference them and the namer
    # walks a clean tree; the gap stays fully defined by its literal coordinates.
    await define_polygon_chain(adapter, gap, gap_pts, label="gap")
    await ensure_fully_defined(adapter, "gap sketch")
    check("exit_sketch gap", await adapter.exit_sketch())
    name_last_feature(adapter, "GapProfile")
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BAR_THICKNESS + 1.0)
    )
    check("cut seed gap", gap_cut)
    gap_cut_name = name_last_feature(adapter, "SeedGap")
    v_gap = GAP_AREA * BAR_THICKNESS
    volume = await volume_check(adapter, "seed gap", volume - v_gap, 0.02 * v_gap)

    # Pattern along +X from the seed at the left end. The direction edge is
    # resolved geometrically (the straight bar edge along +X nearest the
    # point) and FlipDir1 follows from direction_vector, so the active view no
    # longer decides the sense: a top view once picked the -X top edge and an
    # isometric one the back face, sending every gap off the bar. A pattern
    # whose instances all miss now fails loudly in the adapter; the volume
    # check below still catches a partial miss.
    res = await adapter.linear_pattern_feature(
        LinearPatternParameters(
            direction_point=[BAR_LENGTH / 2.0, 0.0, 0.0],
            direction_vector=[1.0, 0.0, 0.0],
            features=[gap_cut_name],
            count=GAP_COUNT,
            spacing=PITCH,
        )
    )
    check("linear pattern gaps", res)
    tooth_pattern_name = name_last_feature(adapter, "ToothPattern")
    v_rack = v_bar - GAP_COUNT * v_gap
    await volume_check(adapter, "toothed rack", v_rack, 0.01 * GAP_COUNT * v_gap)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry (including the patterned mesh) must not move. Only the bar
    # sketch contributes drive jobs -- the gap is intentionally undriven.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rack (equations neutral)", v_rack, 0.01 * GAP_COUNT * v_gap
    )

    await apply_material(adapter, MATERIAL)

    # Named pitch-line axis (local X at y = pitch line, mid-thickness) so the
    # assembly's rack-pinion mate references the RACK's own engagement line --
    # not the platen it happens to be locked to (2026-07-07 field report).
    await name_bore_axis(
        adapter, "Front Plane", BAR_THICKNESS / 2.0,
        "Top Plane", PITCH_LINE_Y, "pitch axis",
    )

    await report_mass_properties(adapter)
    # Assembly views at 1:2 or smaller print the rack's "<cfg> Simplified":
    # the seed gap and its pattern suppressed, a plain bar.
    return await save_simplified_part(adapter, PART_NAME, (gap_cut_name, tooth_pattern_name))


if __name__ == "__main__":
    sys.exit(run_build(build))
