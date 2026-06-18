r"""Reproduction script: amplitude bar (book ch. 15, pp. 30-33).

One of the 20 chrome-finished bars (~80 cm long, 1/4" square) that set each
channel's Fourier coefficient. The bottom-end notch rides the rocker arm;
the deeper top-end notch straddles the channel lever and hangs from its Ø2
bar pin through the top pin hole (M6.3 layout: bars run UP the spine from
the rocker bank to the top-lever bank).

Dimensions: cad/DIMENSIONS.md "Chapter 15" — width 6.35 mm is book-annotated,
length ~80 cm book-stated (legacy 32" = 812.8 mm consistent, used exactly);
notch sizes are uncontradicted legacy values; top pin hole derived (M6.3).
Audit verdict: PASS.

Profile (on the Front plane, bar length along +Y, origin at bottom-left
corner) is a single 12-segment chain; both notches are centred slots in the
end faces. Extruded by the bar depth (+Z, 0..6.35). The top pin hole runs
along global X through the top-slot cheeks at 6.35 below the bar top,
mid-depth (Z = 3.175): a Right-plane sketch maps (x, y) -> global (±Z, Y)
with ambiguous handedness, so the cut is probed by volume read-back and the
sketch-x sign flipped on a miss (crank-arm cross-hole pattern).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_amplitude_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    apply_color,
    BAR_STEEL,
    blank_sketch,
    check,
    define_circle,
    ensure_fully_defined,
    feature_name_by_type,
    bbox_extent_check,
    measure_check,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "amplitude-bar"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

BAR_LENGTH = 32.0 * IN  # 812.8  DIMENSIONS.md ch15: ~80 cm stated; legacy 32" (high)
BAR_WIDTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: annotated (high)
BAR_DEPTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: legacy, square section (med)
BOTTOM_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
BOTTOM_NOTCH_HEIGHT = 0.09375 * IN  # 2.381  DIMENSIONS.md ch15: legacy 3/32" (med)
TOP_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
TOP_NOTCH_HEIGHT = 0.5 * IN  # 12.7   DIMENSIONS.md ch15: legacy (med)
TOP_PIN_HOLE_DIA = 2.0  # DIMENSIONS.md ch15: channel-lever bar pin (derived, M6.3)
TOP_PIN_DROP = 0.25 * IN  # 6.35  DIMENSIONS.md ch15: hole centre below bar top (derived)

NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # notches centred on width
THROUGH_CUT_DEPTH = 20.0  # mid-plane total; > bar width


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    check("create_sketch profile", await adapter.create_sketch("Front"))

    # Clockwise from the origin at the bottom-left corner.
    points = [
        (0.0, 0.0),
        (NOTCH_OFFSET, 0.0),
        (NOTCH_OFFSET, BOTTOM_NOTCH_HEIGHT),
        (NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, BOTTOM_NOTCH_HEIGHT),
        (NOTCH_OFFSET + BOTTOM_NOTCH_WIDTH, 0.0),
        (BAR_WIDTH, 0.0),
        (BAR_WIDTH, BAR_LENGTH),
        (BAR_WIDTH - NOTCH_OFFSET, BAR_LENGTH),
        (BAR_WIDTH - NOTCH_OFFSET, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH - TOP_NOTCH_HEIGHT),
        (BAR_WIDTH - NOTCH_OFFSET - TOP_NOTCH_WIDTH, BAR_LENGTH),
        (0.0, BAR_LENGTH),
    ]
    lines = await add_line_chain(adapter, points)

    horizontal = lines[0::2]  # even-index segments run along X
    vertical = lines[1::2]  # odd-index segments run along Y
    for ent in horizontal:
        check("constraint horizontal", await adapter.add_sketch_constraint(ent, None, "horizontal"))
    for ent in vertical:
        check("constraint vertical", await adapter.add_sketch_constraint(ent, None, "vertical"))

    # Ten driving dimensions; the last horizontal + closing vertical segment
    # lengths follow from profile closure.
    dims = [
        (lines[0], NOTCH_OFFSET, "bottom-left ledge"),
        (lines[1], BOTTOM_NOTCH_HEIGHT, "bottom notch height"),
        (lines[2], BOTTOM_NOTCH_WIDTH, "bottom notch width"),
        (lines[3], BOTTOM_NOTCH_HEIGHT, "bottom notch return"),
        (lines[4], NOTCH_OFFSET, "bottom-right ledge"),
        (lines[5], BAR_LENGTH, "bar length"),
        (lines[6], NOTCH_OFFSET, "top-right ledge"),
        (lines[7], TOP_NOTCH_HEIGHT, "top notch height"),
        (lines[8], TOP_NOTCH_WIDTH, "top notch width"),
        (lines[9], TOP_NOTCH_HEIGHT, "top notch return"),
    ]
    for ent, value, label in dims:
        check(
            f"dimension {label} = {value:g}",
            await adapter.add_sketch_dimension(ent, None, "linear", value),
        )

    # The chain's first vertex sits on the origin; with the h/v relations
    # and the ten dims (closure covers the last two segment lengths) this
    # single anchor completes the 24-DOF profile.
    check(
        "anchor profile corner",
        await adapter.add_sketch_constraint(f"{lines[0]}.start", "origin", "coincident"),
    )
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    check(
        "extrude bar",
        await adapter.create_extrusion(ExtrusionParameters(depth=BAR_DEPTH)),
    )

    # Top pin hole: Ø2 along global X through the top-slot cheeks, hanging
    # the bar from the channel lever's bar pin. Right-plane handedness is
    # ambiguous: the wrong sketch-x sign puts the circle at Z = -3.175,
    # outside the 0..6.35 body, and the cut removes nothing — probe by
    # volume read-back and flip (a dead miss feature may stay in the tree,
    # same precedent as the _common spring-hook flip retry). Inference OFF:
    # with it on, the circle snapped onto the bar's top corner and resized
    # to r 6.35 (live-caught via STL: cut surface fit centre (812.8, 0),
    # r 6.353 — a 100.5 mm^3 corner round-off instead of the 10 mm^3 pin
    # hole), so the removed volume is asserted within ±2 of analytic.
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    print(f"  volume before top pin hole: {vol_before:.1f} mm^3")
    pin_y = BAR_LENGTH - TOP_PIN_DROP
    # cheeks total = bar width - slot width
    expected_removed = (
        math.pi * (TOP_PIN_HOLE_DIA / 2.0) ** 2 * (BAR_WIDTH - TOP_NOTCH_WIDTH)
    )
    for sketch_x in (BAR_DEPTH / 2.0, -BAR_DEPTH / 2.0):
        check("create_sketch top pin hole", await adapter.create_sketch("Right"))
        set_sketch_direct_db(adapter, True)  # inference snaps to the top corner
        await define_circle(
            adapter, sketch_x, pin_y, TOP_PIN_HOLE_DIA / 2.0, "top pin hole"
        )
        set_sketch_direct_db(adapter, False)
        await ensure_fully_defined(adapter, "top pin hole sketch")
        check("exit_sketch top pin hole", await adapter.exit_sketch())
        cut = await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        )
        if not cut.is_success:
            print(
                f"  ..  top pin cut at sketch x={sketch_x:+g} failed"
                f" ({cut.error}); flipping sign"
            )
            # The unconsumed sketch would stay SHOWN and render in all 20
            # assembly instances (floating circles above the top frame).
            orphan = feature_name_by_type(adapter, "ProfileFeature")
            if orphan:
                blank_sketch(adapter, orphan)
            continue
        res = await adapter.get_mass_properties()
        removed = vol_before - res.data.volume
        if abs(removed - expected_removed) < 2.0:
            print(
                f"  OK  top pin hole at sketch x={sketch_x:+g}"
                f" removed {removed:.1f} mm^3 (analytic {expected_removed:.1f})"
            )
            break
        if removed < 1.0:
            print(
                f"  ..  top pin cut at sketch x={sketch_x:+g} removed nothing;"
                " flipping"
            )
            continue
        raise RuntimeError(
            f"top pin cut removed {removed:.1f} mm^3, expected"
            f" {expected_removed:.1f} — circle misplaced/resized"
        )
    else:
        raise RuntimeError("top pin hole cut removed no material on either side")

    # Named axes (parallel to the top-pin bore, view-independent selection):
    # Axis1 = top-pin bore at (y = pin_y, z = mid-depth) -- the hole runs along
    # local X, so the axis is (Top + pin_y) ∩ (Front + depth/2); Axis2 = a foot
    # reference axis at the bar bottom (y = 0), an ~806 mm lever arm from the
    # top pin that the assembly spin driver uses to pin the bar's swing.
    await name_bore_axis(
        adapter, "Top Plane", pin_y, "Front Plane", BAR_DEPTH / 2.0, "top pin bore"
    )
    await name_bore_axis(
        adapter, "Top Plane", 0.0, "Front Plane", BAR_DEPTH / 2.0, "foot axis"
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, BAR_STEEL)  # ch30 plates: see _common palette

    # Verify the two book-sourced dims on the built solid (ch. 15).
    mid_y = BAR_LENGTH / 2.0
    await bbox_extent_check(adapter, "bar width (annotated 6.35)", "x", BAR_WIDTH)
    # End-face pair selection fails (the far face is hidden in the active
    # view and point picking is screen-projected) — use a long silhouette
    # edge instead; the notches only cut the end faces, so it runs full
    # length.
    await measure_check(
        adapter,
        "bar length (stated ~80 cm / legacy 32 in)",
        [{"entity_type": "EDGE", "point": [0.0, mid_y, BAR_DEPTH]}],
        "length",
        BAR_LENGTH,
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
