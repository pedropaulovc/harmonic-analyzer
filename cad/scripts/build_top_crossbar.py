r"""Reproduction script: top crossbar (book ch. 18, pp. 42-43).

The green cast bar spanning the top-frame ring front-to-back (along Z)
at the machine's x mid-line: it carries the knife-mount stud that hangs
the summing-lever knife bar. Same 22 x 41 section as the ring rails
(build_top_frame.py), 202 long: its ends sit face-flush on the ring
window's north/south faces at z +/-101 (INNER_Z; the M6.4 372 span used
the ring's inner X span by mistake and buried both ends in the rails).
A O8.2 vertical hole at its centre passes the O8 stud.

Layout: origin on the stud-hole axis at the bar's bottom face (machine
(15, 999.7, 0)); bar +Y 41, +-Z 186. Dimensions: cad/DIMENSIONS.md
ch. 18 (rail section med, hole low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_top_crossbar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_rectilinear_chain,
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

PART_NAME = "top-crossbar"
MATERIAL = "Gray Cast Iron"  # green casting

BAR_HALF_X = 11.0  # rail section 22 wide (DIMENSIONS.md ch6, med)
BAR_HEIGHT = 41.0  # rail section 41 tall (med)
BAR_HALF_Z = 101.0  # ends flush on the ring window faces at z +/-101 (derived)
# Knife-mount Ø8 stud passes through: 5/16 clearance, CLOSE fit (Ø8.331, the
# wizard twin of the old Ø8.2 artefact dim).
HOLE_SPEC = HoleSpec("clearance", "5/16", fit="close")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rail section (half-width + height),
    # the half-span to the window faces, and the stud-hole diameter. The mm suffix
    # is load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 202 = 202 in, 25.4x too big).
    # (The old HoleDia knob is gone: the stud hole is now a native Hole Wizard
    # 5/16 clearance feature whose diameter comes from the table, not a dim.)
    await set_global(adapter, "BarHalfX", f"{BAR_HALF_X}mm")
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarHalfZ", f"{BAR_HALF_Z}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile in Front (X x Y): base on the X axis (corner at (-BarHalfX, 0)),
    # NOT origin-centred in Y, so this stays a rectilinear chain rather than
    # define_centered_rectangle. Emission order = the kept per-segment distance
    # dims in line order (Width along X, Height along Y), THEN the anchor dims
    # (corner x != 0 -> one dim; corner y == 0 -> none): Width, Height, CornerX.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (-BAR_HALF_X, 0.0),
        (BAR_HALF_X, 0.0),
        (BAR_HALF_X, BAR_HEIGHT),
        (-BAR_HALF_X, BAR_HEIGHT),
    ]
    outline = await add_line_chain(adapter, bar_rect)
    await define_rectilinear_chain(
        adapter, outline, bar_rect, label="bar", dims=bar,
        names=["Width", "Height", "CornerX"],
        drives=['2 * "BarHalfX"', '"BarHeight"', '"BarHalfX"'],
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * BAR_HALF_Z, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")

    # Stud hole on the bar axis (origin): ONE native Hole Wizard 5/16 clearance
    # feature, through-all along Y, drilled from the bar's bottom face (y=0)
    # while the bar is a plain prism.
    hole_dia = blind_cut_dia_mm(HOLE_SPEC)
    wizard_holes(
        adapter, HOLE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0), "knife-mount stud hole (5/16 clearance)", name="StudHole",
    )

    expected = (
        2.0 * BAR_HALF_X * BAR_HEIGHT * 2.0 * BAR_HALF_Z
        - math.pi * (hole_dia / 2.0) ** 2 * BAR_HEIGHT
    )
    await volume_check(adapter, "crossbar", expected, 0.005 * expected)

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crossbar (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
