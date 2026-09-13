r"""Reproduction script: tube frame column (legacy part; book ch. 5-6).

Hollow steel column carrying the upper frame rails: Ø1.0 in (25.4 mm) tube
with a 0.12 in wall, topped by an integral polished dome cap.

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

Length: the 994.0 visible span is extended into the base socket by 25.4,
so the installed top station is preserved when the column origin moves down
from the deck to Y=25.4. Two Ø5 transverse stations are drilled through both
Z walls at the shared lower/top cross-screw axes.

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
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from tube_frame_spec import (
    COLUMN_LENGTH,
    COLUMN_LENGTH_TOLERANCE_MM,
    CROSS_HOLE_DIAMETER,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    INNER_DIA,
    ISOMETRIC_VIEW_NOTE,
    LENGTH_VIEW_NOTE,
    LOWER_CROSS_HOLE_Y,
    OUTER_DIA,
    OUTER_DIA_BAND,
    TOP_END_CHAMFER,
    UPPER_CROSS_HOLE_Y,
    WALL_THICKNESS,
)

PART_NAME = "tube-frame"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# The regular open tube and both matched cross-hole stations share their
# installed geometry with the base, top frame, and purchased cap through
# tube_frame_spec/frame_attachment_spec.

TOP_END_CHAMFER_BAND = (0.15, -0.10)


def _transverse_hole_removal(
    hole_dia: float, outer_dia: float, inner_dia: float
) -> float:
    """Volume removed where a cross drill intersects the tube annulus."""
    hole_r = hole_dia / 2.0
    outer_r = outer_dia / 2.0
    inner_r = inner_dia / 2.0
    step = 0.001
    volume = 0.0
    x = -hole_r
    while x < hole_r:
        dx = x + step / 2.0
        hole_chord = 2.0 * math.sqrt(max(0.0, hole_r * hole_r - dx * dx))
        outer_span = 2.0 * math.sqrt(max(0.0, outer_r * outer_r - dx * dx))
        inner_span = 2.0 * math.sqrt(max(0.0, inner_r * inner_r - dx * dx))
        volume += hole_chord * (outer_span - inner_span) * step
        x += step
    return volume


if not (
    CROSS_HOLE_DIAMETER < INNER_DIA
    and LOWER_CROSS_HOLE_Y > CROSS_HOLE_DIAMETER / 2.0
    and UPPER_CROSS_HOLE_Y < COLUMN_LENGTH - CROSS_HOLE_DIAMETER / 2.0
):
    raise AssertionError("tube cross-hole stations do not leave intact end walls")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs: tube OD, wall, cut length, cross-hole size/stations, and
    # the top-only cap-entry chamfer. Explicit mm is load-bearing in this inch
    # document. InnerDia remains derived from OD minus two walls.
    await set_global(adapter, "OuterDia", f"{OUTER_DIA}mm")
    await set_global(adapter, "WallThickness", f"{WALL_THICKNESS}mm")
    await set_global(adapter, "ColumnLength", f"{COLUMN_LENGTH}mm")
    await set_global(adapter, "InnerDia", '"OuterDia" - 2 * "WallThickness"')
    await set_global(adapter, "TopChamfer", f"{TOP_END_CHAMFER}mm")
    await set_global(adapter, "CrossHoleDia", f"{CROSS_HOLE_DIAMETER}mm")
    await set_global(adapter, "LowerCrossHoleY", f"{LOWER_CROSS_HOLE_Y}mm")
    await set_global(adapter, "UpperCrossHoleY", f"{UPPER_CROSS_HOLE_Y}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: concentric outer + bore circles on the Top plane, both on-axis
    # (origin centre) so each records ONLY its diameter dim.
    annulus = SketchDims()
    check("create_sketch annulus", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter,
        0.0,
        0.0,
        OUTER_DIA / 2.0,
        "outer circle",
        dims=annulus,
        names=("OuterCx", "OuterCz", "OuterDia"),
        drives=(None, None, '"OuterDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        INNER_DIA / 2.0,
        "bore circle",
        dims=annulus,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"InnerDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "annulus sketch")
    check("exit_sketch annulus", await adapter.exit_sketch())
    name_last_feature(adapter, "AnnulusProfile")
    drive_jobs += annulus.apply(adapter, "AnnulusProfile")
    check(
        "extrude open tube",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLUMN_LENGTH)),
    )
    name_last_feature(adapter, "Column")
    depth_dim = name_dimensions(adapter, "Column", ["Length"])
    drive_jobs += [(depth_dim[0], '"ColumnLength"')]
    v_annulus = (
        math.pi * ((OUTER_DIA / 2.0) ** 2 - (INNER_DIA / 2.0) ** 2) * COLUMN_LENGTH
    )
    await volume_check(adapter, "open tube", v_annulus, 0.001 * v_annulus)

    # Two matched clearance stations through both Z walls. One physical column
    # can rotate 180 degrees about Y between front/rear corners because each
    # drilling is diametrically through, not a one-wall set-screw clearance.
    cross = SketchDims()
    check("create_sketch tube cross holes", await adapter.create_sketch("Front"))
    for label, station, dia_name in (
        ("lower", LOWER_CROSS_HOLE_Y, "CrossHoleDia"),
        ("upper", UPPER_CROSS_HOLE_Y, "UpperCrossHoleDia"),
    ):
        await define_circle(
            adapter,
            0.0,
            station,
            CROSS_HOLE_DIAMETER / 2.0,
            f"{label} tube cross hole",
            dims=cross,
            names=(None, f"{label.capitalize()}HoleY", dia_name),
            drives=(None, f'"{label.capitalize()}CrossHoleY"', '"CrossHoleDia"'),
        )
    await ensure_fully_defined(adapter, "tube cross-hole sketch")
    check("exit_sketch tube cross holes", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += cross.apply(adapter, "CrossHoleProfile")
    check(
        "cut tube cross holes through both walls",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * OUTER_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHoles")
    v_cross = _transverse_hole_removal(CROSS_HOLE_DIAMETER, OUTER_DIA, INNER_DIA)
    v_column = v_annulus - 2.0 * v_cross
    await volume_check(adapter, "cross-drilled column", v_column, 0.005 * v_cross + 1.0)

    # Top-only C0.50 x 45 break clears the purchased cap's R0.3175 inner
    # corner. The lower socketed end remains square.
    check(
        "chamfer tube top",
        await adapter.add_chamfer(
            TOP_END_CHAMFER,
            [[OUTER_DIA / 2.0, COLUMN_LENGTH, 0.0]],
        ),
    )
    name_last_feature(adapter, "TopEndBreak")
    chamfer_dim = name_dimensions(adapter, "TopEndBreak", ["TopChamfer"])
    drive_jobs.append((chamfer_dim[0], '"TopChamfer"'))
    v_chamfer = math.pi * TOP_END_CHAMFER**2 * (OUTER_DIA / 2.0 - TOP_END_CHAMFER / 3.0)
    v_total = v_column - v_chamfer
    await volume_check(adapter, "finished open tube", v_total, 0.002 * v_total)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "AnnulusProfile", "OuterDia", *deviations(OUTER_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "Column", "Length", COLUMN_LENGTH_TOLERANCE_MM
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "TopEndBreak",
        "TopChamfer",
        *deviations(TOP_END_CHAMFER_BAND),
    )
    await volume_check(
        adapter, "driven open tube (equations neutral)", v_total, 0.001 * v_total
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)  # ch30 plates: see _common palette

    # Verify the regular tube's cut length; the separate cap establishes the
    # preserved finished assembly top.
    await bbox_extent_check(adapter, "tube cut length", "y", COLUMN_LENGTH)

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
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Length View Note": LENGTH_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
