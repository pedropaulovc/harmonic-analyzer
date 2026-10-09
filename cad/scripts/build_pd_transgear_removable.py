r"""Reproduction script: MHA-PD-009 removable ANSI #25 sprocket (book ch. 23, p. 56-61).

Three purchased steel sprockets -- McMaster 6793K4 / 6793K11 / 6793K17,
12 / 18 / 24 teeth -- with the supplied hub turned off flush with the plate.
Two are mounted at a time to set the platen speed: one on the crank's seat
collar, one on the knob shaft's, both in the ONE chain plane (the third is the
loose spare). One part, three configurations (T12/T18/T24). Every number is
``pd_transgear_removable_spec``'s; this script only turns them into features.

Tooth form (spec docstring): the ANSI B29.1 (ACA) #25 standard form -- the
``SEAT_CURVE_R`` seating arc centred on the pitch circle, the
``WORKING_CURVE_R`` working arc, the straight yz and the topping arc out to
the supplied outside diameter. One tooth gap is one sketch of native arcs and
lines (the in-disc profile, its six joins tangent, closed outside the blank
by two lines to an apex), every dimension driven by an equation-manager
global, cut, then circularly patterned.
``ToothCount`` is the only configuration-specific global; pitch/outside
radius, the ACA angles A and B and the topping radius F are all equations of
it (each round-tripped against ``spec.gap_geometry`` at T24), so every
configuration re-solves its own gap and each configuration's volume is
checked against ``spec.part_volume``.

The vendor-supplied teeth, OD and plate are built natively, not imported from
vendor CAD. One revolved cut of two closed Top-plane triangles reproduces
the supplied tooth-side chamfers on BOTH faces. Its radial position follows
``Ra`` and its axial position follows ``Plate``; the radial width and face
angle are configuration-independent spec values. The hub is absent by
construction; only the through bore and drive-pin holes are shop operations.

Config-independent mounting interface, cut after the tooth pattern: bore
``BORE_DIA`` and two ``PIN_HOLE_DIA`` drive-pin holes on ``PIN_CIRCLE_RADIUS``
at ``PIN_HOLE_ANGLES_DEG`` (local +/-Y). The bore/pin-hole web
(``spec.BORE_PIN_WEB``, 0.60 nominal) sits below the 1.5 wall floor as a
Named exception; the sheet states its printed worst case
(``pd_transgear_removable_notes.BORE_PIN_WEB_NOTE``).

Drawing marks (``draw_pd_transgear_removable``): ``spec.DRAWING_DIMENSIONS`` at
``spec.DRAWING_PRECISION``, the plate thickness banded ``spec.PLATE_BAND``
and each pin centre +/-``spec.DRIVE_PIN_OFFSET_TOL``; the outside diameter
``BlankDia`` is driven per configuration, so each configuration's view prints
its own.  The sheet's SPROCKET DATA and notes are file properties.

Part frame: axis Z through the origin, plate z = 0..PLATE (the Front Plane is
the wheel's FRONT face; ``RearFace`` at z = PLATE seats on the shaft's seat
collar), a TOOTH centred on local +X, gaps centred at pi/N + k 2pi/N. With
that one clocking rule T12 and T24 carry a tooth on the +/-Y hole
centrelines, T18 a gap (90 deg is 4.5 of its pitches).

Named datums, blanked and selectable in every configuration: ``Axis1`` (the
wheel axis), plane ``RearFace``, axes ``PinHoleAxis1`` (+Y hole) and
``PinHoleAxis2`` (-Y hole).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_transgear_removable.py
"""

from __future__ import annotations

import math
import sys

import _config
import _telemetry
import pd_transgear_removable_spec as spec
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
    add_diametric_linear_dimension,
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
from pd_transgear_removable_notes import DRAWING_NOTES, GEAR_DATA

