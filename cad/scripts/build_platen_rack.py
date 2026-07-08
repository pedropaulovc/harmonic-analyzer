r"""Reproduction script: platen rack bar (book ch. 22 pp. 54-55, teeth ch. 23).

The brass rack screwed along the platen's back bottom edge, teeth-down with
the crests protruding ~2 below the platen's bottom edge (ch22 back photo),
driven by the 12T DP 30 feed pinion (build_transgear_feed_pinion.py, the
"fifth gear" of the 4/4 video). The tooth pitch was resolved during M4 gear
prep (DIMENSIONS.md ch. 23: rack pitch measured as DP 30 on
`v4_transgear_028/030` -- it is the scale anchor for the whole chapter). The
12-tall band fits below the platen's bottom guide rail (paper-drive rework
E3); the assembly mounts it rotated 180 about Z so the +Y-authored teeth
point down.

Rack tooth form: straight-flanked trapezoid (the involute rack profile is
exactly straight at the 14.5 deg pressure angle). With the pitch line at
PITCH_LINE_Y, gap half-width is p/4 at the pitch line and flares at 14.5 deg:
root (dedendum 1.157/DP below) half-width 0.412, cut overshoot to y = 13
(past the bar top at 12, so the cut opens cleanly) half-width 1.143. The
teeth crest at the bar top = pitch line + addendum (1/DP).

112 gaps at p = pi/30 in = 2.660 mm fill the 300 mm bar (first gap centre
at 1.33 mm; last opening ends at 297.5 mm).

Layout: bar x = 0..300, y = 0..12, z = 0..6; teeth cut into the top edge.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_rack.py
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
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "platen-rack"
MATERIAL = "Brass"  # ch. 22/23 photos: brass

# The platen recording rack-pinion is its OWN gear pair — ch23 measured it as DP 30
# ("the scale anchor of the chapter") — independent of the cone/cylinder drive train.
# It MUST match the pinion (build_rack_pinion via _gear.build_fixed_gear, default
# dp=30) and the output assembly's PINION_PD_R (/30.0). Do NOT couple this to
# machine.yaml gear_train.diametral_pitch: the value-preserving _config migration
# (2bc0b10) tied them while both were 30, then the OD-62.2 re-anchor moved the train
# DP to 49.82 — silently shrinking the rack pitch to 1.60 mm against the DP-30 pinion
# (2.66 mm) so the mesh interfered (output interference gate, 8 hits ≤ 1.93 mm³).
DP = 30.0  # 1/in, DIMENSIONS.md ch23 (med — scale anchor of the chapter)
PA_DEG = 14.5  # period-typical, same as the gear train
BAR_LENGTH = 282.0  # = platen width (re-measured 2026-07-08, see
# build_platen.PLATE_WIDTH)
BAR_HEIGHT = 12.0  # exposed band below the bottom guide rail (rework E3, low)
BAR_THICKNESS = 6.0  # DIMENSIONS.md ch22: edge-on photo (low)

PITCH = math.pi / DP * IN  # 2.660 mm
ADDENDUM = 1.0 / DP * IN  # 0.847 mm
DEDENDUM = 1.157 / DP * IN  # 0.980 mm -- 14.5 deg full-depth standard

PITCH_LINE_Y = BAR_HEIGHT - ADDENDUM  # 11.153 -- teeth crest at the bar top
ROOT_Y = PITCH_LINE_Y - DEDENDUM  # 28.174
CUT_TOP_Y = BAR_HEIGHT + 1.0  # opens past the top edge
TAN_PA = math.tan(math.radians(PA_DEG))

GAP_COUNT = 106  # fills the 282 bar: 1.33 + 105 * 2.660 = 280.6 (was 112 / 300)
FIRST_GAP_X = PITCH / 2.0  # 1.33 -- first gap centred half a pitch in


def half_width(y: float) -> float:
    """Gap half-width (mm) at height y: p/4 at the pitch line, 14.5 deg flanks."""
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
    # manager reads BARE numbers in document units (an unsuffixed 300 = 300 in,
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

    # Pattern along +X (measuring-stick precedent: direction point on the
    # bottom edge, seed at the left end; the volume check catches reversal).
    res = await adapter.linear_pattern_feature(
        LinearPatternParameters(
            direction_point=[BAR_LENGTH / 2.0, 0.0, 0.0],
            features=[gap_cut_name],
            count=GAP_COUNT,
            spacing=PITCH,
        )
    )
    check("linear pattern gaps", res)
    name_last_feature(adapter, "ToothPattern")
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
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
