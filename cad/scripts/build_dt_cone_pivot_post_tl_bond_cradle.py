r"""Build the cone pivot post's bond cradle (MHA-DT-005-TL-01; shop fixture).

A steel cradle the cone pivot post lies in, gravity-held, while the cone and
crank sleeves' retaining compound cures (``dt_cone_pivot_post_tl_bond_cradle_spec``).
Modelled in the post's own frame R0: post axis +Y, foot B at Y0, crank socket
axis +Z (up), base top at Z -30.

Layout: the base, the foot stop and the two saddles are Right-plane side
profiles extruded mid-plane across X, so every height reads from the base
top and every station from foot B. The two seats are mid-plane cuts on the
post axis from planes square to it. The crank pins rise from a base-top
plane; the cone pins run down the cone journal's tilt from the post's
north-cap plane into the base. Four hidden reference sketches carry what the
drawing prints from the base's west side face, foot B, the base top and the
post axis: the plan layout, the crank pin tops from the post axis, the cone
pins' section (tilt, hole entries, pin tops from the post axis, body seat axis)
and the tail seat axis. Each pin top's relation to the post axis carries its
own band (the spec's *_PIN_FROM_AXIS_TOL).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dt_cone_pivot_post_tl_bond_cradle.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    SketchDims,
    _early_bound,
    _feature_by_name,
    _read_member,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    blank_reference_sketches,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
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
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from dt_cone_pivot_post_spec import INCLINE_DEG
from dt_cone_pivot_post_tl_bond_cradle_spec import (
    BASE_END_Y,
    BASE_LENGTH,
    BASE_THICK,
    BASE_TOP_Z,
    BASE_WIDTH,
    BLOCK_HEIGHT,
    BLOCK_TOP_Z,
    BODY_SADDLE_THICK,
    BODY_SADDLE_Y,
    BODY_SEAT_DIA,
    CONE_PIN_ACROSS,
    CONE_PIN_AXIS,
    CONE_PIN_ENTRY_FROM_SIDE,
    CONE_PIN_FROM_AXIS,
    CONE_PIN_FROM_AXIS_TOL,
    CONE_PIN_SPREAD,
    CONE_PIN_TOP_S,
    CONE_PIN_Y,
    CONE_PINS,
    CRANK_PIN_FROM_AXIS,
    CRANK_PIN_FROM_AXIS_TOL,
    CRANK_PIN_HEIGHT,
    CRANK_PIN_X,
    CRANK_PIN_Y,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_DIA,
    PIN_RADIUS,
    REFERENCE_SKETCHES,
    SADDLE_SIDE_OFFSET,
    SADDLE_WIDTH,
    SEAT_AXIS_HEIGHT,
    SEAT_OVERRUN,
    SIDE_W_X,
    STOP_SIDE_OFFSET,
    STOP_THICK,
    STOP_WIDTH,
    TAIL_SADDLE_THICK,
    TAIL_SADDLE_Y,
    TAIL_SEAT_DIA,
    TAIL_SECTION_Y,
    ConePin,
)

PART_NAME = "dt-cone-pivot-post-tl-bond-cradle"
MATERIAL = "Plain Carbon Steel"  # the registry row names 1018 cold-finished bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# Right-plane sketch coordinates: u = model -Z, v = model Y.
_BASE_TOP_U = -BASE_TOP_Z
_BASE_BOTTOM_U = -BASE_TOP_Z + BASE_THICK
_BLOCK_TOP_U = -BLOCK_TOP_Z
# The gauge line of the section reference drops this far below the base top.
_GAUGE_LINE = 12.0


def _segment_area(radius: float, chord_offset: float) -> float:
    """Area of a circle of ``radius`` beyond a chord ``chord_offset`` from its centre."""
    half = math.sqrt(radius**2 - chord_offset**2)
    return radius**2 * math.acos(chord_offset / radius) - chord_offset * half


V_BASE = BASE_WIDTH * BASE_LENGTH * BASE_THICK
V_STOP = STOP_WIDTH * STOP_THICK * BLOCK_HEIGHT
V_SADDLES = SADDLE_WIDTH * BLOCK_HEIGHT * (BODY_SADDLE_THICK + TAIL_SADDLE_THICK)
# Each seat removes the circle segment above the saddle top's chord, through
# the saddle's thickness.
V_BODY_SEAT = _segment_area(BODY_SEAT_DIA / 2.0, -BLOCK_TOP_Z) * BODY_SADDLE_THICK
V_TAIL_SEAT = _segment_area(TAIL_SEAT_DIA / 2.0, -BLOCK_TOP_Z) * TAIL_SADDLE_THICK
_PIN_AREA = math.pi * PIN_RADIUS**2
V_CRANK_PINS = 2.0 * _PIN_AREA * CRANK_PIN_HEIGHT
# A tilted pin cut by the base top: the oblique cut averages to its axis, so
# each standing volume is the section times its axis length above the base.
V_CONE_PINS = _PIN_AREA * sum(pin.above_base for pin in CONE_PINS.values())
V_TOTAL = (
    V_BASE
    + V_STOP
    + V_SADDLES
    - V_BODY_SEAT
    - V_TAIL_SEAT
    + V_CRANK_PINS
    + V_CONE_PINS
)


def _require_one_solid_body(adapter: Any, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(f"{label}: expected exactly one solid body, found {len(bodies)}")


def _plane_normal(adapter: Any, name: str) -> tuple[float, float, float]:
    """A reference plane's unit normal in model coordinates (the third row of
    ``IRefPlane::Transform``'s rotation; build_dt_crankshaft's reader)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return (data[6], data[7], data[8])