# ``set_global`` is imported from _common under a distinct name: the gap-math
# globals below use involute_gear's stricter 4-arg ``set_global`` (asserts the
# round-tripped value to test the equation-parser dialect), while the plain
# mm length knobs use _common's 3-arg upsert.
from _common import set_global as set_global_mm
from involute_gear import (
    pattern_count_dimension,
    read_dimension,
    set_global,
)

PART_NAME = "pd-transgear-removable"
MATERIAL = "Plain Carbon Steel"  # SW physical material; vendor states steel, no grade

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


# swConstrainedStatus_e
_SKETCH_STATUS = {
    1: "unknown",
    2: "under-defined",
    3: "fully defined",
    4: "over-defined",
    5: "no solution",
    6: "invalid solution",
    7: "autosolve off",
}


def log_gap_state(
    adapter, configuration: str, profile: str, features: tuple[str, ...]
) -> None:
    """Log what regenerated in ``configuration`` ahead of its volume check.

    The gap sketch's solve status and the radial span of its points off the
    origin (from the seat's x points out to the apex at ``RClear`` = 2 Ra, so
    a sketch left at another configuration's gap shows there), and each gap
    feature's ``GetErrorCode2`` (swFeatureError_e, 0 = clean). Read-only: an
    unreadable state is logged, never raised -- the volume check stays the
    gate.
    """
    fields: dict[str, str] = {}
    try:
        part = _early_bound(adapter.currentModel, "IPartDoc")
        feature = _early_bound(part.FeatureByName(profile), "IFeature")
        sketch = _early_bound(feature.GetSpecificFeature2(), "ISketch")
        status = int(sketch.GetConstrainedStatus())
        fields["gap_sketch_status"] = _SKETCH_STATUS.get(status, str(status))
        radii = [
            radius
            for radius in (
                math.hypot(float(point.X), float(point.Y)) * 1000.0
                for point in (
                    _early_bound(raw, "ISketchPoint")
                    for raw in sketch.GetSketchPoints2() or ()
                )
            )
            if radius > 1e-6
        ]
        if radii:
            fields["gap_sketch_r_mm"] = f"{min(radii):.2f}..{max(radii):.2f}"
        for name in features:
            feature = _early_bound(part.FeatureByName(name), "IFeature")
            code, warning = feature.GetErrorCode2()
            fields[f"gap_{name}_error"] = f"{int(code or 0)}" + (
                " (warning)" if code and warning else ""
            )
    except Exception as exc:  # diagnostics only: the volume check is the gate
        fields["gap_state_unreadable"] = repr(exc)
    summary = ", ".join(f"{key}={value}" for key, value in fields.items())
    _telemetry.info(f"{configuration}: {summary}", **fields)


def gap_globals(teeth: int) -> list[tuple[str, str, float]]:
    """Equation-manager globals of one tooth gap: ``(name, expression, value)``.

    Lengths are INCHES (the part template is IPS) and the manager's trig
    takes DEGREES. ``value`` is the expected evaluation at ``teeth`` from
    ``spec.gap_geometry`` -- the round trip is the dialect test.
    ``ToothCount`` is the only configuration-specific one; :data:`GAP_DIMENSIONS`
    drive the gap sketch from the rest.
    """
    g = spec.gap_geometry(teeth)
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
        ("Rp", '"ChainPitch" / sin("HalfDeg") / 2', g["rp"] / IN),
        # spec.outside_dia's ANSI p (0.6 + cot(180/N)), halved.
        ("Ra", '"ChainPitch" * (0.6 + 1 / tan("HalfDeg")) / 2', g["ra"] / IN),
        # ACA A = 35 + 60/N and B = 18 - 56/N.
        ("ADeg", '35 + 60 / "ToothCount"', math.degrees(spec.working_angle(teeth))),
        ("BDeg", '18 - 56 / "ToothCount"', math.degrees(spec.working_arc(teeth))),
        # ACA F = Dr [0.8 cos B + 1.4 cos(17 - 64/N) - 1.3025] - 0.0015 in,
        # written as the tangency it encodes: 17 - 64/N = A - B - 180/N.
        (
            "TopR",
            '"WorkOffset" * cos("BDeg") '
            '+ "TopOffset" * cos("ADeg" - "BDeg" - "HalfDeg") - "WorkR"',
            g["topping_r"] / IN,
        ),
        # Clearance radius for closing the cut outside the blank (removes nothing).
        ("RClear", '2 * "Ra"', 2.0 * g["ra"] / IN),
    ]


