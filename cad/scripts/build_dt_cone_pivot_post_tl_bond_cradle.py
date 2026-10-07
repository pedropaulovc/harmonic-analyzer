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
north-cap plane into the base. Two hidden reference sketches carry the cone
pins' plan stations and their section-view tilt, hole position and gauge
height for the drawing.

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
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
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
    CONE_PIN_AXIS,
    CONE_PIN_ENTRY_S,
    CONE_PIN_ENTRY_X,
    CONE_PIN_FAR_Y,
    CONE_PIN_HIGH_EDGE_HEIGHT,
    CONE_PIN_HIGH_EDGE_X,
    CONE_PIN_HIGH_EDGE_Z,
    CONE_PIN_LENGTH,
    CONE_PIN_NEAR_Y,
    CONE_PIN_TOP_S,
    CONE_PIN_TOP_X,
    CONE_PIN_TOP_Z,
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
    SADDLE_WIDTH,
    SEAT_AXIS_HEIGHT,
    SEAT_OVERRUN,
    STOP_THICK,
    STOP_WIDTH,
    TAIL_SADDLE_THICK,
    TAIL_SADDLE_Y,
    TAIL_SEAT_DIA,
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
# The gauge line of the section reference rises this far above the base top.
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
# the standing volume is the section times the axis length above the base.
V_CONE_PINS = 2.0 * _PIN_AREA * (CONE_PIN_TOP_S - CONE_PIN_ENTRY_S)
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
                ["BaseThick", "BaseLength", "SeatAxisHeight", "BaseEndY"],
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
    for which, y, thick, dia, removed in (
        ("Body", BODY_SADDLE_Y, BODY_SADDLE_THICK, BODY_SEAT_DIA, V_BODY_SEAT),
        ("Tail", TAIL_SADDLE_Y, TAIL_SADDLE_THICK, TAIL_SEAT_DIA, V_TAIL_SEAT),
    ):
        plane = f"{which}SeatPlane"
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
            (f"CrankPin{side}X", "CrankPinY", "CrankPinDia")
            if side == "West"
            else (f"CrankPin{side}X", "CrankPinEastY", "CrankPinEastDia")
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

    # 6. Cone pins: circles on a plane square to the cone journal through the
    # post axis (the post's own ConeShaftNormal construction), extruded from
    # the north-cap plane down the journal axis into the base.
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
    cone = SketchDims()
    check("create sketch ConePinProfile", await adapter.create_sketch("ConePinNormal"))
    for which, y in (("Near", CONE_PIN_NEAR_Y), ("Far", CONE_PIN_FAR_Y)):
        # ConePinNormal's local X points down the model's -Y axis (as the
        # post's ConeShaftNormal): the authored side keeps the pins at +Y.
        await define_circle(
            adapter,
            -y,
            0.0,
            PIN_RADIUS,
            f"cone pin {which.lower()}",
            dims=cone,
            names=(f"ConeHole{which}Y", None, f"ConeHole{which}Dia"),
            drives=(None, None, '"PinDia"'),
        )
    await ensure_fully_defined(adapter, "ConePinProfile")
    check("exit sketch ConePinProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "ConePinProfile")
    drive_jobs += cone.apply(adapter, "ConePinProfile")
    # Start on the north-cap side (-n) and run on down -n: flip when the
    # plane's normal is +n.
    extrude_at_offset(adapter, CONE_PIN_LENGTH, -CONE_PIN_TOP_S, flip=along > 0.0)
    name_last_feature(adapter, "ConePins")
    volume += V_CONE_PINS
    await volume_check(adapter, "cone pins", volume, 0.001 * volume)
    _require_one_solid_body(adapter, label="cone pins")

    # 7. Hidden reference sketches for the drawing.
    # Plan: the cone pin stations from foot B, on a construction line through
    # both pin-top centres.
    station = SketchDims()
    check("create sketch ConePinStationReference", await adapter.create_sketch("Front"))
    station_line = (
        await add_line_chain(
            adapter,
            [(CONE_PIN_TOP_X, CONE_PIN_NEAR_Y), (CONE_PIN_TOP_X, CONE_PIN_FAR_Y)],
            close=False,
        )
    )[0]
    _as_construction(adapter, station_line)
    check(
        "station line vertical",
        await adapter.add_sketch_constraint(station_line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{station_line}.start", CONE_PIN_TOP_X, CONE_PIN_NEAR_Y, "near cone pin"
    )
    station.record("ConePinStationX")
    station.record("ConePinNearY")
    await dimension_between(
        adapter, f"{station_line}.end", "origin", "vertical_distance", CONE_PIN_FAR_Y, "far cone pin"
    )
    station.record("ConePinFarY")
    await ensure_fully_defined(adapter, "ConePinStationReference")
    check("exit sketch ConePinStationReference", await adapter.exit_sketch())
    name_last_feature(adapter, "ConePinStationReference")
    drive_jobs += station.apply(adapter, "ConePinStationReference")

    # Section through the near cone pin (a Top-parallel plane: x = model X,
    # y = model -Z): gauge line A-E rising square from the hole's entry E on
    # the base top, pin axis E-T at the journal tilt to the top centre T,
    # and the top's radius T-H out to its high (-X) edge H.
    await _offset_plane(adapter, "ConePinSectionPlane", "Top Plane", CONE_PIN_NEAR_Y)
    entry = (CONE_PIN_ENTRY_X, -BASE_TOP_Z)
    chain = [
        (CONE_PIN_ENTRY_X, -BASE_TOP_Z - _GAUGE_LINE),
        entry,
        (CONE_PIN_TOP_X, -CONE_PIN_TOP_Z),
        (CONE_PIN_HIGH_EDGE_X, -CONE_PIN_HIGH_EDGE_Z),
    ]
    section = SketchDims()
    check(
        "create sketch ConePinSectionReference",
        await adapter.create_sketch("ConePinSectionPlane"),
    )
    gauge, pin_axis, top_radius = await add_line_chain(adapter, chain, close=False)
    for line in (gauge, pin_axis, top_radius):
        _as_construction(adapter, line)
    check("gauge line vertical", await adapter.add_sketch_constraint(gauge, None, "vertical"))
    await anchor_point_to_origin(adapter, f"{gauge}.end", *entry, "cone pin hole entry")
    section.record("ConePinEntryX")
    section.record("ConePinSectionZ")
    await dimension_between(
        adapter, f"{gauge}.start", f"{gauge}.end", "vertical_distance", _GAUGE_LINE, "gauge line"
    )
    section.record("ConePinGaugeLine")
    check(
        "cone pin tilt",
        await adapter.add_sketch_dimension(gauge, pin_axis, "angular", INCLINE_DEG),
    )
    section.record("ConePinTilt")
    check(
        "pin top square to its axis",
        await adapter.add_sketch_constraint(pin_axis, top_radius, "perpendicular"),
    )
    await dimension_between(
        adapter, f"{top_radius}.start", f"{top_radius}.end", "distance", PIN_RADIUS, "pin top radius"
    )
    section.record("ConePinTopRadius")
    await dimension_between(
        adapter,
        f"{gauge}.end",
        f"{top_radius}.end",
        "vertical_distance",
        CONE_PIN_HIGH_EDGE_HEIGHT,
        "cone pin high edge",
    )
    section.record("ConePinHighEdge")
    await ensure_fully_defined(adapter, "ConePinSectionReference")
    check("exit sketch ConePinSectionReference", await adapter.exit_sketch())
    name_last_feature(adapter, "ConePinSectionReference")
    drive_jobs += section.apply(adapter, "ConePinSectionReference")

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
            ("post axis", "AXIS"),
        ),
    )
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
