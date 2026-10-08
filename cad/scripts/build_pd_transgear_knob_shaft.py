r"""Reproduction script: transgear knob shaft MHA-PD-008 (book ch. 23, pp. 56-59).

One turned steel shaft on the knob axis K, front to rear: the 1/4-20 stud end
the thumbnut runs on and its thread relief, the plain Ø6.35 core the brass
drive collar (MHA-PD-022) slides on, the integral 12T DP38 pinion meshing the
120T disc, and the Ø8.5 journal running in the arm plate's bore, carrying the
MHA-PD-016 cup on its rear extension.  Every number and the part frame live in
``pd_transgear_knob_shaft_spec`` (contract §1.1, round 10; R9-70 K-1).

Layout: axis local +Z (machine +Z, rearward), origin on the 12T's front face
F (the Front Plane).

* ``GearBlank`` + the seed gap and its pattern: the 12T, z 0..FACE_WIDTH,
  root-relieved to the shifted full-depth gap floor (``_gear.build_fixed_gear``).
* ``StudProfile``: the revolve in front of F -- the Ø6.35 core, the thread
  relief, the Ø6.22 thread blank and the 45-degree tip chamfer; a
  construction witness carries the tooth-tip blank (OutsideDia).
* ``JournalProfile``: the Ø8.5 journal revolve behind the teeth.
* ``RunoutSlot`` + its pattern: the form cutter's run-out behind the
  full-depth station (R9-21), twelve hidden slots in the journal's front end
  under the thrust ring, one per gap.  The seed is the Ø1.25 in cutter's
  circle at the nominal full-depth station, cut behind the rear tooth ends
  on the plane through the axis and the seed gap's centre line.

Datums: ``Axis1`` (the tooth pattern's axis, the shaft axis); ``Front
Plane`` = F; planes ``PinionRear``, ``RearFace``, ``ThreadEnd`` and
``StudTip``.  The Ø1.6 spring-pin holes are drilled at assembly and are not
modelled: through the core along the collar's rear slot (R9-6) and through
the cup and journal for MHA-VN-048 (R9-70, K-1).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_knob_shaft.py
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
    set_dimension_prefix,
    set_dimension_symmetric_tolerance,
)
from _drawing_simplified import save_simplified_part
from _fit_limits import deviations
from _gear import build_fixed_gear, volume_check
from _part_pmi import author_part_pmi
from _visibility import blank_reference_geometry
from pd_transgear_knob_shaft_spec import (
    CORE_DIA,
    CORE_DIA_BAND,
    CORE_LENGTH,
    CUTTER_AXIS_R,
    CUTTER_AXIS_Z,
    CUTTER_DIA_MAX,
    CUTTER_RUNOUT_DEVIATIONS,
    CUTTER_RUNOUT_MAX,
    CUTTER_RUNOUT_PLACES,
    CUTTER_RUNOUT_PREFIX,
    CUTTER_RUNOUT_TOL_TYPE,
    DEDENDUM_FACTOR,
    DIAMETRAL_PITCH,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FACE_WIDTH,
    FULL_DEPTH,
    FULL_DEPTH_BAND,
    FULL_DEPTH_PREFIX,
    GAP_AZIMUTH_DEG,
    GEAR_DATA,
    JOURNAL_DIA,
    JOURNAL_DIA_BAND,
    JOURNAL_LENGTH,
    OUTSIDE_DIA,
    PINION_REAR_Z,
    PLAIN_CORE,
    PRESSURE_ANGLE_DEG,
    PROFILE_SHIFT,
    REAR_END_Z,
    RELIEF_DIA,
    ROOT_DIA,
    RUNOUT_SLOT_END_Z,
    RUNOUT_SLOT_WIDTH,
    SURFACE_FINISHES,
    TEETH,
    THREAD_BLANK_DIA,
    THREAD_BLANK_DIA_BAND,
    THREAD_END_Z,
    TIP_CHAMFER,
    TIP_STATION,
    TIP_Z,
)

PART_NAME = "pd-transgear-knob-shaft"
MATERIAL = "Plain Carbon Steel"  # contract §1.1: steel, made

_R_CORE = CORE_DIA / 2.0
_R_RELIEF = RELIEF_DIA / 2.0
_R_BLANK = THREAD_BLANK_DIA / 2.0
_R_JOURNAL = JOURNAL_DIA / 2.0
_R_CUTTER = CUTTER_DIA_MAX / 2.0

# Solid volumes the gates expect (mm^3).
V_STUD = (
    math.pi * _R_CORE**2 * CORE_LENGTH
    + math.pi * _R_RELIEF**2 * (PLAIN_CORE - CORE_LENGTH)
    + math.pi * _R_BLANK**2 * (TIP_STATION - PLAIN_CORE)
    - math.pi * TIP_CHAMFER**2 * (_R_BLANK - TIP_CHAMFER / 3.0)
)
V_JOURNAL = math.pi * _R_JOURNAL**2 * JOURNAL_LENGTH


def runout_slot_volume(steps: int = 400) -> float:
    """One run-out slot: the flat-walled RUNOUT_SLOT_WIDTH slab of the
    cutter's circle behind the rear tooth ends, inside the journal.  At an
    axial station z the cutter reaches down to f(z) along the gap's centre
    line; at a tangential offset t the journal's surface stands at
    √(Rj² − t²), so the slab removes max(0, √(Rj² − t²) − f(z)) there."""
    z0, z1 = PINION_REAR_Z, RUNOUT_SLOT_END_Z
    half = RUNOUT_SLOT_WIDTH / 2.0
    dz, dt = (z1 - z0) / steps, 2.0 * half / steps
    total = 0.0
    for i in range(steps):
        z = z0 + (i + 0.5) * dz
        floor = CUTTER_AXIS_R - math.sqrt(_R_CUTTER**2 - (z - CUTTER_AXIS_Z) ** 2)
        for j in range(steps):
            t = -half + (j + 0.5) * dt
            total += max(0.0, math.sqrt(_R_JOURNAL**2 - t * t) - floor)
    return total * dz * dt


V_RUNOUT_SLOT = runout_slot_volume()


def cutter_arc_points(
    to_sketch: Callable[[tuple[float, float, float]], tuple[float, float]],
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """``(centre, start, end)`` of the seed slot's cutter arc in sketch
    coordinates: the arc runs counter-clockwise from ``start`` round the
    cutter's far (rearward) side to ``end``, both on the chord at the rear
    tooth ends, so arc + chord close the region behind them."""
    azimuth = math.radians(GAP_AZIMUTH_DEG)
    radial = (math.cos(azimuth), math.sin(azimuth))

    def model(r: float, z: float) -> tuple[float, float, float]:
        return (r * radial[0], r * radial[1], z)

    half_chord = math.sqrt(_R_CUTTER**2 - (PINION_REAR_Z - CUTTER_AXIS_Z) ** 2)
    centre = to_sketch(model(CUTTER_AXIS_R, CUTTER_AXIS_Z))
    near = to_sketch(model(CUTTER_AXIS_R - half_chord, PINION_REAR_Z))
    far = to_sketch(model(CUTTER_AXIS_R + half_chord, PINION_REAR_Z))
    back = to_sketch(model(CUTTER_AXIS_R, CUTTER_AXIS_Z + _R_CUTTER))

    def angle(point: tuple[float, float]) -> float:
        return math.atan2(point[1] - centre[1], point[0] - centre[0]) % math.tau

    def ccw(a: float, b: float) -> float:
        return (b - a) % math.tau

    # Counter-clockwise from `near`, the rearmost point must come before `far`.
    if ccw(angle(near), angle(back)) < ccw(angle(near), angle(far)):
        return centre, near, far
    return centre, far, near


def _plane_normal(adapter: Any, name: str) -> tuple[float, float, float]:
    """A reference plane's unit normal in model coordinates (the third row of
    ``IRefPlane::Transform``'s rotation; build_dt_crankshaft's reader)."""
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
    """The plane through the shaft axis and the seed gap's centre line.

    ``InsertRefPlane`` has two angled solutions per magnitude; the first
    attempt is kept only if the gap's radial direction lies in it, else the
    mirror is built and proven the same way (build_dt_crankshaft's recipe)."""
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
    1 = v) the shaft axis runs along.  The plane contains the axis and the
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
        raise RuntimeError(f"{label}: the shaft axis maps to {along!r}")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        mapped = raw(model_mm)
        if abs(mapped[2]) > 1e-6:
            raise RuntimeError(f"{label}: {model_mm!r} is off the sketch plane")
        return (mapped[0], mapped[1])

    return to_sketch, axis


