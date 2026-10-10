r"""Reproduction script: rocker pivot shaft (MHA-CH-005; book ch. 14 / ch. 17; 1 used).

The Ø6.35 steel shaft that carries the 20 rocker arms at machine
(x, y) = (72.9, 253.8), held by the two pivot brackets and preloaded north by
the MHA-VN-053 spring (#948 ruling R, PR #1292). It is turned from O10 bar and keeps an integral
O10 x 1.5 shoulder one ear thickness from its north end. The shoulder bears
on the north ear's inner face, and rocker 19's hub bears on the shoulder;
the spring holds the stack north off the MHA-CH-009 washer at the south ear
(``rocker_bank_layout``). The cylinder spans both ears' outer faces and each
end is domed 1.5 proud, like the cylinder arbor's ends (ch14 page002_img07
shows the near-flush domed end on the ear).

Layout: axis along Z with the origin on the axis at the NORTH (shouldered)
end of the cylinder; the body runs toward -Z. The stepped body is ONE
Right-plane half-profile revolved (sketch +u -> model -Z, +v -> model Y), so
every turned diameter and length imports into the side view (policy rule 7,
the crank-pinion boss idiom). Each dome is its own revolved cap (the
pinion-pivot-shaft crown idiom), sketched on the same plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_shaft.py
"""

from __future__ import annotations

import math
import sys

from _appearance import POLISHED_STEEL, apply_color, apply_material
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_deviations import deviations
from _part_pmi import author_part_pmi
from ch_pivot_shaft_spec import (
    DOME_HEIGHT,
    DOME_SPHERE_RADIUS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    JOURNAL_LENGTH,
    RELIEF_DIA,
    RELIEF_WIDTH,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHOULDER_DIA,
    SHOULDER_LENGTH,
    SURFACE_FINISHES,
    V_DOME,
)
from rocker_bank_layout import PIVOT_SHAFT_LENGTH

PART_NAME = "ch-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # see _appearance.apply_material docstring

SHAFT_R = SHAFT_DIA / 2.0
SHOULDER_R = SHOULDER_DIA / 2.0
SHAFT_LENGTH = PIVOT_SHAFT_LENGTH  # the cylinder: the span over both ears (REF)
V_BODY = math.pi * (
    SHAFT_R**2 * (SHAFT_LENGTH - SHOULDER_LENGTH) + SHOULDER_R**2 * SHOULDER_LENGTH
)
RELIEF_R = RELIEF_DIA / 2.0
# Two grooves, each RELIEF_WIDTH long, from the O.D. down to the relief
# diameter (the cut rises to the shoulder O.D., through air).
V_RELIEFS = 2.0 * math.pi * (SHAFT_R**2 - RELIEF_R**2) * RELIEF_WIDTH
if SHAFT_LENGTH <= JOURNAL_LENGTH + SHOULDER_LENGTH:
    raise AssertionError(
        "the pivot shaft's body is shorter than its journal and shoulder"
    )


