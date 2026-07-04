r"""Reproduction script: pinion swing bracket (book ch. 25; 2 used).

The polished-steel strap that carries one end of the alignment-pinion
drum (p. 68 close-ups, shot from the BACK side): a short rounded-end
flat bar with TWO Ø6.35 bores -- the bottom one pivots on the torque
shaft (build_pinion_pivot_shaft.py), the top one journals the drum's
arbor stub (build_alignment_pinion.py). The lift rod's cam pin
(build_pinion_lift_rod.py) bears on the strap flank to swing it.

Layout: pivot bore at the origin, arbor bore at (0, C2C), strap up +Y,
thickness z 0..5.

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
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

PART_NAME = "pinion-bracket"
MATERIAL = "Plain Carbon Steel"  # p.68: bright steel strap

WIDTH = 18.0  # ch25 strap width, photo-scaled vs the 42T drum tip Ø22.4 in
# v4_pinion_018 (strap ~0.8x the tip OD; the teeth stand proud of BOTH flanks
# -- the old 22 sat flush with the tips). Assembly guard: build_drive_train's
# STRAP_R_END must match WIDTH / 2.
C2C = 43.0  # pivot bore to arbor bore (ch30 GT 2026-07-02, was 31): the pinion
# now parks LEVEL with the drive axis, 42.0 above the pivot bore, so the strap
# spans sqrt(42^2 + 9.22^2) at a 12.4 deg west lean in the disengaged rest
# (build_drive_train_assembly STRAP_C2C / STRAP_LEAN_DEG -- must match)
THICKNESS = 5.0  # photo-scaled (low)
BORE = 6.35  # both bores: torque shaft below, drum arbor stub above (derived)

R_END = WIDTH / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the strap width (= cap radius x 2), the
    # bore-to-bore centre distance and the bore diameter. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 22 = 22 in). Thickness is the
    # extrude feature parameter (built with the literal); StrapThickness is
    # declared so a GUI edit sees the knob.
    await set_global(adapter, "StrapWidth", f"{WIDTH}mm")
    await set_global(adapter, "C2C", f"{C2C}mm")
    await set_global(adapter, "StrapThickness", f"{THICKNESS}mm")
    await set_global(adapter, "Bore", f"{BORE}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outer rounded-bar loop + both bores in ONE sketch -> single extrude.
    # Inference OFF: the bottom cap arc endpoints sit near the origin.
    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom_cap = check(
        "add bottom cap arc",
        await adapter.add_arc(0.0, 0.0, -R_END, 0.0, R_END, 0.0),
    )
    check("add right edge", await adapter.add_line(R_END, 0.0, R_END, C2C))
    top_cap = check(
        "add top cap arc",
        await adapter.add_arc(0.0, C2C, R_END, C2C, -R_END, C2C),
    )
    check("add left edge", await adapter.add_line(-R_END, C2C, -R_END, 0.0))
    # Pivot bore on the origin (only its diameter recorded); arbor bore on the +Y
    # axis (x 0): one centre dim (the rise, driven by the positive C2C) + diameter.
    await define_circle(
        adapter, 0.0, 0.0, BORE / 2.0, "pivot bore", dims=strap,
        names=("PivotBoreCx", "PivotBoreCz", "PivotBoreDia"),
        drives=(None, None, '"Bore"'),
    )
    arbor_bore = await define_circle(
        adapter, 0.0, C2C, BORE / 2.0, "arbor bore", dims=strap,
        names=("ArborBoreCx", "ArborBoreCz", "ArborBoreDia"),
        drives=(None, '"C2C"', '"Bore"'),
    )
    set_sketch_direct_db(adapter, False)
    # Cap arcs: centre + radius + endpoint alignment (one angle constraint
    # per endpoint -- centre + radius + both endpoints fully located would
    # over-define an arc's 5 DOF). The side edges carry no relations of
    # their own: their endpoints merged with the cap endpoints at creation,
    # so the four h-aligned cap ends pin them too.
    check(
        "anchor bottom cap centre",
        await adapter.add_sketch_constraint(
            f"{bottom_cap}.center", "origin", "coincident"
        ),
    )
    check(
        "bottom cap radius",
        await adapter.add_sketch_dimension(bottom_cap, None, "radial", R_END),
    )
    strap.record("BottomCapRadius", '"StrapWidth" / 2')
    # The top cap is CONCENTRIC with the arbor bore -- that is the design intent,
    # so say it as a constraint instead of re-dimensioning the rise. (The obvious
    # alternative, anchor_point_to_origin + an ArborCentreRise = "C2C" equation,
    # fails live: SolidWorks rejects ANY equation binding on that point-to-origin
    # distance dim -- even a literal 43mm -- erroring the Equations folder on
    # rebuild, while the identical dim on the bore circle takes "C2C" fine.
    # Probed 2026-07-02; same bug class as the magnifying-lever dome radius.)
    check(
        "top cap centre concentric with arbor bore",
        await adapter.add_sketch_constraint(
            f"{top_cap}.center", f"{arbor_bore}.center", "coincident"
        ),
    )
    check(
        "top cap radius",
        await adapter.add_sketch_dimension(top_cap, None, "radial", R_END),
    )
    strap.record("TopCapRadius", '"StrapWidth" / 2')
    for cap, end in (
        (bottom_cap, "start"),
        (bottom_cap, "end"),
        (top_cap, "start"),
        (top_cap, "end"),
    ):
        check(
            f"cap {end} level",
            await adapter.add_sketch_constraint(
                f"{cap}.{end}", f"{cap}.center", "horizontal_points"
            ),
        )
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(ExtrusionParameters(depth=THICKNESS)),
    )
    name_last_feature(adapter, "Strap")
    area = (
        WIDTH * C2C
        + math.pi * R_END**2
        - 2.0 * math.pi * (BORE / 2.0) ** 2
    )
    expected = area * THICKNESS
    await volume_check(adapter, "strap", expected, 0.005 * expected)

    # Named bore axes for the assembly: the pivot bore (Axis1) rides the torque
    # shaft, the arbor bore (Axis2) journals the pinion. The p2 swing group keys
    # off these (concentric to the shaft + lock the pinion in -- build_drive_train).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pivot bore")
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", C2C, "arbor bore")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven strap (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