def _as_construction(adapter: Any, line: str) -> None:
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{line}: failed to become construction geometry")


async def _stud_profile(adapter: Any) -> list[tuple[str, str]]:
    """The revolve in front of F.  Right sketch (u, v) maps to model (-Z, Y),
    so the stud (model z < 0) lies at positive u."""
    profile = SketchDims()
    check("create_sketch stud", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "stud axis centerline", await adapter.add_centerline(0.0, 0.0, TIP_STATION, 0.0)
    )
    # The core steps down to the thread relief, which steps up at the
    # full-thread end to the thread blank; the blank runs to the tip chamfer.
    points = [
        (0.0, 0.0),
        (0.0, _R_CORE),
        (CORE_LENGTH, _R_CORE),
        (CORE_LENGTH, _R_RELIEF),
        (PLAIN_CORE, _R_RELIEF),
        (PLAIN_CORE, _R_BLANK),
        (TIP_STATION - TIP_CHAMFER, _R_BLANK),
        (TIP_STATION, _R_BLANK - TIP_CHAMFER),
        (TIP_STATION, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    outside = check(
        "tooth-tip blank witness",
        await adapter.add_line(0.0, OUTSIDE_DIA / 2.0, -FACE_WIDTH, OUTSIDE_DIA / 2.0),
    )
    # R9-21: the cutter's full-depth station and run-out limit, from F along
    # the tooth tips' lower line, so each baseline dimension below the side
    # view rises from the part's edge.
    tip_v = -OUTSIDE_DIA / 2.0
    runout_ref = check(
        "run-out-limit witness",
        await adapter.add_line(0.0, tip_v, -CUTTER_RUNOUT_MAX, tip_v),
    )
    full_depth_ref = check(
        "full-depth witness", await adapter.add_line(0.0, tip_v, -FULL_DEPTH, tip_v)
    )
    set_sketch_direct_db(adapter, False)
    for line in (outside, runout_ref, full_depth_ref):
        _as_construction(adapter, line)
    (
        front_face,
        core,
        core_step,
        relief,
        thread_end,
        blank,
        chamfer,
        tip_face,
        axis_edge,
    ) = lines
    for line, relation in (
        (front_face, "vertical"),
        (core, "horizontal"),
        (core_step, "vertical"),
        (relief, "horizontal"),
        (thread_end, "vertical"),
        (blank, "horizontal"),
        (tip_face, "vertical"),
        (axis_edge, "horizontal"),
        (outside, "horizontal"),
        (runout_ref, "horizontal"),
        (full_depth_ref, "horizontal"),
    ):
        check(
            f"stud profile {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "tip witness starts at F",
        await adapter.add_sketch_constraint(
            f"{outside}.start", "origin", "vertical_points"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{front_face}.start", 0.0, 0.0, "stud profile at F"
    )
    await dimension_between(
        adapter,
        f"{tip_face}.end",
        "origin",
        "horizontal_distance",
        TIP_STATION,
        "stud TipStation",
    )
    profile.record("TipStation", '"TipStation"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "horizontal_distance",
        TIP_CHAMFER,
        "stud TipChamfer",
    )
    profile.record("TipChamfer", '"TipChamfer"')
    await dimension_between(
        adapter,
        f"{chamfer}.start",
        f"{chamfer}.end",
        "vertical_distance",
        TIP_CHAMFER,
        "stud tip chamfer rise",
    )
    profile.record("TipChamferRise", '"TipChamfer"')
    for name, line, value in (
        ("CoreLength", core_step, CORE_LENGTH),
        ("PlainCore", thread_end, PLAIN_CORE),
    ):
        await dimension_between(
            adapter,
            f"{line}.start",
            "origin",
            "horizontal_distance",
            value,
            f"stud {name}",
        )
        profile.record(name, f'"{name}"')
    await dimension_between(
        adapter,
        f"{outside}.start",
        f"{outside}.end",
        "horizontal_distance",
        FACE_WIDTH,
        "tooth-tip witness span",
    )
    profile.record("BlankSpan", '"FaceWidth"')
    for name, target, xy in (
        ("CoreDia", core, (CORE_LENGTH / 2.0, _R_CORE + 5.0)),
        ("ReliefDia", relief, ((CORE_LENGTH + PLAIN_CORE) / 2.0, _R_RELIEF + 5.0)),
        (
            "ThreadBlankDia",
            blank,
            ((PLAIN_CORE + TIP_STATION) / 2.0, _R_BLANK + 5.0),
        ),
        (
            "OutsideDia",
            f"{outside}.start",
            (-FACE_WIDTH / 2.0, OUTSIDE_DIA / 2.0 + 5.0),
        ),
    ):
        await add_diametric_linear_dimension(adapter, axis, target, xy, name)
        profile.record(name, f'"{name}"')
    check(
        "full-depth witness starts on the run-out witness",
        await adapter.add_sketch_constraint(
            f"{full_depth_ref}.start", f"{runout_ref}.start", "coincident"
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{runout_ref}.start", 0.0, tip_v, "witnesses on the tip line"
    )
    profile.record("WitnessDrop", '"OutsideDia" / 2')
    for name, line, value, drive in (
        ("FullDepth", full_depth_ref, FULL_DEPTH, '"FullDepth"'),
        ("CutterRunout", runout_ref, CUTTER_RUNOUT_MAX, '"CutterRunoutMax"'),
    ):
        await dimension_between(
            adapter, f"{line}.end", "origin", "horizontal_distance", value, name
        )
        profile.record(name, drive)
    await ensure_fully_defined(adapter, "stud sketch")
    check("exit_sketch stud", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    return profile.apply(adapter, "StudProfile")


def _runout_max_limit(adapter: Any) -> None:
    """CutterRunout as the single limit "10.50 MAX" (swTolMAX): SolidWorks
    prints the nominal then the limit word, so the nominal is the limit; the
    deviations stay on the native tolerance as the model's record of the
    band."""
    lower, upper = CUTTER_RUNOUT_DEVIATIONS
    _, dimension = _named_dimension(adapter, "StudProfile", "CutterRunout")
    label = "CutterRunout@StudProfile"
    if not math.isclose(
        float(dimension.SystemValue), CUTTER_RUNOUT_MAX / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"{label}: nominal is not the run-out limit")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = CUTTER_RUNOUT_TOL_TYPE
    if not tolerance.SetValues(lower / 1000.0, upper / 1000.0):
        raise RuntimeError(f"{label}: SetValues rejected {lower:+g}/{upper:+g} mm")
    if (
        int(tolerance.Type) != CUTTER_RUNOUT_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
    ):
        raise RuntimeError(f"{label}: MAX-limit tolerance readback changed")
    _telemetry.success(
        f"{label}: single limit {CUTTER_RUNOUT_MAX:.{CUTTER_RUNOUT_PLACES}f} MAX"
    )


async def _journal_profile(adapter: Any) -> list[tuple[str, str]]:
    """The Ø8.5 journal behind the teeth: Right sketch, u = -z."""
    profile = SketchDims()
    check("create_sketch journal", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "journal axis centerline",
        await adapter.add_centerline(-PINION_REAR_Z, 0.0, -REAR_END_Z, 0.0),
    )
    points = [
        (-PINION_REAR_Z, 0.0),
        (-PINION_REAR_Z, _R_JOURNAL),
        (-REAR_END_Z, _R_JOURNAL),
        (-REAR_END_Z, 0.0),
    ]
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for i, line in enumerate(lines):
        (_, y1), (_, y2) = points[i], points[(i + 1) % len(lines)]
        relation = "horizontal" if y1 == y2 else "vertical"
        check(
            f"journal {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    await anchor_point_to_origin(
        adapter, f"{lines[0]}.start", -PINION_REAR_Z, 0.0, "journal at the rear teeth"
    )
    profile.record("ProfileStart", '"FaceWidth"')
    await dimension_between(
        adapter,
        f"{lines[1]}.start",
        f"{lines[1]}.end",
        "horizontal_distance",
        JOURNAL_LENGTH,
        "journal JournalLength",
    )
    profile.record("JournalLength", '"JournalLength"')
    await add_diametric_linear_dimension(
        adapter,
        axis,
        lines[1],
        (-(PINION_REAR_Z + REAR_END_Z) / 2.0, _R_JOURNAL + 5.0),
        "JournalDia",
    )
    profile.record("JournalDia", '"JournalDia"')
    await ensure_fully_defined(adapter, "journal sketch")
    check("exit_sketch journal", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalProfile")
    return profile.apply(adapter, "JournalProfile")


async def _runout_slot_seed(adapter: Any) -> list[tuple[str, str]]:
    """The seed run-out slot's cutter segment on the gap plane."""
    profile = SketchDims()
    check("create_sketch run-out slot", await adapter.create_sketch("GapPlane"))
    to_sketch, axial = _sketch_mapper(adapter, label="run-out slot sketch")
    centre, start, end = cutter_arc_points(to_sketch)
    set_sketch_direct_db(adapter, True)
    arc = check("cutter arc", await adapter.add_arc(*centre, *start, *end))
    chord = check("rear tooth-end chord", await adapter.add_line(*end, *start))
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
        PINION_REAR_Z,
        "run-out slot starts at the rear tooth ends",
    )
    profile.record("SlotStart", '"FaceWidth"')
    await ensure_fully_defined(adapter, "run-out slot sketch")
    check("exit_sketch run-out slot", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutSlotProfile")
    return profile.apply(adapter, "RunoutSlotProfile")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the mm suffix is load-bearing (INCH
    # document).  TEETH/DP stay module constants -- the teeth are built by
    # build_fixed_gear with literal numerics.
    for name, value in (
        ("FaceWidth", FACE_WIDTH),
        ("OutsideDia", OUTSIDE_DIA),
        ("RootDia", ROOT_DIA),
        ("CoreDia", CORE_DIA),
        ("CoreLength", CORE_LENGTH),
        ("ReliefDia", RELIEF_DIA),
        ("PlainCore", PLAIN_CORE),
        ("ThreadBlankDia", THREAD_BLANK_DIA),
        ("TipStation", TIP_STATION),
        ("TipChamfer", TIP_CHAMFER),
        ("JournalDia", JOURNAL_DIA),
        ("JournalLength", JOURNAL_LENGTH),
        ("FullDepth", FULL_DEPTH),
        ("CutterRunoutMax", CUTTER_RUNOUT_MAX),
        ("CutterDia", CUTTER_DIA_MAX),
        ("RunoutSlotWidth", RUNOUT_SLOT_WIDTH),
    ):
        await set_global(adapter, name, f"{value}mm")

    drive_jobs: list[tuple[str, str]] = []

    # --- The 12T, z 0..FACE_WIDTH off the Front plane (F) ---------------------
    # Shift thickens the involutes and raises tip/root together. The gap's
    # root relief and the journal run-out both read ROOT_DIA from the spec.
    disc = await build_fixed_gear(
        adapter,
        TEETH,
        FACE_WIDTH,
        dp=DIAMETRAL_PITCH,
        pa_deg=PRESSURE_ANGLE_DEG,
        root_relief=True,
        dedendum=DEDENDUM_FACTOR,
        profile_shift=PROFILE_SHIFT,
    )
    volume = disc.volume
    # The tooth pattern's Top x Right axis is the part's first reference axis:
    # the shaft axis every mate uses.
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

    # --- Stud end and plain core in front of F --------------------------------
    drive_jobs += await _stud_profile(adapter)
    check("revolve stud", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stud")
    volume = await volume_check(
        adapter, "core and stud end", volume + V_STUD, 0.005 * V_STUD
    )

    # --- Journal behind the teeth ---------------------------------------------
    drive_jobs += await _journal_profile(adapter)
    check(
        "revolve journal", await adapter.create_revolve(RevolveParameters(angle=360.0))
    )
    name_last_feature(adapter, "Journal")
    volume = await volume_check(
        adapter, "journal", volume + V_JOURNAL, 0.005 * V_JOURNAL
    )

    # --- The form cutter's run-out slots (R9-21) -------------------------------
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
    volume = await volume_check(
        adapter, "seed run-out slot", volume - V_RUNOUT_SLOT, 0.05 * V_RUNOUT_SLOT
    )
    # A feature pattern, not _gear.pattern_about_z's geometry pattern, which
    # failed natively here (run 20261001T011714683Z).  The likely cause is the
    # seed's chord lying in the journal's front shoulder plane, a coplanar
    # boundary a geometry copy cannot re-trim; each instance here re-cuts the
    # transformed arc-and-chord profile instead.
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
        0.05 * TEETH * V_RUNOUT_SLOT,
    )
    blank_reference_geometry(adapter, (("GapPlane", "PLANE"),))

    # --- Mate datums along the axis, each driven by its station ---------------
    stations = (
        ("PinionRear", PINION_REAR_Z, '"FaceWidth"'),
        ("RearFace", REAR_END_Z, '"FaceWidth" + "JournalLength"'),
        ("ThreadEnd", THREAD_END_Z, '"PlainCore"'),
        ("StudTip", TIP_Z, '"TipStation"'),
    )
    for plane, offset, expr in stations:
        check(
            f"create_plane {plane} (Front Plane {offset:+g})",
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
    blank_reference_geometry(adapter, tuple((p, "PLANE") for p, _, _ in stations))

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knob shaft (equations neutral)", volume, 0.005 * V_JOURNAL
    )
    _telemetry.info(
        f"knob shaft: run-out slots end F + {RUNOUT_SLOT_END_Z:.2f}"
    )

    # Bands (pd_transgear_knob_shaft_spec): the sliding core and the running
    # journal carry their fits, the thread blank its 2A-major band, the
    # journal length its title-block .XXX row (the cup is set on a feeler at
    # fit-up, R9-70 K-1), the cutter's full-depth station its .XXX band
    # and its run-out a MAX limit (R9-21); the rest print at the title block's
    # rows for the places they are authored at.
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "CoreDia", *deviations(CORE_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "StudProfile", "ThreadBlankDia", *deviations(THREAD_BLANK_DIA_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "JournalProfile", "JournalDia", *deviations(JOURNAL_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "StudProfile", "FullDepth", FULL_DEPTH_BAND
    )
    _runout_max_limit(adapter)
    # Each cutter station names itself: neither ends at a drawn edge.
    set_dimension_prefix(adapter, "StudProfile", "FullDepth", FULL_DEPTH_PREFIX)
    set_dimension_prefix(adapter, "StudProfile", "CutterRunout", CUTTER_RUNOUT_PREFIX)

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