def _pin_centre_in_sketch(adapter: Any, pin: ConePin) -> tuple[float, float]:
    """Where ``pin``'s axis crosses the active sketch's plane (the cone
    journal's normal plane through the post axis), in sketch mm.

    That plane's sketch axes are SOLIDWORKS's to state
    (``ModelToSketchTransform``; build_dt_cone_gear_shaft's reader), not ours
    to assume: the model point maps through it, and the sketch must hold the
    station on its x (model -Y, as the post's ConeShaftNormal) and the spread
    on its y.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    spread = pin.side * CONE_PIN_SPREAD
    model_mm = (spread * CONE_PIN_ACROSS[0], CONE_PIN_Y, spread * CONE_PIN_ACROSS[2])
    sketch = _early_bound(adapter.currentModel.SketchManager.ActiveSketch, "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    point = _early_bound(
        utility.CreatePoint(double_array([v / 1000.0 for v in model_mm])), "IMathPoint"
    )
    moved = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
    x, y, z = (float(v) * 1000.0 for v in moved.ArrayData)
    if abs(x + CONE_PIN_Y) > 1e-6 or abs(abs(y) - CONE_PIN_SPREAD) > 1e-6 or abs(z) > 1e-6:
        raise RuntimeError(f"cone pin {pin.side:+d} maps to sketch ({x:g}, {y:g}, {z:g})")
    return x, y


def _add_driving_tilt(
    adapter: Any,
    gauge_line: str,
    pin_line: str,
    vertex: tuple[float, float],
    *,
    label: str,
) -> None:
    """Author the acute tilt between the gauge line and the pin axis as DRIVING.

    Both lines are selected as segments: the adapter's angular route (one
    segment plus its vertex) never yields an angular control (the post's
    ``_add_driving_plan_incline``, ``diag_mcmaster_lib``). The text point
    sits on the bisector of the two rays from ``vertex`` -- down the gauge
    line (sketch +y) and back down the pin axis (-sin i, cos i) -- inside
    the acute wedge under the base, passed with sketch y in both the y and
    the -z slots so it lands there whether SOLIDWORKS reads it in sketch or
    in model space.
    """
    from solidworks_mcp.adapters import sw_type_info as _sw_type_info
    from solidworks_mcp.adapters.solidworks.sketch import _select_sketch_entities

    text_radius_mm = 8.0
    half = math.radians(INCLINE_DEG / 2.0)
    text_x = (vertex[0] - text_radius_mm * math.sin(half)) / 1000.0
    text_y = (vertex[1] + text_radius_mm * math.cos(half)) / 1000.0
    model = adapter.currentModel
    model.ClearSelection2(True)
    _select_sketch_entities(adapter, [gauge_line, pin_line], 0)
    extension = _sw_type_info.early_bound_or_flag(
        model.Extension, "IModelDocExtension", "AddSpecificDimension"
    )
    display, status = extension.AddSpecificDimension(
        text_x,
        text_y,
        -text_y,
        3,  # swDimensionType_e.swAngularDimension
        0,
    )
    model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"{label}: AddSpecificDimension(angular) failed ({status})")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    actual = math.degrees(abs(float(dimension.SystemValue)))
    if abs(actual - INCLINE_DEG) > 1e-6:
        raise RuntimeError(
            f"{label}: angular dimension measured {actual:.6f} deg, "
            f"expected {INCLINE_DEG:.6f} deg"
        )
    dimension.DrivenState = 2  # swDimensionDrivenState_e.swDimensionDriving
    if int(dimension.DrivenState) != 2:
        raise RuntimeError(f"{label}: angular dimension did not become driving")



def _as_construction(adapter: Any, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _side_profile(
    adapter: Any,
    sketch: str,
    rectangles: list[tuple[list[tuple[float, float]], list[str], list[str | None]]],
) -> list[tuple[str, str]]:
    """One Right-plane sketch of closed axis-parallel rectangles (u, v)."""
    dims = SketchDims()
    check(f"create sketch {sketch}", await adapter.create_sketch("Right"))
    for points, names, drives in rectangles:
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(
            adapter, lines, points, 0, sketch, dims=dims, names=names, drives=drives
        )
    await ensure_fully_defined(adapter, sketch)
    check(f"exit sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    return dims.apply(adapter, sketch)


async def _midplane_extrude(
    adapter: Any, feature: str, width: float, name: str, *, cut: bool = False
) -> str:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    parameters = ExtrusionParameters(depth=width, both_directions=True)
    if cut:
        check(f"cut {feature}", await adapter.create_cut_extrude(parameters))
    else:
        check(f"extrude {feature}", await adapter.create_extrusion(parameters))
    name_last_feature(adapter, feature)
    return name_dimensions(adapter, feature, [name])[0]


async def _offset_plane(adapter: Any, name: str, base: str, offset: float) -> None:
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {name}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane=base, offset=offset)
        ),
    )
    name_last_feature(adapter, name)


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    globals_mm = {
        "BaseWidth": BASE_WIDTH,
        "BaseLength": BASE_LENGTH,
        "BaseThick": BASE_THICK,
        "SeatAxisHeight": SEAT_AXIS_HEIGHT,
        "StopWidth": STOP_WIDTH,
        "StopThick": STOP_THICK,
        "BlockHeight": BLOCK_HEIGHT,
        "SaddleWidth": SADDLE_WIDTH,
        "BodySaddleY": BODY_SADDLE_Y,
        "BodySaddleThick": BODY_SADDLE_THICK,
        "TailSaddleY": TAIL_SADDLE_Y,
        "TailSaddleThick": TAIL_SADDLE_THICK,
        "BodySeatDia": BODY_SEAT_DIA,
        "TailSeatDia": TAIL_SEAT_DIA,
        "PinDia": PIN_DIA,
        "CrankPinX": CRANK_PIN_X,
        "CrankPinY": CRANK_PIN_Y,
        "CrankPinHeight": CRANK_PIN_HEIGHT,
    }
    for name, value in globals_mm.items():
        await set_global(adapter, name, f"{value}mm")

    # 1. Base plate: side profile u 30..40 (Z -30..-40), v from the base end
    # to the tail end; the anchor corner's u is the seat axis height above
    # the base top.
    drive_jobs = await _side_profile(
        adapter,
        "BaseProfile",
        [
            (
                [
                    (_BASE_TOP_U, BASE_END_Y),
                    (_BASE_BOTTOM_U, BASE_END_Y),
                    (_BASE_BOTTOM_U, BASE_END_Y + BASE_LENGTH),
                    (_BASE_TOP_U, BASE_END_Y + BASE_LENGTH),
                ],
                ["BaseThick", "BaseLength", "BaseTopZ", "BaseEndY"],
                ['"BaseThick"', '"BaseLength"', '"SeatAxisHeight"', '"StopThick"'],
            )
        ],
    )
    width = await _midplane_extrude(adapter, "Base", BASE_WIDTH, "BaseWidth")
    drive_jobs.append((width, '"BaseWidth"'))
    volume = V_BASE
    await volume_check(adapter, "base", volume, 0.001 * volume)

    # 2. Foot stop: its +Y face on Y0 is foot B.
    drive_jobs += await _side_profile(
        adapter,
        "StopProfile",
        [
            (
                [
                    (_BLOCK_TOP_U, 0.0),
                    (_BASE_TOP_U, 0.0),
                    (_BASE_TOP_U, -STOP_THICK),
                    (_BLOCK_TOP_U, -STOP_THICK),
                ],
                ["StopHeight", "StopThick", "StopTopZ"],
                ['"BlockHeight"', '"StopThick"', None],
            )
        ],
    )
    width = await _midplane_extrude(adapter, "Stop", STOP_WIDTH, "StopWidth")
    drive_jobs.append((width, '"StopWidth"'))
    volume += V_STOP
    await volume_check(adapter, "foot stop", volume, 0.001 * volume)

    # 3. Body and tail saddles, one sketch, one mid-plane width.
    drive_jobs += await _side_profile(
        adapter,
        "SaddlesProfile",
        [
            (
                [
                    (_BLOCK_TOP_U, y),
                    (_BASE_TOP_U, y),
                    (_BASE_TOP_U, y + thick),
                    (_BLOCK_TOP_U, y + thick),
                ],
                [f"{which}SaddleHeight", f"{which}SaddleThick", f"{which}SaddleTopZ", f"{which}SaddleY"],
                ['"BlockHeight"', f'"{which}SaddleThick"', None, f'"{which}SaddleY"'],
            )
            for which, y, thick in (
                ("Body", BODY_SADDLE_Y, BODY_SADDLE_THICK),
                ("Tail", TAIL_SADDLE_Y, TAIL_SADDLE_THICK),
            )
        ],
    )
    width = await _midplane_extrude(adapter, "Saddles", SADDLE_WIDTH, "SaddleWidth")
    drive_jobs.append((width, '"SaddleWidth"'))
    volume += V_SADDLES
    await volume_check(adapter, "saddles", volume, 0.001 * volume)
    _require_one_solid_body(adapter, label="blocks")

    # 4. Seats: on the post axis, cut mid-plane through each saddle from a
    # plane square to the axis at the saddle's mid-thickness. Top-plane
    # sketches: x = model X, y = model -Z, so the origin is the post axis.
    for which, plane, y, thick, dia, removed in (
        (
            "Body",
            "BodySeatPlane",
            BODY_SADDLE_Y,
            BODY_SADDLE_THICK,
            BODY_SEAT_DIA,
            V_BODY_SEAT,
        ),
        (
            "Tail",
            "TailSeatPlane",
            TAIL_SADDLE_Y,
            TAIL_SADDLE_THICK,
            TAIL_SEAT_DIA,
            V_TAIL_SEAT,
        ),
    ):
        await _offset_plane(adapter, plane, "Top Plane", y + thick / 2.0)
        seat = SketchDims()
        sketch = f"{which}SeatProfile"
        check(f"create sketch {sketch}", await adapter.create_sketch(plane))
        await define_circle(
            adapter,
            0.0,
            0.0,
            dia / 2.0,
            f"{which.lower()} seat",
            dims=seat,
            names=(None, None, f"{which}SeatDia"),
            drives=(None, None, f'"{which}SeatDia"'),
        )
        await ensure_fully_defined(adapter, sketch)
        check(f"exit sketch {sketch}", await adapter.exit_sketch())
        name_last_feature(adapter, sketch)
        drive_jobs += seat.apply(adapter, sketch)
        await _midplane_extrude(
            adapter, f"{which}Seat", thick + 2.0 * SEAT_OVERRUN, f"{which}SeatLength", cut=True
        )
        volume -= removed
        await volume_check(adapter, f"{which.lower()} seat", volume, 0.001 * volume)

    # 5. Crank pins: two vertical circles on the base-top plane, extruded up
    # by their gauge height. The pair is symmetric in X, so the plane's
    # sketch handedness cannot move them; the extrude direction follows the
    # plane's read-back normal.
    await _offset_plane(adapter, "BaseTop", "Front Plane", BASE_TOP_Z)
    base_top_normal = _plane_normal(adapter, "BaseTop")
    if abs(abs(base_top_normal[2]) - 1.0) > 1e-9:
        raise RuntimeError(f"BaseTop is not square to Z: normal {base_top_normal}")
    crank = SketchDims()
    check("create sketch CrankPinProfile", await adapter.create_sketch("BaseTop"))
    for side, x in (("West", -CRANK_PIN_X), ("East", CRANK_PIN_X)):
        names = (
            (f"CrankPin{side}Offset", "CrankPinY", "CrankPinDia")
            if side == "West"
            else (f"CrankPin{side}Offset", "CrankPinEastY", "CrankPinEastDia")
        )
        await define_circle(
            adapter,
            x,
            CRANK_PIN_Y,
            PIN_RADIUS,
            f"crank pin {side.lower()}",
            dims=crank,
            names=names,
            drives=('"CrankPinX"', '"CrankPinY"', '"PinDia"'),
        )
    await ensure_fully_defined(adapter, "CrankPinProfile")
    check("exit sketch CrankPinProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankPinProfile")
    drive_jobs += crank.apply(adapter, "CrankPinProfile")
    check(
        "extrude CrankPins",
        await adapter.create_extrusion(
            ExtrusionParameters(
                depth=CRANK_PIN_HEIGHT, reverse_direction=base_top_normal[2] < 0.0
            )
        ),
    )
    name_last_feature(adapter, "CrankPins")
    drive_jobs.append(
        (name_dimensions(adapter, "CrankPins", ["CrankPinHeight"])[0], '"CrankPinHeight"')
    )
    volume += V_CRANK_PINS
    await volume_check(adapter, "crank pins", volume, 0.001 * volume)
    _require_one_solid_body(adapter, label="crank pins")

    # 6. Cone pins: a circle on a plane square to the cone journal through
    # the post axis (the post's own ConeShaftNormal construction) per pin,
    # each extruded its own dowel length from the north-cap plane down the
    # journal axis into the base.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "post axis")
    name_last_feature(adapter, "post axis")
    check(
        "create ConePinNormal",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Front Plane",
                angle=-INCLINE_DEG,
                pivot_axis="post axis",
            )
        ),
    )
    name_last_feature(adapter, "ConePinNormal")
    normal = _plane_normal(adapter, "ConePinNormal")
    along = sum(a * b for a, b in zip(normal, CONE_PIN_AXIS, strict=True))
    if abs(abs(along) - 1.0) > 1e-9:
        raise RuntimeError(
            f"ConePinNormal {normal} is not square to the cone journal {CONE_PIN_AXIS}"
        )
    for which, pin in CONE_PINS.items():
        title = which.title()
        profile = f"ConePin{title}Profile"
        cone = SketchDims()
        check(f"create sketch {profile}", await adapter.create_sketch("ConePinNormal"))
        x, y = _pin_centre_in_sketch(adapter, pin)
        await define_circle(
            adapter,
            x,
            y,
            PIN_RADIUS,
            f"cone pin {which}",
            dims=cone,
            names=(f"ConeHole{title}Y", f"ConeHole{title}Across", f"ConeHole{title}Dia"),
            drives=(None, None, '"PinDia"'),
        )
        await ensure_fully_defined(adapter, profile)
        check(f"exit sketch {profile}", await adapter.exit_sketch())
        name_last_feature(adapter, profile)
        drive_jobs += cone.apply(adapter, profile)
        # Start on the north-cap side (-n) and run on down -n: flip when the
        # plane's normal is +n.
        extrude_at_offset(adapter, pin.length, -CONE_PIN_TOP_S, flip=along > 0.0)
        name_last_feature(adapter, f"ConePin{title}")
        volume += _PIN_AREA * pin.above_base
        await volume_check(adapter, f"cone pin {which}", volume, 0.001 * volume)
        _require_one_solid_body(adapter, label=f"cone pin {which}")

    # 7. Hidden reference sketches for the drawing. Every transverse location
    # prints from the base's west side face (SIDE_W_X), drawn as a
    # construction line on that face in each sketch.
    # Plan (Front: x = model X, y = model Y): the west side W from the base's
    # end corner; the stop's and the tail saddle's west edges; the crank pin
    # centres; the cone pin stations from foot B on a line through both
    # pin-top centres.
    plan = SketchDims()
    check("create sketch PlanReference", await adapter.create_sketch("Front"))
    side = (
        await add_line_chain(
            adapter,
            [(SIDE_W_X, BASE_END_Y), (SIDE_W_X, BASE_END_Y + BASE_LENGTH)],
            close=False,
        )
    )[0]
    stop_edge = (
        await add_line_chain(
            adapter,
            [(SIDE_W_X + STOP_SIDE_OFFSET, 0.0), (SIDE_W_X + STOP_SIDE_OFFSET, BASE_END_Y)],
            close=False,
        )
    )[0]
    saddle_edge = (
        await add_line_chain(
            adapter,
            [
                (SIDE_W_X + SADDLE_SIDE_OFFSET, TAIL_SADDLE_Y),
                (SIDE_W_X + SADDLE_SIDE_OFFSET, TAIL_SADDLE_Y + TAIL_SADDLE_THICK),
            ],
            close=False,
        )
    )[0]
    crank_line = (
        await add_line_chain(
            adapter, [(-CRANK_PIN_X, CRANK_PIN_Y), (CRANK_PIN_X, CRANK_PIN_Y)], close=False
        )
    )[0]
    west, east = CONE_PINS["west"], CONE_PINS["east"]
    station_line = (
        await add_line_chain(
            adapter,
            [(west.top_x, CONE_PIN_Y), (east.top_x, CONE_PIN_Y)],
            close=False,
        )
    )[0]
    for line in (side, stop_edge, saddle_edge):
        _as_construction(adapter, line)
        check(f"{line} vertical", await adapter.add_sketch_constraint(line, None, "vertical"))
    for line, what in ((crank_line, "crank pin"), (station_line, "cone pin")):
        _as_construction(adapter, line)
        check(
            f"{what} line horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    corner = f"{side}.start"
    await anchor_point_to_origin(adapter, corner, SIDE_W_X, BASE_END_Y, "base west corner")
    plan.record("PlanSideX")
    plan.record("PlanSideY")
    await dimension_between(
        adapter, corner, f"{side}.end", "vertical_distance", BASE_LENGTH, "base west side"
    )
    plan.record("PlanSideLength")
    for line, offset, y0, length, name in (
        (stop_edge, STOP_SIDE_OFFSET, 0.0, STOP_THICK, "Stop"),
        (saddle_edge, SADDLE_SIDE_OFFSET, TAIL_SADDLE_Y, TAIL_SADDLE_THICK, "Saddle"),
    ):
        await dimension_between(
            adapter, corner, f"{line}.start", "horizontal_distance", offset, f"{name.lower()} side"
        )
        plan.record(f"{name}SideX")
        await dimension_between(
            adapter, corner, f"{line}.start", "vertical_distance", y0 - BASE_END_Y, f"{name.lower()} edge start"
        )
        plan.record(f"{name}EdgeY")
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "vertical_distance", length, f"{name.lower()} edge"
        )
        plan.record(f"{name}EdgeLength")
    for point, x, name in (
        (f"{crank_line}.start", -CRANK_PIN_X, "CrankPinWestX"),
        (f"{crank_line}.end", CRANK_PIN_X, "CrankPinEastX"),
    ):
        await dimension_between(
            adapter, corner, point, "horizontal_distance", x - SIDE_W_X, name
        )
        plan.record(name)
    await dimension_between(
        adapter, f"{crank_line}.start", "origin", "vertical_distance", CRANK_PIN_Y, "crank pin line"
    )
    plan.record("CrankPinLineY")
    await anchor_point_to_origin(
        adapter, f"{station_line}.start", west.top_x, CONE_PIN_Y, "west cone pin"
    )
    plan.record("ConePinStationX")
    plan.record("ConePinY")
    await dimension_between(
        adapter,
        f"{station_line}.start",
        f"{station_line}.end",
        "horizontal_distance",
        east.top_x - west.top_x,
        "cone pin spread",
    )
    plan.record("ConePinSpreadX")
    await ensure_fully_defined(adapter, "PlanReference")
    check("exit sketch PlanReference", await adapter.exit_sketch())
    name_last_feature(adapter, "PlanReference")
    drive_jobs += plan.apply(adapter, "PlanReference")

    # Crank pin tops from the post axis (Right: u = model -Z, v = model Y):
    # the axis from foot B to the crank station, then square down to the
    # pins' top plane, one relation the elevation prints.
    crank_ref = SketchDims()
    check("create sketch CrankPinReference", await adapter.create_sketch("Right"))
    axis_line, crank_drop = await add_line_chain(
        adapter,
        [(0.0, 0.0), (0.0, CRANK_PIN_Y), (CRANK_PIN_FROM_AXIS, CRANK_PIN_Y)],
        close=False,
    )
    for line in (axis_line, crank_drop):
        _as_construction(adapter, line)
    await anchor_point_to_origin(adapter, f"{axis_line}.start", 0.0, 0.0, "post axis at foot B")
    check("post axis vertical", await adapter.add_sketch_constraint(axis_line, None, "vertical"))
    await dimension_between(
        adapter, f"{axis_line}.start", f"{axis_line}.end", "vertical_distance", CRANK_PIN_Y, "crank station"
    )
    crank_ref.record("CrankAxisY")
    check(
        "crank pin drop horizontal",
        await adapter.add_sketch_constraint(crank_drop, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{crank_drop}.start",
        f"{crank_drop}.end",
        "horizontal_distance",
        CRANK_PIN_FROM_AXIS,
        "crank pin top from axis",
    )
    crank_ref.record("CrankPinFromAxis")
    await ensure_fully_defined(adapter, "CrankPinReference")
    check("exit sketch CrankPinReference", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankPinReference")
    drive_jobs += crank_ref.apply(adapter, "CrankPinReference")

    async def _seat_axis_from_side(sketch_dims: SketchDims, which: str) -> str:
        """The west side W on the section plane (x = model X, y = model -Z)
        from the base top to its bottom, its top corner anchored to the seat
        axis (the sketch origin): the seat axis prints from W and the base top."""
        line = (
            await add_line_chain(
                adapter, [(SIDE_W_X, _BASE_TOP_U), (SIDE_W_X, _BASE_BOTTOM_U)], close=False
            )
        )[0]
        _as_construction(adapter, line)
        check(f"{which} side vertical", await adapter.add_sketch_constraint(line, None, "vertical"))
        await anchor_point_to_origin(
            adapter, f"{line}.start", SIDE_W_X, _BASE_TOP_U, f"{which} seat axis"
        )
        sketch_dims.record(f"{which}SeatAxisX")
        sketch_dims.record(f"{which}SeatAxisHeight")
        await dimension_between(
            adapter, f"{line}.start", f"{line}.end", "vertical_distance", BASE_THICK, f"{which} side"
        )
        sketch_dims.record(f"{which}SideLength")
        return f"{line}.start"

    # Section through both cone pins at their station (a Top-parallel plane:
    # x = model X, y = model -Z). Per pin: gauge line dropping square from
    # the hole's entry E on the base top through the base, pin axis E-T at the
    # journal tilt to the top centre T. The tops line T-T joins both tops,
    # square to the pins: it is the north-cap plane's trace. From the post
    # axis O (the sketch origin) a line runs to the tops line's midpoint F,
    # which lies square under O (the tops straddle the journal axis
    # equally), so O-F is the tops' plane from the post axis. The tilt reads
    # at the east pin, between its gauge line and its axis carried back
    # through E, under the base, clear of the seat; the west pin runs
    # parallel.
    await _offset_plane(adapter, "ConePinSectionPlane", "Top Plane", CONE_PIN_Y)

    def _entry(pin: ConePin) -> tuple[float, float]:
        return (pin.entry_x, -BASE_TOP_Z)

    def _top(pin: ConePin) -> tuple[float, float]:
        return (pin.top_x, -pin.top_z)

    chain = [
        (west.entry_x, -BASE_TOP_Z + _GAUGE_LINE),
        _entry(west),
        _top(west),
        _top(east),
        _entry(east),
        (east.entry_x, -BASE_TOP_Z + _GAUGE_LINE),
    ]
    foot = (CONE_PIN_TOP_S * CONE_PIN_AXIS[0], -CONE_PIN_TOP_S * CONE_PIN_AXIS[2])
    section = SketchDims()
    check(
        "create sketch ConePinSectionReference",
        await adapter.create_sketch("ConePinSectionPlane"),
    )
    section_corner = await _seat_axis_from_side(section, "Body")
    gauge_w, pin_w, tops, pin_e, gauge_e = await add_line_chain(adapter, chain, close=False)
    (to_tops,) = await add_line_chain(adapter, [(0.0, 0.0), foot], close=False)
    for line in (gauge_w, pin_w, tops, pin_e, gauge_e, to_tops):
        _as_construction(adapter, line)
    for which, gauge, entry_ref, foot_ref in (
        ("West", gauge_w, f"{gauge_w}.end", f"{gauge_w}.start"),
        ("East", gauge_e, f"{gauge_e}.start", f"{gauge_e}.end"),
    ):
        check(
            f"{which.lower()} gauge line vertical",
            await adapter.add_sketch_constraint(gauge, None, "vertical"),
        )
        await dimension_between(
            adapter,
            section_corner,
            entry_ref,
            "horizontal_distance",
            CONE_PIN_ENTRY_FROM_SIDE[which.lower()],
            f"{which.lower()} cone pin hole entry",
        )
        section.record(f"ConePinEntry{which}X")
        await dimension_between(
            adapter, entry_ref, "origin", "vertical_distance", -BASE_TOP_Z, f"{which.lower()} hole entry height"
        )
        section.record(f"ConePin{which}SectionZ")
        await dimension_between(
            adapter, foot_ref, entry_ref, "vertical_distance", _GAUGE_LINE, f"{which.lower()} gauge line"
        )
        section.record(f"ConePin{which}GaugeLine")
    _add_driving_tilt(adapter, gauge_e, pin_e, _entry(east), label="cone pin tilt")
    section.record("ConePinTilt")
    check("cone pins parallel", await adapter.add_sketch_constraint(pin_w, pin_e, "parallel"))
    check("tops line square to the pins", await adapter.add_sketch_constraint(tops, pin_e, "perpendicular"))
    await anchor_point_to_origin(adapter, f"{to_tops}.start", 0.0, 0.0, "post axis")
    check(
        "tops line midpoint under the post axis",
        await adapter.add_sketch_constraint(f"{to_tops}.end", tops, "midpoint"),
    )
    await dimension_between(
        adapter,
        f"{to_tops}.start",
        f"{to_tops}.end",
        "distance",
        CONE_PIN_FROM_AXIS,
        "cone pin tops from axis",
    )
    section.record("ConePinFromAxis")
    await ensure_fully_defined(adapter, "ConePinSectionReference")
    check("exit sketch ConePinSectionReference", await adapter.exit_sketch())
    name_last_feature(adapter, "ConePinSectionReference")
    drive_jobs += section.apply(adapter, "ConePinSectionReference")

    # Section B-B between the crank pins and the tail saddle, looking on to
    # the saddle's south face: the tail seat's axis from W and the base top.
    await _offset_plane(adapter, "TailSectionPlane", "Top Plane", TAIL_SECTION_Y)
    tail = SketchDims()
    check("create sketch TailSeatReference", await adapter.create_sketch("TailSectionPlane"))
    await _seat_axis_from_side(tail, "Tail")
    await ensure_fully_defined(adapter, "TailSeatReference")
    check("exit sketch TailSeatReference", await adapter.exit_sketch())
    name_last_feature(adapter, "TailSeatReference")
    drive_jobs += tail.apply(adapter, "TailSeatReference")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven cradle (equations neutral)", V_TOTAL, 0.001 * V_TOTAL
    )
    _require_one_solid_body(adapter, label="driven cradle")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    # The pin tops' own bands, the fixture's share of the post bands they set
    # (derivation in the spec's *_PIN_FROM_AXIS_TOL).
    set_dimension_symmetric_tolerance(
        adapter, "CrankPinReference", "CrankPinFromAxis", CRANK_PIN_FROM_AXIS_TOL
    )
    set_dimension_symmetric_tolerance(
        adapter, "ConePinSectionReference", "ConePinFromAxis", CONE_PIN_FROM_AXIS_TOL
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_geometry(
        adapter,
        (
            ("BodySeatPlane", "PLANE"),
            ("TailSeatPlane", "PLANE"),
            ("BaseTop", "PLANE"),
            ("ConePinNormal", "PLANE"),
            ("ConePinSectionPlane", "PLANE"),
            ("TailSectionPlane", "PLANE"),
            ("post axis", "AXIS"),
        ),
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
