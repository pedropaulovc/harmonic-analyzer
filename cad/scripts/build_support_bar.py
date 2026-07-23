r"""Reproduction script: platen support bar (book ch. 21/22, pp. 50-55, 62-63).

THE bar the platen rides on (book p.62 caption, singular): one rectangular
steel bar clamped across the two front columns by the two-piece column
clamps (build_column_clamp_front/back.py), carrying the hanging platen
(guides + locks on the platen back) and, on its own back face, the
transgear bracket (build_transgear_bracket.py). Cross-section 22 tall x
9 deep (ch22 back-side wear band + ch30 front view); 452 long so the ends
run ~29 past each column (ch30 p002).

Holes (all along local Z, the machine front-back axis):
* 4x clamp-screw counterbores flanking each column (x +-197 -+ 17.5):
  the screw heads sit sub-flush in the BAR's front face so the refitted platen
  can slide across the east clamp, and thread into the back clamp arc.
* 2x O4.0 bracket-screw holes at MACHINE x -10 / +10 (the two large slotted
  screws of the p.62/63 top/back views, flanking the stud at machine x 0).

The bracket holes make the bar x-ASYMMETRIC, so it is authored MACHINE-
handed and placed on its exact machine transform (an x-mirrored insert
would flip the holes to +2/+22, off the stud line).

Layout: bar axis along X, origin at the bar centre; height along Y,
depth along Z (front face local z -4.5). Dimensions: memory/
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
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes

PART_NAME = "support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_HEIGHT = 22.0  # tall (Y) -- ch22 back-side wear band (low)
BAR_DEPTH = 9.0  # deep (Z) -- front face rubs the platen back (low)
BAR_LENGTH = 452.0  # ends at x +-226, ~29 past each Ø25.4 column (ch30 p002)

COLUMN_X = 197.0  # frame column line (frame assembly)
CLAMP_SCREW_DX = 17.5  # clamp screws flank each column
# The O3.9 clamp-screw shanks pass through #8 clearance holes. Their Ø8 heads
# are recessed 0.2 below the bar front: the right-shifted platen now travels
# across the east clamp screw line, so proud heads would block its slide.
CLAMP_CBORE_DIA = 8.5
CLAMP_CBORE_DEPTH = 2.7
CLAMP_HOLE_DIA = 4.978
CLAMP_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    "#8",
    overrides_mm={
        "HoleDiameter": CLAMP_HOLE_DIA,
        "CounterBoreDiameter": CLAMP_CBORE_DIA,
        "CounterBoreDepth": CLAMP_CBORE_DEPTH,
    },
)
BRACKET_STUD_X = 0.0
BRACKET_HOLE_X = tuple(BRACKET_STUD_X + dx for dx in (-10.0, 10.0))
# The ~Ø4 bracket screws THREAD IN: tapped #8-32 (nearest UNC coarse).
BRACKET_HOLE_SPEC = HoleSpec("tapped", "#8-32")

CLAMP_HOLE_X = tuple(
    s * (COLUMN_X + d) for s in (-1.0, 1.0) for d in (-CLAMP_SCREW_DX, CLAMP_SCREW_DX)
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 452 = 452 in).
    # (The old ClampHoleDia/BracketHoleDia knobs are gone: the screw holes are
    # now native Hole Wizard features whose diameters come from the ANSI-inch
    # clearance/tap tables, not driven dims.)
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile: width along X = length, height along Y; depth extruded along Z.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_HEIGHT / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Height", drive_depth='"BarHeight"',
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

    # Screw holes, all through along Z at the bar's mid-height, drilled from the
    # bar FRONT face (local z = -BAR_DEPTH/2, where the clamp-screw heads sit --
    # ch30 p002), while the bar is still a plain prism: TWO native Hole Wizard
    # features -- 4 clamp-screw #8 COUNTERBORES flanking the columns, and 2
    # #8-32 TAPPED bracket-screw holes at the stud line (the bracket screws
    # thread into the bar; covered by the platen, so a through cut reads clean).
    # Positions are the photo layout.
    front_z = -BAR_DEPTH / 2.0
    clamp_dia = CLAMP_HOLE_DIA
    bracket_dia = blind_cut_dia_mm(BRACKET_HOLE_SPEC)
    wizard_holes(
        adapter, CLAMP_HOLE_SPEC,
        [[x, 0.0, front_z] for x in CLAMP_HOLE_X],
        (0.0, 0.0, -1.0), "clamp-screw counterbores (#8)", name="ClampHoles",
    )
    wizard_holes(
        adapter, BRACKET_HOLE_SPEC,
        [[x, 0.0, front_z] for x in BRACKET_HOLE_X],
        (0.0, 0.0, -1.0), "bracket-screw tapped holes (#8-32)", name="BracketHoles",
    )
    v_holes = (
        len(CLAMP_HOLE_X)
        * (
            math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
            + math.pi
            * ((CLAMP_CBORE_DIA / 2.0) ** 2 - (clamp_dia / 2.0) ** 2)
            * CLAMP_CBORE_DEPTH
        )
        + len(BRACKET_HOLE_X)
        * math.pi
        * (bracket_dia / 2.0) ** 2
        * BAR_DEPTH
    )
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
