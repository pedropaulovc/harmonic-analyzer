r"""Reproduction script: transgear disc hub (MHA-PD-17; ch. 23; 1 used).

The turned brass hub and flange whose reamed round bore slides on the pinion
sleeve's (MHA-PD-10) boss. Its rear spigot passes the reducer disc's
(MHA-PD-06) bore, which it clears, and seats on the sleeve's step; the
flange's rear face clamps the disc's front face and three #0-80 fillister
screws (MHA-PD-VN-55) hold them.  One 1/16 dowel (MHA-PD-VN-69), pressed
from +X into a .0615 chord ream on local -Y to its stop, lies along the
sleeve's D-flat and keys the hub in rotation
(``pd_transgear_disc_hub_spec``, ``pd_transgear_disc_hub_geometry``).

Layout (the spec's frame): the spigot, flange and hub body are one turned
profile on the Top plane, (u, v) = model (X, -Z), revolved about the gear
axis, so the sheet's edge view carries all three turned diameters (policy
drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The spigot runs z = 0..SPIGOT_LENGTH, the flange
z = -FLANGE_THICK..0 and the hub body forward to the hub front face, so
``Front Plane`` (z = 0) is the flange's rear face, the one that clamps the
disc, and the spigot's and flange's printed lengths run from it.  The
overall, spigot end to hub front face, is printed, as is the spigot length,
both terms of the disc cluster stack.  The bore is one Front-plane round
cut through the whole part.  The three screw holes lie on a construction
bolt circle whose driving diameter is the printed Ø.75.  The key pin's
chord hole is a revolve cut on a hidden plane through its station, parallel
to local X on -Y: the .0615 ream from past the +X O.D. to its stop, the
#56 knockout on past the -X O.D., so section A-A, cut on that plane,
prints its sizes, its chord offset and its stop from the hub axis.  A hidden
construction reference line on the hub's +X O.D. line carries the station
from the hub front face for the sheet.  The radial oil hole is a Top-plane
cut toward +Y through the wall at the same station (R9-60).  ``Axis1``
is the gear axis (Top
Plane ∩ Right Plane); the paper-drive assembly mates it to the sleeve's axis
and the Front Plane to the disc's front face, unrotated.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_disc_hub.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_circle import define_circle
from _drawing_dimension_insert import add_diametric_linear_dimension
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _visibility import blank_reference_geometry
from pd_transgear_disc_hub_geometry import (
    BOLT_CIRCLE_DIA,
    BOLT_CIRCLE_X_FACTOR,
    BOLT_CIRCLE_Y_FACTOR,
    screw_centres,
)
from pd_transgear_disc_hub_spec import (
    BORE_DEVIATIONS,
    BORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FLANGE_DIA,
    FLANGE_THICK,
    HUB_BODY_LENGTH,
    HUB_DIA,
    HUB_FRONT_Z,
    HUB_LENGTH,
    HUB_LENGTH_BAND,
    KEY_PIN_CHORD_OFFSET,
    KEY_PIN_DRILL_DIA,
    KEY_PIN_HOLE_DEVIATIONS,
    KEY_PIN_HOLE_DIA,
    KEY_PIN_LOCATION_BAND,
    KEY_PIN_STATION,
    KEY_PIN_STOP,
    KEY_PIN_Z,
    OIL_HOLE_DIA,
    REFERENCE_SKETCHES,
    SCREW_HOLE_DIA,
    SPIGOT_DIA,
    SPIGOT_DIA_DEVIATIONS,
    SPIGOT_LENGTH,
    SPIGOT_LENGTH_BAND,
    UNIT,
)

PART_NAME = "pd-transgear-disc-hub"
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


def chord_hole_volume(
    offset: float,
    segments: tuple[tuple[float, float, float], ...],
    inner: float,
    outer: float,
) -> float:
    """Volume a stepped hole on a chord removes from a tube wall.

    The hole runs parallel to X at ``offset`` from the tube's axis, as
    ``segments`` of (x0, x1, radius).  Across the hole at offset ``t`` from
    its axis (the wall's y = offset + t) the tube's wall spans
    √(inner² − y²) <= |x| <= √(outer² − y²), so each strip of width
    2·√(radius² − t²) removes that span's overlap with the segment exactly;
    midpoint quadrature across the hole to well under the volume gate's
    tolerance.
    """
    steps = 2000
    total = 0.0
    for x0, x1, radius in segments:
        width = 2.0 * radius / steps
        for i in range(steps):
            t = -radius + (i + 0.5) * width
            y = offset + t
            if y * y >= outer * outer:
                continue
            far = math.sqrt(outer * outer - y * y)
            near = math.sqrt(inner * inner - y * y) if y * y < inner * inner else 0.0
            span = sum(
                max(0.0, min(x1, hi) - max(x0, lo))
                for lo, hi in ((-far, -near), (near, far))
            )
            total += 2.0 * math.sqrt(radius * radius - t * t) * span * width
    return total


V_SPIGOT = math.pi * SPIGOT_R**2 * SPIGOT_LENGTH
V_FLANGE = math.pi * FLANGE_R**2 * FLANGE_THICK
V_HUB_BODY = math.pi * HUB_R**2 * HUB_BODY_LENGTH
V_BORE = math.pi * BORE_R**2 * HUB_LENGTH
V_SCREW_HOLES = len(screw_centres()) * math.pi * SCREW_HOLE_R**2 * FLANGE_THICK
V_OIL_HOLE = radial_hole_volume(OIL_HOLE_R, BORE_R, HUB_R)
# The key pin's chord hole: the ream from past the +X O.D. to its stop, the
# #56 knockout from the stop on past the -X O.D.
_KEY_PIN_OVERRUN = 1.0
_KEY_PIN_OUT = HUB_R + _KEY_PIN_OVERRUN
V_KEY_PIN_HOLE = chord_hole_volume(
    KEY_PIN_CHORD_OFFSET,
    (
        (-KEY_PIN_STOP, _KEY_PIN_OUT, KEY_PIN_HOLE_DIA / 2.0),
        (-_KEY_PIN_OUT, -KEY_PIN_STOP, KEY_PIN_DRILL_DIA / 2.0),
    ),
    BORE_R,
    HUB_R,
)
V_FINAL = (
    V_SPIGOT
    + V_FLANGE
    + V_HUB_BODY
    - V_BORE
    - V_SCREW_HOLES
    - V_OIL_HOLE
    - V_KEY_PIN_HOLE
)

# The Top-plane sketch's (u, v) is model (X, -Z): the spigot's end at
# v = -SPIGOT_LENGTH, the hub front face at v = -HUB_FRONT_Z.
_SPIGOT_END_V = -SPIGOT_LENGTH
_HUB_FRONT_V = -HUB_FRONT_Z
_KEY_PIN_V = -KEY_PIN_Z
_KEY_PIN_PLANE = "KeyPinStationPlane"


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


async def _key_pin_reference(adapter) -> list[tuple[str, str]]:
    """The hidden ``KeyPinReference`` sketch on the Top plane: one
    construction line on the hub's +X O.D. line from the hub front face back
    to the key-pin hole's axis, whose driving dimension is the printed
    station; returns its deferred drive jobs (the station, then the start
    point's two origin anchors)."""
    sketch = REFERENCE_SKETCHES[0]
    start, end = (HUB_R, _HUB_FRONT_V), (HUB_R, _KEY_PIN_V)
    check(f"create_sketch {sketch}", await adapter.create_sketch("Top"))
    # Direct-to-DB: the line lies on the O.D. outline and runs along the
    # sketch's v axis, so creation-time inference would add relations that
    # over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(*start, *end))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} vertical",
        await adapter.add_sketch_constraint(line, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        KEY_PIN_STATION,
        "key-pin station from the hub front face",
    )
    await anchor_point_to_origin(
        adapter, f"{line}.start", *start, "key-pin station datum at hub front"
    )
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    full = name_dimensions(
        adapter,
        sketch,
        ["KeyPinStation", "KeyPinStationAnchor1", "KeyPinStationAnchor2"],
    )
    return list(
        zip(
            full,
            ('"KeyPinStation"', '"HubDia" / 2', '"HubLength" - "SpigotLength"'),
            strict=True,
        )
    )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    An offset plane's sketch axes are SolidWorks' choice; the profile points
    go through ``ModelToSketchTransform`` so only the orientation (which
    relations read horizontal/vertical) is assumed, and it is checked here
    (build_pd_transgear_arm_plate).
    """
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

    base = raw((0.0, 0.0, 0.0))
    for axis, want in ((u_axis, 0), (v_axis, 1)):
        unit = [0.0, 0.0, 0.0]
        unit[axis] = 1.0
        moved = raw(tuple(unit))
        delta = [m - b for m, b in zip(moved, base, strict=True)]
        if abs(abs(delta[want]) - 1.0) > 1e-6:
            raise RuntimeError(
                f"{label}: model axis {axis} maps to sketch {delta!r}, not along "
                f"sketch {'uv'[want]}"
            )

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, float]:
        u, v, w = raw(model_mm)
        if abs(w) > 1e-4:
            raise RuntimeError(f"{label}: {model_mm} is {w:g} mm off the sketch")
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


def _key_pin_profile_points() -> list[tuple[float, float]]:
    """The chord hole's half profile in model (X, Y) at its station: the
    ream's rim from past the +X O.D. to the stop, the stop's shoulder, the
    #56 knockout's rim on past the -X O.D., back along the hole's axis."""
    axis_y = -KEY_PIN_CHORD_OFFSET
    ream_y = axis_y - KEY_PIN_HOLE_DIA / 2.0
    drill_y = axis_y - KEY_PIN_DRILL_DIA / 2.0
    return [
        (_KEY_PIN_OUT, axis_y),
        (_KEY_PIN_OUT, ream_y),
        (-KEY_PIN_STOP, ream_y),
        (-KEY_PIN_STOP, drill_y),
        (-_KEY_PIN_OUT, drill_y),
        (-_KEY_PIN_OUT, axis_y),
    ]


async def _key_pin_hole(adapter) -> list[tuple[str, str]]:
    """The key pin's chord hole, the drive collar's flat-pin way: on a plane
    through the station (section A-A's cutting plane, so the hole's marked
    sizes and locations print there), a stepped half profile beside the
    hole's centreline parallel to model X at y = -KEY_PIN_CHORD_OFFSET,
    revolved about that line.  The plane's offset follows the reference
    sketch's station; the chord and the stop run from the sketch origin, the
    hub axis."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create_plane {_KEY_PIN_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=KEY_PIN_Z
            )
        ),
    )
    name_last_feature(adapter, _KEY_PIN_PLANE)
    jobs = [
        (
            name_dimensions(adapter, _KEY_PIN_PLANE, ["KeyPinZ"])[0],
            '"HubLength" - "SpigotLength" - "KeyPinStation"',
        )
    ]
    blank_reference_geometry(adapter, ((_KEY_PIN_PLANE, "PLANE"),))

    hole = SketchDims()
    check("create_sketch key-pin hole", await adapter.create_sketch(_KEY_PIN_PLANE))
    # Model X runs along the sketch's u, model Y along its v.
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label="key-pin hole")
    origin = to_sketch((0.0, 0.0, KEY_PIN_Z))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"key-pin hole: sketch origin maps to {origin}")
    model = _key_pin_profile_points()
    points = [to_sketch((x, y, KEY_PIN_Z)) for x, y in model]
    set_sketch_direct_db(adapter, True)
    axis = check(
        "key-pin hole centreline",
        await adapter.add_centerline(*points[-1], *points[0]),
    )
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    for index, line in enumerate(lines):
        (x0, _), (x1, _) = model[index], model[(index + 1) % len(lines)]
        relation = "vertical" if x0 == x1 else "horizontal"
        check(
            f"key-pin hole {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        "key-pin hole centreline horizontal",
        await adapter.add_sketch_constraint(axis, None, "horizontal"),
    )
    _out_end, ream, stop, drill, _in_end, _on_axis = lines
    await dimension_between(
        adapter,
        f"{_out_end}.start",
        "origin",
        "vertical_distance",
        KEY_PIN_CHORD_OFFSET,
        "key-pin chord from the hub axis",
    )
    hole.record("KeyPinChord", '"KeyPinChord"')
    await dimension_between(
        adapter,
        f"{stop}.start",
        "origin",
        "horizontal_distance",
        KEY_PIN_STOP,
        "key-pin ream stop from the hub axis",
    )
    hole.record("KeyPinStop", '"KeyPinStop"')
    await dimension_between(
        adapter,
        f"{ream}.start",
        f"{ream}.end",
        "horizontal_distance",
        _KEY_PIN_OUT + KEY_PIN_STOP,
        "key-pin ream run from past the O.D.",
    )
    hole.record("KeyPinReamRun")
    await dimension_between(
        adapter,
        f"{drill}.start",
        f"{drill}.end",
        "horizontal_distance",
        _KEY_PIN_OUT - KEY_PIN_STOP,
        "key-pin knockout run past the O.D.",
    )
    hole.record("KeyPinDrillRun")
    ream_text = to_sketch((_KEY_PIN_OUT / 2.0, model[1][1] - 2.0, KEY_PIN_Z))
    await add_diametric_linear_dimension(adapter, axis, ream, ream_text, "KeyPinDia")
    hole.record("KeyPinDia", '"KeyPinHoleDia"')
    drill_text = to_sketch((-_KEY_PIN_OUT / 2.0, model[3][1] - 2.0, KEY_PIN_Z))
    await add_diametric_linear_dimension(
        adapter, axis, drill, drill_text, "KeyPinDrillDia"
    )
    hole.record("KeyPinDrillDia", '"KeyPinDrillDia"')
    await ensure_fully_defined(adapter, "key-pin hole sketch")
    check("exit_sketch key-pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "KeyPinProfile")
    return jobs + hole.apply(adapter, "KeyPinProfile")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

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
        ("KeyPinStation", KEY_PIN_STATION),
        ("KeyPinHoleDia", KEY_PIN_HOLE_DIA),
        ("KeyPinDrillDia", KEY_PIN_DRILL_DIA),
        ("KeyPinChord", KEY_PIN_CHORD_OFFSET),
        ("KeyPinStop", KEY_PIN_STOP),
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

    # The reamed bore: one round Front-plane cut, mid-plane, through spigot,
    # flange and body at once.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "bore",
        dims=bore,
        names=(None, None, "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut hub bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * HUB_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    await volume_check(adapter, "hub bore", v_body - V_BORE, 0.01 * V_BORE)
    v_body -= V_BORE

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

    # Radial oil hole on +Y, one wall to the bore, at the key pin's station.
    # Top-plane sketch (u, v) = model (X, -Z): a construction line on the
    # axis from the hub front face to the hole centre carries the key-pin
    # station (R9-60: match-drilled at assembly opposite the key pin); the
    # circle's centre sits on its end.
    oil = SketchDims()
    check("create_sketch oil hole", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    station = check(
        "oil hole station line",
        await adapter.add_line(0.0, _HUB_FRONT_V, 0.0, _KEY_PIN_V),
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
        KEY_PIN_STATION,
        "oil hole station from the hub front face",
    )
    oil.record("OilHoleStation", '"KeyPinStation"')
    sketch_mgr = adapter.currentSketchManager
    prev_add_to_db = bool(sketch_mgr.AddToDB)
    sketch_mgr.AddToDB = True
    try:
        circle = check(
            "oil hole circle", await adapter.add_circle(0.0, _KEY_PIN_V, OIL_HOLE_R)
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
    await volume_check(adapter, "oil hole", V_FINAL + V_KEY_PIN_HOLE, 0.05 * V_OIL_HOLE)

    # The key-pin hole's printed station, on a hidden reference line.
    drive_jobs += await _key_pin_reference(adapter)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)

    # The key pin's chord hole: the .0615 ream from +X to its stop, the #56
    # knockout on through the -X wall.
    drive_jobs += await _key_pin_hole(adapter)
    check(
        "revolve-cut key-pin hole",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "KeyPinHole")
    await volume_check(adapter, "key-pin hole", V_FINAL, 0.05 * V_KEY_PIN_HOLE)

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
    # The bore carries its reamed band, the sliding fit on the sleeve's boss;
    # the key-pin ream its REAM_H7 band, the pin's press, and its chord and
    # stop the reamed hole's location band; the spigot carries
    # its turned-row band, clear of the disc's bore.  The overall and spigot
    # lengths carry the disc cluster stack's printed band.  Every other size
    # is governed by its places, the holes by the title block's DRILLED HOLES
    # row (the spec's DRAWING_PRECISION).  All print in inches.
    set_dimension_bilateral_tolerance(
        adapter, "BoreProfile", "BoreDia", *BORE_DEVIATIONS, display_unit=UNIT
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "KeyPinProfile",
        "KeyPinDia",
        *KEY_PIN_HOLE_DEVIATIONS,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "KeyPinProfile",
        "KeyPinChord",
        KEY_PIN_LOCATION_BAND,
        display_unit=UNIT,
    )
    set_dimension_symmetric_tolerance(
        adapter,
        "KeyPinProfile",
        "KeyPinStop",
        KEY_PIN_LOCATION_BAND,
        display_unit=UNIT,
    )
    set_dimension_bilateral_tolerance(
        adapter, "HubProfile", "SpigotDia", *SPIGOT_DIA_DEVIATIONS, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "HubProfile", "HubLength", HUB_LENGTH_BAND, display_unit=UNIT
    )
    set_dimension_symmetric_tolerance(
        adapter, "HubProfile", "SpigotLength", SPIGOT_LENGTH_BAND, display_unit=UNIT
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