Point = tuple[float, float]


def gap_points(teeth: int) -> dict[str, Point]:
    """The seed gap's named points (mm), centred on angle pi/N off +X.

    ``spec.gap_geometry``'s upper side (``_u``) and its mirror (``_l``),
    turned onto the seed gap: pocket centre ``a``, working centres ``c``,
    topping centres ``b``, the seat/working tangency ``x``, the flank's
    tangencies ``y`` (working) and ``z`` (topping), the OD corner ``k`` and
    the clearance apex ``q`` at ``RClear`` = 2 Ra on the gap centreline.
    """
    g = spec.gap_geometry(teeth)
    cos_h, sin_h = math.cos(g["half_pitch_angle"]), math.sin(g["half_pitch_angle"])

    def seed(x: float, y: float) -> Point:
        return x * cos_h - y * sin_h, x * sin_h + y * cos_h

    seat = (
        g["rp"] + g["seat_r"] * math.cos(g["seat_start"]),
        g["seat_r"] * math.sin(g["seat_start"]),
    )
    side = {
        "x": seat,
        "c": (g["working_cx"], g["working_cy"]),
        "y": (g["flank_start_x"], g["flank_start_y"]),
        "z": (g["flank_end_x"], g["flank_end_y"]),
        "b": (g["topping_cx"], g["topping_cy"]),
        "k": (g["corner_x"], g["corner_y"]),
    }
    points = {
        "origin": (0.0, 0.0),
        "a": seed(g["rp"], 0.0),
        "q": seed(2.0 * g["ra"], 0.0),
    }
    for name, (x, y) in side.items():
        points[f"{name}_u"] = seed(x, y)
        points[f"{name}_l"] = seed(x, -y)
    return points


# The gap sketch: ``name -> (centre, start, end)`` point names (centre None
# for a line). Arcs run CCW from start to end. In loop order from the upper
# seat/working tangency x_u: the seating arc round the bottom, the lower
# working arc, flank and topping arc out to the OD corner, a clearance line
# to the apex q and back to the upper corner, the upper topping arc, flank
# and working arc. ``GAP_AXIS`` is the construction centreline O -> q.
GAP_AXIS = "GapAxis"
GAP_ENTITIES: dict[str, tuple[str | None, str, str]] = {
    GAP_AXIS: (None, "origin", "q"),
    "Seat": ("a", "x_u", "x_l"),
    "WorkLower": ("c_l", "x_l", "y_l"),
    "FlankLower": (None, "y_l", "z_l"),
    "TopLower": ("b_l", "k_l", "z_l"),
    "ClearLower": (None, "k_l", "q"),
    "ClearUpper": (None, "q", "k_u"),
    "TopUpper": ("b_u", "z_u", "k_u"),
    "FlankUpper": (None, "z_u", "y_u"),
    "WorkUpper": ("c_u", "y_u", "x_u"),
}

# Relations over entity names / ``<entity>.<start|end|center>`` / ``origin``.
# Shared end points are not related: drawn at identical coordinates with
# inference off, they merge (the _chain_link obround recipe). With the
# dimensions below they leave the sketch fully defined (45 entity DOF = 20
# merged-point + 12 relation + 13 dimension equations). B is not dimensioned:
# the flank's two tangencies imply it (``TopR`` encodes that tangency).
GAP_RELATIONS: tuple[tuple[str, str, str], ...] = (
    ("coincident", f"{GAP_AXIS}.start", "origin"),
    ("coincident", "Seat.center", GAP_AXIS),
    ("tangent", "Seat", "WorkUpper"),
    ("tangent", "Seat", "WorkLower"),
    ("tangent", "WorkUpper", "FlankUpper"),
    ("tangent", "WorkLower", "FlankLower"),
    ("tangent", "FlankUpper", "TopUpper"),
    ("tangent", "FlankLower", "TopLower"),
    ("equal", "WorkLower", "WorkUpper"),
    ("equal", "TopLower", "TopUpper"),
    # b sits TopOffset from a square to the next pocket: straight below a on
    # the side whose neighbouring tooth is on +X.
    ("vertical_points", "Seat.center", "TopLower.center"),
)

