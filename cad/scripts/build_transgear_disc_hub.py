r"""Reproduction script: transgear disc hub (MHA-159; ch. 23; 1 used).

The turned brass hub and flange whose bore slides on the pinion sleeve's
(MHA-110) Ø9 boss and drives through its D-flat.  Its rear spigot passes the
120T disc's (MHA-070) bore, which pilots on it, and seats on the sleeve's
step; the flange's rear face clamps the disc's front face and three #0-80
fillister screws (MHA-161) hold them.  Nothing fastens the hub to the
sleeve: the spigot bears on the step and the MHA-181 front bushing traps hub
and disc forward; the D-flat drives (``transgear_disc_hub_spec``,
``transgear_disc_hub_geometry``).

Layout (the spec's frame): the spigot, flange and hub body are one turned
profile on the Top plane, (u, v) = model (X, -Z), revolved about the gear
axis, so the sheet's edge view carries all three turned diameters (policy
rule 7).  The spigot runs z = 0..SPIGOT_LENGTH, the flange
z = -FLANGE_THICK..0 and the hub body forward to the hub front face, so
``Front Plane`` (z = 0) is the flange's rear face, the one that clamps the
disc, and the spigot's and flange's printed lengths run from it.  The
overall, spigot end to hub front face, is the cluster fit's model length
(the hub front face is faced to the sleeve's nose at assembly).  The bore
is two Front-plane cuts: the D-bore (its flat on local -Y) forward through
flange and body, and the round bore back through the spigot.  The three
screw holes lie on a construction bolt circle whose driving diameter is the
printed Ø19.  The radial oil hole is a Top-plane cut toward +Y through one
wall, centred on the hub body by a construction station line from the hub
front face (R9-60).  ``Axis1`` is the gear axis (Top Plane ∩ Right Plane);
the paper-drive assembly mates it to the sleeve's axis and the Front Plane
to the disc's front face, unrotated.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_disc_hub.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
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
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_X_FACTOR,
    BOLT_CIRCLE_Y_FACTOR,
    screw_centres,
)
from transgear_disc_hub_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLANGE_DIA,
    FLANGE_THICK,
    FLAT_TO_AXIS,
    FLAT_TO_AXIS_DEVIATIONS,
    HUB_BODY_LENGTH,
    HUB_DIA,
    HUB_FRONT_Z,
    HUB_LENGTH,
    OIL_HOLE_DIA,
    OIL_HOLE_STATION,
    SCREW_HOLE_DIA,
    SPIGOT_DIA,
    SPIGOT_DIA_DEVIATIONS,
    SPIGOT_LENGTH,
)

PART_NAME = "transgear-disc-hub"
MATERIAL = "Brass"  # C36000 free-machining brass (the registry row names it)

FLANGE_R = FLANGE_DIA / 2.0
HUB_R = HUB_DIA / 2.0
BORE_R = BORE_DIA / 2.0
SPIGOT_R = SPIGOT_DIA / 2.0
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


def d_bore_area(radius: float, flat_to_axis: float) -> float:
    """Area of a round bore trimmed by a flat ``flat_to_axis`` off its centre."""
    half_chord = math.sqrt(radius * radius - flat_to_axis * flat_to_axis)
    segment = (
        radius * radius * math.acos(flat_to_axis / radius) - flat_to_axis * half_chord
    )
    return math.pi * radius * radius - segment


V_SPIGOT = math.pi * SPIGOT_R**2 * SPIGOT_LENGTH
V_FLANGE = math.pi * FLANGE_R**2 * FLANGE_THICK
V_HUB_BODY = math.pi * HUB_R**2 * HUB_BODY_LENGTH
# The D-bore through flange and body, the round bore through the spigot.
V_D_BORE = d_bore_area(BORE_R, FLAT_TO_AXIS) * -HUB_FRONT_Z
V_SPIGOT_BORE = math.pi * BORE_R**2 * SPIGOT_LENGTH
V_SCREW_HOLES = len(screw_centres()) * math.pi * SCREW_HOLE_R**2 * FLANGE_THICK
V_OIL_HOLE = radial_hole_volume(OIL_HOLE_R, BORE_R, HUB_R)
V_FINAL = (
    V_SPIGOT
    + V_FLANGE
    + V_HUB_BODY
    - V_D_BORE
    - V_SPIGOT_BORE
    - V_SCREW_HOLES
    - V_OIL_HOLE
)

# The Top-plane sketch's (u, v) is model (X, -Z): the spigot's end at
# v = -SPIGOT_LENGTH, the hub front face at v = -HUB_FRONT_Z.
_SPIGOT_END_V = -SPIGOT_LENGTH
_HUB_FRONT_V = -HUB_FRONT_Z
_OIL_HOLE_V = _HUB_FRONT_V - OIL_HOLE_STATION


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
    """The frame's promise: the flange's rear face on z = 0, the spigot toward
    +Z, the hub toward -Z."""
    front, rear = _z_extreme_mm(adapter, -1.0), _z_extreme_mm(adapter, 1.0)
    if abs(rear - SPIGOT_LENGTH) > 1e-3 or abs(front - HUB_FRONT_Z) > 1e-3:
        raise RuntimeError(
            f"disc hub spans z {front:.4f}..{rear:.4f}, "
            f"not {HUB_FRONT_Z:g}..{SPIGOT_LENGTH:g}"
        )


def _as_construction(adapter, entity_id: str) -> None:
    """Make a registered sketch segment construction-only and prove the flag."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _d_bore(adapter) -> list[tuple[str, str]]:
    """The Front-plane D-bore: a major arc through +Y closed by its flat on
    -Y.  A construction witness from the bore's axis to the flat owns the
    flat's printed distance (FlatToAxis), independent of BoreDia."""
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    half_chord = math.sqrt(BORE_R * BORE_R - FLAT_TO_AXIS * FLAT_TO_AXIS)
    set_sketch_direct_db(adapter, True)
    arc = check(
        "D-bore major arc",
        await adapter.add_arc(
            0.0, 0.0, half_chord, -FLAT_TO_AXIS, -half_chord, -FLAT_TO_AXIS
        ),
    )
    flat = check(
        "D-bore flat",
        await adapter.add_line(-half_chord, -FLAT_TO_AXIS, half_chord, -FLAT_TO_AXIS),
    )
    witness = check(
        "D-bore flat witness",
        await adapter.add_line(0.0, 0.0, 0.0, -FLAT_TO_AXIS),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, witness)
    for label, first, second, relation in (
        ("bore arc centre", f"{arc}.center", "origin", "coincident"),
        ("bore left junction", f"{flat}.start", f"{arc}.end", "coincident"),
        ("bore right junction", f"{flat}.end", f"{arc}.start", "coincident"),
        ("horizontal bore flat", flat, None, "horizontal"),
        ("vertical flat witness", witness, None, "vertical"),
        ("witness on bore axis", f"{witness}.start", "origin", "coincident"),
        ("witness on bore flat", f"{witness}.end", flat, "coincident"),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "bore diameter",
        await adapter.add_sketch_dimension(arc, None, "diameter", BORE_DIA),
    )
    bore.record("BoreDia", '"BoreDia"')
    await dimension_between(
        adapter,
        f"{witness}.start",
        f"{witness}.end",
        "vertical_distance",
        FLAT_TO_AXIS,
        "bore flat from the axis",
    )
    bore.record("FlatToAxis", '"FlatToAxis"')
    await ensure_fully_defined(adapter, "D-bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    return bore.apply(adapter, "BoreProfile")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    for name, value in (
        ("FlangeDia", FLANGE_DIA),
        ("FlangeThick", FLANGE_THICK),
        ("HubDia", HUB_DIA),
        ("HubLength", HUB_LENGTH),
        ("SpigotDia", SPIGOT_DIA),
        ("SpigotLength", SPIGOT_LENGTH),
        ("BoreDia", BORE_DIA),
        ("FlatToAxis", FLAT_TO_AXIS),
        ("BoltCircleDia", BOLT_CIRCLE_DIA),
        ("ScrewHoleDia", SCREW_HOLE_DIA),
        ("OilHoleDia", OIL_HOLE_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Turned profile about the gear axis, Top-plane (u, v) = model (X, -Z):
    # spigot end, spigot O.D., flange rear face (on the Front Plane), flange
    # O.D., flange front face, hub O.D., hub front face.  The spigot's and
    # flange's lengths run from the flange's rear face; the overall the sheet
    # prints as a reference runs from the spigot's end (R9-68); the hub
    # body's own length is the remainder, never printed.
    profile = SketchDims()
    check("create_sketch hub profile", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "hub axis",
        await adapter.add_centerline(0.0, _SPIGOT_END_V, 0.0, _HUB_FRONT_V),
    )
    points = [
        (0.0, _SPIGOT_END_V),
        (SPIGOT_R, _SPIGOT_END_V),
        (SPIGOT_R, 0.0),
        (FLANGE_R, 0.0),
        (FLANGE_R, FLANGE_THICK),
        (HUB_R, FLANGE_THICK),
        (HUB_R, _HUB_FRONT_V),
        (0.0, _HUB_FRONT_V),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        p0 = points[index]
        p1 = points[(index + 1) % len(points)]
        relation = "horizontal" if p0[1] == p1[1] else "vertical"
        check(
            f"hub profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "hub axis vertical", await adapter.add_sketch_constraint(axis, None, "vertical")
    )
    # The axis on u = 0, the flange's rear face on v = 0.
    check(
        "spigot end centre on the axis",
        await adapter.add_sketch_constraint(
            f"{lines[0]}.start", "origin", "vertical_points"
        ),
    )
    check(
        "flange rear face on the Front Plane",
        await adapter.add_sketch_constraint(
            f"{lines[2]}.start", "origin", "horizontal_points"
        ),
    )
    await add_diametric_linear_dimension(
        adapter, axis, lines[1], (SPIGOT_R + 4.0, _SPIGOT_END_V / 2.0), "SpigotDia"
    )
    profile.record("SpigotDia", '"SpigotDia"')
    await add_diametric_linear_dimension(
        adapter, axis, lines[3], (FLANGE_R + 4.0, FLANGE_THICK / 2.0), "FlangeDia"
    )
    profile.record("FlangeDia", '"FlangeDia"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        lines[5],
        (HUB_R + 4.0, (FLANGE_THICK + _HUB_FRONT_V) / 2.0),
        "HubDia",
    )
    profile.record("HubDia", '"HubDia"')
    check(
        "spigot length",
        await adapter.add_sketch_dimension(lines[1], None, "linear", SPIGOT_LENGTH),
    )
    profile.record("SpigotLength", '"SpigotLength"')
    check(
        "flange thickness",
        await adapter.add_sketch_dimension(lines[3], None, "linear", FLANGE_THICK),
    )
    profile.record("FlangeThick", '"FlangeThick"')
    # The overall, spigot end to hub front face (outer corners, where the
    # drawing's extension lines rise).
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[6]}.start",
        "vertical_distance",
        HUB_LENGTH,
        "hub overall length",
    )
    profile.record("HubLength", '"HubLength"')
    await ensure_fully_defined(adapter, "hub profile")
    check("exit_sketch hub profile", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += profile.apply(adapter, "HubProfile")
    check("revolve hub", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "HubBody")
    v_body = V_SPIGOT + V_FLANGE + V_HUB_BODY
    await volume_check(adapter, "spigot + flange + hub body", v_body, 0.005 * v_body)
    await bbox_extent_check(adapter, "overall length", "z", HUB_LENGTH)
    await bbox_extent_check(adapter, "flange O.D.", "x", FLANGE_DIA)
    _check_z_span(adapter)

    # D-bore forward through flange and body (a cut runs against the sketch
    # normal: -Z); the flat drives only, from the flange's rear face.
    drive_jobs += await _d_bore(adapter)
    check(
        "cut hub D-bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=-HUB_FRONT_Z)),
    )
    name_last_feature(adapter, "ThroughBore")
    await volume_check(adapter, "hub D-bore", v_body - V_D_BORE, 0.01 * V_D_BORE)
    v_body -= V_D_BORE

    # The spigot's bore: the same Ø9 H7, round, reversed (+Z) from the Front
    # Plane to the spigot's end, driven by the D-bore's own BoreDia.
    spigot_bore = SketchDims()
    check("create_sketch spigot bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "spigot bore",
        dims=spigot_bore,
        names=(None, None, "SpigotBoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "spigot bore sketch")
    check("exit_sketch spigot bore", await adapter.exit_sketch())
    name_last_feature(adapter, "SpigotBoreProfile")
    drive_jobs += spigot_bore.apply(adapter, "SpigotBoreProfile")
    check(
        "cut spigot bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SPIGOT_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "SpigotBore")
    drive_jobs.append(
        (
            name_dimensions(adapter, "SpigotBore", ["SpigotBoreDepth"])[0],
            '"SpigotLength"',
        )
    )
    await volume_check(
        adapter, "spigot bore", v_body - V_SPIGOT_BORE, 0.01 * V_SPIGOT_BORE
    )
    v_body -= V_SPIGOT_BORE

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
    await volume_check(
        adapter, "screw holes", v_body - V_SCREW_HOLES, 0.02 * V_SCREW_HOLES
    )

    # Radial oil hole on +Y, one wall to the bore.  Top-plane sketch (u, v) =
    # model (X, -Z): a construction line on the axis from the hub front face
    # to the hole centre carries the station, half the hub body (R9-60: the
    # sheet prints no station; the hole is centred at fit-up); the circle's
    # centre sits on its end.
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
    oil.record("OilHoleDatum", '"HubLength" - "SpigotLength"')
    await dimension_between(
        adapter,
        f"{station}.start",
        f"{station}.end",
        "vertical_distance",
        OIL_HOLE_STATION,
        "oil hole station from the hub front face",
    )
    oil.record("OilHoleStation", '("HubLength" - "SpigotLength" - "FlangeThick") / 2')
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
    # The bore carries both its bands on the model: the round's H7 and the
    # flat's band, which together set the fit on the sleeve's boss and flat;
    # the spigot carries its h6, the disc's pilot.  Every other size is
    # governed by its places, the holes by the title block's DRILLED HOLES
    # row (the spec's DRAWING_PRECISION).
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *BORE_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "FlatToAxis", *FLAT_TO_AXIS_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "SpigotDia", *SPIGOT_DIA_DEVIATIONS
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
