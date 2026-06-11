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

import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    measure_check,
    report_mass_properties,
    run_build,
    save_part_and_images,
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

    await ensure_fully_defined(adapter, "bar profile", fix_entities=lines)
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
    # same precedent as the _common spring-hook flip retry).
    res = await adapter.get_mass_properties()
    vol_before = res.data.volume
    print(f"  volume before top pin hole: {vol_before:.1f} mm^3")
    pin_y = BAR_LENGTH - TOP_PIN_DROP
    for sketch_x in (BAR_DEPTH / 2.0, -BAR_DEPTH / 2.0):
        check("create_sketch top pin hole", await adapter.create_sketch("Right"))
        await define_circle(
            adapter, sketch_x, pin_y, TOP_PIN_HOLE_DIA / 2.0, "top pin hole"
        )
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
            continue
        res = await adapter.get_mass_properties()
        removed = vol_before - res.data.volume
        if removed > 1.0:
            print(
                f"  OK  top pin hole at sketch x={sketch_x:+g}"
                f" removed {removed:.1f} mm^3"
            )
            # expected: pi * 1^2 * (2 cheeks * 1.5875) = ~10 mm^3
            break
        print(f"  ..  top pin cut at sketch x={sketch_x:+g} removed nothing; flipping")
    else:
        raise RuntimeError("top pin hole cut removed no material on either side")

    await apply_material(adapter, MATERIAL)

    # Verify the two book-sourced dims on the built solid (ch. 15).
    mid_y, mid_z = BAR_LENGTH / 2.0, BAR_DEPTH / 2.0
    await measure_check(
        adapter,
        "bar width (annotated 6.35)",
        [
            {"entity_type": "FACE", "point": [0.0, mid_y, mid_z]},
            {"entity_type": "FACE", "point": [BAR_WIDTH, mid_y, mid_z]},
        ],
        "normal_distance",
        BAR_WIDTH,
    )
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