# ``(name, kind, ref, other ref, drive)``, in creation order. Every one is
# measured from the origin or from the pocket centre a, so a configuration
# change moves the gap mostly as a whole.
GAP_DIMENSIONS: tuple[tuple[str, str, str, str | None, str], ...] = (
    ("GapSeatR", "radial", "Seat", None, '"SeatR"'),
    ("GapWorkR", "radial", "WorkUpper", None, '"WorkR"'),
    ("GapTopR", "radial", "TopUpper", None, '"TopR"'),
    (
        "GapSeatX",
        "horizontal_distance",
        "Seat.center",
        "origin",
        '"Rp" * cos("HalfDeg")',
    ),
    ("GapSeatY", "vertical_distance", "Seat.center", "origin", '"ChainPitch" / 2'),
    ("GapClear", "distance", f"{GAP_AXIS}.end", "origin", '"RClear"'),
    (
        "GapWorkUpper",
        "vertical_distance",
        "Seat.center",
        "WorkUpper.center",
        '"WorkOffset" * cos("ADeg" + "HalfDeg")',
    ),
    (
        "GapWorkLower",
        "horizontal_distance",
        "Seat.center",
        "WorkLower.center",
        '"WorkOffset" * sin("ADeg" - "HalfDeg")',
    ),
    (
        "GapTopLower",
        "vertical_distance",
        "Seat.center",
        "TopLower.center",
        '"TopOffset"',
    ),
    (
        "GapTopUpperX",
        "horizontal_distance",
        "Seat.center",
        "TopUpper.center",
        '"TopOffset" * sin(2 * "HalfDeg")',
    ),
    (
        "GapTopUpperY",
        "vertical_distance",
        "Seat.center",
        "TopUpper.center",
        '"TopOffset" * cos(2 * "HalfDeg")',
    ),
    ("GapCornerUpper", "distance", "TopUpper.end", "origin", '"Ra"'),
    ("GapCornerLower", "distance", "TopLower.start", "origin", '"Ra"'),
)


def gap_point(points: dict[str, Point], ref: str) -> Point:
    """The point a ``<entity>.<start|end|center>`` or ``origin`` ref names."""
    if ref == "origin":
        return points["origin"]
    entity, _, suffix = ref.partition(".")
    centre, start, end = GAP_ENTITIES[entity]
    name = {"center": centre, "start": start, "end": end}[suffix]
    if name is None:
        raise ValueError(f"{ref}: a line has no centre")
    return points[name]


def gap_dimension_value(
    points: dict[str, Point], kind: str, ref: str, other: str | None
) -> float:
    """What a :data:`GAP_DIMENSIONS` row measures on ``points`` (mm)."""
    if kind == "radial":
        centre, start, _end = GAP_ENTITIES[ref]
        return math.dist(points[centre], points[start])
    (x1, y1), (x2, y2) = gap_point(points, ref), gap_point(points, other)
    return {
        "horizontal_distance": abs(x2 - x1),
        "vertical_distance": abs(y2 - y1),
        "distance": math.hypot(x2 - x1, y2 - y1),
    }[kind]


