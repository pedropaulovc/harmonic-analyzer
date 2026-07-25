r"""Reproduction script: top crossbar (book ch. 18, pp. 42-43).

The green cast bar spanning the top-frame ring front-to-back (along Z)
at the machine's x mid-line: it carries the knife-mount stud that hangs
the summing-lever knife bar. Same 22 x 41 section as the ring rails
(build_top_frame.py), 237.415 long after the v2 rear-frame re-anchor: its
ends sit face-flush on the ring window at z -101 / +136.415 (the M6.4 372 span used
the ring's inner X span by mistake and buried both ends in the rails).
A O8.2 vertical hole at machine z +35.415 passes the O8 stud.

Layout: the part origin is at the asymmetric frame span centre; the stud
hole is +17.7075 in part Z. Dimensions: cad/DIMENSIONS.md
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
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes
from top_crossbar_spec import (
    BAR_HALF_X,
    BAR_HALF_Z,
    BAR_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    STUD_HOLE_FIT,
    STUD_HOLE_SIZE,
    STUD_HOLE_Z,
    TOP_VIEW_NOTE,
)

PART_NAME = "top-crossbar"
MATERIAL = "Gray Cast Iron"  # green casting

# Knife-mount Ø8 stud passes through: 5/16 clearance, CLOSE fit (Ø8.331, the
# wizard twin of the old Ø8.2 artefact dim).
HOLE_SPEC = HoleSpec("clearance", STUD_HOLE_SIZE, fit=STUD_HOLE_FIT)


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
    await set_global(adapter, "StudHoleZ", f"{STUD_HOLE_Z}mm")

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
    depth_dim = name_dimensions(adapter, "Bar", ["Depth"])
    drive_jobs += [(depth_dim[0], '2 * "BarHalfZ"')]

    # Stud hole on the shifted summing axis: ONE native Hole Wizard 5/16 clearance
    # feature, through-all along Y, drilled from the bar's bottom face (y=0)
    # while the bar is a plain prism.
    hole_dia = blind_cut_dia_mm(HOLE_SPEC)
    wizard_holes(
        adapter, HOLE_SPEC,
        [[0.0, 0.0, STUD_HOLE_Z]],
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
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Top View Note": TOP_VIEW_NOTE,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
