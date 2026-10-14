r"""Build the rocker template trammel's pivot plate (MHA-CH-006-TL-19; shop fixture).

A 1018 bar offcut screwed to the MDF scribing board; the trammel's 60 degree
pivot point runs in its centre-drilled seat while R800/R816 are scribed
(``ch_rocker_arm_tl_trammel_pivot_plate_spec``).

Layout (the spec's model frame, +Y up): the plate is a Top-plane rectangle
(sketch v along model -Z) extruded +Y by the stock height; the two screw holes
are Top-plane circles cut through; the 5/64 pilot is a circle on a plane at
the seat face, cut blind down into the plate. The seat cone and the two
countersinks are revolved cuts sketched on a plane through the hole axes
(model Z = -HOLE_Y), each a triangle from the face to its cone's apex. The
cone depth drives the flank; the face-to-flank angle is a driven reference
dimension at the mouth vertex.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_trammel_pivot_plate.py
"""

from __future__ import annotations

import math
import sys
from collections.abc import Callable
from typing import Any

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_dimension_insert import (
    add_angular_reference_dimension,
    add_diametric_linear_dimension,
)
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from ch_rocker_arm_tl_trammel_pivot_plate_spec import (
    CSK_DIA,
    CSK_FLANK_ANGLE,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRILLED_BAND,
    DRILLED_DIMENSIONS,
    HOLE_DIA,
    HOLE_Y,
    ISOMETRIC_VIEW_NOTE,
    PILOT_DEPTH,
    PILOT_DIA,
    PLATE_HEIGHT,
    PLATE_LENGTH,
    PLATE_WIDTH,
    SCREW_X,
    SEAT_DIA,
    SEAT_FLANK_ANGLE,
    SEAT_X,
)

PART_NAME = "ch-rocker-arm-tl-trammel-pivot-plate"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 bar offcut
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# Above the seat face: the revolve axis centerline's free end.
AXIS_OVERRUN = 2.0
THROUGH_CUT_DEPTH = 2.0 * PLATE_HEIGHT

_R_HOLE = HOLE_DIA / 2.0
_R_PILOT = PILOT_DIA / 2.0


def _cone_cut_volume(mouth_r: float, flank_deg: float, bore_r: float) -> float:
    """A cone from a mouth on the face to its apex on the axis, less the part
    of it a coaxial bore (deeper than the apex) has already removed."""
    rise = math.tan(math.radians(flank_deg))
    cone = math.pi * mouth_r**2 * (mouth_r * rise) / 3.0
    inside_bore = 2.0 * math.pi * rise * (mouth_r * bore_r**2 / 2.0 - bore_r**3 / 3.0)
    return cone - inside_bore


