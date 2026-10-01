r"""Reproduction script: translational-gearing feed-pinion sleeve (book ch. 23).

The "fifth gear" of the 4/4 video narration: "Behind and attached to the
fourth gear is the fifth gear. This gear has twelve teeth and engages the
rack." 12T at DP 30 (it MUST match the rack -- the scale anchor of ch. 23),
PD 10.160, cut on the rear end of one turned steel sleeve (MHA-110) that
runs on the fixed stud's Ø3.9 journal. In front of the teeth the sleeve
steps to the Ø10 spigot that locates the 120T disc and the Ø8.2 shank the
brass hub is pressed on; the nose stands proud of the hub as the cluster's
front thrust face (transgear_feed_pinion_spec, rulings R9-5 / R9-8).

Layout: origin on the axis at the sleeve's rear end (on the stud's Ø9 step),
+Z toward the machine front. Teeth z 0..9.5 (root at the 1.25/P full-depth
floor), spigot to SPIGOT_FRONT_STATION, shank to OVERALL_LENGTH, Ø3.9 bore
through, Ø1.2 oil hole on +Y at OIL_HOLE_Z. The form cutter's run-out slots
the spigot's rear end behind the gaps (R9-67). Datums: ``Front Plane`` is the
rear face (``RearFace``); ``GearFace`` and ``SpigotFront`` are offset
planes; ``Axis1`` is the tooth pattern's Top x Right axis.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_feed_pinion.py
"""

from __future__ import annotations

import math
import sys
from typing import Any, Callable

import _telemetry
from _common import (
    SketchDims,
    _early_bound,
    _feature_by_name,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    set_global,
    set_sketch_direct_db,
)
from _drawing_marks import (
    _named_dimension,
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _drawing_simplified import save_simplified_part
from _gear import build_fixed_gear, volume_check
from _holes import cross_hole_volume_mm3
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from transgear_feed_pinion_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    CUTTER_AXIS_R,
    CUTTER_AXIS_Z,
    CUTTER_DIA_MAX,
    DEDENDUM_FACTOR,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FULL_DEPTH,
    GAP_AZIMUTH_DEG,
    GEAR_DATA,
    GEAR_FACE_STATION,
    OIL_HOLE_DIA,
    OIL_HOLE_Z,
    OUTSIDE_DIA,
    OUTSIDE_DIA_DEVIATIONS,
    OVERALL_LENGTH,
    PRESSURE_ANGLE_DEG,
    ROOT_DIA,
    ROOT_DIA_DEVIATIONS,
    ROOT_DIA_MIN,
    ROOT_DIA_TOL_TYPE,
    RUNOUT_SLOT_END_Z,
    RUNOUT_SLOT_WIDTH,
    SHANK_DIA,
    SHANK_DIA_DEVIATIONS,
    SPIGOT_DIA,
    SPIGOT_DIA_DEVIATIONS,
    SPIGOT_FRONT_STATION,
    SURFACE_FINISHES,
    STATION_TOL,
    TEETH,
)

PART_NAME = "transgear-feed-pinion"
MATERIAL = "Plain Carbon Steel"  # contract §2.3: steel, made

# TEETH (12, the 4/4 video narration: "this gear has twelve teeth") comes from
# the spec; DP meshes the DP30 rack (the ch23 scale anchor).
DP = DIAMETRAL_PITCH
FACE_WIDTH = GEAR_FACE_STATION  # teeth from the rear face to the disc seat

# Solid volumes the gates expect (mm^3).
V_SPIGOT = math.pi * (SPIGOT_DIA / 2.0) ** 2 * (SPIGOT_FRONT_STATION - FACE_WIDTH)
V_SHANK = math.pi * (SHANK_DIA / 2.0) ** 2 * (OVERALL_LENGTH - SPIGOT_FRONT_STATION)
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * OVERALL_LENGTH
# One wall only (+Y): half the through cross-drill of the shank less the bore's.
V_OIL_HOLE = (
    cross_hole_volume_mm3(OIL_HOLE_DIA, SHANK_DIA)
    - cross_hole_volume_mm3(OIL_HOLE_DIA, BORE_DIA)
) / 2.0

_R_SPIGOT = SPIGOT_DIA / 2.0
_R_CUTTER = CUTTER_DIA_MAX / 2.0