async def _shaft_profile(adapter) -> list[tuple[str, str]]:
    """The stepped half-profile, revolved into the body. Every printed
    length and diameter is one of its driving dimensions."""
    from solidworks_mcp.adapters.base import RevolveParameters

    journal_end = JOURNAL_LENGTH
    shoulder_end = JOURNAL_LENGTH + SHOULDER_LENGTH
    dims = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "shaft axis centerline",
        await adapter.add_centerline(0.0, 0.0, SHAFT_LENGTH, 0.0),
    )
    points = [
        (0.0, 0.0),
        (0.0, SHAFT_R),
        (journal_end, SHAFT_R),
        (journal_end, SHOULDER_R),
        (shoulder_end, SHOULDER_R),
        (shoulder_end, SHAFT_R),
        (SHAFT_LENGTH, SHAFT_R),
        (SHAFT_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    n = len(lines)
    for i, line in enumerate(lines):
        (_, v1), (_, v2) = points[i], points[(i + 1) % n]
        direction = "horizontal" if v1 == v2 else "vertical"
        check(
            f"shaft {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    journal, shoulder, body = lines[1], lines[3], lines[5]
    # The journal and the body are one O.D.: their outlines share a height.
    check(
        "journal on the body O.D.",
        await adapter.add_sketch_constraint(
            f"{journal}.start", f"{body}.end", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{journal}.start",
        f"{body}.end",
        "horizontal_distance",
        SHAFT_LENGTH,
        "shaft ShaftLength",
    )
    dims.record("ShaftLength", '"ShaftLength"')
    await dimension_between(
        adapter,
        f"{journal}.start",
        f"{journal}.end",
        "horizontal_distance",
        JOURNAL_LENGTH,
        "shaft JournalLength",
    )
    dims.record("JournalLength", '"JournalLength"')
    await dimension_between(
        adapter,
        f"{shoulder}.start",
        f"{shoulder}.end",
        "horizontal_distance",
        SHOULDER_LENGTH,
        "shaft ShoulderLength",
    )
    dims.record("ShoulderLength", '"ShoulderLength"')
    await add_diametric_linear_dimension(
        adapter, axis, body, (SHAFT_LENGTH / 2.0, SHAFT_R + 5.0), "ShaftDia"
    )
    dims.record("ShaftDia", '"ShaftDia"')
    await add_diametric_linear_dimension(
        adapter, axis, shoulder, (shoulder_end, SHOULDER_R + 5.0), "ShoulderDia"
    )
    dims.record("ShoulderDia", '"ShoulderDia"')
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", 0.0, 0.0, "shaft anchor")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs = dims.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")
    return drive_jobs


async def _reliefs(adapter) -> list[tuple[str, str]]:
    """The two shoulder reliefs: one revolved cut from two rectangles on the
    Right plane, each flush against a shoulder face. Its own feature, so the
    sheet imports its dimensions into the enlarged detail alone."""
    from solidworks_mcp.adapters.base import RevolveParameters

    north_face = JOURNAL_LENGTH
    south_face = JOURNAL_LENGTH + SHOULDER_LENGTH
    dims = SketchDims()
    check("create_sketch relief", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    north_points = [
        (north_face - RELIEF_WIDTH, RELIEF_R),
        (north_face, RELIEF_R),
        (north_face, SHOULDER_R),
        (north_face - RELIEF_WIDTH, SHOULDER_R),
    ]
    south_points = [
        (south_face, RELIEF_R),
        (south_face + RELIEF_WIDTH, RELIEF_R),
        (south_face + RELIEF_WIDTH, SHOULDER_R),
        (south_face, SHOULDER_R),
    ]
    north = await add_line_chain(adapter, north_points)
    south = await add_line_chain(adapter, south_points)
    axis = check(
        "relief axis centerline",
        await adapter.add_centerline(0.0, 0.0, north_face - RELIEF_WIDTH, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    for tag, lines in (("north", north), ("south", south)):
        for i, line in enumerate(lines):
            direction = "horizontal" if i % 2 == 0 else "vertical"
            check(
                f"relief {tag} {direction} {line}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
    # The axis: from the origin, level, ending under the north groove's
    # outer wall (the diameter dimension's reference).
    check(
        "relief axis at the origin",
        await adapter.add_sketch_constraint(f"{axis}.start", "origin", "coincident"),
    )
    check(
        "relief axis level",
        await adapter.add_sketch_constraint(axis, None, "horizontal"),
    )
    check(
        "relief axis end under the north groove",
        await adapter.add_sketch_constraint(
            f"{axis}.end", f"{north[0]}.start", "vertical_points"
        ),
    )
    # One bottom and one top line for both grooves.
    check(
        "relief bottoms level",
        await adapter.add_sketch_constraint(
            f"{south[0]}.start", f"{north[0]}.start", "horizontal_points"
        ),
    )
    check(
        "relief tops level",
        await adapter.add_sketch_constraint(
            f"{south[2]}.start", f"{north[2]}.start", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{north[0]}.start",
        f"{north[0]}.end",
        "horizontal_distance",
        RELIEF_WIDTH,
        "relief ReliefWidth",
    )
    dims.record("ReliefWidth", '"ReliefWidth"')
    await dimension_between(
        adapter,
        f"{north[0]}.end",
        "origin",
        "horizontal_distance",
        north_face,
        "relief north station",
    )
    dims.record("NorthStation", '"JournalLength"')
    await dimension_between(
        adapter,
        f"{north[1]}.start",
        f"{north[1]}.end",
        "vertical_distance",
        SHOULDER_R - RELIEF_R,
        "relief rise",
    )
    dims.record("Rise", '("ShoulderDia" - "ReliefDia") / 2')
    await add_diametric_linear_dimension(
        adapter, axis, north[0], (north_face - RELIEF_WIDTH / 2.0, -5.0), "ReliefDia"
    )
    dims.record("ReliefDia", '"ReliefDia"')
    await dimension_between(
        adapter,
        f"{south[0]}.start",
        f"{south[0]}.end",
        "horizontal_distance",
        RELIEF_WIDTH,
        "relief south width",
    )
    dims.record("SouthWidth", '"ReliefWidth"')
    await dimension_between(
        adapter,
        f"{south[0]}.start",
        "origin",
        "horizontal_distance",
        south_face,
        "relief south station",
    )
    dims.record("SouthStation", '"JournalLength" + "ShoulderLength"')
    await ensure_fully_defined(adapter, "relief sketch")
    check("exit_sketch relief", await adapter.exit_sketch())
    name_last_feature(adapter, "ReliefProfile")
    drive_jobs = dims.apply(adapter, "ReliefProfile")
    check(
        "revolve reliefs",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "Relief")
    return drive_jobs


async def _dome(adapter, tag: str, u_end: float, sign: float) -> list[tuple[str, str]]:
    """One spherical crown DOME_HEIGHT proud of the end face at sketch
    ``u_end`` (``sign`` -1 north, the crown toward -u; +1 south): radial base
    line on the end face, arc from the rim to the on-axis apex, on-axis close
    line doubling as the revolve axis edge. Constraint accounting as in
    build_dt_pinion_pivot_shaft's caps, on this plane's axes: base vertical +
    close horizontal (directions), rim reach (radius), height (apex), one
    station anchor (origin-coincident at the north end, a driven distance at
    the south end), arc radius (the outward lobe as drawn; the volume gate
    arbitrates it)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    u_apex = u_end + sign * DOME_HEIGHT
    u_centre = u_end - sign * (DOME_SPHERE_RADIUS - DOME_HEIGHT)
    name = f"{tag}CapProfile"
    dims = SketchDims()
    check(f"create_sketch {name}", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check(
        f"{name} centerline",
        await adapter.add_centerline(u_end, 0.0, u_apex, 0.0),
    )
    base = check(f"{name} base", await adapter.add_line(u_end, 0.0, u_end, SHAFT_R))
    # add_arc sweeps CCW p1 -> p2: the outward lobe runs rim -> apex at the
    # north end (crown toward -u) and apex -> rim at the south end.
    rim, apex = (u_end, SHAFT_R), (u_apex, 0.0)
    p1, p2 = (rim, apex) if sign < 0 else (apex, rim)
    arc = check(
        f"{name} arc",
        await adapter.add_arc(u_centre, 0.0, p1[0], p1[1], p2[0], p2[1]),
    )
    close = check(f"{name} close", await adapter.add_line(u_apex, 0.0, u_end, 0.0))
    set_sketch_direct_db(adapter, False)
    check(
        f"{name} base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    check(
        f"{name} close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{base}.end", "origin", "vertical_distance", SHAFT_R, f"{name} rim"
    )
    dims.record("Rim", '"ShaftDia" / 2')
    await dimension_between(
        adapter,
        f"{close}.start",
        f"{close}.end",
        "horizontal_distance",
        DOME_HEIGHT,
        f"{name} height",
    )
    dims.record("DomeHeight" if sign < 0 else "SouthDomeHeight", '"DomeHeight"')
    if u_end:
        check(
            f"{name} on axis",
            await adapter.add_sketch_constraint(
                f"{base}.start", "origin", "horizontal_points"
            ),
        )
        await dimension_between(
            adapter,
            f"{base}.start",
            "origin",
            "horizontal_distance",
            u_end,
            f"{name} station",
        )
        dims.record("Station", '"ShaftLength"')
    else:
        check(
            f"{name} station",
            await adapter.add_sketch_constraint(
                f"{base}.start", "origin", "coincident"
            ),
        )
    check(
        f"{name} radius",
        await adapter.add_sketch_dimension(arc, None, "radial", DOME_SPHERE_RADIUS),
    )
    dims.record(
        "Radius",
        '("ShaftDia" / 2 * "ShaftDia" / 2 + "DomeHeight" * "DomeHeight") / (2 * "DomeHeight")',
    )
    await ensure_fully_defined(adapter, f"{name} sketch")
    check(f"exit_sketch {name}", await adapter.exit_sketch())
    name_last_feature(adapter, name)
    drive_jobs = dims.apply(adapter, name)
    check(
        f"revolve {tag} cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, f"{tag}Cap")
    return drive_jobs


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 156.6 = 156.6 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "ShoulderDia", f"{SHOULDER_DIA}mm")
    await set_global(adapter, "ShoulderLength", f"{SHOULDER_LENGTH}mm")
    await set_global(adapter, "JournalLength", f"{JOURNAL_LENGTH}mm")
    await set_global(adapter, "DomeHeight", f"{DOME_HEIGHT}mm")
    await set_global(adapter, "ReliefWidth", f"{RELIEF_WIDTH}mm")
    await set_global(adapter, "ReliefDia", f"{RELIEF_DIA}mm")

    drive_jobs = await _shaft_profile(adapter)
    volume = await volume_check(adapter, "shaft", V_BODY, 0.005 * V_BODY)
    drive_jobs += await _reliefs(adapter)
    volume = await volume_check(
        adapter, "shoulder reliefs", volume - V_RELIEFS, 0.05 * V_RELIEFS
    )
    drive_jobs += await _dome(adapter, "North", 0.0, -1.0)
    volume = await volume_check(adapter, "north dome", volume + V_DOME, 0.03 * V_DOME)
    drive_jobs += await _dome(adapter, "South", SHAFT_LENGTH, 1.0)
    volume = await volume_check(adapter, "south dome", volume + V_DOME, 0.03 * V_DOME)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shaft (equations neutral)", volume, 0.005 * volume
    )

    # The rockers ride this axis by name.  A point on the O.D. is a
    # view-dependent pick that grazes the silhouette in the standard views,
    # where the rocker and ear bores' edges sit 0.075 mm off it (#916).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "shaft axis")
    name_last_feature(adapter, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDia", *deviations(SHAFT_DIA_BAND)
    )
    # Decimal places belong to the model dimension, not to the sheet.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The running faces' roughness lives on the MODEL as plain annotations.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