V_PLATE = PLATE_LENGTH * PLATE_WIDTH * PLATE_HEIGHT
V_HOLES = len(SCREW_X) * math.pi * _R_HOLE**2 * PLATE_HEIGHT
V_PILOT = math.pi * _R_PILOT**2 * PILOT_DEPTH
V_SEAT = _cone_cut_volume(SEAT_DIA / 2.0, SEAT_FLANK_ANGLE, _R_PILOT)
V_CSK = _cone_cut_volume(CSK_DIA / 2.0, CSK_FLANK_ANGLE, _R_HOLE)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _sketch_mapper(
    adapter: Any, *, u_axis: int, v_axis: int, label: str
) -> Callable[[tuple[float, float, float]], tuple[float, float]]:
    """Map model points (mm) into the ACTIVE sketch, requiring model axis
    ``u_axis`` along the sketch's u and ``v_axis`` along its v (either sign).

    A plane's sketch axes are SolidWorks' choice; the profile points go
    through ``ModelToSketchTransform`` so only the orientation (which
    relations read horizontal/vertical) is assumed, and it is checked here
    (build_pd_transgear_arm_plate's mapper). Coordinates are rounded to the
    nanometre so axis-parallel segments compare equal.
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
        u, v = round(u, 9), round(v, 9)
        return (0.0 if abs(u) < 1e-9 else u, 0.0 if abs(v) < 1e-9 else v)

    return to_sketch


async def _cone_cut(
    adapter: Any,
    *,
    sketch_name: str,
    feature_name: str,
    x: float,
    mouth_r: float,
    flank_deg: float,
    names: tuple[str, str, str, str, str, str],
    drives: tuple[str, str, str],
    label: str,
) -> list[tuple[str, str]]:
    """Revolve-cut one cone on HoleAxisPlane: mouth on the seat face at model
    X = ``x``, apex on the axis ``mouth_r * tan(flank)`` below it.

    Profile: axis-top P0 (on the face) -> mouth P1 -> apex P2 -> P0, with
    explicit junction coincidences (build_ch_rocker_arm_tl_trammel_setting_bar's
    seat, farm-proven). The revolve axis is a centerline from P0 up past the
    face (build_pd_transgear_arm_plate's countersinks). The cone's depth from
    the mouth to the apex fixes the flank, driven from the mouth diameter and
    the half-angle: the adapter's driving angular dimension leaves the profile
    under-defined on the farm (this plate's seat, round 1; the setting bar's
    seat; the magnifying wheel's tie 2). The printed face-to-flank angle is a
    driven reference at the shared mouth vertex, so its interior angle is the
    flank angle itself. ``names`` follow creation order: station, face height,
    mouth diameter, cone depth, flank angle, axis length; ``drives`` are the
    station, face height and mouth diameter expressions.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch("HoleAxisPlane"))
    to_sketch = _sketch_mapper(adapter, u_axis=0, v_axis=1, label=label)
    origin = to_sketch((0.0, 0.0, -HOLE_Y))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"{label}: sketch origin maps to {origin}")
    drop = mouth_r * math.tan(math.radians(flank_deg))
    profile = [
        to_sketch((x, PLATE_HEIGHT, -HOLE_Y)),
        to_sketch((x + mouth_r, PLATE_HEIGHT, -HOLE_Y)),
        to_sketch((x, PLATE_HEIGHT - drop, -HOLE_Y)),
    ]
    set_sketch_direct_db(adapter, True)
    axis = check(
        f"{label} axis",
        await adapter.add_centerline(
            *profile[0], *to_sketch((x, PLATE_HEIGHT + AXIS_OVERRUN, -HOLE_Y))
        ),
    )
    lines = await add_line_chain(adapter, profile)
    set_sketch_direct_db(adapter, False)
    face, flank, axis_side = lines
    for i in range(len(lines)):
        check(
            f"{label} junction {i}",
            await adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    for first, second, relation in (
        (face, None, "horizontal"),
        (axis_side, None, "vertical"),
        (axis, None, "vertical"),
        (f"{axis}.start", f"{face}.start", "coincident"),
    ):
        check(
            f"{label} {relation} {first}",
            await adapter.add_sketch_constraint(first, second, relation),
        )
    station, face_height, dia, depth, angle, axis_length = names
    d_station, d_face, d_dia = drives
    await dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "horizontal_distance",
        abs(profile[0][0]),
        f"{label} station",
    )
    dims.record(station, d_station)
    await dimension_between(
        adapter,
        "origin",
        f"{face}.start",
        "vertical_distance",
        abs(profile[0][1]),
        f"{label} on the seat face",
    )
    dims.record(face_height, d_face)
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{flank}.start",
        to_sketch((x + mouth_r, PLATE_HEIGHT + 3.0, -HOLE_Y)),
        f"{label} mouth diameter",
    )
    dims.record(dia, d_dia)
    await dimension_between(
        adapter,
        f"{flank}.start",
        f"{flank}.end",
        "vertical_distance",
        drop,
        f"{label} cone depth",
    )
    dims.record(depth, f"{d_dia} / 2 / tan({90.0 - flank_deg:g})")
    # Text on the wedge's bisector at the mouth vertex, inside the profile.
    bisector = math.radians(180.0 + flank_deg / 2.0)
    reach = 0.5 * mouth_r
    await add_angular_reference_dimension(
        adapter,
        face,
        flank,
        to_sketch(
            (
                x + mouth_r + reach * math.cos(bisector),
                PLATE_HEIGHT + reach * math.sin(bisector),
                -HOLE_Y,
            )
        ),
        f"{label} face-to-flank angle",
        expected_degrees=flank_deg,
    )
    dims.record(angle)
    check(
        f"{label} axis length",
        await adapter.add_sketch_dimension(axis, None, "linear", AXIS_OVERRUN),
    )
    dims.record(axis_length)
    await ensure_fully_defined(adapter, f"{label} profile")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch_name)
    jobs = dims.apply(adapter, sketch_name)
    check(
        f"revolve-cut {label}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, feature_name)
    return jobs


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for name, value in (
        ("PlateLength", PLATE_LENGTH),
        ("PlateWidth", PLATE_WIDTH),
        ("PlateHeight", PLATE_HEIGHT),
        ("HoleLeftX", SCREW_X[0]),
        ("HoleRightX", SCREW_X[1]),
        ("HoleY", HOLE_Y),
        ("HoleDia", HOLE_DIA),
        ("SeatX", SEAT_X),
        ("PilotDia", PILOT_DIA),
        ("PilotDepth", PILOT_DEPTH),
        ("SeatDia", SEAT_DIA),
        ("CskDia", CSK_DIA),
    ):
        await set_global(adapter, name, f"{value}mm")

    # --- Plate: Top-plane rectangle from the origin, extruded +Y ------------
    plate = SketchDims()
    check("create_sketch plate", await adapter.create_sketch("Top"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="plate profile")
    points = [
        to_top((0.0, 0.0, 0.0)),
        to_top((PLATE_LENGTH, 0.0, 0.0)),
        to_top((PLATE_LENGTH, 0.0, -PLATE_WIDTH)),
        to_top((0.0, 0.0, -PLATE_WIDTH)),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="plate profile",
        dims=plate,
        names=["PlateLength", "PlateWidth"],
        drives=['"PlateLength"', '"PlateWidth"'],
    )
    await ensure_fully_defined(adapter, "plate profile")
    check("exit_sketch plate", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs = plate.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_HEIGHT)),
    )
    name_last_feature(adapter, "Plate")
    drive_jobs.append(
        (name_dimensions(adapter, "Plate", ["PlateHeight"])[0], '"PlateHeight"')
    )
    volume = await volume_check(adapter, "plate", V_PLATE, 0.002 * V_PLATE)

    # --- Screw clearance holes, through on the mid-width line ---------------
    holes = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Top"))
    to_top = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="screw holes")
    for x, names, drives in zip(
        SCREW_X,
        (("HoleLeftX", "HoleY", "HoleDia"), ("HoleRightX", "HoleRightY", "HoleDia2")),
        (
            ('"HoleLeftX"', '"HoleY"', '"HoleDia"'),
            ('"HoleRightX"', '"HoleY"', '"HoleDia"'),
        ),
        strict=True,
    ):
        await define_circle(
            adapter,
            *to_top((x, 0.0, -HOLE_Y)),
            _R_HOLE,
            f"screw hole X{x:g}",
            dims=holes,
            names=names,
            drives=drives,
        )
    await ensure_fully_defined(adapter, "screw-hole sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += holes.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    volume = await volume_check(
        adapter, "screw holes", volume - V_HOLES, 0.01 * V_HOLES
    )

    # --- Named planes: the seat face and the hole axes' mid-width plane -----
    check(
        "create_plane TopFace",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=PLATE_HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "TopFace")
    drive_jobs.append(
        (name_dimensions(adapter, "TopFace", ["TopFaceOffset"])[0], '"PlateHeight"')
    )
    check(
        "create_plane HoleAxisPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=-HOLE_Y
            )
        ),
    )
    name_last_feature(adapter, "HoleAxisPlane")
    blank_reference_geometry(
        adapter, (("TopFace", "PLANE"), ("HoleAxisPlane", "PLANE"))
    )

    # --- Seat pilot: 5/64 blind from the seat face --------------------------
    # A cut on a plane runs against the plane normal by default (+Y here),
    # so it enters the plate from the seat face.
    pilot = SketchDims()
    check("create_sketch pilot", await adapter.create_sketch("TopFace"))
    to_face = _sketch_mapper(adapter, u_axis=0, v_axis=2, label="pilot")
    origin = to_face((0.0, PLATE_HEIGHT, 0.0))
    if origin != (0.0, 0.0):
        raise RuntimeError(f"pilot: sketch origin maps to {origin}")
    await define_circle(
        adapter,
        *to_face((SEAT_X, PLATE_HEIGHT, -HOLE_Y)),
        _R_PILOT,
        "seat pilot",
        dims=pilot,
        names=("PilotX", "PilotY", "PilotDia"),
        drives=('"SeatX"', '"HoleY"', '"PilotDia"'),
    )
    await ensure_fully_defined(adapter, "pilot sketch")
    check("exit_sketch pilot", await adapter.exit_sketch())
    name_last_feature(adapter, "PilotProfile")
    drive_jobs += pilot.apply(adapter, "PilotProfile")
    check(
        "cut pilot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=PILOT_DEPTH)),
    )
    name_last_feature(adapter, "Pilot")
    drive_jobs.append(
        (name_dimensions(adapter, "Pilot", ["PilotDepth"])[0], '"PilotDepth"')
    )
    volume = await volume_check(
        adapter, "seat pilot", volume - V_PILOT, 0.01 * V_PILOT + 0.05
    )

    # --- The 60 degree seat cone over the pilot ------------------------------
    drive_jobs += await _cone_cut(
        adapter,
        sketch_name="SeatProfile",
        feature_name="Seat",
        x=SEAT_X,
        mouth_r=SEAT_DIA / 2.0,
        flank_deg=SEAT_FLANK_ANGLE,
        names=(
            "SeatStation",
            "SeatFace",
            "SeatDia",
            "SeatConeDepth",
            "SeatFlankAngle",
            "SeatAxisLength",
        ),
        drives=('"SeatX"', '"PlateHeight"', '"SeatDia"'),
        label="seat cone",
    )
    volume = await volume_check(
        adapter, "seat cone", volume - V_SEAT, 0.03 * V_SEAT + 0.05
    )

    # --- 90 degree countersinks on the screw holes --------------------------
    for index, (x, x_drive) in enumerate(
        zip(SCREW_X, ('"HoleLeftX"', '"HoleRightX"'), strict=True), start=1
    ):
        suffix = "" if index == 1 else str(index)
        drive_jobs += await _cone_cut(
            adapter,
            sketch_name=f"CountersinkProfile{index}",
            feature_name=f"Countersink{index}",
            x=x,
            mouth_r=CSK_DIA / 2.0,
            flank_deg=CSK_FLANK_ANGLE,
            names=(
                f"Csk{index}X",
                f"Csk{index}Face",
                f"CskDia{suffix}",
                f"Csk{index}ConeDepth",
                f"CskFlankAngle{suffix}",
                f"Csk{index}AxisLength",
            ),
            drives=(x_drive, '"PlateHeight"', '"CskDia"'),
            label=f"countersink {index}",
        )
        volume = await volume_check(
            adapter, f"countersink {index}", volume - V_CSK, 0.03 * V_CSK + 0.05
        )
    _require_one_solid_body(adapter, label="pivot plate")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pivot plate (equations neutral)", volume, 0.002 * V_PLATE
    )
    _require_one_solid_body(adapter, label="driven pivot plate")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for feature_name, dimension_name in DRILLED_DIMENSIONS:
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(DRILLED_BAND)
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
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
