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

Length: 994.0 OVERALL (dome apex included) so the column top lands at
1044.8 = base top 50.8 + 994.0 -- a short capped stub 8.6 above the
top-frame casting's rail top 1036.2 and 4.1 above its corner-boss tops
1040.7. The 2026-09-02 user re-read of the ch30 p002 plate shows the
columns ending JUST above the corner bosses, superseding the 2026-08-02
+28.6 stub (1014.0 / top 1064.8) and, before it, the M6.8 "no stub above"
reading; the ch. 6 "107 cm" remains the overall frame height, not the
bare column.

Cap: the polished turned cap pressed into each tube mouth (top.png /
ch30 p002 crops) is modeled INTEGRAL: a full-width spherical dome --
base Ø25.4 at the tube mouth y 990.7, rise 3.3 to the 994.0 apex,
SR 26.09 from the chord -- revolved about the column axis (the
magnifying-lever dome-arc convention). Plain capped stub: NO nut and
NO thread above the casting (user-corrected).

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
    anchor_point_to_origin,
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
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from tube_frame_spec import (
    BODY_LENGTH,
    CAP_HEIGHT,
    CAP_SPHERE_RADIUS,
    COLUMN_LENGTH,
    COLUMN_LENGTH_TOLERANCE_MM,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    INNER_DIA,
    LENGTH_VIEW_NOTE,
    OUTER_DIA,
    OUTER_DIA_BAND,
    WALL_THICKNESS,
)

PART_NAME = "tube-frame"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# Tube nominals (OUTER_DIA / WALL_THICKNESS / INNER_DIA / COLUMN_LENGTH /
# CAP_*) live in tube_frame_spec -- the COM-free contract the drawing shares.
# Ø25.4 OD rederived from the ch30 8-views (Ø23.8±1.0 -> 1 in stock); 0.12 in
# wall -> Ø19.304 bore; 994.0 overall = 990.7 tube + 3.3 dome cap,
# photo-locked to the top-frame stack (see build docstring).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): outer dia, wall, overall column
    # length, cap rise + sphere radius. The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    # InnerDia is the derived bore (OuterDia minus two walls), so editing
    # OuterDia or WallThickness reshapes the annulus. ColumnLength is the
    # OVERALL length (dome apex included): the tube extrude DEPTH is driven as
    # ColumnLength - CapHeight and the cap sketch's three axis stations hang
    # off ColumnLength / CapHeight / CapSphereR, so editing ColumnLength moves
    # the whole top end coherently. CapSphereR is data (26.088), re-derived in
    # tube_frame_spec from the OD/2 chord + CapHeight rise.
    await set_global(adapter, "OuterDia", f"{OUTER_DIA}mm")
    await set_global(adapter, "WallThickness", f"{WALL_THICKNESS}mm")
    await set_global(adapter, "ColumnLength", f"{COLUMN_LENGTH}mm")
    await set_global(adapter, "CapHeight", f"{CAP_HEIGHT}mm")
    await set_global(adapter, "CapSphereR", f"{CAP_SPHERE_RADIUS}mm")
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
        await adapter.create_extrusion(ExtrusionParameters(depth=BODY_LENGTH)),
    )
    name_last_feature(adapter, "Column")
    depth_dim = name_dimensions(adapter, "Column", ["Depth"])
    drive_jobs += [(depth_dim[0], '"ColumnLength" - "CapHeight"')]
    v_annulus = (
        math.pi * ((OUTER_DIA / 2.0) ** 2 - (INNER_DIA / 2.0) ** 2) * BODY_LENGTH
    )
    await volume_check(adapter, "annulus column", v_annulus, 0.001 * v_annulus)

    # Integral dome cap: the pressed-in polished turned cap, modeled as one
    # full-width spherical cap on the tube mouth (base Ø25.4 at y BODY_LENGTH,
    # rise CAP_HEIGHT to the COLUMN_LENGTH apex; sphere radius CAP_SPHERE_RADIUS
    # follows from the chord). Front-plane half profile revolved about the
    # column axis (the magnifying-lever dome-arc scheme): merged on-axis
    # centerline, a horizontal base line closing the tube mouth, and the CCW
    # dome arc from the rim up to the apex. The base inner corner, arc centre
    # and apex all sit ON the axis (vertical_points relation + one Y-station
    # dim each); the rim vertex then falls on the arc/base-line intersection
    # (the intrinsic equal-radius arc constraint; the solver keeps the created
    # side), so the three axis-station dims fully define the profile.
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "cap centerline",
        await adapter.add_centerline(0.0, BODY_LENGTH, 0.0, COLUMN_LENGTH),
    )
    cap_base = check(
        "add_line cap base",
        await adapter.add_line(0.0, BODY_LENGTH, OUTER_DIA / 2.0, BODY_LENGTH),
    )
    cap_arc = check(
        "add_arc cap dome",
        await adapter.add_arc(
            0.0, COLUMN_LENGTH - CAP_SPHERE_RADIUS,
            OUTER_DIA / 2.0, BODY_LENGTH,
            0.0, COLUMN_LENGTH,
        ),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "cap base horizontal",
        await adapter.add_sketch_constraint(cap_base, None, "horizontal"),
    )
    # Record each display dim into SketchDims as it is emitted (creation
    # order): three on-axis vertical-distance dims -- the tube-mouth station,
    # the sphere-centre station, the apex station (the marked OVERALL-length
    # acceptance dim, see DRAWING_DIMENSIONS).
    await anchor_point_to_origin(
        adapter, f"{cap_base}.start", 0.0, BODY_LENGTH, "cap base on axis"
    )
    cap.record("CapBaseY", '"ColumnLength" - "CapHeight"')
    await anchor_point_to_origin(
        adapter, f"{cap_arc}.center", 0.0, COLUMN_LENGTH - CAP_SPHERE_RADIUS,
        "cap sphere centre",
    )
    cap.record("CapCentreY", '"ColumnLength" - "CapSphereR"')
    await anchor_point_to_origin(
        adapter, f"{cap_arc}.end", 0.0, COLUMN_LENGTH, "cap apex"
    )
    cap.record("CapApexY", '"ColumnLength"')
    await ensure_fully_defined(adapter, "cap sketch")
    check("exit_sketch cap", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += cap.apply(adapter, "CapProfile")
    check(
        "revolve cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Cap")
    # Spherical-cap volume pi*h/6*(3a^2 + h^2); the cap's flat base disc seats
    # exactly on the tube mouth (covering the annulus ring AND the bore
    # opening), so the union adds exactly the cap solid.
    v_cap = (
        math.pi * CAP_HEIGHT / 6.0
        * (3.0 * (OUTER_DIA / 2.0) ** 2 + CAP_HEIGHT**2)
    )
    v_total = v_annulus + v_cap
    await volume_check(adapter, "capped column", v_total, 0.001 * v_total)

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
        adapter, "CapProfile", "CapApexY", COLUMN_LENGTH_TOLERANCE_MM
    )
    await volume_check(adapter, "driven capped column (equations neutral)", v_total, 0.001 * v_total)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)  # ch30 plates: see _common palette

    # Verify the photo-locked OVERALL column height (tube + dome cap) via the
    # solid bounding box (the end faces were screen-projected and collapsed).
    await bbox_extent_check(
        adapter, "column length (capped stub top 1044.8)", "y", COLUMN_LENGTH
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
