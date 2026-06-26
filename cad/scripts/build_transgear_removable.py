r"""Reproduction script: removable speed-change gear set (book ch. 23, p. 57).

Three steel gears -- 12 / 18 / 24 teeth (annotated, high) -- of which two are
mounted at a time on the translational gearing's pin-drive stubs to set the
platen speed (small driving + large driven = slowest, large + small = fastest,
medium + medium = 1:1; every combination sums 36 teeth, so the centre distance
is fixed). One part, three configurations (T12/T18/T24), exactly the cone
gear's validated equation-driven recipe (see ``build_cone_gear.py`` for the
involute math and the SW 2026 parser dialect facts) at module 2.0 mm
(DP 25.4/2 = 12.7 -- keyframe measurement, DIMENSIONS.md ch. 23).

Config-independent mounting interface, cut after the tooth pattern: common
bore (Ø12) and two drive-pin holes (Ø3.5 on a Ø19 bolt circle) matching the
oval-pin stub shaft in `v4_transgear_020/025/030`. The pin circle's outer
extent (11.25 mm) clears the 12T gear's gap-floor chord (11.53 mm), so the
holes stay in solid material in every configuration.

The 12T gear comes out stub/undercut at standard proportions, like the 6T
cone gear -- the real hand-cut gear is similarly approximate.

Layout: gear axis = Z through the origin, disc z = 0..5 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_removable.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    OUT_PNG,
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)
# ``set_global`` is imported from _common under a distinct name: the gear-math
# globals below use build_cone_gear's stricter 4-arg ``set_global`` (asserts the
# round-tripped value to test the equation-parser dialect), while the plain
# length knobs added for the self-naming conversion use _common's mm-suffixing
# 3-arg upsert. Keeping both avoids touching the validated involute math.
from _common import set_global as set_global_mm
from build_cone_gear import (
    PI_LIT,
    equation_curve,
    gap_area_in_disc,
    gear_facts,
    pattern_count_dimension,
    read_dimension,
    set_global,
    set_global_read,
)

import _telemetry

PART_NAME = "transgear-removable"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel, unlike the brass wheels

DP_GEAR = 12.7  # module 2.0 mm, DIMENSIONS.md ch23 keyframe measurement (med)
PA_DEG = 14.5  # period-typical, same assumption as the rest of the machine
FACE_WIDTH = 5.0  # mm, catalog shot v4_transgear_015 (low)
BORE_DIAMETER = 12.0  # mm, common to all three gears (low)
PIN_HOLE_DIAMETER = 3.5  # mm, 2x drive-pin holes (low)
PIN_CIRCLE_RADIUS = 9.5  # mm, bolt-circle radius (low)

CONFIGS = [("T12", 12), ("T18", 18), ("T24", 24)]
DEFAULT_TEETH = 24

# Static cross-section removed by the bore + two pin holes (mm^2).
BORE_PINS_AREA = (
    math.pi * (BORE_DIAMETER / 2.0) ** 2
    + 2.0 * math.pi * (PIN_HOLE_DIAMETER / 2.0) ** 2
)


def expected_volume(teeth: int) -> float:
    """Analytic part volume (mm^3) for a configuration."""
    f = gear_facts(teeth, DP_GEAR, PA_DEG)
    ra_mm = f["Ra"] * IN
    blank = math.pi * ra_mm**2 * FACE_WIDTH
    gaps = teeth * gap_area_in_disc(teeth, dp=DP_GEAR, pa_deg=PA_DEG) * IN**2 * FACE_WIDTH
    return blank - gaps - BORE_PINS_AREA * FACE_WIDTH


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        CreateConfigurationParameters,
        CreateEquationParameters,
        ExtrusionParameters,
        RevolveParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())

    # ------------------------------------------------------------------
    # Equation-manager globals (dialect probes first -- see build_cone_gear).
    # ------------------------------------------------------------------
    facts = gear_facts(DEFAULT_TEETH, DP_GEAR, PA_DEG)
    await set_global(adapter, "TrigProbe", "cos(60)", 0.5)
    await set_global(adapter, "SqrProbe", "sqr(2)", math.sqrt(2.0))
    atn_probe = await set_global_read(adapter, "AtnProbe", "atn(1)")
    if abs(atn_probe - 45.0) < 1e-6:
        atn_rad = f"atn(%s) * {PI_LIT} / 180"
    elif abs(atn_probe - math.pi / 4.0) < 1e-6:
        atn_rad = "atn(%s)"
    else:
        raise RuntimeError(f"atn(1) evaluated to {atn_probe!r} -- unknown dialect")
    atn_tmax = atn_rad % '"Tmax"'

    await set_global(adapter, "ToothCount", str(DEFAULT_TEETH), DEFAULT_TEETH)
    await set_global(adapter, "DP", f"{DP_GEAR:g}", DP_GEAR)
    await set_global(adapter, "PA", f"{PA_DEG:g}", PA_DEG)
    await set_global(adapter, "PArad", f'"PA" * {PI_LIT} / 180', facts["PArad"])
    await set_global(adapter, "Rb", '"ToothCount" / "DP" * cos("PA") / 2', facts["Rb"])
    await set_global(adapter, "Ra", '("ToothCount" + 2) / "DP" / 2', facts["Ra"])
    await set_global(
        adapter, "Tmax", 'sqr("Ra" * "Ra" / ("Rb" * "Rb") - 1)', facts["Tmax"]
    )
    await set_global(
        adapter,
        "Delta",
        f'{PI_LIT} / (2 * "ToothCount") + tan("PA") - "PArad"',
        facts["Delta"],
    )
    await set_global(adapter, "Gamma", f'2 * {PI_LIT} / "ToothCount"', facts["Gamma"])
    await set_global(
        adapter, "ThetaL", f'{atn_tmax} - "Tmax" + "Delta"', facts["ThetaL"]
    )
    await set_global(
        adapter,
        "ThetaU",
        f'"Tmax" - {atn_tmax} - "Delta" + "Gamma"',
        facts["ThetaU"],
    )

    # Plain length knobs for the config-independent geometry (blank face width +
    # the mounting interface). mm suffix is load-bearing -- this is an INCH
    # document, so a bare number would be read as inches and blow the part up
    # 25.4x. The blank's RADIAL extent is NOT a knob here: it is config-driven by
    # the "Ra" equation link below, so only the (constant) face width is exposed.
    await set_global_mm(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global_mm(adapter, "BoreDia", f"{BORE_DIAMETER}mm")
    await set_global_mm(adapter, "PinHoleDia", f"{PIN_HOLE_DIAMETER}mm")
    await set_global_mm(adapter, "PinCircleRadius", f"{PIN_CIRCLE_RADIUS}mm")

    # Drive equations are recorded per sketch as the dims are created and applied
    # in one deferred batch once the whole single-config model exists (every
    # equation target must resolve against a finished, rebuilt model).
    drive_jobs: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Blank: revolved dimensioned rectangle, radial dim equation-linked to
    # "Ra" (the canonical configuration pattern from build_cone_gear).
    # ------------------------------------------------------------------
    ra_default_mm = facts["Ra"] * IN
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Top"))
    blank_lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (ra_default_mm, 0.0),
            (ra_default_mm, -FACE_WIDTH),
            (0.0, -FACE_WIDTH),
        ],
    )
    radial_line, side_line, _inner_line, axis_edge = blank_lines
    for ent, relation in (
        (radial_line, "horizontal"),
        (side_line, "vertical"),
        (_inner_line, "horizontal"),
        (axis_edge, "vertical"),
    ):
        check(f"blank {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check(
        "blank radial dim (D1)",
        await adapter.add_sketch_dimension(radial_line, None, "linear", ra_default_mm),
    )
    # Record in creation order. The radial dim is left UNDRIVEN here (drive None):
    # it is bound to the config-driving "Ra" global by the explicit create_equation
    # block below, so adding it to drive_jobs would double-drive it.
    blank.record("BlankRadial", None)
    check(
        "blank width dim (D2)",
        await adapter.add_sketch_dimension(side_line, None, "linear", FACE_WIDTH),
    )
    blank.record("BlankWidth", '"FaceWidth"')
    # Pin the (0, 0) corner to the origin explicitly. The h/v relations + the
    # two dims fix the rectangle's shape but not its position; previously the
    # corner was only located by SolidWorks snapping it onto the origin during
    # the (inference-on) line draw -- a crutch removed now that add_line_chain
    # suppresses inference. Same explicit anchor the sibling blanks use.
    check(
        "blank corner -> origin",
        await adapter.add_sketch_constraint(f"{radial_line}.start", "origin", "coincident"),
    )
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, -1.0, 0.0, -(FACE_WIDTH - 1.0)),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    blank_sketch = name_last_feature(adapter, "BlankProfile")
    drive_jobs += blank.apply(adapter, blank_sketch)
    check(
        "revolve blank",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Blank")

    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"blank mass properties failed: {mass.error}")
    com_z = float(mass.data.center_of_mass[2])
    if abs(com_z - FACE_WIDTH / 2.0) > 0.1:
        raise RuntimeError(
            f"blank centre of mass z = {com_z:.2f}, expected {FACE_WIDTH / 2.0:.2f}"
        )
    blank_volume = float(mass.data.volume)
    expected_blank = math.pi * ra_default_mm**2 * FACE_WIDTH
    if abs(blank_volume - expected_blank) > 0.02 * expected_blank:
        raise RuntimeError(
            f"blank volume {blank_volume:.1f} mm^3, expected {expected_blank:.1f}"
        )
    _telemetry.success(f"blank volume {blank_volume:.1f} mm^3 (com z {com_z:.2f})")

    # The radial dim was renamed D1 -> BlankRadial by blank.apply above, so the
    # captured auto-name "D1@..." would be stale -- reference the new name.
    radial_dim = f"BlankRadial@{blank_sketch}"
    before = read_dimension(adapter, radial_dim)
    if abs(before - facts["Ra"]) < 1e-6 * facts["Ra"]:
        dim_unit = 1.0
    elif abs(before - ra_default_mm) < 1e-6 * ra_default_mm:
        dim_unit = 25.4
    else:
        raise RuntimeError(
            f"{radial_dim} reads {before!r}, matches neither inches nor mm"
        )
    _telemetry.debug(f"{radial_dim} reads {before:g} (unit factor {dim_unit:g})")
    check(
        f"link {radial_dim} to Ra",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{radial_dim}" = "Ra"')
        ),
    )

    # ------------------------------------------------------------------
    # One tooth gap (global-referencing equation curves, t in [0,1]).
    # ------------------------------------------------------------------
    check("create_sketch gap", await adapter.create_sketch("Front"))
    u = '("Tmax" * t)'
    ph_low = f'({u} - "Delta")'
    ph_up = f'({u} - "Delta" + "Gamma")'
    r_clear = 60.0 / 25.4
    gap_curves = [
        await equation_curve(
            adapter,
            "lower flank",
            f'"Rb" * (cos{ph_low} + {u} * sin{ph_low})',
            f'"Rb" * ({u} * cos{ph_low} - sin{ph_low})',
        ),
        await equation_curve(
            adapter,
            "upper flank",
            f'"Rb" * (cos{ph_up} + {u} * sin{ph_up})',
            f'"Rb" * (sin{ph_up} - {u} * cos{ph_up})',
        ),
        await equation_curve(
            adapter,
            "base chord A2->A1",
            '"Rb" * ((1 - t) * cos("Gamma" - "Delta") + t * cos("Delta"))',
            '"Rb" * ((1 - t) * sin("Gamma" - "Delta") + t * sin("Delta"))',
        ),
        await equation_curve(
            adapter,
            "lower radial extension",
            f'("Ra" + t * ({r_clear:g} - "Ra")) * cos("ThetaL")',
            f'("Ra" + t * ({r_clear:g} - "Ra")) * sin("ThetaL")',
        ),
        await equation_curve(
            adapter,
            "outer clearance arc",
            f'{r_clear:g} * cos("ThetaL" + t * ("ThetaU" - "ThetaL"))',
            f'{r_clear:g} * sin("ThetaL" + t * ("ThetaU" - "ThetaL"))',
        ),
        await equation_curve(
            adapter,
            "upper radial extension",
            f'({r_clear:g} + t * ("Ra" - {r_clear:g})) * cos("ThetaU")',
            f'({r_clear:g} + t * ("Ra" - {r_clear:g})) * sin("ThetaU")',
        ),
    ]
    # The gap profile is six equation-driven curves whose shape and position
    # re-solve from the equation globals on every configuration change
    # (ToothCount 12/18/24) -- no static relation/dimension scheme can define
    # them, and fix relations are gone -- so the gap sketch is left
    # intentionally under-defined (its geometry is pinned by the equations).
    _telemetry.warn(f"gap sketch left under-defined ({len(gap_curves)} equation curves, no fix)")
    check("exit_sketch gap", await adapter.exit_sketch())
    # GEAR-MESHING SKETCH: name only, no SketchDims. The six curves are
    # equation-driven (they carry no display dimensions to record), and pinning
    # static dims on them would break the per-configuration re-solve that makes
    # the teeth mesh -- so the tooth-gap profile is named but never driven here.
    name_last_feature(adapter, "ToothGapProfile")
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FACE_WIDTH + 1.0)
    )
    check("cut tooth gap", gap_cut)

    # ------------------------------------------------------------------
    # Pattern about Z; link the instance count to ToothCount.
    # ------------------------------------------------------------------
    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    adapter._zoom_to_fit(adapter.currentModel)
    candidates = [[0.0, 0.0, FACE_WIDTH / 2.0]]
    for angle_deg in (-45.0, -90.0, -135.0, 135.0, 45.0):
        a = math.radians(angle_deg)
        candidates.append(
            [ra_default_mm * math.cos(a), ra_default_mm * math.sin(a), FACE_WIDTH / 2.0]
        )
    pattern = None
    for point in candidates:
        # geometry_pattern: per-instance re-solve of the global-driven
        # equation-curve profile produces corrupt sliver cuts (live SW 2026
        # finding, this part); verbatim geometry copies are exact.
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point,
                features=[gap_cut.data.name],
                count=DEFAULT_TEETH,
                geometry_pattern=True,
            )
        )
        if res.is_success:
            pattern = res
            _telemetry.success(f"circular pattern axis via point {point}")
            break
        _telemetry.debug(f"axis candidate {point} failed: {res.error}")
    if pattern is None:
        raise RuntimeError("circular pattern: no axis candidate selectable")
    count_dim = pattern_count_dimension(adapter, pattern.data.name, DEFAULT_TEETH)
    check(
        f"link {count_dim} to ToothCount",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{count_dim}" = "ToothCount"')
        ),
    )

    # Fail fast: validate the toothed disc at the default tooth count before
    # any configuration work (localises pattern failures to this feature).
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"post-pattern mass properties failed: {mass.error}")
    toothed = float(mass.data.volume)
    expected_toothed = expected_volume(DEFAULT_TEETH) + BORE_PINS_AREA * FACE_WIDTH
    if abs(toothed - expected_toothed) > 0.01 * expected_toothed:
        raise RuntimeError(
            f"toothed disc volume {toothed:.1f} mm^3, analytic "
            f"{expected_toothed:.1f} -- pattern produced wrong geometry"
        )
    _telemetry.success(f"toothed disc volume {toothed:.1f} (analytic {expected_toothed:.1f})")

    # ------------------------------------------------------------------
    # Mounting interface (config-independent, after the pattern): bore +
    # two drive-pin holes on the +/-X axis.
    # ------------------------------------------------------------------
    bore_pins = SketchDims()
    check("create_sketch bore+pins", await adapter.create_sketch("Front"))
    # Direct-to-DB: the on-axis-revolved blank leaves its seam edge along +X
    # on this face, exactly under the pin centres -- creation-time inference
    # snaps the circles to it and the auto-relation then makes every driving
    # point-pair dim fail (diag_onaxis_pin.py scenarios G/H vs I).
    set_sketch_direct_db(adapter, True)
    # Emission order per circle = its non-zero centre coords (x if x!=0, z if
    # y!=0) THEN diameter. Bore is on-origin -> diameter only. Both pins sit on
    # the +/-X axis (y=0) -> one centre-X dim each, then diameter. The -X pin's
    # centre dim is an UNSIGNED distance (displays 9.5), so it drives to the
    # POSITIVE "PinCircleRadius" -- not its signed -9.5 coordinate.
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore_pins,
        names=("BoreCx", "BoreCz", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    await define_circle(
        adapter, PIN_CIRCLE_RADIUS, 0.0, PIN_HOLE_DIAMETER / 2.0, "pin hole +X",
        dims=bore_pins,
        names=("PinPosX", "PinPosZ", "PinPosDia"),
        drives=('"PinCircleRadius"', None, '"PinHoleDia"'),
    )
    await define_circle(
        adapter, -PIN_CIRCLE_RADIUS, 0.0, PIN_HOLE_DIAMETER / 2.0, "pin hole -X",
        dims=bore_pins,
        names=("PinNegX", "PinNegZ", "PinNegDia"),
        drives=('"PinCircleRadius"', None, '"PinHoleDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "bore+pins sketch")
    check("exit_sketch bore+pins", await adapter.exit_sketch())
    name_last_feature(adapter, "BorePinsProfile")
    drive_jobs += bore_pins.apply(adapter, "BorePinsProfile")
    check(
        "cut bore+pins",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "BorePinsCut")

    # ------------------------------------------------------------------
    # Deferred drive batch + neutrality re-check (still at DEFAULT_TEETH, no
    # configs yet): apply every recorded equation after a rebuild, then confirm
    # the single-config geometry did not move (each equation evaluates to its
    # as-built value). Done BEFORE configurations are spun up so the neutral
    # baseline is the un-driven default the per-config checks already trust.
    # ------------------------------------------------------------------
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"post-drive mass properties failed: {mass.error}")
    driven = float(mass.data.volume)
    expected_driven = expected_volume(DEFAULT_TEETH)
    if abs(driven - expected_driven) > 0.01 * expected_driven:
        raise RuntimeError(
            f"driven part volume {driven:.1f} mm^3, analytic {expected_driven:.1f} "
            "-- drive equations are not geometry-neutral"
        )
    _telemetry.success(f"driven part volume {driven:.1f} (equations neutral, analytic {expected_driven:.1f})")

    await apply_material(adapter, MATERIAL)

    # ------------------------------------------------------------------
    # Configurations + regeneration checks (cone-gear validation recipe).
    # ------------------------------------------------------------------
    for name, teeth in CONFIGS:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(
                    name=name, comment=f"{teeth}-tooth removable gear"
                )
            ),
        )
    for name, teeth in CONFIGS:
        check(
            f"ToothCount = {teeth} in {name}",
            await adapter.set_global_variable(
                SetGlobalVariableParameters(
                    name="ToothCount", expression=str(teeth), configuration=name
                )
            ),
        )

    png_dir = OUT_PNG / PART_NAME
    png_dir.mkdir(parents=True, exist_ok=True)
    artefacts: dict[str, str] = {}
    volumes: dict[str, float] = {}
    for name, teeth in CONFIGS:
        check(f"activate {name}", await adapter.set_active_configuration(name))

        count = read_dimension(adapter, count_dim)
        if abs(count - teeth) > 1e-9:
            raise RuntimeError(
                f"{name}: pattern instance count reads {count:g}, expected {teeth}"
            )
        cfg = gear_facts(teeth, DP_GEAR, PA_DEG)
        mass = await adapter.get_mass_properties()
        if not mass.is_success:
            raise RuntimeError(f"{name}: get_mass_properties failed: {mass.error}")
        volume = float(mass.data.volume)
        expected = expected_volume(teeth)
        if abs(volume - expected) > 0.01 * expected:
            raise RuntimeError(
                f"{name}: volume {volume:.1f} mm^3, analytic {expected:.1f} -- "
                "regeneration produced wrong geometry"
            )
        volumes[name] = volume
        _telemetry.success(f"{name}: count {count:g}, volume {volume:.1f} (analytic {expected:.1f})")

        radial = read_dimension(adapter, radial_dim)
        if abs(radial - cfg["Ra"] * dim_unit) > 1e-4 * cfg["Ra"] * dim_unit:
            raise RuntimeError(
                f"{name}: {radial_dim} reads {radial:g}, expected "
                f"{cfg['Ra'] * dim_unit:g}"
            )

        img = (png_dir / f"{PART_NAME}_{name}_isometric.png").resolve()
        check(
            f"export_image {name}",
            await adapter.export_image(
                {
                    "file_path": str(img),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": "isometric",
                }
            ),
        )
        artefacts[f"iso_{name}"] = str(img)

    ordered = [volumes[name] for name, _ in CONFIGS]
    if not all(a < b for a, b in zip(ordered, ordered[1:], strict=False)):
        raise RuntimeError(f"volumes not monotonically increasing: {volumes}")

    first_name, _ = CONFIGS[0]
    check(f"re-activate {first_name}", await adapter.set_active_configuration(first_name))
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"re-check {first_name}: {mass.error}")
    revisit = float(mass.data.volume)
    if abs(revisit - volumes[first_name]) > abs(volumes[first_name]) * 1e-6:
        raise RuntimeError(
            f"{first_name} volume drifted on revisit: {revisit} vs {volumes[first_name]}"
        )
    _telemetry.success(f"{first_name} volume reproduced on revisit: {revisit:.1f} mm^3")

    check("activate T24 for saved views", await adapter.set_active_configuration("T24"))
    await report_mass_properties(adapter)
    artefacts.update(await save_part_and_images(adapter, PART_NAME))
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