async def draw_gap_sketch(adapter, teeth: int, dims: SketchDims) -> None:
    """Draw, relate and dimension the seed gap in the active sketch at
    ``teeth``, recording each dimension's name and drive in ``dims``."""
    points = gap_points(teeth)
    ids: dict[str, str] = {}
    set_sketch_direct_db(adapter, True)
    for name, (centre, start, end) in GAP_ENTITIES.items():
        if name == GAP_AXIS:
            res = await adapter.add_centerline(*points[start], *points[end])
        elif centre is None:
            res = await adapter.add_line(*points[start], *points[end])
        else:
            res = await adapter.add_arc(*points[centre], *points[start], *points[end])
        ids[name] = check(f"gap {name}", res)
    set_sketch_direct_db(adapter, False)

    def entity_ref(ref: str) -> str:
        entity, dot, suffix = ref.partition(".")
        return ref if ref == "origin" else ids[entity] + dot + suffix

    for relation, ref, other in GAP_RELATIONS:
        check(
            f"gap {relation} {ref} / {other}",
            await adapter.add_sketch_constraint(
                entity_ref(ref), entity_ref(other), relation
            ),
        )
    for name, kind, ref, other, drive in GAP_DIMENSIONS:
        value = gap_dimension_value(points, kind, ref, other)
        check(
            f"gap {name} = {value:.4f}",
            await adapter.add_sketch_dimension(
                entity_ref(ref), entity_ref(other) if other else None, kind, value
            ),
        )
        dims.record(name, drive)


def chamfer_globals() -> list[tuple[str, str, float]]:
    """Supplied-face chamfer globals: IPS lengths and degree-based trig."""
    return [
        (
            "ToothChamferRadial",
            repr(spec.CHAMFER_RADIAL / IN),
            spec.CHAMFER_RADIAL / IN,
        ),
        (
            "ToothChamferFaceDeg",
            repr(spec.CHAMFER_FACE_ANGLE_DEG),
            spec.CHAMFER_FACE_ANGLE_DEG,
        ),
        (
            "ToothChamferAxial",
            '"ToothChamferRadial" * tan("ToothChamferFaceDeg")',
            spec.CHAMFER_AXIAL / IN,
        ),
    ]


def chamfer_points(teeth: int) -> dict[str, Point]:
    """Radial/axial Top-plane section (mm): sketch Y is part -Z.

    Each closed triangle extends one radial width beyond Ra into air, avoiding
    a cut edge coincident with the tooth-tip cylinder. Its diagonal intersects
    Ra at CHAMFER_AXIAL inside its face and starts at Ra - CHAMFER_RADIAL
    on that face. Both cones therefore leave the mounting plate untouched.
    """
    inner = spec.outside_dia(teeth) / 2.0 - spec.CHAMFER_RADIAL
    outer = spec.outside_dia(teeth) / 2.0 + spec.CHAMFER_RADIAL
    return {
        "origin": (0.0, 0.0),
        "axis_rear": (0.0, -spec.PLATE),
        "front_inner": (inner, 0.0),
        "front_outer": (outer, 0.0),
        "front_tip": (outer, -2.0 * spec.CHAMFER_AXIAL),
        "rear_inner": (inner, -spec.PLATE),
        "rear_outer": (outer, -spec.PLATE),
        "rear_tip": (outer, -spec.PLATE + 2.0 * spec.CHAMFER_AXIAL),
    }


CHAMFER_ENTITIES: dict[str, tuple[str, str]] = {
    "ChamferAxis": ("origin", "axis_rear"),
    "FrontFace": ("front_inner", "front_outer"),
    "FrontOuter": ("front_outer", "front_tip"),
    "FrontCone": ("front_tip", "front_inner"),
    "RearFace": ("rear_inner", "rear_outer"),
    "RearOuter": ("rear_outer", "rear_tip"),
    "RearCone": ("rear_tip", "rear_inner"),
}

