r"""Reproduction script: transgear disc hub (MHA-159; ch. 23; 1 used).

The turned brass hub and flange pressed on the pinion sleeve's (MHA-110)
front shank; the flange's rear face seats the 120T disc (MHA-070) and three
#0-80 fillister screws (MHA-161) clamp them (``transgear_disc_hub_spec``,
``transgear_disc_hub_geometry``).

Layout (the spec's frame): Front-plane circles extruded toward -Z.  The
flange runs z = -FLANGE_THICK..0 and the hub body z = -HUB_LENGTH..0 over it,
so ``Front Plane`` (z = 0) is the flange's rear face, the one that seats on
the disc, and the hub body's extrusion depth IS the printed overall length.
The bore and the three screw holes are Front-plane cuts; the screw holes lie
on a construction bolt circle whose driving diameter is the printed Ø16.4.
The radial oil hole is a Top-plane cut toward +Y through one wall, located
by a construction station line from the hub front face.  ``Axis1`` is the
gear axis (Top Plane ∩ Right Plane); the paper-drive assembly mates it to
the sleeve's axis and the Front Plane to the disc's front face, unrotated.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_disc_hub.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    anchor_point_to_origin,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
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
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_X_FACTOR,
    BOLT_CIRCLE_Y_FACTOR,
    screw_centres,
)
from transgear_disc_hub_spec import (
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLANGE_DIA,
    FLANGE_THICK,
    HUB_BODY_LENGTH,
    HUB_DIA,
    HUB_LENGTH,
    OIL_HOLE_DIA,
    OIL_HOLE_STATION,
    OIL_HOLE_Z,
    SCREW_HOLE_DIA,
)

PART_NAME = "transgear-disc-hub"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

FLANGE_R = FLANGE_DIA / 2.0
HUB_R = HUB_DIA / 2.0
BORE_R = BORE_DIA / 2.0
SCREW_HOLE_R = SCREW_HOLE_DIA / 2.0
OIL_HOLE_R = OIL_HOLE_DIA / 2.0


def radial_hole_volume(radius: float, inner: float, outer: float) -> float:
    """Volume a radial drill of ``radius`` removes from a tube wall.

    The hole's cross-section, sliced across the tube's circumference at
    offset ``x`` from the hole axis, is a strip of width 2·√(radius² − x²)
    running from the bore (√(inner² − x²)) to the O.D. (√(outer² − x²));
    midpoint quadrature to well under the volume gate's tolerance.
    """
    steps = 2000
    width = 2.0 * radius / steps
    total = 0.0
    for i in range(steps):
        x = -radius + (i + 0.5) * width
        chord = 2.0 * math.sqrt(radius * radius - x * x)
        wall = math.sqrt(outer * outer - x * x) - math.sqrt(inner * inner - x * x)
        total += chord * wall * width
    return total


V_FLANGE = math.pi * FLANGE_R**2 * FLANGE_THICK
V_HUB_BODY = math.pi * HUB_R**2 * HUB_BODY_LENGTH
V_BORE = math.pi * BORE_R**2 * HUB_LENGTH
V_SCREW_HOLES = len(screw_centres()) * math.pi * SCREW_HOLE_R**2 * FLANGE_THICK
V_OIL_HOLE = radial_hole_volume(OIL_HOLE_R, BORE_R, HUB_R)
V_FINAL = V_FLANGE + V_HUB_BODY - V_BORE - V_SCREW_HOLES - V_OIL_HOLE

# The hub front face in the Top-plane sketch, whose (u, v) is model (X, -Z).
_HUB_FRONT_V = HUB_LENGTH
_OIL_HOLE_V = -OIL_HOLE_Z


def _z_extreme_mm(adapter, sign: float) -> float:
    """The solid's extreme model Z (mm) toward ``sign`` (+1 / -1).

    ``IBody2::GetExtremePoint`` is exact; the early-bound wrapper returns
    (ok, x, y, z) in metres.
    """
    doc = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = adapter._attempt(lambda: doc.GetBodies2(0, False)) or []
    if len(bodies) != 1:
        raise RuntimeError(f"disc hub: expected one solid body, found {len(bodies)}")
    body = _early_bound(bodies[0], "IBody2")
    res = adapter._attempt(lambda: body.GetExtremePoint(0.0, 0.0, sign), default=None)
    if not res or len(res) < 4:
        raise RuntimeError("disc hub: GetExtremePoint failed")
    return float(res[3]) * 1000.0


def _check_z_span(adapter) -> None:
    """The frame's promise: the flange's rear face on z = 0, the hub toward -Z."""
    front, rear = _z_extreme_mm(adapter, -1.0), _z_extreme_mm(adapter, 1.0)
    if abs(rear) > 1e-3 or abs(front + HUB_LENGTH) > 1e-3:
        raise RuntimeError(
            f"disc hub spans z {front:.4f}..{rear:.4f}, not {-HUB_LENGTH:g}..0"
        )


def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch segment construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _front_circle(
    adapter, radius: float, label: str, feature: str, name: str
) -> list[tuple[str, str]]:
    """One on-axis Front-plane circle whose diameter is the ``name`` global."""
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        radius,
        label,
        dims=dims,
        names=(None, None, name),
        drives=(None, None, f'"{name}"'),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, feature)
    return dims.apply(adapter, feature)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("FlangeDia", FLANGE_DIA),
        ("FlangeThick", FLANGE_THICK),
        ("HubDia", HUB_DIA),
        ("HubLength", HUB_LENGTH),
        ("BoreDia", BORE_DIA),
        ("BoltCircleDia", BOLT_CIRCLE_DIA),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("OilHoleStation", OIL_HOLE_STATION),
        ("OilHoleDia", OIL_HOLE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Flange: a Front-plane disc extruded toward -Z (a boss's reverse), so
    # its rear face is the Front Plane.
    drive_jobs += await _front_circle(
        adapter, FLANGE_R, "flange", "FlangeProfile", "FlangeDia"
    )
    check(
        "extrude flange",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FLANGE_THICK, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Flange")
    drive_jobs.append(
        (name_dimensions(adapter, "Flange", ["FlangeThick"])[0], '"FlangeThick"')
    )
    await volume_check(adapter, "flange", V_FLANGE, 0.005 * V_FLANGE)

    # Hub body from the same plane: its depth is the overall length the sheet
    # prints (R9-5); the body's own length is the remainder, never printed.
    drive_jobs += await _front_circle(
        adapter, HUB_R, "hub body", "HubBodyProfile", "HubDia"
    )
    check(
        "extrude hub body",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "HubBody")
    drive_jobs.append(
        (name_dimensions(adapter, "HubBody", ["HubLength"])[0], '"HubLength"')
    )
    await volume_check(
        adapter, "flange + hub body", V_FLANGE + V_HUB_BODY, 0.005 * V_HUB_BODY
    )
    await bbox_extent_check(adapter, "overall length", "z", HUB_LENGTH)
    await bbox_extent_check(adapter, "flange O.D.", "x", FLANGE_DIA)
    _check_z_span(adapter)

    # Pressed bore, through (a cut runs against the sketch normal: -Z).
    drive_jobs += await _front_circle(
        adapter, BORE_R, "hub bore", "BoreProfile", "BoreDia"
    )
    check(
        "cut hub bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=HUB_LENGTH)),
    )
    name_last_feature(adapter, "ThroughBore")
    v_body = V_FLANGE + V_HUB_BODY
    await volume_check(adapter, "hub bore", v_body - V_BORE, 0.01 * V_BORE)

    # Three screw holes through the flange on the shared bolt circle: a
    # construction circle carries the printed diameter; each hole centre is
    # driven from the same global (0 deg on +X, 120 / 240 CCW from +Z).
    holes = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Front"))
    bolt_circle = await define_circle(
        adapter,
        0.0,
        0.0,
        BOLT_CIRCLE_DIA / 2.0,
        "bolt circle",
        dims=holes,
        names=(None, None, "BoltCircleDia"),
        drives=(None, None, '"BoltCircleDia"'),
    )
    _as_construction(adapter, bolt_circle)
    x_drive = f'"BoltCircleDia" * {BOLT_CIRCLE_X_FACTOR!r}'
    y_drive = f'"BoltCircleDia" * {BOLT_CIRCLE_Y_FACTOR!r}'
    for index, (x, y) in enumerate(screw_centres()):
        await define_circle(
            adapter,
            x,
            y,
            SCREW_HOLE_R,
            f"screw hole {index}",
            dims=holes,
            names=(
                f"ScrewHole{index}X",
                f"ScrewHole{index}Y",
                "ScrewHoleDia" if index == 0 else f"ScrewHole{index}Dia",
            ),
            drives=(
                '"BoltCircleDia" / 2' if index == 0 else x_drive,
                y_drive,
                '"ScrewHoleDia"',
            ),
        )
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += holes.apply(adapter, "ScrewHoleProfile")
    # Blind past the flange into open air: the holes stand outside the hub.
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=HUB_LENGTH)),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_body -= V_BORE
    await volume_check(
        adapter, "screw holes", v_body - V_SCREW_HOLES, 0.02 * V_SCREW_HOLES
    )

    # Radial oil hole on +Y, one wall to the bore.  Top-plane sketch (u, v) =
    # model (X, -Z): a construction line on the axis from the hub front face
    # to the hole centre carries the printed station; the circle's centre
    # sits on its end.
    oil = SketchDims()
    check("create_sketch oil hole", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    station = check(
        "oil hole station line",
        await adapter.add_line(0.0, _HUB_FRONT_V, 0.0, _OIL_HOLE_V),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, station)
    check(
        "oil hole station vertical",
        await adapter.add_sketch_constraint(station, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{station}.start", 0.0, _HUB_FRONT_V, "oil hole datum at hub front"
    )
    oil.record("OilHoleDatum", '"HubLength"')
    await dimension_between(
        adapter,
        f"{station}.start",
        f"{station}.end",
        "vertical_distance",
        OIL_HOLE_STATION,
        "oil hole station from the hub front face",
    )
    oil.record("OilHoleStation", '"OilHoleStation"')
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = check(
            "oil hole circle", await adapter.add_circle(0.0, _OIL_HOLE_V, OIL_HOLE_R)
        )
    finally:
        sketch_mgr.AddToDB = prev_add_to_db
    check(
        "oil hole centre on the station",
        await adapter.add_sketch_constraint(
            f"{circle}.center", f"{station}.end", "coincident"
        ),
    )
    check(
        "oil hole diameter",
        await adapter.add_sketch_dimension(circle, None, "diameter", OIL_HOLE_DIA),
    )
    oil.record("OilHoleDia", '"OilHoleDia"')
    await ensure_fully_defined(adapter, "oil hole sketch")
    check("exit_sketch oil hole", await adapter.exit_sketch())
    name_last_feature(adapter, "OilHoleProfile")
    drive_jobs += oil.apply(adapter, "OilHoleProfile")
    # Reversed cut from the Top plane runs +Y: the +Y wall only.
    check(
        "cut oil hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HUB_DIA, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "OilHole")
    drive_jobs.append(
        (name_dimensions(adapter, "OilHole", ["OilHoleDepth"])[0], '"HubDia"')
    )
    await volume_check(adapter, "oil hole", V_FINAL, 0.05 * V_OIL_HOLE)

    # The mate axis: the first reference axis, so it is Axis1.
    axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "gear axis"
    )
    if axis != "Axis1":
        raise RuntimeError(f"gear axis came back {axis!r}, not Axis1")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven disc hub (equations neutral)", V_FINAL, 0.05 * V_OIL_HOLE
    )
    _check_z_span(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # No model band: every printed size is governed by its places, the holes
    # by the title block's DRILLED HOLES row (the spec's DRAWING_PRECISION).
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    # The cut sketches are absorbed (hidden) by their features; the drawing
    # imports their dimensions through those features.
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
