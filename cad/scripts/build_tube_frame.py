r"""Reproduction script: tube frame column (legacy part; book ch. 5-6).

Hollow steel column carrying the upper frame rails: Ø1.0 in (25.4 mm) tube
with a 0.12 in wall.

Diameter: REDERIVED from the ch30 8-view set (supersedes the legacy
Ø1.375 in, which had no book numeric and overstated the OD by ~45%). The
four quarter views (p003/p005/p007/p009) resolve the frame into four
isolated single columns; under the manifest's orthographic cameras a
vertical cylinder's apparent width = diameter x scale, with the per-view
scale fit from the known column corner stations (±197, ±112) and azimuth
(R^2 0.94-0.99) and cross-checked against the base plate (460 mm -> ~1500
px in the front view, matching the column-spacing scale and confirming
the ±197 stations). Seven isolated-column reads gave Ø23.8 ± 1.0 mm;
rounded to the standard 1 in tube stock the machine (1896 Gaertner & Co.)
would have used. The wall is the uncontradicted legacy 0.12 in (no
view-based interior numeric). See cad/DIMENSIONS.md tube-frame row.

Surface: SMOOTH polished tube (M6.8 ch30 8-view pass, user-confirmed).
The M4 fluting (16 grooves, photogrammetry estimate) is retired: every
ch30 plate shows plain reflective columns, and the groove edges also
painted the columns black at capture scale.

Length: 989.9 so the column top lands flush with the top-frame ring's
top face (1040.7 = base top 50.8 + 989.9) - all eight ch30 plates show
the columns capped by the ring's corner bosses, with NO stub above
(user-confirmed; supersedes the ch. 6 "107 cm" reading, which matches
the overall frame height, not the bare column).

Dimensions: cad/DIMENSIONS.md "Legacy part audit" - OD rederived from the
ch30 8-views (med), wall legacy (med), length photo-locked to the
top-frame stack (med).

Layout: tube axis along +Y (column standing upright), annulus sketched on
the Top plane at the origin, extruded upward.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_tube_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    apply_color,
    POLISHED_STEEL,
    check,
    bbox_extent_check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from tube_frame_spec import (
    COLUMN_LENGTH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    INNER_DIA,
    LENGTH_VIEW_NOTE,
    OUTER_DIA,
    WALL_THICKNESS,
)

PART_NAME = "tube-frame"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# Tube nominals (OUTER_DIA / WALL_THICKNESS / INNER_DIA / COLUMN_LENGTH) live in
# tube_frame_spec -- the COM-free contract the drawing shares. Ø25.4 OD rederived
# from the ch30 8-views (Ø23.8±1.0 -> 1 in stock); 0.12 in wall -> Ø19.304 bore;
# length photo-locked to the top-frame stack (see build docstring).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): outer dia, wall, column length. The mm
    # suffix is load-bearing (INCH document; the equation manager reads bare
    # numbers in document units). InnerDia is the derived bore (OuterDia minus two
    # walls), so editing OuterDia or WallThickness reshapes the annulus. ColumnLength
    # is the extrude DEPTH (a feature parameter, not a sketch dim) -- an editable
    # knob that nothing in drive_jobs references.
    await set_global(adapter, "OuterDia", f"{OUTER_DIA}mm")
    await set_global(adapter, "WallThickness", f"{WALL_THICKNESS}mm")
    await set_global(adapter, "ColumnLength", f"{COLUMN_LENGTH}mm")
    await set_global(adapter, "InnerDia", '"OuterDia" - 2 * "WallThickness"')

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: concentric outer + bore circles on the Top plane, both on-axis
    # (origin centre) so each records ONLY its diameter dim.
    annulus = SketchDims()
    check("create_sketch annulus", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, 0.0, 0.0, OUTER_DIA / 2.0, "outer circle", dims=annulus,
        names=("OuterCx", "OuterCz", "OuterDia"),
        drives=(None, None, '"OuterDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, INNER_DIA / 2.0, "bore circle", dims=annulus,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"InnerDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    drive_jobs += annulus.apply(adapter, "AnnulusProfile")
    check(
        "extrude column",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLUMN_LENGTH)),
    )
    name_last_feature(adapter, "Column")
    depth_dim = name_dimensions(adapter, "Column", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ColumnLength"')]
    v_annulus = (
        math.pi * ((OUTER_DIA / 2.0) ** 2 - (INNER_DIA / 2.0) ** 2) * COLUMN_LENGTH
    )
    await volume_check(adapter, "annulus column", v_annulus, 0.001 * v_annulus)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven annulus column (equations neutral)", v_annulus, 0.001 * v_annulus)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)  # ch30 plates: see _common palette

    # Verify the photo-locked column height via the solid bounding box (the
    # end-annulus face pair was screen-projected and collapsed to one face).
    await bbox_extent_check(
        adapter, "column length (top-frame flush 989.9)", "y", COLUMN_LENGTH
    )

    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Length View Note": LENGTH_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
