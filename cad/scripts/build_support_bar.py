r"""Reproduction script: platen support bar (book ch. 21/22, pp. 50-55, 62-63).

THE bar the platen rides on (book p.62 caption, singular): one rectangular
steel bar clamped across the two front columns by the two-piece column
clamps (build_column_clamp_front/back.py), carrying the hanging platen
(guides + locks on the platen back) and, on its own back face, the
transgear bracket (build_transgear_bracket.py). Cross-section 22 tall x
9 deep (ch22 back-side wear band + ch30 front view); 452 long so the ends
run ~29 past each column (ch30 p002).

Holes (all along local Z, the machine front-back axis):
* 4x O4.4 clamp-screw through-holes flanking each column (x +-197 -+ 17.5):
  the screw heads sit on the BAR's front face (ch30 p002) and thread into
  the back clamp arc.
* 2x O4.0 bracket sockets in the BACK face at x 2 / 22, 8 deep (the two
  large slotted screws of the p.62/63 top/back views).

Layout: bar axis along X, origin at the bar centre; height along Y,
depth along Z (front face local z -4.5). Dimensions: docs/
paper-drive-rework.md E1/E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_support_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_HEIGHT = 22.0  # tall (Y) -- ch22 back-side wear band (low)
BAR_DEPTH = 9.0  # deep (Z) -- front face rubs the platen back (low)
BAR_LENGTH = 452.0  # ends at x +-226, ~29 past each Ø25.4 column (ch30 p002)

COLUMN_X = 197.0  # frame column line (frame assembly)
CLAMP_SCREW_DX = 17.5  # clamp screws flank each column
CLAMP_HOLE_DIA = 4.4  # O4 clamp-screw shanks pass through
BRACKET_HOLE_X = (2.0, 22.0)  # transgear-bracket screw line (stud x 12 +- 10)
BRACKET_HOLE_DIA = 4.0  # O4 bracket screws thread in

CLAMP_HOLE_X = tuple(
    s * (COLUMN_X + d) for s in (-1.0, 1.0) for d in (-CLAMP_SCREW_DX, CLAMP_SCREW_DX)
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 452 = 452 in).
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "ClampHoleDia", f"{CLAMP_HOLE_DIA}mm")
    await set_global(adapter, "BracketHoleDia", f"{BRACKET_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile: width along X = length, height along Y; depth extruded along Z.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_HEIGHT / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Height", drive_depth='"BarHeight"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BarLength" / 2', '"BarHeight" / 2'),
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")

    expected = BAR_HEIGHT * BAR_DEPTH * BAR_LENGTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Screw holes, all through along Z at the bar's mid-height: 4 clamp-screw
    # clearance holes flanking the columns + 2 bracket-screw holes at the stud
    # line (covered by the platen, so a through cut reads clean and avoids an
    # offset blind cut). Off-axis circles emit centre-x + diameter dims (y = 0
    # on the mid-height axis emits nothing); positions are the photo layout, so
    # they are named but undriven -- only the diameters ride the globals.
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, x in enumerate(CLAMP_HOLE_X):
        await define_circle(
            adapter, x, 0.0, CLAMP_HOLE_DIA / 2.0, f"clamp hole x{x:.0f}",
            dims=holes,
            names=(f"C{n}X", f"C{n}Z", f"C{n}Dia"),
            drives=(None, None, '"ClampHoleDia"'),
        )
    for n, x in enumerate(BRACKET_HOLE_X):
        await define_circle(
            adapter, x, 0.0, BRACKET_HOLE_DIA / 2.0, f"bracket hole x{x:.0f}",
            dims=holes,
            names=(f"B{n}X", f"B{n}Z", f"B{n}Dia"),
            drives=(None, None, '"BracketHoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_holes = (
        len(CLAMP_HOLE_X) * math.pi * (CLAMP_HOLE_DIA / 2.0) ** 2
        + len(BRACKET_HOLE_X) * math.pi * (BRACKET_HOLE_DIA / 2.0) ** 2
    ) * BAR_DEPTH
    expected -= v_holes
    await volume_check(adapter, "bar with holes", expected, 0.02 * v_holes)

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
