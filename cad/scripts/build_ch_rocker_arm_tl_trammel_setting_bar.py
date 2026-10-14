r"""Build the rocker trammel setting bar (MHA-CH-006-TL-17; shop gauge).

A 1018 cold-finished flat bar at its supply length with three trammel-point
seats on its centreline: H0 (pivot), H800 and H816 (scribers)
(``ch_rocker_arm_tl_trammel_setting_bar_spec``).

Layout (spec frame): the bar profile is a Top-plane rectangle, extruded -Y
so the seat face is y = 0. Each seat is one revolve cut of a half profile (cone
over a through pilot): H0 on the Right plane, so its sizes print on a
cross-section through H0; H800 and H816 on the Front plane, each placed by
its station from H0. The two stations print from hidden Top-plane reference
lines anchored on H0, so both are dimensioned from the pivot seat.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_trammel_setting_bar.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_dimension_insert import (
    add_angular_reference_dimension,
    add_diametric_linear_dimension,
)
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
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
from _sketch_chains import define_rectilinear_chain
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import set_dimension_bilateral_tolerance
from _fit_deviations import deviations
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_trammel_setting_bar_spec import (
    BAR_LENGTH,
    BAR_THICKNESS,
    BAR_WIDTH,
    DRAWING_BANDS,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    H0_FROM_END,
    H800,
    H816,
    ISOMETRIC_VIEW_NOTE,
    PILOT_DIA,
    REFERENCE_SKETCHES,
    SEAT_CONE_DEPTH,
    SEAT_DIA,
    SEAT_FLANK_ANGLE_DEG,
    SEAT_HALF_ANGLE_DEG,
)

PART_NAME = "ch-rocker-arm-tl-trammel-setting-bar"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 1018 CF flat stock
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# The pilot profile runs 1 mm past the far face so the cut leaves no skin.
PILOT_RUN = BAR_THICKNESS + 1.0
_RM = SEAT_DIA / 2.0
_RP = PILOT_DIA / 2.0
V_BAR = BAR_LENGTH * BAR_WIDTH * BAR_THICKNESS
V_SEAT = math.pi * SEAT_CONE_DEPTH / 3.0 * (
    _RM**2 + _RM * _RP + _RP**2
) + math.pi * _RP**2 * (BAR_THICKNESS - SEAT_CONE_DEPTH)


def _require_one_solid_body(adapter, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != 1:
        raise RuntimeError(
            f"{label}: expected exactly one solid body, found {len(bodies)}"
        )


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment, not the ISketchLine the registry binds)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _seat(
    adapter, *, sketch: str, plane: str, station: float, names: dict[str, str]
) -> list[tuple[str, str]]:
    """One seat: a closed half profile (mouth, cone, pilot wall to past the
    far face, back up the axis) revolved 360 deg as a cut about its axis.

    ``plane`` "Right" puts the profile at x = 0, (u, v) = (-z, y); "Front"
    puts it at z = 0, (u, v) = (x, y), and ``station`` offsets it along u.
    """
    from solidworks_mcp.adapters.base import RevolveParameters

    s = station
    points = [
        (s, 0.0),
        (s + _RM, 0.0),
        (s + _RP, -SEAT_CONE_DEPTH),
        (s + _RP, -PILOT_RUN),
        (s, -PILOT_RUN),
    ]
    dims = SketchDims()
    check(f"create_sketch {sketch}", await adapter.create_sketch(plane))
    # Direct-to-DB: the axis and the mouth lie on the sketch axes, so
    # creation-time inference would add relations the recipe then repeats.
    set_sketch_direct_db(adapter, True)
    axis = check(f"{sketch} axis", await adapter.add_centerline(s, 0.0, s, -PILOT_RUN))
    lines = await add_line_chain(adapter, points)
    set_sketch_direct_db(adapter, False)
    mouth, cone, wall, floor, back = lines
    for i in range(len(lines)):
        check(
            f"{sketch} junction {i}",
            await adapter.add_sketch_constraint(
                f"{lines[i]}.end", f"{lines[(i + 1) % len(lines)]}.start", "coincident"
            ),
        )
    # The axis takes both ends from the chain (no orientation of its own: the
    # back line's vertical already fixes it, and repeating it over-defines).
    for line, relation in (
        (mouth, "horizontal"),
        (wall, "vertical"),
        (floor, "horizontal"),
        (back, "vertical"),
    ):
        check(
            f"{sketch} {relation} {line}",
            await adapter.add_sketch_constraint(line, None, relation),
        )
    check(
        f"{sketch} axis top",
        await adapter.add_sketch_constraint(
            f"{axis}.start", f"{mouth}.start", "coincident"
        ),
    )
    check(
        f"{sketch} axis foot",
        await adapter.add_sketch_constraint(
            f"{axis}.end", f"{floor}.end", "coincident"
        ),
    )
    if s == 0.0:
        check(
            f"{sketch} seat on origin",
            await adapter.add_sketch_constraint(
                f"{mouth}.start", "origin", "coincident"
            ),
        )
    else:
        await anchor_point_to_origin(
            adapter, f"{mouth}.start", s, 0.0, f"{sketch} station"
        )
        dims.record(names.get("station"), names.get("station_drive"))
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{mouth}.end",
        text_xy=(s + _RM + 2.0, 1.0),
        label=f"{sketch} mouth diameter",
    )
    dims.record(names.get("dia"), '"SeatDia"')
    # The cone's depth below the face fixes the flank, not a driving angular
    # dimension: the adapter's angular form left this profile under-defined
    # on the farm (run 20261014T195954719Z), as it did the magnifying wheel's
    # tie 2 and the arm plate's countersinks. The drive keeps the 60 deg seat
    # when SeatDia or PilotDia moves; the printed angle is a driven reference.
    await dimension_between(
        adapter,
        f"{mouth}.end",
        f"{cone}.end",
        "vertical_distance",
        SEAT_CONE_DEPTH,
        f"{sketch} cone depth",
    )
    dims.record(
        "SeatConeDepth",
        f'("SeatDia" - "PilotDia") / 2 / tan({SEAT_HALF_ANGLE_DEG:g})',
    )
    # Text inside the face-to-flank wedge at the mouth vertex under either
    # reading of the location (sketch (u, v), or model with u collapsing to
    # the axis on the Right plane).
    await add_angular_reference_dimension(
        adapter,
        mouth,
        cone,
        (s + _RM - 2.6, -1.5),
        f"{sketch} flank angle",
        expected_degrees=SEAT_FLANK_ANGLE_DEG,
    )
    dims.record(names.get("angle"))
    await add_diametric_linear_dimension(
        adapter,
        axis,
        f"{wall}.end",
        text_xy=(s + _RP + 2.0, -PILOT_RUN - 1.0),
        label=f"{sketch} pilot diameter",
    )
    dims.record(names.get("pilot"), '"PilotDia"')
    await dimension_between(
        adapter,
        f"{back}.start",
        f"{back}.end",
        "vertical_distance",
        PILOT_RUN,
        f"{sketch} pilot run",
    )
    dims.record(None)
    await ensure_fully_defined(adapter, f"{sketch} profile")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    drive_jobs = dims.apply(adapter, sketch)
    check(
        f"revolve {sketch}",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    return drive_jobs


async def _reference_line(
    adapter, sketch: str, dimension: str, x: float, drive: str
) -> list[tuple[str, str]]:
    """One hidden-reference sketch: a Top-plane construction line from H0 to
    a station whose driving dimension IS the station."""
    check(f"create_sketch {sketch}", await adapter.create_sketch("Top"))
    # Direct-to-DB: the line lies on the sketch x axis, so creation-time
    # inference would over-define the sketch.
    set_sketch_direct_db(adapter, True)
    line = check(f"{sketch} line", await adapter.add_line(0.0, 0.0, x, 0.0))
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, line)
    check(
        f"{sketch} horizontal",
        await adapter.add_sketch_constraint(line, None, "horizontal"),
    )
    await dimension_between(
        adapter, f"{line}.start", f"{line}.end", "horizontal_distance", x, sketch
    )
    await anchor_point_to_origin(adapter, f"{line}.start", 0.0, 0.0, sketch)
    await ensure_fully_defined(adapter, f"{sketch} sketch")
    check(f"exit_sketch {sketch}", await adapter.exit_sketch())
    name_last_feature(adapter, sketch)
    full = name_dimensions(adapter, sketch, [dimension])
    measured = (
        float(
            _early_bound(
                adapter.currentModel.Parameter(full[0]), "IDimension"
            ).SystemValue
        )
        * 1000.0
    )
    if abs(measured - x) > 1e-6:
        raise RuntimeError(f"{full[0]} measures {measured:g} mm, expected {x:g} mm")
    return [(full[0], drive)]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "BarWidth", f"{BAR_WIDTH}mm")
    await set_global(adapter, "BarThickness", f"{BAR_THICKNESS}mm")
    await set_global(adapter, "H0FromEnd", f"{H0_FROM_END}mm")
    await set_global(adapter, "H800", f"{H800}mm")
    await set_global(adapter, "H816", f"{H816}mm")
    await set_global(adapter, "SeatDia", f"{SEAT_DIA}mm")
    await set_global(adapter, "PilotDia", f"{PILOT_DIA}mm")

    # Top plane (u, v) = (x, -z): the bar from H0_FROM_END left of H0, centred
    # across z, anchored at its corner so the seats sit on its centreline.
    profile = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Top"))
    points = [
        (-H0_FROM_END, -BAR_WIDTH / 2.0),
        (BAR_LENGTH - H0_FROM_END, -BAR_WIDTH / 2.0),
        (BAR_LENGTH - H0_FROM_END, BAR_WIDTH / 2.0),
        (-H0_FROM_END, BAR_WIDTH / 2.0),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label="bar profile",
        dims=profile,
        names=["BarLength", "BarWidth", "H0FromEnd", "H0FromSide"],
        drives=['"BarLength"', '"BarWidth"', '"H0FromEnd"', '"BarWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "bar profile")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs = profile.apply(adapter, "BarProfile")
    # Reversed: -Y, so the Top plane is the seat face.
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Bar")
    drive_jobs.append(
        (name_dimensions(adapter, "Bar", ["BarThickness"])[0], '"BarThickness"')
    )
    volume = await volume_check(adapter, "bar", V_BAR, 0.002 * V_BAR)

    seat_names = {"dia": "SeatDia", "angle": "SeatFlankAngle", "pilot": "PilotDia"}
    for sketch, feature, plane, station, extra in (
        ("H0SeatProfile", "H0Seat", "Right", 0.0, {}),
        (
            "H800SeatProfile",
            "H800Seat",
            "Front",
            H800,
            {"station": "H800SeatX", "station_drive": '"H800"'},
        ),
        (
            "H816SeatProfile",
            "H816Seat",
            "Front",
            H816,
            {"station": "H816SeatX", "station_drive": '"H816"'},
        ),
    ):
        # Every seat follows the globals; only H0's are marked for the sheet.
        names = {**seat_names, **extra}
        drive_jobs += await _seat(
            adapter, sketch=sketch, plane=plane, station=station, names=names
        )
        name_last_feature(adapter, feature)
        # A seat sketched on the wrong side of the bar cuts nothing.
        volume = await volume_check(
            adapter, f"{feature} seat", volume - V_SEAT, 0.02 * V_SEAT + 0.05
        )
    _require_one_solid_body(adapter, label="seated bar")

    # The stations' drawing-reference lines from H0 (no metal).
    drive_jobs += await _reference_line(
        adapter, "H800Reference", "H800X", H800, '"H800"'
    )
    drive_jobs += await _reference_line(
        adapter, "H816Reference", "H816X", H816, '"H816"'
    )

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", volume, 0.002 * V_BAR)
    _require_one_solid_body(adapter, label="driven bar")
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for (feature_name, dimension_name), band in DRAWING_BANDS.items():
        set_dimension_bilateral_tolerance(
            adapter, feature_name, dimension_name, *deviations(band)
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
