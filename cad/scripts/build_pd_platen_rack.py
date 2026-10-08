r"""32DP PA20 brass catalog rack on the existing platen backer envelope.

The 3/16 x 3/16 in SDP/SI brass rack family (PA code Y) is cut to the
platen's width and soft-soldered to a brass backer. The backer's existing
soldered attachment to the platen is retained; there are no new screws or
holes. The compound section stays within 269.64 x 12 x 6 mm.

The rack is centred across the backer's depth and sits on its upper edge.
The part's +Y teeth become teeth-down under the assembly's Rx180 pose.
Straight PA20 rack flanks match the shifted 12T feed sleeve; profile shift
changes the axis-to-pitch-line distance, not this unshifted rack profile.

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
from _visibility import blank_reference_geometry
import pd_transgear_feed_pinion_spec as FEED

PART_NAME = "pd-platen-rack"
MATERIAL = "Brass"  # ch. 22/23 photos: brass

# Rack and feed sleeve share one pitch/PA authority, independent of the
# cone/cylinder train. A PA suffix must be specified when ordering the rack.
DP = FEED.DIAMETRAL_PITCH
PA_DEG = FEED.PRESSURE_ANGLE_DEG
BAR_LENGTH = 269.64  # ch30-p002 Pose Studio: equals resized platen width
BAR_HEIGHT = 12.0  # exposed band below the bottom guide rail (rework E3, low)
BAR_THICKNESS = 6.0  # DIMENSIONS.md ch22: edge-on photo (low)

RACK_HEIGHT = 3.0 / 16.0 * IN
RACK_THICKNESS = RACK_HEIGHT
BACKER_HEIGHT = BAR_HEIGHT - RACK_HEIGHT
RACK_Z0 = (BAR_THICKNESS - RACK_THICKNESS) / 2.0
PITCH = math.pi * FEED.MODULE_MM
ADDENDUM = FEED.MODULE_MM
DEDENDUM = 1.25 * FEED.MODULE_MM

PITCH_LINE_Y = BAR_HEIGHT - ADDENDUM
ROOT_Y = PITCH_LINE_Y - DEDENDUM
CUT_TOP_Y = BAR_HEIGHT + 1.0  # opens past the top edge
TAN_PA = math.tan(math.radians(PA_DEG))

GAP_COUNT = int(BAR_LENGTH / PITCH)
FIRST_GAP_X = PITCH / 2.0  # 1.33 -- first gap centred half a pitch in


def half_width(y: float) -> float:
    """Rack gap half-width (mm): p/4 on the reference line, PA20 flanks."""
    return PITCH / 4.0 + (y - PITCH_LINE_Y) * TAN_PA


# Exact per-gap cross-section inside the bar (trapezoid clipped at the top).
GAP_AREA = (half_width(ROOT_Y) + half_width(BAR_HEIGHT)) * (BAR_HEIGHT - ROOT_Y)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        LinearPatternParameters,
    )

    check("create_part", await adapter.create_part())

    # The backer and stock rack retain the existing envelope. Tooth pitch and
    # flank geometry remain literal-numeric, from the feed sleeve's spec.
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 269.64 is inches,
    # blowing the part up 25.4x).
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarThickness", f"{BAR_THICKNESS}mm")
    await set_global(adapter, "RackHeight", f"{RACK_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar blank: origin-cornered rectangle (the ORDINARY sketch -- fully driven).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (0.0, 0.0),
        (BAR_LENGTH, 0.0),
        (BAR_LENGTH, BACKER_HEIGHT),
        (0.0, BACKER_HEIGHT),
    ]
    bar_lines = await add_line_chain(adapter, bar_rect)
    # Emission order (anchor vertex 0 at origin = 0 anchor dims; then the kept
    # per-segment distance dims in line order, skipping the last of each
    # direction): line0 horizontal span = BarLength, line1 vertical span =
    # BarHeight; lines 2/3 close.
    await define_rectilinear_chain(
        adapter, bar_lines, bar_rect, label="bar", dims=bar,
        names=["Length", "Height"],
        drives=['"BarLength"', '"BarHeight" - "RackHeight"'],
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
    v_backer = BAR_LENGTH * BACKER_HEIGHT * BAR_THICKNESS
    volume = await volume_check(adapter, "backer blank", v_backer, 0.005 * v_backer)

    # Catalog square rack blank, soft-soldered on the backer's upper edge.
    # Model the permanent brass union while retaining the distinct stock
    # cross-section; only the rack's 4.7625-mm depth carries the tooth cuts.
    check(
        "create rack seat plane",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Front Plane", offset=RACK_Z0,
        )),
    )
    name_last_feature(adapter, "RackSeatPlane")
    check("create_sketch rack stock", await adapter.create_sketch("RackSeatPlane"))
    stock_pts = [
        (0.0, BACKER_HEIGHT), (BAR_LENGTH, BACKER_HEIGHT),
        (BAR_LENGTH, BAR_HEIGHT), (0.0, BAR_HEIGHT),
    ]
    set_sketch_direct_db(adapter, True)
    stock_lines = await add_line_chain(adapter, stock_pts)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, stock_lines, stock_pts, label="rack stock",
    )
    await ensure_fully_defined(adapter, "rack stock sketch")
    check("exit_sketch rack stock", await adapter.exit_sketch())
    name_last_feature(adapter, "RackStockProfile")
    check(
        "extrude rack stock",
        await adapter.create_extrusion(ExtrusionParameters(depth=RACK_THICKNESS)),
    )
    name_last_feature(adapter, "RackStock")
    v_bar = v_backer + BAR_LENGTH * RACK_HEIGHT * RACK_THICKNESS
    volume = await volume_check(adapter, "rack and backer", v_bar, 0.005 * v_bar)
    blank_reference_geometry(adapter, (("RackSeatPlane", "PLANE"),))

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
    # The stock rack's pitch and PA must match the feed pinion. Keep the cut
    # sketch literal and fully defined, not separately editable mesh knobs.
    await define_polygon_chain(adapter, gap, gap_pts, label="gap")
    await ensure_fully_defined(adapter, "gap sketch")
    check("exit_sketch gap", await adapter.exit_sketch())
    name_last_feature(adapter, "GapProfile")
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BAR_THICKNESS + 1.0)
    )
    check("cut seed gap", gap_cut)
    gap_cut_name = name_last_feature(adapter, "SeedGap")
    v_gap = GAP_AREA * RACK_THICKNESS
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
