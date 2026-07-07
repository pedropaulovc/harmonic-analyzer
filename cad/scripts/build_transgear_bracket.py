r"""Reproduction script: transgear bracket (book ch. 23, pp. 62-63).

The black plate that hangs the whole translational-gear cluster off the BACK
of the platen support bar (p.62 top-down / p.63 back view): fastened to the
bar by two large slotted screws (build_bracket_screw.py), with the stud bore
below the bar carrying the fixed stud (build_transgear_stub.py) on which the
120T disc + feed pinion turn and the latch arm swings.

Layout: plate in the Front plane, thickness extruded +Z (the assembly seats
local z 0 on the bar's back face, plate spanning machine z -129.9..-125.9).
Origin at the STUD BORE centre; the two O4.4 screw holes sit at x +-10 on
the bar's mid-height line (local y 40.53), plate top edge flush with the
bar top.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

PART_NAME = "transgear-bracket"
MATERIAL = "Gray Cast Iron"  # black casting like the clamps (p.62/63)

PLATE_HALF_W = 15.0  # lateral half-width about the stud line
PLATE_Y = (-12.0, 51.53)  # 12 below the stud .. flush with the bar top
PLATE_THICK = 4.0
STUD_BORE_DIA = 9.6  # the O9.525 stud plugs in
SCREW_HOLE_DX = 10.0  # bar sockets at stud x +-10 (support-bar BRACKET_HOLE_X)
SCREW_HOLE_Y = 40.53  # bar mid-height above the stud (338.5 - 297.97)
SCREW_HOLE_DIA = 4.4  # clearance for the O3.9 bracket screws


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "PlateHalfW", f"{PLATE_HALF_W}mm")
    await set_global(adapter, "PlateY0", f"{-PLATE_Y[0]}mm")  # unsigned drop below the stud
    await set_global(adapter, "PlateY1", f"{PLATE_Y[1]}mm")
    await set_global(adapter, "PlateThick", f"{PLATE_THICK}mm")
    await set_global(adapter, "StudBoreDia", f"{STUD_BORE_DIA}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Plate outline: rectangle spanning x -+PLATE_HALF_W, y PLATE_Y. Emission
    # order (rectilinear chain, anchor vertex 0 at (-W, y0), both coords
    # non-zero): seg0 width, seg1 height, then anchor x (unsigned W) and
    # anchor z (unsigned |y0|).
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Front"))
    rect = [
        (-PLATE_HALF_W, PLATE_Y[0]),
        (PLATE_HALF_W, PLATE_Y[0]),
        (PLATE_HALF_W, PLATE_Y[1]),
        (-PLATE_HALF_W, PLATE_Y[1]),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="plate", dims=plate,
        names=["Width", "Height", "AnchorX", "AnchorZ"],
        drives=[
            '2 * "PlateHalfW"',
            '"PlateY1" + "PlateY0"',
            '"PlateHalfW"',
            '"PlateY0"',
        ],
    )
    await ensure_fully_defined(adapter, "plate sketch")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICK)),
    )
    name_last_feature(adapter, "Plate")
    expected = 2.0 * PLATE_HALF_W * (PLATE_Y[1] - PLATE_Y[0]) * PLATE_THICK
    await volume_check(adapter, "plate", expected, 0.005 * expected)

    # Stud bore (origin: only the diameter is a dim) + the two screw holes
    # (off-axis in x and y: three dims each; positions are the bar layout, so
    # they are named but undriven -- only the diameters ride the globals).
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, 0.0, 0.0, STUD_BORE_DIA / 2.0, "stud bore", dims=holes,
        names=("StudCx", "StudCz", "StudDia"),
        drives=(None, None, '"StudBoreDia"'),
    )
    for label, x in (("Pos", SCREW_HOLE_DX), ("Neg", -SCREW_HOLE_DX)):
        await define_circle(
            adapter, x, SCREW_HOLE_Y, SCREW_HOLE_DIA / 2.0, f"screw hole {label}",
            dims=holes,
            names=(f"Screw{label}X", f"Screw{label}Z", f"Screw{label}Dia"),
            drives=(None, None, '"ScrewHoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PLATE_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Holes")
    v_holes = (
        math.pi * (STUD_BORE_DIA / 2.0) ** 2
        + 2.0 * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2
    ) * PLATE_THICK
    expected -= v_holes
    await volume_check(adapter, "holes", expected, 0.02 * v_holes)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven bracket (equations neutral)", expected, 0.02 * v_holes
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
