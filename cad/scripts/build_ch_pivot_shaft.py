r"""Reproduction script: rocker pivot shaft (MHA-CH-005; book ch. 14 / ch. 17; 1 used).

The Ø6.35 steel shaft that carries the 20 rocker arms at machine
(x, y) = (72.9, 253.8), held by the two pivot brackets and preloaded north by
the MHA-VN-053 spring (#948 ruling R, PR #1292). It is a PLAIN rod: rocker
19's hub bears through a MHA-CH-009 thrust washer on the north ear's inner
face, and the spring pushes on a second washer at hub 0's south face from the
south ear (``rocker_bank_layout``). The
cylinder spans both ears' outer faces and each end is domed 1.5 proud, like
the cylinder arbor's ends (ch14 page002_img07 shows the near-flush domed end
on the ear). One MHA-VN-034 #4-40 cup-point set screw drops through each
ear's apex onto a flat milled under it; both flats face +Y, in line.

Layout: axis along Z with the origin on the axis at the NORTH end of the
cylinder; the body runs toward -Z. The body is ONE Right-plane half-profile
(a plain rectangle) revolved (sketch +u -> model -Z, +v -> model Y), so the
diameter and length import into the side view (policy rule 7, the
crank-pinion boss idiom). Each dome is its own revolved cap (the
pinion-pivot-shaft crown idiom), sketched on the same plane. Both flats are
ONE Right-plane cut (``FlatProfile``, the cone-gear-shaft flat idiom turned
into the side view), so their length, across-flat and stations import there
too.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_pivot_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    dimension_between,
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
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from ch_pivot_shaft_spec import (
    DOME_HEIGHT,
    DOME_SPHERE_RADIUS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLAT_AF,
    FLAT_DEPTH,
    FLAT_LENGTH,
    ISOMETRIC_VIEW_NOTE,
    NORTH_FLAT_STATION,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SURFACE_FINISHES,
    V_DOME,
    V_FLAT,
)
from rocker_bank_layout import PIVOT_SHAFT_FLAT_STATIONS, PIVOT_SHAFT_LENGTH

PART_NAME = "ch-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_R = SHAFT_DIA / 2.0
SHAFT_LENGTH = PIVOT_SHAFT_LENGTH  # the cylinder: the span over both ears (REF)
V_BODY = math.pi * SHAFT_R**2 * SHAFT_LENGTH
# Each flat's centre from the north end: the south one is driven off the
# length (ShaftLength - NorthFlatStation), which must be the layout's station.
FLAT_STATIONS = (SHAFT_LENGTH - NORTH_FLAT_STATION, NORTH_FLAT_STATION)
if any(
    abs(built - laid) > 1e-6
    for built, laid in zip(FLAT_STATIONS, PIVOT_SHAFT_FLAT_STATIONS, strict=True)
):
    raise AssertionError(
        f"flat stations {FLAT_STATIONS} != layout {PIVOT_SHAFT_FLAT_STATIONS}"
    )


async def _shaft_profile(adapter) -> list[tuple[str, str]]:
    """The plain half-profile, revolved into the body. The printed length
    and diameter are its driving dimensions."""
    from solidworks_mcp.adapters.base import RevolveParameters

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
    body = lines[1]
    await dimension_between(
        adapter,
        f"{body}.start",
        f"{body}.end",
        "horizontal_distance",
        SHAFT_LENGTH,
        "shaft ShaftLength",
    )
    dims.record("ShaftLength", '"ShaftLength"')
    await add_diametric_linear_dimension(
        adapter, axis, body, (SHAFT_LENGTH / 2.0, SHAFT_R + 5.0), "ShaftDia"
    )
    dims.record("ShaftDia", '"ShaftDia"')
    await anchor_point_to_origin(adapter, f"{lines[0]}.start", 0.0, 0.0, "shaft anchor")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs = dims.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")
    return drive_jobs


def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch line construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _flats(adapter) -> list[tuple[str, str]]:
    """Both set-screw flats: ONE cut from two rectangles on the Right plane
    (the build_dt_cone_gear_shaft flat idiom, sketched in the side view so
    every flat dimension imports there). Each rectangle's inner edge is its
    flat, at v = SHAFT_R - FLAT_DEPTH (model +Y), its other three edges 1 mm
    clear of the rod; a construction line from the rod's far side (v =
    -SHAFT_R) to the flat's midpoint has the across-flat ``FlatAF`` as its
    length, and its end's distance from the origin along the axis is the
    flat's station from the north end. A mid-plane cut 1 mm past the rod each
    side of the Right plane takes the whole segment."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    offset = SHAFT_R - FLAT_DEPTH
    reach = SHAFT_R + 1.0
    dims = SketchDims()
    check("create_sketch flats", await adapter.create_sketch("Right"))
    drawn = []
    for tag, station in zip(("South", "North"), FLAT_STATIONS, strict=True):
        u0, u1 = station - FLAT_LENGTH / 2.0, station + FLAT_LENGTH / 2.0
        flat, end, top, start = await add_line_chain(
            adapter, [(u0, offset), (u1, offset), (u1, reach), (u0, reach)]
        )
        for edge, direction in (
            (flat, "horizontal"),
            (end, "vertical"),
            (top, "horizontal"),
            (start, "vertical"),
        ):
            check(
                f"{tag} flat {direction} {edge}",
                await adapter.add_sketch_constraint(edge, None, direction),
            )
        (across,) = await add_line_chain(
            adapter, [(station, -SHAFT_R), (station, offset)], close=False
        )
        _as_construction(adapter, across)
        check(
            f"{tag} flat across-flat vertical",
            await adapter.add_sketch_constraint(across, None, "vertical"),
        )
        check(
            f"{tag} flat across-flat meets the flat",
            await adapter.add_sketch_constraint(f"{across}.end", flat, "midpoint"),
        )
        drawn.append((tag, flat, end, across))
    for tag, flat, end, across in drawn:
        north = tag == "North"
        await dimension_between(
            adapter,
            f"{flat}.start",
            f"{flat}.end",
            "horizontal_distance",
            FLAT_LENGTH,
            f"{tag} flat length",
        )
        dims.record("FlatLength" if north else "SouthFlatLength", '"FlatLength"')
        await dimension_between(
            adapter,
            f"{end}.start",
            f"{end}.end",
            "vertical_distance",
            reach - offset,
            f"{tag} flat reach",
        )
        dims.record(f"{tag}FlatReach")
        await dimension_between(
            adapter,
            f"{across}.start",
            "origin",
            "vertical_distance",
            SHAFT_R,
            f"{tag} flat far side",
        )
        dims.record(f"{tag}FarSide", '"ShaftDia" / 2')
        await dimension_between(
            adapter,
            f"{across}.start",
            f"{across}.end",
            "vertical_distance",
            FLAT_AF,
            f"{tag} flat across flat",
        )
        dims.record("FlatAF" if north else "SouthFlatAF", '"FlatAF"')
        await dimension_between(
            adapter,
            f"{across}.end",
            "origin",
            "horizontal_distance",
            NORTH_FLAT_STATION if north else SHAFT_LENGTH - NORTH_FLAT_STATION,
            f"{tag} flat station",
        )
        dims.record(
            f"{tag}FlatStation",
            '"NorthFlatStation"' if north else '"ShaftLength" - "NorthFlatStation"',
        )
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    drive_jobs = dims.apply(adapter, "FlatProfile")
    check(
        "cut flats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * reach, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Flats")
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
    await set_global(adapter, "DomeHeight", f"{DOME_HEIGHT}mm")
    await set_global(adapter, "FlatLength", f"{FLAT_LENGTH}mm")
    await set_global(adapter, "FlatAF", f"{FLAT_AF}mm")
    await set_global(adapter, "NorthFlatStation", f"{NORTH_FLAT_STATION}mm")

    drive_jobs = await _shaft_profile(adapter)
    volume = await volume_check(adapter, "shaft", V_BODY, 0.005 * V_BODY)
    drive_jobs += await _dome(adapter, "North", 0.0, -1.0)
    volume = await volume_check(adapter, "north dome", volume + V_DOME, 0.03 * V_DOME)
    drive_jobs += await _dome(adapter, "South", SHAFT_LENGTH, 1.0)
    volume = await volume_check(adapter, "south dome", volume + V_DOME, 0.03 * V_DOME)
    drive_jobs += await _flats(adapter)
    volume = await volume_check(
        adapter, "set-screw flats", volume - 2.0 * V_FLAT, 0.05 * V_FLAT
    )

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
