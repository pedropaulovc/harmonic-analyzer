r"""Reproduction script: amplitude bar (book ch. 15, pp. 30-33).

One of the 20 chrome-finished bars (~80 cm long, 1/4" square) that set each
channel's Fourier coefficient. The bottom-end notch rides the rocker arm;
the deeper top-end notch hangs from the channel lever.

Dimensions: cad/DIMENSIONS.md "Chapter 15" — width 6.35 mm is book-annotated,
length ~80 cm book-stated (legacy 32" = 812.8 mm consistent, used exactly);
notch sizes are uncontradicted legacy values. Audit verdict: PASS.

Profile (on the Front plane, bar length along +Y, origin at bottom-left
corner) is a single 12-segment chain; both notches are centred slots in the
end faces. Extruded by the bar depth.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_amplitude_bar.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    add_line_chain,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "amplitude-bar"

BAR_LENGTH = 32.0 * IN  # 812.8  DIMENSIONS.md ch15: ~80 cm stated; legacy 32" (high)
BAR_WIDTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: annotated (high)
BAR_DEPTH = 0.25 * IN  # 6.35   DIMENSIONS.md ch15: legacy, square section (med)
BOTTOM_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
BOTTOM_NOTCH_HEIGHT = 0.09375 * IN  # 2.381  DIMENSIONS.md ch15: legacy 3/32" (med)
TOP_NOTCH_WIDTH = 0.125 * IN  # 3.175  DIMENSIONS.md ch15: legacy (med)
TOP_NOTCH_HEIGHT = 0.5 * IN  # 12.7   DIMENSIONS.md ch15: legacy (med)

NOTCH_OFFSET = (BAR_WIDTH - BOTTOM_NOTCH_WIDTH) / 2.0  # notches centred on width


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

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