# Same dimension/drive recording convention as GAP_DIMENSIONS; distances are
# unsigned, with the two triangles created on their intended sides of the faces.
CHAMFER_DIMENSIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("ChamferAxisLength", "vertical_distance", "ChamferAxis.end", "origin", '"Plate"'),
    (
        "FrontChamferRadius",
        "horizontal_distance",
        "FrontFace.start",
        "origin",
        '"Ra" - "ToothChamferRadial"',
    ),
    (
        "FrontChamferWidth",
        "horizontal_distance",
        "FrontFace.start",
        "FrontFace.end",
        '2 * "ToothChamferRadial"',
    ),
    (
        "FrontChamferDepth",
        "vertical_distance",
        "FrontOuter.start",
        "FrontOuter.end",
        '2 * "ToothChamferAxial"',
    ),
    (
        "RearChamferRadius",
        "horizontal_distance",
        "RearFace.start",
        "origin",
        '"Ra" - "ToothChamferRadial"',
    ),
    ("RearChamferOffset", "vertical_distance", "RearFace.start", "origin", '"Plate"'),
    (
        "RearChamferWidth",
        "horizontal_distance",
        "RearFace.start",
        "RearFace.end",
        '2 * "ToothChamferRadial"',
    ),
    (
        "RearChamferDepth",
        "vertical_distance",
        "RearOuter.start",
        "RearOuter.end",
        '2 * "ToothChamferAxial"',
    ),
)


def chamfer_point(points: dict[str, Point], ref: str) -> Point:
    """Resolve a chamfer sketch entity endpoint or the origin."""
    if ref == "origin":
        return points["origin"]
    entity, _, suffix = ref.partition(".")
    return points[CHAMFER_ENTITIES[entity][{"start": 0, "end": 1}[suffix]]]


async def draw_chamfer_sketch(adapter, teeth: int, dims: SketchDims) -> None:
    """Two closed, fully dimensioned triangles and one Z rotation axis."""
    points = chamfer_points(teeth)
    ids: dict[str, str] = {}
    set_sketch_direct_db(adapter, True)
    for name, (start, end) in CHAMFER_ENTITIES.items():
        if name == "ChamferAxis":
            result = await adapter.add_centerline(*points[start], *points[end])
        else:
            result = await adapter.add_line(*points[start], *points[end])
        ids[name] = check(f"tooth chamfer {name}", result)
    set_sketch_direct_db(adapter, False)

    def entity_ref(ref: str) -> str:
        entity, dot, suffix = ref.partition(".")
        return ref if ref == "origin" else ids[entity] + dot + suffix

    for name, relation in (
        ("ChamferAxis", "vertical"),
        ("FrontFace", "horizontal"),
        ("FrontOuter", "vertical"),
        ("RearFace", "horizontal"),
        ("RearOuter", "vertical"),
    ):
        check(
            f"tooth chamfer {name} {relation}",
            await adapter.add_sketch_constraint(ids[name], None, relation),
        )
    for ref, relation in (
        ("ChamferAxis.start", "coincident"),
        ("FrontFace.start", "horizontal_points"),
    ):
        check(
            f"tooth chamfer {ref} -> origin",
            await adapter.add_sketch_constraint(entity_ref(ref), "origin", relation),
        )
    # Identical endpoints merge at creation with inference off, as in the gap
    # sketch; no fixed entities or configuration-specific coordinates survive.
    for name, kind, ref, other, drive in CHAMFER_DIMENSIONS:
        first, second = chamfer_point(points, ref), chamfer_point(points, other)
        coordinate = 0 if kind == "horizontal_distance" else 1
        value = abs(first[coordinate] - second[coordinate])
        check(
            f"tooth chamfer {name} = {value:.4f}",
            await adapter.add_sketch_dimension(
                entity_ref(ref), entity_ref(other), kind, value
            ),
        )
        dims.record(name, drive)


