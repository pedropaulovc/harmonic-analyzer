r"""Reproduction script: platen rack bar (book ch. 22 pp. 54-55, teeth ch. 23).

The brass rack screwed along the platen's back bottom edge, driven by the
120T DP 30 rack pinion. The bar section comes from the ch. 22 photos; the
tooth pitch was resolved during M4 gear prep (DIMENSIONS.md ch. 23: rack
pitch measured as DP 30 on `v4_transgear_028/030` -- it is the scale anchor
for the whole chapter), superseding this script's M2 smooth-bar version.
Mounting holes stay deferred to the M6 drive-train work (Appendix C #8).

Rack tooth form: straight-flanked trapezoid (the involute rack profile is
exactly straight at the 14.5 deg pressure angle). With the pitch line at
PITCH_LINE_Y, gap half-width is p/4 at the pitch line and flares at 14.5 deg:
root (dedendum 1.157/DP below) half-width 0.412, cut overshoot to y = 31
(past the bar top at 30, so the cut opens cleanly) half-width 1.143. The
teeth crest at the bar top = pitch line + addendum (1/DP).

112 gaps at p = pi/30 in = 2.660 mm fill the 300 mm bar (first gap centre
at 1.33 mm; last opening ends at 297.5 mm).

Layout: bar x = 0..300, y = 0..30, z = 0..6; teeth cut into the top edge.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_rack.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_polygon_chain,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)
from _gear import volume_check

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
BAR_LENGTH = 300.0  # DIMENSIONS.md ch22: = platen width (low)
BAR_HEIGHT = 30.0  # DIMENSIONS.md ch22: back-side brass strip (low)
BAR_THICKNESS = 6.0  # DIMENSIONS.md ch22: edge-on photo (low)

PITCH = math.pi / DP * IN  # 2.660 mm
ADDENDUM = 1.0 / DP * IN  # 0.847 mm
DEDENDUM = 1.157 / DP * IN  # 0.980 mm -- 14.5 deg full-depth standard

PITCH_LINE_Y = BAR_HEIGHT - ADDENDUM  # 29.153 -- teeth crest at the bar top
ROOT_Y = PITCH_LINE_Y - DEDENDUM  # 28.174
CUT_TOP_Y = BAR_HEIGHT + 1.0  # opens past the top edge
TAN_PA = math.tan(math.radians(PA_DEG))

GAP_COUNT = 112
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

    # Bar blank: origin-cornered rectangle.
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (0.0, 0.0),
        (BAR_LENGTH, 0.0),
        (BAR_LENGTH, BAR_HEIGHT),
        (0.0, BAR_HEIGHT),
    ]
    bar_lines = await add_line_chain(adapter, bar_rect)
    await define_rectilinear_chain(adapter, bar_lines, bar_rect, label="bar")
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_THICKNESS)),
    )
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
    await define_polygon_chain(adapter, gap, gap_pts, label="gap")
    await ensure_fully_defined(adapter, "gap sketch")
    check("exit_sketch gap", await adapter.exit_sketch())
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BAR_THICKNESS + 1.0)
    )
    check("cut seed gap", gap_cut)
    v_gap = GAP_AREA * BAR_THICKNESS
    volume = await volume_check(adapter, "seed gap", volume - v_gap, 0.02 * v_gap)

    # Pattern along +X (measuring-stick precedent: direction point on the
    # bottom edge, seed at the left end; the volume check catches reversal).
    res = await adapter.linear_pattern_feature(
        LinearPatternParameters(
            direction_point=[BAR_LENGTH / 2.0, 0.0, 0.0],
            features=[gap_cut.data.name],
            count=GAP_COUNT,
            spacing=PITCH,
        )
    )
    check("linear pattern gaps", res)
    v_rack = v_bar - GAP_COUNT * v_gap
    await volume_check(adapter, "toothed rack", v_rack, 0.01 * GAP_COUNT * v_gap)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