def runout_slot_volume(steps: int = 400) -> float:
    """One run-out slot: the flat-walled RUNOUT_SLOT_WIDTH slab of the
    cutter's circle in front of the gear face, inside the spigot.  At an
    axial station z the cutter reaches down to f(z) along the gap's centre
    line; at a tangential offset t the spigot's surface stands at
    √(Rs² − t²), so the slab removes max(0, √(Rs² − t²) − f(z)) there."""
    z0, z1 = FACE_WIDTH, RUNOUT_SLOT_END_Z
    half = RUNOUT_SLOT_WIDTH / 2.0
    dz, dt = (z1 - z0) / steps, 2.0 * half / steps
    total = 0.0
    for i in range(steps):
        z = z0 + (i + 0.5) * dz
        floor = CUTTER_AXIS_R - math.sqrt(_R_CUTTER**2 - (z - CUTTER_AXIS_Z) ** 2)
        for j in range(steps):
            t = -half + (j + 0.5) * dt
            total += max(0.0, math.sqrt(_R_SPIGOT**2 - t * t) - floor)
    return total * dz * dt


V_RUNOUT_SLOT = runout_slot_volume()


def cutter_arc_points(
    to_sketch: Callable[[tuple[float, float, float]], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """``(centre, start, end)`` of the seed slot's cutter arc in sketch
    coordinates: the arc runs counter-clockwise from ``start`` round the
    cutter's far (forward) side to ``end``, both on the chord at the gear
    face, so arc + chord close the region in front of it."""
    azimuth = math.radians(GAP_AZIMUTH_DEG)
    radial = (math.cos(azimuth), math.sin(azimuth))

    def model(r: float, z: float) -> tuple[float, float, float]:
        return (r * radial[0], r * radial[1], z)

    half_chord = math.sqrt(_R_CUTTER**2 - (FACE_WIDTH - CUTTER_AXIS_Z) ** 2)
    centre = to_sketch(model(CUTTER_AXIS_R, CUTTER_AXIS_Z))
    near = to_sketch(model(CUTTER_AXIS_R - half_chord, FACE_WIDTH))
    far = to_sketch(model(CUTTER_AXIS_R + half_chord, FACE_WIDTH))
    front = to_sketch(model(CUTTER_AXIS_R, CUTTER_AXIS_Z + _R_CUTTER))

    def angle(point: tuple[float, float]) -> float:
        return math.atan2(point[1] - centre[1], point[0] - centre[0]) % math.tau

    def ccw(a: float, b: float) -> float:
        return (b - a) % math.tau

    # Counter-clockwise from `near`, the foremost point must come before `far`.
    if ccw(angle(near), angle(front)) < ccw(angle(near), angle(far)):
        return centre, near, far
    return centre, far, near


def _plane_normal(adapter: Any, name: str) -> tuple[float, float, float]:
    """A reference plane's unit normal in model coordinates (the third row of
    ``IRefPlane::Transform``'s rotation; build_crankshaft's reader)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return (data[6], data[7], data[8])


def _delete_feature(adapter: Any, name: str, kind: str) -> None:
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, kind, 0, 0, 0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"cannot select {name!r} for deletion")
    if not model.Extension.DeleteSelection2(0):
        raise RuntimeError(f"DeleteSelection2 refused {name!r}")
    model.ClearSelection2(True)


async def _gap_plane(adapter: Any, name: str) -> None:
    """The plane through the sleeve axis and the seed gap's centre line.

    ``InsertRefPlane`` has two angled solutions per magnitude; the first
    attempt is kept only if the gap's radial direction lies in it, else the
    mirror is built and proven the same way (build_crankshaft's recipe)."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    azimuth = math.radians(GAP_AZIMUTH_DEG)
    direction = (math.cos(azimuth), math.sin(azimuth), 0.0)
    for attempt, signed in enumerate((GAP_AZIMUTH_DEG, -GAP_AZIMUTH_DEG)):
        check(
            f"create_plane {name} ({signed:+.1f} deg about Axis1)",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="angle",
                    base_plane="Top Plane",
                    angle=signed,
                    pivot_axis="Axis1",
                )
            ),
        )
        name_last_feature(adapter, name)
        normal = _plane_normal(adapter, name)
        off_plane = abs(sum(n * d for n, d in zip(normal, direction, strict=True)))
        _telemetry.info(
            f"{name}: attempt {attempt + 1} normal {normal}, |n.d| = {off_plane:.3e}"
        )
        if off_plane < 1e-6:
            return
        _delete_feature(adapter, name, "PLANE")
    raise RuntimeError(f"{name}: neither angled-plane solution contains the gap")


def _sketch_mapper(
    adapter: Any, *, label: str
) -> tuple[Callable[[tuple[float, float, float]], tuple[float, float]], int]:
    """Map model points (mm) into the ACTIVE sketch through
    ``ModelToSketchTransform``; return the mapper and the sketch axis (0 = u,
    1 = v) the sleeve axis runs along.  The plane contains the axis and the
    origin, so the axis must map onto one sketch axis through the origin."""
    import pythoncom
    from win32com.client import VARIANT

    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError(f"{label}: no active sketch")
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def raw(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    origin = raw((0.0, 0.0, 0.0))
    along = raw((0.0, 0.0, 1.0))
    if max(abs(c) for c in origin) > 1e-6:
        raise RuntimeError(f"{label}: the model origin maps to {origin!r}")
    axial = [abs(along[0]), abs(along[1])]
    axis = 0 if axial[0] > 0.5 else 1
    if abs(axial[axis] - 1.0) > 1e-6 or abs(axial[1 - axis]) > 1e-6:
        raise RuntimeError(f"{label}: the sleeve axis maps to {along!r}")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        mapped = raw(model_mm)
        if abs(mapped[2]) > 1e-6:
            raise RuntimeError(f"{label}: {model_mm!r} is off the sketch plane")
        return (mapped[0], mapped[1])

    return to_sketch, axis


async def _runout_slot_seed(adapter: Any) -> list[tuple[str, str]]:
    """The seed run-out slot's cutter segment on the gap plane."""
    profile = SketchDims()
    check("create_sketch run-out slot", await adapter.create_sketch("GapPlane"))
    to_sketch, axial = _sketch_mapper(adapter, label="run-out slot sketch")
    centre, start, end = cutter_arc_points(to_sketch)
    set_sketch_direct_db(adapter, True)
    arc = check("cutter arc", await adapter.add_arc(*centre, *start, *end))
    chord = check("gear-face chord", await adapter.add_line(*end, *start))
    set_sketch_direct_db(adapter, False)
    for label, first, second, relation in (
        ("chord starts at the arc end", f"{chord}.start", f"{arc}.end", "coincident"),
        ("chord ends at the arc start", f"{chord}.end", f"{arc}.start", "coincident"),
        (
            "chord square to the axis",
            chord,
            None,
            "vertical" if axial == 0 else "horizontal",
        ),
    ):
        check(label, await adapter.add_sketch_constraint(first, second, relation))
    check(
        "cutter diameter",
        await adapter.add_sketch_dimension(arc, None, "diameter", CUTTER_DIA_MAX),
    )
    profile.record("CutterDia", '"CutterDia"')
    # The centre's two distances from the origin, horizontal then vertical:
    # the axial one is the full-depth station, the radial one the gap floor
    # plus the cutter's radius.
    await anchor_point_to_origin(adapter, f"{arc}.center", *centre, "cutter centre")
    drives = {
        "CutterAxisZ": '"FullDepth"',
        "CutterAxisR": '"RootDia" / 2 + "CutterDia" / 2',
    }
    order = (
        ("CutterAxisZ", "CutterAxisR") if axial == 0 else ("CutterAxisR", "CutterAxisZ")
    )
    for name in order:
        profile.record(name, drives[name])
    await dimension_between(
        adapter,
        f"{chord}.start",
        "origin",
        "horizontal_distance" if axial == 0 else "vertical_distance",
        FACE_WIDTH,
        "run-out slot starts at the gear face",
    )
    profile.record("SlotStart", '"FaceWidth"')
    await ensure_fully_defined(adapter, "run-out slot sketch")
    check("exit_sketch run-out slot", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutSlotProfile")
    return profile.apply(adapter, "RunoutSlotProfile")


def _as_construction(adapter, line: str) -> None:
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{line}: failed to become construction geometry")


def _root_min_limit(adapter) -> None:
    """RootDia as a single MIN limit: the cutter-depth floor the wall reads."""
    lower, upper = ROOT_DIA_DEVIATIONS
    _, dimension = _named_dimension(adapter, "SleeveProfile", "RootDia")
    label = "RootDia@SleeveProfile"
    # RootDia is driven by its global, which the build writes in inches to 8
    # decimals (8.0433334 mm against the spec's 8.0433333), so a 1e-12 m match
    # never holds; 1e-9 m is the convention every other readback here uses.
    if not math.isclose(float(dimension.SystemValue), ROOT_DIA / 1000.0, abs_tol=1e-9):
        raise RuntimeError(
            f"{label}: nominal {float(dimension.SystemValue) * 1000.0:.7f} is not "
            f"the modelled root {ROOT_DIA:.7f}"
        )
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = ROOT_DIA_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != ROOT_DIA_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MIN-limit tolerance readback changed")
    _telemetry.success(f"{label}: single limit {ROOT_DIA_MIN:.2f} MIN")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): every length carries the load-bearing
    # mm suffix (INCH document). TEETH/DP stay module constants -- the tooth
    # gap and pattern are built by build_fixed_gear with literal numerics.
    for name, value in (
        ("FaceWidth", FACE_WIDTH),
        ("OutsideDia", OUTSIDE_DIA),
        ("RootDia", ROOT_DIA),
        ("BoreDia", BORE_DIA),
        ("SpigotDia", SPIGOT_DIA),
        ("ShankDia", SHANK_DIA),
        ("SpigotFront", SPIGOT_FRONT_STATION),
        ("OverallLength", OVERALL_LENGTH),
        ("OilHoleDia", OIL_HOLE_DIA),
        ("OilHoleZ", OIL_HOLE_Z),
        ("FullDepth", FULL_DEPTH),
        ("CutterDia", CUTTER_DIA_MAX),
        ("RunoutSlotWidth", RUNOUT_SLOT_WIDTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Teeth z 0..FACE_WIDTH off the Front plane (the rear face). Root relief
    # cuts the gap floor at the 1.25/P root the sheet floors (8.04 MIN): the
    # base-chord floor would leave the rack's tips no working depth.  The
    # model cuts full depth over the whole face: behind FULL_DEPTH the
    # cutter's arc leaves the gaps up to 0.66 shallow at the gear face, clear
    # of the rack, which ends at 5.24 at its worst.
    disc = await build_fixed_gear(
        adapter,
        TEETH,
        FACE_WIDTH,
        dp=DP,
        pa_deg=PRESSURE_ANGLE_DEG,
        root_relief=True,
        dedendum=DEDENDUM_FACTOR,
    )
    volume = disc.volume
    # The tooth pattern's Top x Right axis is the part's first reference axis:
    # the sleeve axis every mate uses.
    _feature_by_name(adapter, "Axis1")

    _feature_by_name(adapter, "Boss-Extrude1").Name = "GearBlank"
    _telemetry.success("feature 'Boss-Extrude1' -> 'GearBlank'")
    drive_jobs += [
        (name_dimensions(adapter, "GearBlank", ["FaceWidth"])[0], '"FaceWidth"')
    ]
    _feature_by_name(adapter, "Sketch1").Name = "GearBlankProfile"
    _telemetry.success("feature 'Sketch1' -> 'GearBlankProfile'")
    drive_jobs += [
        (
            name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])[0],
            '"OutsideDia"',
        )
    ]

    # Spigot + shank: a revolve of a half-profile on the Right plane (local
    # x -> model -Z, local y -> model Y), so each turned diameter prints
    # beside its length on the section (rule 7). The profile starts AT the
    # tooth face, clear of the relieved gap floors (crank pinion #906).
    # Construction witnesses carry the tip, root and bore diameters.
    profile = SketchDims()
    check("create_sketch sleeve", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "sleeve axis centerline",
        await adapter.add_centerline(-FACE_WIDTH, 0.0, -OVERALL_LENGTH, 0.0),
    )
    points = [
        (-FACE_WIDTH, 0.0),
        (-FACE_WIDTH, SPIGOT_DIA / 2.0),
        (-SPIGOT_FRONT_STATION, SPIGOT_DIA / 2.0),
        (-SPIGOT_FRONT_STATION, SHANK_DIA / 2.0),
        (-OVERALL_LENGTH, SHANK_DIA / 2.0),
        (-OVERALL_LENGTH, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    outside_ref = check(
        "outside-diameter witness",
        await adapter.add_line(0.0, OUTSIDE_DIA / 2.0, -FACE_WIDTH, OUTSIDE_DIA / 2.0),
    )
    root_ref = check(
        "root-diameter witness",
        await adapter.add_line(0.0, ROOT_DIA / 2.0, -FACE_WIDTH, ROOT_DIA / 2.0),
    )
    bore_ref = check(
        "bore-diameter witness",
        await adapter.add_line(0.0, BORE_DIA / 2.0, -OVERALL_LENGTH, BORE_DIA / 2.0),
    )
    set_sketch_direct_db(adapter, False)
    for line in (outside_ref, root_ref, bore_ref):
        _as_construction(adapter, line)
    for i, line in enumerate(lines):
        (_, y1), (_, y2) = points[i], points[(i + 1) % len(lines)]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"sleeve {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    for label, line, end_point in (
        ("outside-diameter witness", outside_ref, f"{lines[0]}.start"),
        ("root-diameter witness", root_ref, f"{lines[0]}.start"),
        ("bore-diameter witness", bore_ref, f"{lines[4]}.end"),
    ):
        check(
            f"{label} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
        check(
            f"{label} starts at the rear face",
            await adapter.add_sketch_constraint(
                f"{line}.start", "origin", "vertical_points"
            ),
        )
        check(
            f"{label} ends at its feature's end",
            await adapter.add_sketch_constraint(
                f"{line}.end", end_point, "vertical_points"
            ),
        )
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", -FACE_WIDTH, 0.0, "sleeve profile anchor"
    )
    profile.record("ProfileStart", '"FaceWidth"')
    await dimension_between(
        adapter,
        f"{lines[1]}.end",
        "origin",
        "horizontal_distance",
        SPIGOT_FRONT_STATION,
        "SpigotFront",
    )
    profile.record("SpigotFront", '"SpigotFront"')
    await dimension_between(
        adapter,
        f"{lines[3]}.end",
        "origin",
        "horizontal_distance",
        OVERALL_LENGTH,
        "OverallLength",
    )
    profile.record("OverallLength", '"OverallLength"')
    for name, target, xy in (
        (
            "SpigotDia",
            lines[1],
            (-(FACE_WIDTH + SPIGOT_FRONT_STATION) / 2.0, SPIGOT_DIA / 2.0 + 5.0),
        ),
        (
            "ShankDia",
            lines[3],
            (-(SPIGOT_FRONT_STATION + OVERALL_LENGTH) / 2.0, SHANK_DIA / 2.0 + 5.0),
        ),
        (
            "OutsideDia",
            f"{outside_ref}.start",
            (-FACE_WIDTH / 2.0, OUTSIDE_DIA / 2.0 + 5.0),
        ),
        ("RootDia", f"{root_ref}.start", (-FACE_WIDTH / 2.0, -(ROOT_DIA / 2.0 + 5.0))),
        ("BoreDia", f"{bore_ref}.start", (-OVERALL_LENGTH / 2.0, BORE_DIA / 2.0 + 3.0)),
    ):
        await add_diametric_linear_dimension(adapter, axis, target, xy, name)
        profile.record(name, f'"{name}"')
    await ensure_fully_defined(adapter, "sleeve sketch")
    check("exit_sketch sleeve", await adapter.exit_sketch())
    name_last_feature(adapter, "SleeveProfile")
    drive_jobs += profile.apply(adapter, "SleeveProfile")
    check(
        "revolve sleeve", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Sleeve")
    v_sleeve = V_SPIGOT + V_SHANK
    volume = await volume_check(
        adapter, "spigot and shank", volume + v_sleeve, 0.01 * v_sleeve
    )

    # --- The form cutter's run-out slots (R9-67) -------------------------------
    await _gap_plane(adapter, "GapPlane")
    drive_jobs += await _runout_slot_seed(adapter)
    check(
        "cut seed run-out slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=RUNOUT_SLOT_WIDTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RunoutSlot")
    drive_jobs.append(
        (
            name_dimensions(adapter, "RunoutSlot", ["RunoutSlotWidth"])[0],
            '"RunoutSlotWidth"',
        )
    )
    # Each slot is only ~0.16 mm^3 (at the gear face the cutter is already
    # 0.66 up its arc, 0.32 into the Ø10), so the gates allow a quarter of it.
    volume = await volume_check(
        adapter, "seed run-out slot", volume - V_RUNOUT_SLOT, 0.25 * V_RUNOUT_SLOT
    )
    # A feature pattern, as the knob shaft's (R9-21): each instance re-cuts the
    # transformed arc-and-chord profile, whose chord lies in the gear-face
    # shoulder plane, a coplanar boundary a geometry pattern cannot re-trim.
    axis = check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    check(
        f"run-out slot pattern about {axis.name}",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_name=axis.name,
                features=["RunoutSlot"],
                count=TEETH,
                geometry_pattern=False,
            )
        ),
    )
    name_last_feature(adapter, "RunoutSlots")
    blank_reference_geometry(adapter, ((axis.name, "AXIS"),))
    volume = await volume_check(
        adapter,
        "twelve run-out slots",
        volume - (TEETH - 1) * V_RUNOUT_SLOT,
        0.25 * TEETH * V_RUNOUT_SLOT,
    )
    blank_reference_geometry(adapter, (("GapPlane", "PLANE"),))

    # Bore through (centre 0,0): define_circle emits only the diameter dim.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "bore",
        dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=OVERALL_LENGTH + 2.0)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", volume - V_BORE, 0.01 * V_BORE)

    # Oil hole (R9-8): Ø1.2 on +Y through the shank wall at OIL_HOLE_Z, where
    # the hub's own hole lands; match-drilled through both at assembly. Top
    # plane sketch (u, v) = model (X, -Z); a reversed cut runs +Y, one wall.
    oil = SketchDims()
    check("create_sketch oil hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -OIL_HOLE_Z,
        OIL_HOLE_DIA / 2.0,
        "oil hole",
        dims=oil,
        names=("OilHoleX", "OilHoleZ", "OilHoleDia"),
        drives=(None, '"OilHoleZ"', '"OilHoleDia"'),
    )
    await ensure_fully_defined(adapter, "oil hole sketch")
    check("exit_sketch oil hole", await adapter.exit_sketch())
    name_last_feature(adapter, "OilHoleProfile")
    drive_jobs += oil.apply(adapter, "OilHoleProfile")
    check(
        "cut oil hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=SHANK_DIA, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "OilHole")
    drive_jobs.append(
        (name_dimensions(adapter, "OilHole", ["OilHoleDepth"])[0], '"ShankDia"')
    )
    volume = await volume_check(
        adapter, "oil hole", volume - V_OIL_HOLE, 0.05 * V_OIL_HOLE
    )

    # Mate datums: the disc seat and the spigot front, each driven by the
    # station it sits at; the rear face is the Front Plane.
    for plane, offset, expr in (
        ("GearFace", FACE_WIDTH, '"FaceWidth"'),
        ("SpigotFront", SPIGOT_FRONT_STATION, '"SpigotFront"'),
    ):
        check(
            f"create_plane {plane}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Front Plane", offset=offset
                )
            ),
        )
        name_last_feature(adapter, plane)
        drive_jobs.append(
            (name_dimensions(adapter, plane, [f"{plane}Offset"])[0], expr)
        )
    blank_reference_geometry(adapter, (("GearFace", "PLANE"), ("SpigotFront", "PLANE")))

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven feed-pinion sleeve (equations neutral)", volume, 0.01 * V_BORE
    )

    # Bands (transgear_feed_pinion_spec): the three stations ±0.05 (R9-5), the
    # reamed bore, the spigot's slip band under the disc's reamed bore, the
    # shank's press band under the hub's reamed bore (R9-45), the tip's
    # +0/-0.10, the root as a MIN floor.
    set_dimension_symmetric_tolerance(adapter, "GearBlank", "FaceWidth", STATION_TOL)
    set_dimension_symmetric_tolerance(
        adapter, "SleeveProfile", "SpigotFront", STATION_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "SleeveProfile", "OverallLength", STATION_TOL
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "BoreDia", *BORE_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "SpigotDia", *SPIGOT_DIA_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "ShankDia", *SHANK_DIA_DEVIATIONS
    )
    set_dimension_bilateral_tolerance(
        adapter, "SleeveProfile", "OutsideDia", *OUTSIDE_DIA_DEVIATIONS
    )
    _root_min_limit(adapter)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Gear Data": GEAR_DATA, "Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_simplified_part(adapter, PART_NAME, disc.tooth_features)


if __name__ == "__main__":
    sys.exit(run_build(build))