def chamfer_volume_tolerance(teeth: int, expected: float) -> float:
    """Keep either missing supplied face outside the native volume gate."""
    return min(0.01 * expected, spec.chamfer_volume(teeth) / 4.0)


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
    # Equation-manager globals (trig dialect probe first -- see build_dt_cone_gear).
    # ------------------------------------------------------------------
    await set_global(adapter, "TrigProbe", "cos(60)", 0.5)
    for name, expression, expected in gap_globals(DEFAULT_TEETH):
        await set_global(adapter, name, expression, expected)
    for name, expression, expected in chamfer_globals():
        await set_global(adapter, name, expression, expected)

    # Plain length knobs for the config-independent geometry (plate + the
    # mounting interface). mm suffix is load-bearing -- this is an INCH
    # document, so a bare number would be read as inches and blow the part up
    # 25.4x. The blank's outside diameter is NOT a knob here: it is
    # config-driven by the "Ra" equation link below.
    await set_global_mm(adapter, "Plate", f"{spec.PLATE}mm")
    await set_global_mm(adapter, "BoreDia", f"{spec.BORE_DIA}mm")
    await set_global_mm(adapter, "PinHoleDia", f"{spec.PIN_HOLE_DIA}mm")
    await set_global_mm(adapter, "PinCircleRadius", f"{spec.PIN_CIRCLE_RADIUS}mm")

    # Drive equations are recorded per sketch as the dims are created and applied
    # in one deferred batch once the whole single-config model exists (every
    # equation target must resolve against a finished, rebuilt model).
    drive_jobs: list[tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Blank: revolved dimensioned rectangle, its outside diameter equation-linked
    # to 2 * "Ra" (the canonical configuration pattern from build_dt_cone_gear).
    # ------------------------------------------------------------------
    ra_default_mm = spec.outside_dia(DEFAULT_TEETH) / 2.0
    blank = SketchDims()
    check("create_sketch blank", await adapter.create_sketch("Top"))
    # The axis centerline spans the on-axis edge exactly, so its endpoints merge
    # into the (0, 0) / (0, -PLATE) corners and the chain's own relations define
    # it (the build_vn_crank_hub_pin pattern); the diameter is measured from it.
    set_sketch_direct_db(adapter, True)
    axis = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, 0.0, -spec.PLATE),
    )
    blank_lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (ra_default_mm, 0.0),
            (ra_default_mm, -spec.PLATE),
            (0.0, -spec.PLATE),
        ],
    )
    set_sketch_direct_db(adapter, False)
    radial_line, side_line, _inner_line, axis_edge = blank_lines
    for ent, relation in (
        (radial_line, "horizontal"),
        (side_line, "vertical"),
        (_inner_line, "horizontal"),
        (axis_edge, "vertical"),
    ):
        check(f"blank {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    # The supplied outside diameter, doubled off the axis so the model owns
    # the diameter a drawing prints (not a radius a sheet would have to double).
    await add_diametric_linear_dimension(
        adapter, axis, side_line, (ra_default_mm / 2.0, 4.0), "BlankDia"
    )
    # Record in creation order. The diameter is left UNDRIVEN here (drive None):
    # it is bound to the config-driving "Ra" global by the explicit create_equation
    # block below, so adding it to drive_jobs would double-drive it.
    blank.record("BlankDia", None)
    check(
        "blank width dim",
        await adapter.add_sketch_dimension(side_line, None, "linear", spec.PLATE),
    )
    blank.record("BlankWidth", '"Plate"')
    # Pin the (0, 0) corner to the origin explicitly: the h/v relations + the
    # two dims fix the rectangle's shape but not its position.
    check(
        "blank corner -> origin",
        await adapter.add_sketch_constraint(f"{radial_line}.start", "origin", "coincident"),
    )
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

    # The diameter was renamed D1 -> BlankDia by blank.apply above, so the
    # captured auto-name "D1@..." would be stale -- reference the new name.
    od_dim = f"BlankDia@{blank_sketch}"
    od_default_in = 2.0 * ra_default_mm / IN
    before = read_dimension(adapter, od_dim)
    if abs(before - od_default_in) < 1e-6 * od_default_in:
        dim_unit = 1.0
    elif abs(before - 2.0 * ra_default_mm) < 1e-6 * 2.0 * ra_default_mm:
        dim_unit = IN
    else:
        raise RuntimeError(f"{od_dim} reads {before!r}, matches neither inches nor mm")
    _telemetry.debug(f"{od_dim} reads {before:g} (unit factor {dim_unit:g})")
    check(
        f"link {od_dim} to 2 * Ra",
        await adapter.create_equation(
            CreateEquationParameters(equation=f'"{od_dim}" = 2 * "Ra"')
        ),
    )

    # ------------------------------------------------------------------
    # One tooth gap: native arcs and lines, every dimension driven by the
    # globals, so each configuration re-solves it from its own ToothCount.
    # ------------------------------------------------------------------
    gap_dims = SketchDims()
    check("create_sketch gap", await adapter.create_sketch("Front"))
    await draw_gap_sketch(adapter, DEFAULT_TEETH, gap_dims)
    await ensure_fully_defined(adapter, "gap sketch")
    check("exit_sketch gap", await adapter.exit_sketch())
    gap_profile = name_last_feature(adapter, "ToothGapProfile")
    drive_jobs += gap_dims.apply(adapter, gap_profile)
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
        # geometry_pattern: per-instance re-solve of the global-driven gap
        # profile produced corrupt sliver cuts (live SW 2026 finding, this
        # part's equation-curve form); verbatim geometry copies are exact.
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

    # ------------------------------------------------------------------
    # Supplied tooth-side chamfers: both faces in one native revolve cut.
    # Cut AFTER the pattern, so the toothed-volume gate includes both cones
    # intersected with the actual teeth, not a full-disc ring subtraction.
    # ------------------------------------------------------------------
    chamfer_dims = SketchDims()
    check("create_sketch tooth chamfers", await adapter.create_sketch("Top"))
    await draw_chamfer_sketch(adapter, DEFAULT_TEETH, chamfer_dims)
    await ensure_fully_defined(adapter, "tooth chamfer sketch")
    check("exit_sketch tooth chamfers", await adapter.exit_sketch())
    chamfer_profile = name_last_feature(adapter, "ToothChamferProfile")
    drive_jobs += chamfer_dims.apply(adapter, chamfer_profile)
    check(
        "revolve both tooth chamfers",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    tooth_chamfers = name_last_feature(adapter, "ToothSideChamfers")

    # Fail fast: validate supplied teeth AND both chamfers at the default
    # count before configuration work (localises tooth-feature failures).
    mass = await adapter.get_mass_properties()
    if not mass.is_success:
        raise RuntimeError(f"post-chamfer mass properties failed: {mass.error}")
    toothed = float(mass.data.volume)
    expected_toothed = spec.toothed_volume(DEFAULT_TEETH)
    if abs(toothed - expected_toothed) > chamfer_volume_tolerance(
        DEFAULT_TEETH, expected_toothed
    ):
        raise RuntimeError(
            f"toothed disc volume {toothed:.1f} mm^3, analytic "
            f"{expected_toothed:.1f} -- teeth/chamfers produced wrong geometry"
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
    if abs(driven - expected_driven) > chamfer_volume_tolerance(
        DEFAULT_TEETH, expected_driven
    ):
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
        log_gap_state(
            adapter, name, gap_profile, (gap_cut, gap_pattern, tooth_chamfers)
        )

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
        if abs(volume - expected) > chamfer_volume_tolerance(teeth, expected):
            raise RuntimeError(
                f"{name}: volume {volume:.1f} mm^3, analytic {expected:.1f} -- "
                "regeneration produced wrong geometry"
            )
        volumes[name] = volume
        _telemetry.success(f"{name}: count {count:g}, volume {volume:.1f} (analytic {expected:.1f})")

        outside = read_dimension(adapter, od_dim)
        od_in = spec.outside_dia(teeth) / IN
        if abs(outside - od_in * dim_unit) > 1e-4 * od_in * dim_unit:
            raise RuntimeError(
                f"{name}: {od_dim} reads {outside:g}, expected {od_in * dim_unit:g}"
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
    # Manufacturing drawing support: supplied plate thickness stays within
    # its nominal band and each machined pin centre holds its location band.
    # Bore and pin-hole sizes are drilled (the title block's DRILLED HOLES
    # row governs them). The places are the part's (policy rule 2).
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
