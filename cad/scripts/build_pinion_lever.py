r"""Reproduction script: pinion engage lever (book ch. 25).

The tapered rod that turns the lift rod (build_pinion_lift_rod.py) to
swing the pinion into mesh: a cylindrical HUB at the root seats over
the lift rod's front end (p.69 ``page002_img07``: a short fat cylinder
with a slightly domed south cap -- NOT a ball, PR7 review item), the
rod reaches up-and-out with a visible taper (Ø4 at the root growing
to ~Ø6 at the tip; the 86 length and taper both re-derived from img07
against the annotated 6 mm rod). Standing up = disengaged, folded flat
= engaged; the model carries the DISENGAGED rest pose.

Layout: hub axis Z centred at the origin (z -5..+5), BLIND bore Ø6.35
from the +Z face down to z -3 (2 wall behind), domed cap (sagitta 1.5)
proud of the -Z face -- the lift rod's front end hides inside. Rod: a
frustum revolved about +Y from y RodY0 (buried in the hub) to 86,
radius 3 -> 2. Revolve LAST (nothing later crosses its axis -- the
on-axis-revolve pitfall's safe case).

Volume gate (mm^3): annulus + wall disc + cap (spherical-cap formula)
+ frustum - frustum/hub-OD overlap (Simpson over circular segments).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
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
from _saved_part_guard import require_saved_drawing_properties
from pinion_lever_spec import (
    BORE,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    HUB_LEN,
    HUB_OD,
    ISOMETRIC_VIEW_NOTE,
    ROD_LEN,
    ROD_ROOT_DIA,
    ROD_TIP_DIA,
    ROD_Y0,
    WALL_T,
)

PART_NAME = "pinion-lever"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

ROD_ROOT_R = ROD_ROOT_DIA / 2.0
ROD_TIP_R = ROD_TIP_DIA / 2.0
HUB_R = HUB_OD / 2.0
BORE_R = BORE / 2.0
CAP_R = (HUB_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 14.83 crown sphere radius

V_ANNULUS = math.pi * (HUB_R**2 - BORE_R**2) * (HUB_LEN - WALL_T)
V_WALL = math.pi * HUB_R**2 * WALL_T
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 101.3
_H = ROD_LEN - ROD_Y0
V_FRUSTUM = (
    math.pi / 3.0 * _H
    * (ROD_ROOT_R**2 + ROD_ROOT_R * ROD_TIP_R + ROD_TIP_R**2)
)


def _rod_r(y: float) -> float:
    return ROD_ROOT_R - (ROD_ROOT_R - ROD_TIP_R) * (y - ROD_Y0) / _H


def _hub_overlap() -> float:
    """Frustum volume already inside the hub OD cylinder: Simpson over
    y in [ROD_Y0, HUB_R] of the disc-segment area |x| <= sqrt(HUB_R^2-y^2)
    on the rod's section disc (the rod's z-extent stays inside the hub)."""
    n = 2000
    y0, y1 = ROD_Y0, HUB_R
    h = (y1 - y0) / n

    def area(y: float) -> float:
        r = _rod_r(y)
        c = math.sqrt(max(HUB_R**2 - y * y, 0.0))
        if c >= r:
            return math.pi * r * r
        return 2.0 * (c * math.sqrt(r * r - c * c) + r * r * math.asin(c / r))

    total = area(y0) + area(y1)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * area(y0 + i * h)
    return total * h / 3.0


V_TOTAL = V_ANNULUS + V_WALL + V_CAP + V_FRUSTUM - _hub_overlap()


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document). HubLen/WallT feed extrude DEPTHS (feature parameters).
    await set_global(adapter, "RodRootDia", f"{ROD_ROOT_DIA}mm")
    await set_global(adapter, "RodTipDia", f"{ROD_TIP_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "RodY0", f"{ROD_Y0}mm")
    await set_global(adapter, "HubOd", f"{HUB_OD}mm")
    await set_global(adapter, "HubLen", f"{HUB_LEN}mm")
    await set_global(adapter, "Bore", f"{BORE}mm")
    await set_global(adapter, "WallT", f"{WALL_T}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bored hub barrel: annulus (OD + bore, both origin-centred) from the
    # blind wall's north face up the +Z length.
    barrel = SketchDims()
    check("create_sketch barrel", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_R, "hub OD", dims=barrel,
        names=("HubOdCx", "HubOdCz", "HubOd"),
        drives=(None, None, '"HubOd"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, BORE_R, "hub bore", dims=barrel,
        names=("HubBoreCx", "HubBoreCz", "HubBore"),
        drives=(None, None, '"Bore"'),
    )
    await ensure_fully_defined(adapter, "barrel sketch")
    check("exit_sketch barrel", await adapter.exit_sketch())
    name_last_feature(adapter, "BarrelProfile")
    drive_jobs += barrel.apply(adapter, "BarrelProfile")
    extrude_at_offset(adapter, HUB_LEN - WALL_T, -HUB_LEN / 2.0 + WALL_T)
    name_last_feature(adapter, "Barrel")
    drive_jobs += [
        (
            name_dimensions(adapter, "Barrel", ["BoreDepth"])[0],
            '"HubLen" - "WallT"',
        )
    ]
    expected = V_ANNULUS
    await volume_check(adapter, "barrel", expected, 0.005 * V_ANNULUS)

    # Blind wall disc at the south end (z -5..-3).
    wall = SketchDims()
    check("create_sketch wall", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_R, "wall", dims=wall,
        names=("WallCx", "WallCz", "WallDia"),
        drives=(None, None, '"HubOd"'),
    )
    await ensure_fully_defined(adapter, "wall sketch")
    check("exit_sketch wall", await adapter.exit_sketch())
    name_last_feature(adapter, "WallProfile")
    drive_jobs += wall.apply(adapter, "WallProfile")
    extrude_at_offset(adapter, WALL_T, -HUB_LEN / 2.0)
    name_last_feature(adapter, "Wall")
    drive_jobs += [
        (name_dimensions(adapter, "Wall", ["EndWall"])[0], '"WallT"')
    ]
    expected += V_WALL
    await volume_check(adapter, "wall", expected, 0.005 * V_WALL)

    # Domed south cap (sagitta CAP_SAG proud of z -5): Top-plane rim->apex
    # arc revolved about Z -- the pivot-shaft front-cap idiom (apex at the
    # more-positive sketch v, rim -> apex is the minor CCW lobe).
    v_base = HUB_LEN / 2.0  # sketch v = -z: the -Z face
    v_apex = HUB_LEN / 2.0 + CAP_SAG
    v_centre = HUB_LEN / 2.0 + CAP_SAG - CAP_R
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("cap centerline", await adapter.add_centerline(0.0, v_base, 0.0, v_apex))
    base = check("cap base", await adapter.add_line(0.0, v_base, HUB_R, v_base))
    arc = check(
        "cap arc",
        await adapter.add_arc(0.0, v_centre, HUB_R, v_base, 0.0, v_apex),
    )
    close = check("cap close", await adapter.add_line(0.0, v_apex, 0.0, v_base))
    set_sketch_direct_db(adapter, False)
    check("cap base horizontal", await adapter.add_sketch_constraint(base, None, "horizontal"))
    check("cap close vertical", await adapter.add_sketch_constraint(close, None, "vertical"))
    check(
        "cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "horizontal_distance", HUB_R
        ),
    )
    cap.record("CapRim", '"HubOd" / 2')
    check(
        "cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "cap on axis",
        await adapter.add_sketch_constraint(f"{base}.start", "origin", "vertical_points"),
    )
    check(
        "cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "vertical_distance", v_base
        ),
    )
    cap.record("CapZ", '"HubLen" / 2')
    check(
        "cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("HubOd" / 2 * "HubOd" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "cap sketch")
    check("exit_sketch cap", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += cap.apply(adapter, "CapProfile")
    check("revolve cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cap")
    expected += V_CAP
    await volume_check(adapter, "cap", expected, 0.03 * V_CAP)

    # Tapered grip rod LAST: frustum profile on the Front plane revolved
    # about +Y (centerline on the axis; nothing later crosses it).
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "rod centerline",
        await adapter.add_centerline(0.0, ROD_Y0, 0.0, ROD_LEN),
    )
    pts = [
        (0.0, ROD_Y0),
        (ROD_ROOT_R, ROD_Y0),
        (ROD_TIP_R, ROD_LEN),
        (0.0, ROD_LEN),
        (0.0, ROD_Y0),
    ]
    lines = await add_line_chain(adapter, pts, close=False)
    set_sketch_direct_db(adapter, False)
    r_base, flank, r_top, axis_edge = lines
    check("rod base horizontal", await adapter.add_sketch_constraint(r_base, None, "horizontal"))
    check("rod top horizontal", await adapter.add_sketch_constraint(r_top, None, "horizontal"))
    check("rod axis vertical", await adapter.add_sketch_constraint(axis_edge, None, "vertical"))
    check(
        "rod base on axis",
        await adapter.add_sketch_constraint(f"{r_base}.start", "origin", "vertical_points"),
    )
    check(
        "rod base height",
        await adapter.add_sketch_dimension(
            f"{r_base}.start", "origin", "vertical_distance", ROD_Y0
        ),
    )
    rod.record("RodBaseY", '"RodY0"')
    check(
        "rod root radius",
        await adapter.add_sketch_dimension(r_base, None, "linear", ROD_ROOT_R),
    )
    rod.record("RodRootR", '"RodRootDia" / 2')
    check(
        "rod tip radius",
        await adapter.add_sketch_dimension(r_top, None, "linear", ROD_TIP_R),
    )
    rod.record("RodTipR", '"RodTipDia" / 2')
    check(
        "rod length",
        await adapter.add_sketch_dimension(
            f"{r_top}.end", "origin", "vertical_distance", ROD_LEN
        ),
    )
    rod.record("RodTipY", '"RodLen"')
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += rod.apply(adapter, "RodProfile")
    check("revolve rod", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Rod")
    await volume_check(adapter, "lever", V_TOTAL, 0.01 * V_FRUSTUM)

    # Named hub-bore axis (Axis1): the assembly clamps the lever coaxial on
    # the lift rod (PR8 -- it spins with the rod to drive the cams).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "hub bore")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven lever (equations neutral)", V_TOTAL, 0.01 * V_FRUSTUM)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
