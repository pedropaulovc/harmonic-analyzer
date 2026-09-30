r"""Reproduction script: MHA-081 removable ANSI #25 sprocket (book ch. 23, p. 56-61).

Three bright-steel sprockets -- 12 / 18 / 24 teeth -- of which two are mounted
at a time to set the platen speed: one on the crank's seat collar, one on the
knob shaft's, both in the ONE chain plane (the third is the loose spare). One
part, three configurations (T12/T18/T24). Every number is
``transgear_removable_spec``'s; this script only turns them into features.

Tooth form (spec docstring): the ANSI B29.1 (ACA) #25 standard form -- the
``SEAT_CURVE_R`` seating arc centred on the pitch circle, the
``WORKING_CURVE_R`` working arc, the straight yz and the topping arc out to
the turned outside diameter. One tooth gap is ten equation curves
referencing equation-manager globals, cut, then circularly patterned.
``ToothCount`` is the only configuration-specific global; pitch/outside
radius, the ACA angles A and B, the working and topping centres, the
topping radius F and the OD corner are all equations of it (the
manager-side mirror of ``spec.gap_geometry``, each round-tripped against it
at T24), so every configuration re-solves its own gap and each
configuration's volume is checked against ``spec.part_volume``.

Config-independent mounting interface, cut after the tooth pattern: bore
``BORE_DIA`` and two ``PIN_HOLE_DIA`` drive-pin holes on ``PIN_CIRCLE_RADIUS``
at ``PIN_HOLE_ANGLES_DEG`` (local +/-Y). The bore/pin-hole web
(``spec.BORE_PIN_WEB``, 0.60 nominal) sits below the 1.5 wall floor as a
Named exception; the sheet states its printed worst case
(``transgear_removable_notes.BORE_PIN_WEB_NOTE``).

Drawing marks (``draw_transgear_removable``): ``spec.DRAWING_DIMENSIONS`` at
``spec.DRAWING_PRECISION``, the plate thickness banded ``spec.PLATE_BAND``
and each pin centre +/-``spec.DRIVE_PIN_OFFSET_TOL``; the sheet's SPROCKET
DATA and notes are file properties.

Part frame: axis Z through the origin, plate z = 0..PLATE (the Front Plane is
the wheel's FRONT face; ``RearFace`` at z = PLATE seats on the shaft's seat
collar), a TOOTH centred on local +X, gaps centred at pi/N + k 2pi/N. With
that one clocking rule T12 and T24 carry a tooth on the +/-Y hole
centrelines, T18 a gap (90 deg is 4.5 of its pitches).

Named datums, blanked and selectable in every configuration: ``Axis1`` (the
wheel axis), plane ``RearFace``, axes ``PinHoleAxis1`` (+Y hole) and
``PinHoleAxis2`` (-Y hole).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_removable.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
import transgear_removable_spec as spec
from _common import (
    IN,
    OUT_PNG,
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    set_sketch_direct_db,
)
from _drawing_marks import (
    _named_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _drawing_simplified import save_simplified_part
from _fit_limits import deviations
from _grouped_bom_properties import apply_grouped_bom_properties
from _visibility import blank_reference_geometry
from transgear_removable_notes import DRAWING_NOTES, GEAR_DATA

# ``set_global`` is imported from _common under a distinct name: the gap-math
# globals below use involute_gear's stricter 4-arg ``set_global`` (asserts the
# round-tripped value to test the equation-parser dialect), while the plain
# mm length knobs use _common's 3-arg upsert.
from _common import set_global as set_global_mm
from involute_gear import (
    PI_LIT,
    pattern_count_dimension,
    read_dimension,
    set_global,
    set_global_read,
)

PART_NAME = "transgear-removable"
MATERIAL = "Plain Carbon Steel"  # contract: bright plain-carbon steel plate

DEFAULT_TEETH = spec.TEETH[spec.DEFAULT_CONFIG]
DRAWING_DIMENSIONS = spec.DRAWING_DIMENSIONS

# The pin holes are placed as on-axis circles and their axes as Right Plane x
# (Top Plane offset): both constructions assume the spec's angles are +/-Y.
PIN_HOLE_CENTRES = tuple(
    (
        spec.PIN_CIRCLE_RADIUS * math.cos(math.radians(angle)),
        spec.PIN_CIRCLE_RADIUS * math.sin(math.radians(angle)),
    )
    for angle in spec.PIN_HOLE_ANGLES_DEG
)
if any(abs(x) > 1e-9 for x, _y in PIN_HOLE_CENTRES):
    raise AssertionError("drive-pin holes must sit on local +/-Y")
# The equation manager writes atan2 as a plain atn(vy / vx): valid only while
# vx > 0, for b's bearing about the axis and the corner's about b.
for _name, _teeth in spec.CONFIGS:
    _g = spec.gap_geometry(_teeth)
    if _g["topping_cx"] <= 0.0 or _g["corner_x"] <= _g["topping_cx"]:
        raise AssertionError(f"{_name}: topping-curve bearings leave atn's half-plane")


_TOL_BILAT = 2  # swTolType_e.swTolBILAT
_TOL_SYMMETRIC = 4  # swTolType_e.swTolSYMMETRIC


def family_bands() -> dict[tuple[str, str], tuple[int, float, float]]:
    """``(feature, dimension) -> (tolerance type, lower, upper)`` in mm: the
    bands the sheet prints once for T12, T18 and T24 (they share the plate
    and the pin holes), as the build sets them below."""
    pin = (_TOL_SYMMETRIC, -spec.DRIVE_PIN_OFFSET_TOL, spec.DRIVE_PIN_OFFSET_TOL)
    return {
        ("BlankProfile", "BlankWidth"): (_TOL_BILAT, *deviations(spec.PLATE_BAND)),
        ("BorePinsProfile", "PinPosY"): pin,
        ("BorePinsProfile", "PinNegY"): pin,
    }


async def assert_bands_in_every_configuration(adapter) -> None:
    """Read the family's bands back in each configuration.

    ``SetValues`` writes them with the default configuration active and names
    no configuration, so nothing else proves T12 and T18 carry them.  The
    sheet's views show T24, but the shop makes all three from it.
    """
    expected = family_bands()
    for name, _teeth in spec.CONFIGS:
        check(
            f"activate {name} for the band readback",
            await adapter.set_active_configuration(name),
        )
        for (feature, dimension_name), (kind, lower, upper) in expected.items():
            _display, dimension = _named_dimension(adapter, feature, dimension_name)
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            observed = (
                int(tolerance.Type),
                float(tolerance.GetMinValue()) * 1000.0,
                float(tolerance.GetMaxValue()) * 1000.0,
            )
            if (
                observed[0] != kind
                or abs(observed[1] - lower) > 1e-6
                or abs(observed[2] - upper) > 1e-6
            ):
                raise RuntimeError(
                    f"{name}: {dimension_name}@{feature} tolerance reads "
                    f"type {observed[0]} {observed[1]:+g}/{observed[2]:+g} mm, "
                    f"expected type {kind} {lower:+g}/{upper:+g} mm"
                )
    check(
        f"re-activate {spec.DEFAULT_CONFIG} after the band readback",
        await adapter.set_active_configuration(spec.DEFAULT_CONFIG),
    )
    _telemetry.success(
        f"plate and pin-location bands read back in {len(spec.CONFIGS)} configurations"
    )


def gap_globals(atn_rad: str, teeth: int) -> list[tuple[str, str, float]]:
    """Equation-manager globals of one tooth gap: ``(name, expression, value)``.

    Lengths are INCHES (the part template is IPS and equation curves evaluate
    in document units); the manager's direct trig takes DEGREES, so the
    ``*Deg`` globals feed it, while ``Half``, ``SeatStart``, ``WorkEnd``,
    ``TopStart``, ``TopEnd`` and ``Corner`` are RADIANS for the equation
    curves (whose trig is radian). ``atn_rad`` is the probed ``atn`` dialect
    with its result in radians. ``value`` is the expected evaluation at
    ``teeth`` from ``spec.gap_geometry`` -- the round trip is the dialect test.
    The centres are in the gap's own frame (gap centred on +X, upper flank's
    centres); :func:`gap_curves` turns them onto the seed gap.
    """
    g = spec.gap_geometry(teeth)
    top_dist = math.hypot(g["topping_cx"], g["topping_cy"])
    ra = g["ra"]
    cos_gamma = (top_dist**2 + ra**2 - g["topping_r"] ** 2) / (2.0 * top_dist * ra)
    # The OD corner is b's bearing less the law-of-cosines angle gamma:
    # atan2 as atn(vy / vx) (vx > 0, asserted at import), acos as pi/2 - asin
    # and asin through atn.
    bearing = atn_rad % '"TopCY" / "TopCX"'
    asin_gamma = atn_rad % '"CosGamma" / sqr(1 - "CosGamma" * "CosGamma")'
    to_rad = f"* {PI_LIT} / 180"
    return [
        ("ToothCount", str(teeth), float(teeth)),
        ("ChainPitch", repr(spec.CHAIN_PITCH / IN), spec.CHAIN_PITCH / IN),
        ("SeatR", repr(spec.SEAT_CURVE_R / IN), spec.SEAT_CURVE_R / IN),
        ("WorkR", repr(spec.WORKING_CURVE_R / IN), spec.WORKING_CURVE_R / IN),
        (
            "WorkOffset",
            repr(spec.WORKING_CENTRE_OFFSET / IN),
            spec.WORKING_CENTRE_OFFSET / IN,
        ),
        (
            "TopOffset",
            repr(spec.TOPPING_CENTRE_OFFSET / IN),
            spec.TOPPING_CENTRE_OFFSET / IN,
        ),
        ("HalfDeg", '180 / "ToothCount"', math.degrees(g["half_pitch_angle"])),
        ("Half", f'{PI_LIT} / "ToothCount"', g["half_pitch_angle"]),
        ("Rp", '"ChainPitch" / sin("HalfDeg") / 2', g["rp"] / IN),
        # spec.outside_dia's ANSI p (0.6 + cot(180/N)), halved.
        ("Ra", '"ChainPitch" * (0.6 + 1 / tan("HalfDeg")) / 2', ra / IN),
        # ACA A = 35 + 60/N and B = 18 - 56/N.
        ("ADeg", '35 + 60 / "ToothCount"', math.degrees(spec.working_angle(teeth))),
        ("BDeg", '18 - 56 / "ToothCount"', math.degrees(spec.working_arc(teeth))),
        ("SeatStart", f'("ADeg" + 90) {to_rad}', g["seat_start"]),
        ("WorkEnd", f'("ADeg" - "BDeg" + 90) {to_rad}', g["working_end"]),
        ("WorkCX", '"Rp" + "WorkOffset" * sin("ADeg")', g["working_cx"] / IN),
        ("WorkCY", '0 - "WorkOffset" * cos("ADeg")', g["working_cy"] / IN),
        # ACA F = Dr [0.8 cos B + 1.4 cos(17 - 64/N) - 1.3025] - 0.0015 in,
        # written as the tangency it encodes: 17 - 64/N = A - B - 180/N.
        (
            "TopR",
            '"WorkOffset" * cos("BDeg") '
            '+ "TopOffset" * cos("ADeg" - "BDeg" - "HalfDeg") - "WorkR"',
            g["topping_r"] / IN,
        ),
        ("TopCX", '"Rp" - "TopOffset" * sin("HalfDeg")', g["topping_cx"] / IN),
        ("TopCY", '"TopOffset" * cos("HalfDeg")', g["topping_cy"] / IN),
        ("TopStart", f'("ADeg" - "BDeg" - 90) {to_rad}', g["topping_start"]),
        ("TopDist", 'sqr("TopCX" * "TopCX" + "TopCY" * "TopCY")', top_dist / IN),
        (
            "CosGamma",
            '("TopDist" * "TopDist" + "Ra" * "Ra" - "TopR" * "TopR") '
            '/ (2 * "TopDist" * "Ra")',
            cos_gamma,
        ),
        ("Corner", f"{bearing} - {PI_LIT} / 2 + {asin_gamma}", g["corner_angle"]),
        ("CornerDeg", f'"Corner" * 180 / {PI_LIT}', math.degrees(g["corner_angle"])),
        ("CornerX", '"Ra" * cos("CornerDeg")', g["corner_x"] / IN),
        ("CornerY", '"Ra" * sin("CornerDeg")', g["corner_y"] / IN),
        (
            "TopEnd",
            atn_rad % '("CornerY" - "TopCY") / ("CornerX" - "TopCX")',
            g["topping_end"],
        ),
        # Clearance radius for closing the cut outside the blank (removes nothing).
        ("RClear", '2 * "Ra"', 2.0 * ra / IN),
    ]


def _at(radius: str, angle: str) -> tuple[str, str]:
    """Polar point (curve dialect: radian trig)."""
    return f"{radius} * cos({angle})", f"{radius} * sin({angle})"


def _plus(a: tuple[str, str], b: tuple[str, str]) -> tuple[str, str]:
    return f"{a[0]} + {b[0]}", f"{a[1]} + {b[1]}"


def _segment(p: tuple[str, str], q: tuple[str, str]) -> tuple[str, str]:
    """Straight line p -> q over t in [0, 1]."""
    return (
        f"({p[0]}) + t * (({q[0]}) - ({p[0]}))",
        f"({p[1]}) + t * (({q[1]}) - ({p[1]}))",
    )


def _about(cx: str, cy: str, radius: str, angle: str, upper: bool) -> tuple[str, str]:
    """A point ``radius`` from a gap-frame centre (cx, cy) at gap-frame
    ``angle``, on the seed gap: the upper flank's as given, the lower flank's
    mirrored in the gap centreline, both then turned by ``Half``."""
    if upper:
        centre = (
            f'{cx} * cos("Half") - {cy} * sin("Half")',
            f'{cx} * sin("Half") + {cy} * cos("Half")',
        )
        return _plus(centre, _at(radius, f'("Half" + {angle})'))
    centre = (
        f'{cx} * cos("Half") + {cy} * sin("Half")',
        f'{cx} * sin("Half") - {cy} * cos("Half")',
    )
    return _plus(centre, _at(radius, f'("Half" - {angle})'))


def _sweep(start: str, end: str) -> str:
    """Angle ``start`` -> ``end`` over t in [0, 1]."""
    return f"({start} + t * ({end} - {start}))"


def _working(angle: str, upper: bool) -> tuple[str, str]:
    return _about('"WorkCX"', '"WorkCY"', '"WorkR"', angle, upper)


def _topping(angle: str, upper: bool) -> tuple[str, str]:
    return _about('"TopCX"', '"TopCY"', '"TopR"', angle, upper)


def gap_curves() -> list[tuple[str, str, str]]:
    """The seed gap's closed loop as ``(label, x(t), y(t))`` equation curves.

    Centred on angle ``Half`` (pi/N, the first gap off the +X tooth), in
    order: seating arc upper x -> bottom -> lower x', lower working arc to
    y', the straight y'z', lower topping arc to the OD corner at
    ``Half - Corner``, out to ``RClear``, around, back to the upper corner at
    ``Half + Corner``, upper topping arc to z, the straight zy, upper working
    arc back to x.
    """
    seat = _plus(
        _at('"Rp"', '"Half"'),
        _at(
            '"SeatR"', f'("Half" + "SeatStart" + t * (2 * {PI_LIT} - 2 * "SeatStart"))'
        ),
    )
    return [
        ("seating arc", *seat),
        ("lower working arc", *_working(_sweep('"SeatStart"', '"WorkEnd"'), False)),
        (
            "lower flank",
            *_segment(_working('"WorkEnd"', False), _topping('"TopStart"', False)),
        ),
        ("lower topping arc", *_topping(_sweep('"TopStart"', '"TopEnd"'), False)),
        (
            "lower clearance ray",
            *_at('("Ra" + t * ("RClear" - "Ra"))', '("Half" - "Corner")'),
        ),
        (
            "outer clearance arc",
            *_at('"RClear"', '("Half" - "Corner" + 2 * t * "Corner")'),
        ),
        (
            "upper clearance ray",
            *_at('("RClear" + t * ("Ra" - "RClear"))', '("Half" + "Corner")'),
        ),
        ("upper topping arc", *_topping(_sweep('"TopEnd"', '"TopStart"'), True)),
        (
            "upper flank",
            *_segment(_topping('"TopStart"', True), _working('"WorkEnd"', True)),
        ),
        ("upper working arc", *_working(_sweep('"WorkEnd"', '"SeatStart"'), True)),
    ]


async def gap_curve(adapter, label: str, x_expr: str, y_expr: str) -> str:
    """Add one gap curve over t in [0, 1] with UNLOCKED end points.

    The ten curves share their end points in one closed loop. With locked
    ends (the ``CreateEquationSpline2`` default) the fix escalation closed
    that loop redundantly: the fourth fix left the sketch at swNoSolution
    with no over-defining relation (farm, 2026-09-30, six-curve form).
    Unlocked, each fix pins only its own curve and the last fully defines
    the sketch.
    """
    from solidworks_mcp.adapters.base import CreateEquationCurveParameters

    res = await adapter.create_equation_driven_curve(
        CreateEquationCurveParameters(
            x_expression=x_expr,
            y_expression=y_expr,
            range_start="0",
            range_end="1",
            lock_start=False,
            lock_end=False,
        )
    )
    return check(f"curve {label}", res)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        CreateConfigurationParameters,
        CreateEquationParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
        SetGlobalVariableParameters,
    )

    check("create_part", await adapter.create_part())

    # ------------------------------------------------------------------
    # Equation-manager globals (dialect probes first -- see build_cone_gear).
    # ------------------------------------------------------------------
    await set_global(adapter, "TrigProbe", "cos(60)", 0.5)
    await set_global(adapter, "SqrProbe", "sqr(2)", math.sqrt(2.0))
    atn_probe = await set_global_read(adapter, "AtnProbe", "atn(1)")
    if abs(atn_probe - 45.0) < 1e-6:
        atn_rad = f"atn(%s) * {PI_LIT} / 180"
    elif abs(atn_probe - math.pi / 4.0) < 1e-6:
        atn_rad = "atn(%s)"
    else:
        raise RuntimeError(f"atn(1) evaluated to {atn_probe!r} -- unknown dialect")
    for name, expression, expected in gap_globals(atn_rad, DEFAULT_TEETH):
        await set_global(adapter, name, expression, expected)

    # Plain length knobs for the config-independent geometry (plate + the
    # mounting interface). mm suffix is load-bearing -- this is an INCH
    # document, so a bare number would be read as inches and blow the part up
    # 25.4x. The blank's RADIAL extent is NOT a knob here: it is config-driven by
    # the "Ra" equation link below.
    await set_global_mm(adapter, "Plate", f"{spec.PLATE}mm")
    await set_global_mm(adapter, "BoreDia", f"{spec.BORE_DIA}mm")
    await set_global_mm(adapter, "PinHoleDia", f"{spec.PIN_HOLE_DIA}mm")
    await set_global_mm(adapter, "PinCircleRadius", f"{spec.PIN_CIRCLE_RADIUS}mm")

    # Drive equations are recorded per sketch as the dims are created and applied
    # in one deferred batch once the whole single-config model exists (every
    # equation target must resolve against a finished, rebuilt model).
    drive_jobs: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Blank: revolved dimensioned rectangle, radial dim equation-linked to
    # "Ra" (the canonical configuration pattern from build_cone_gear).
    # ------------------------------------------------------------------
    ra_default_mm = spec.outside_dia(DEFAULT_TEETH) / 2.0
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Top"))
    blank_lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (ra_default_mm, 0.0),
            (ra_default_mm, -spec.PLATE),
            (0.0, -spec.PLATE),
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
        await adapter.add_sketch_dimension(side_line, None, "linear", spec.PLATE),
    )
    blank.record("BlankWidth", '"Plate"')
    # Pin the (0, 0) corner to the origin explicitly: the h/v relations + the
    # two dims fix the rectangle's shape but not its position.
    check(
        "blank corner -> origin",
        await adapter.add_sketch_constraint(f"{radial_line}.start", "origin", "coincident"),
    )
    set_sketch_direct_db(adapter, True)
    check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, -1.0, 0.0, -(spec.PLATE - 1.0)),
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
    if abs(com_z - spec.PLATE / 2.0) > 0.1:
        raise RuntimeError(
            f"blank centre of mass z = {com_z:.2f}, expected {spec.PLATE / 2.0:.2f}"
        )
    blank_volume = float(mass.data.volume)
    expected_blank = spec.blank_volume(DEFAULT_TEETH)
    if abs(blank_volume - expected_blank) > 0.02 * expected_blank:
        raise RuntimeError(
            f"blank volume {blank_volume:.1f} mm^3, expected {expected_blank:.1f}"
        )
    _telemetry.success(f"blank volume {blank_volume:.1f} mm^3 (com z {com_z:.2f})")

    # The radial dim was renamed D1 -> BlankRadial by blank.apply above, so the
    # captured auto-name "D1@..." would be stale -- reference the new name.
    radial_dim = f"BlankRadial@{blank_sketch}"
    ra_default_in = ra_default_mm / IN
    before = read_dimension(adapter, radial_dim)
    if abs(before - ra_default_in) < 1e-6 * ra_default_in:
        dim_unit = 1.0
    elif abs(before - ra_default_mm) < 1e-6 * ra_default_mm:
        dim_unit = IN
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
    curves = [await gap_curve(adapter, *curve) for curve in gap_curves()]
    # Whitelisted fix escalation: the gap profile is ten equation-driven
    # curves whose shape and position re-solve from the equation globals
    # on every configuration change (ToothCount 12/18/24) -- no static
    # relation/dimension scheme can define them without breaking that.
    await ensure_fully_defined(
        adapter, "gap sketch", fix_entities=curves, allow_fix_escalation=True
    )
    check("exit_sketch gap", await adapter.exit_sketch())
    # Named only, no SketchDims: the ten curves are equation-driven (they carry
    # no display dimensions), and static dims would break the per-configuration
    # re-solve of the gap.
    name_last_feature(adapter, "ToothGapProfile")
    check(
        "cut tooth gap",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.PLATE + 1.0)),
    )
    gap_cut = name_last_feature(adapter, "ToothGap")

    # ------------------------------------------------------------------
    # Pattern about Z; link the instance count to ToothCount.
    # ------------------------------------------------------------------
    pattern_axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    adapter._zoom_to_fit(adapter.currentModel)
    # The seed gap spans angles Half - Corner..Half + Corner (under 15 deg at
    # T24); the OD candidates below stay on uncut blank.
    candidates = [[0.0, 0.0, spec.PLATE / 2.0]]
    for angle_deg in (-45.0, -90.0, -135.0, 135.0, 45.0):
        a = math.radians(angle_deg)
        candidates.append(
            [ra_default_mm * math.cos(a), ra_default_mm * math.sin(a), spec.PLATE / 2.0]
        )
    pattern = None
    for point in candidates:
        # geometry_pattern: per-instance re-solve of the global-driven
        # equation-curve profile produces corrupt sliver cuts (live SW 2026
        # finding, this part); verbatim geometry copies are exact.
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point,
                features=[gap_cut],
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
    gap_pattern = name_last_feature(adapter, "ToothGapPattern")
    # Hide only now: the pattern picks the axis by screen point, which a
    # blanked axis would refuse.
    blank_reference_geometry(adapter, ((pattern_axis, "AXIS"),))
    count_dim = pattern_count_dimension(adapter, gap_pattern, DEFAULT_TEETH)
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
    expected_toothed = spec.toothed_volume(DEFAULT_TEETH)
    if abs(toothed - expected_toothed) > 0.01 * expected_toothed:
        raise RuntimeError(
            f"toothed disc volume {toothed:.1f} mm^3, analytic "
            f"{expected_toothed:.1f} -- pattern produced wrong geometry"
        )
    _telemetry.success(f"toothed disc volume {toothed:.1f} (analytic {expected_toothed:.1f})")

    # ------------------------------------------------------------------
    # Mounting interface (config-independent, after the pattern): bore +
    # two drive-pin holes on the +/-Y axis.
    # ------------------------------------------------------------------
    bore_pins = SketchDims()
    check("create_sketch bore+pins", await adapter.create_sketch("Front"))
    # Direct-to-DB: creation-time inference must not snap the circles to the
    # blank's edges on this face -- the auto-relation then makes every driving
    # point-pair dim fail (diag_onaxis_pin.py scenarios G/H vs I).
    set_sketch_direct_db(adapter, True)
    # Emission order per circle = its non-zero centre coords THEN diameter.
    # Bore is on-origin -> diameter only. Both pins sit on the +/-Y axis
    # (x = 0) -> one centre-Y dim each, then diameter. The -Y pin's centre dim
    # is an UNSIGNED distance, so it drives to the POSITIVE "PinCircleRadius".
    await define_circle(
        adapter,
        0.0,
        0.0,
        spec.BORE_DIA / 2.0,
        "bore",
        dims=bore_pins,
        names=("BoreCx", "BoreCy", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    pin_labels = ("PinPos", "PinNeg")
    for label, (x, y) in zip(pin_labels, PIN_HOLE_CENTRES, strict=True):
        await define_circle(
            adapter,
            x,
            y,
            spec.PIN_HOLE_DIA / 2.0,
            f"pin hole {label}",
            dims=bore_pins,
            names=(f"{label}X", f"{label}Y", f"{label}Dia"),
            drives=(None, '"PinCircleRadius"', '"PinHoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "bore+pins sketch")
    check("exit_sketch bore+pins", await adapter.exit_sketch())
    name_last_feature(adapter, "BorePinsProfile")
    drive_jobs += bore_pins.apply(adapter, "BorePinsProfile")
    check(
        "cut bore+pins",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=spec.PLATE + 2.0)),
    )
    name_last_feature(adapter, "BorePinsCut")

    # ------------------------------------------------------------------
    # Named mate datums (every configuration): the seat face and the two
    # drive-pin hole axes. Axis1 (the pattern axis above) is the wheel axis.
    # ------------------------------------------------------------------
    check(
        "create_plane RearFace (Front Plane + Plate)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=spec.PLATE
            )
        ),
    )
    name_last_feature(adapter, "RearFace")
    blank_reference_geometry(adapter, (("RearFace", "PLANE"),))
    rear_offset = name_dimensions(adapter, "RearFace", ["RearFaceOffset"])
    drive_jobs += [(rear_offset[0], '"Plate"')]
    for axis_name, (_x, y) in zip(
        ("PinHoleAxis1", "PinHoleAxis2"), PIN_HOLE_CENTRES, strict=True
    ):
        await name_bore_axis(
            adapter,
            "Right Plane",
            0.0,
            "Top Plane",
            y,
            axis_name,
            drive_b='"PinCircleRadius"',
            drive_jobs=drive_jobs,
        )
        name_last_feature(adapter, axis_name)

    # ------------------------------------------------------------------
    # Deferred drive batch + neutrality re-check (still at DEFAULT_TEETH, no
    # configs yet): apply every recorded equation after a rebuild, then confirm
    # the single-config geometry did not move (each equation evaluates to its
    # as-built value).
    # ------------------------------------------------------------------
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"post-drive mass properties failed: {mass.error}")
    driven = float(mass.data.volume)
    expected_driven = spec.part_volume(DEFAULT_TEETH)
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
    for name, teeth in spec.CONFIGS:
        check(
            f"create_configuration {name}",
            await adapter.create_configuration(
                CreateConfigurationParameters(
                    name=name, comment=f"{teeth}-tooth ANSI #25 sprocket"
                )
            ),
        )
    for name, teeth in spec.CONFIGS:
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
    for name, teeth in spec.CONFIGS:
        check(f"activate {name}", await adapter.set_active_configuration(name))

        count = read_dimension(adapter, count_dim)
        if abs(count - teeth) > 1e-9:
            raise RuntimeError(
                f"{name}: pattern instance count reads {count:g}, expected {teeth}"
            )
        mass = await adapter.get_mass_properties()
        if not mass.is_success:
            raise RuntimeError(f"{name}: get_mass_properties failed: {mass.error}")
        volume = float(mass.data.volume)
        expected = spec.part_volume(teeth)
        if abs(volume - expected) > 0.01 * expected:
            raise RuntimeError(
                f"{name}: volume {volume:.1f} mm^3, analytic {expected:.1f} -- "
                "regeneration produced wrong geometry"
            )
        volumes[name] = volume
        _telemetry.success(f"{name}: count {count:g}, volume {volume:.1f} (analytic {expected:.1f})")

        radial = read_dimension(adapter, radial_dim)
        ra_in = spec.outside_dia(teeth) / 2.0 / IN
        if abs(radial - ra_in * dim_unit) > 1e-4 * ra_in * dim_unit:
            raise RuntimeError(
                f"{name}: {radial_dim} reads {radial:g}, expected {ra_in * dim_unit:g}"
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

    ordered = [volumes[name] for name, _ in spec.CONFIGS]
    if not all(a < b for a, b in zip(ordered, ordered[1:], strict=False)):
        raise RuntimeError(f"volumes not monotonically increasing: {volumes}")

    first_name, _ = spec.CONFIGS[0]
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

    grouped_spec = _config.parts(PART_NAME)
    apply_grouped_bom_properties(
        adapter,
        [name for name, _teeth in spec.CONFIGS],
        part_number=str(grouped_spec.get("number", "")),
        description=str(grouped_spec.get("description", "")),
    )
    check(
        f"activate {spec.DEFAULT_CONFIG} for saved views",
        await adapter.set_active_configuration(spec.DEFAULT_CONFIG),
    )
    await report_mass_properties(adapter)
    # Manufacturing drawing support: the plate is faced never over nominal and
    # each pin centre holds its location band; the bore and pin-hole sizes are
    # drilled (the title block's DRILLED HOLES row governs them).  The places
    # are the part's (policy rule 2).
    set_dimension_bilateral_tolerance(
        adapter, "BlankProfile", "BlankWidth", *deviations(spec.PLATE_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "BorePinsProfile", "PinPosY", spec.DRIVE_PIN_OFFSET_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "BorePinsProfile", "PinNegY", spec.DRIVE_PIN_OFFSET_TOL
    )
    await assert_bands_in_every_configuration(adapter)
    apply_drawing_precision(adapter, spec.DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    # paper-drive places T12 and T18 while the part saves on T24, so their
    # saved caches are what it rebuilds: save_simplified_part reopens the file
    # and proves every configuration the way it loads them (cg-fx1: the same
    # equation-driven recipe saved cone-gear's inactive caches faulted).
    artefacts.update(
        await save_simplified_part(adapter, PART_NAME, (gap_cut, gap_pattern))
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
