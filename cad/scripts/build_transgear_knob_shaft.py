r"""Reproduction script: transgear knob shaft MHA-078 (book ch. 23, pp. 56-59).

The shaft riding the latch arm's small hub: it carries the mounted
removable sprocket MHA-081 (ANSI #25, chain-wrapped -- the chain rides the
removable's teeth directly) seated on an integral collar, the 12T DP38 third
gear (build_transgear_pinion.py) on a turned-down O5 seat directly behind
that collar (at DP 38 the 12T root sits below a 3/8" shaft's surface, so the
seat steps down), and ends in the large brass thumb knob (engineerguy
v4_transgear_008/020). The knob's reeding is omitted (simplification -- the
reeding recipe needs an X-axis layout and this part's stack is sized along
its axis).

The seat is the one both removable shafts share (transgear_removable_spec):
a O17.5 x 4.6 collar (the crank's seat-spigot diameter) whose FRONT face is
the seat face the wheel's rear face bears on, the wheel piloted on the plain
O9.525 shaft in front of it, and two MHA-155 dowels pressed into holes reamed
THROUGH the collar on the wheel's O14 pin circle. No floor stops the press:
each pin is pressed in from the seat face onto a stop that leaves it
DRIVE_PIN_PROUD out (knob_pin.PROUD_RANGE, printed on the MHA-155 sheet),
its pressed end PIN_PRESS_DEPTH behind the seat face and inside the collar,
whose rear face stays clear of the 120T disc even at the collar's long .X
limit (paper-drive asserts it).

Layout: axis +Y, origin at the FRONT tip of the pilot; the assembly rotates
+Y to +Z (machine back) and places the seat face on the removable band's
SEAT_FACE_Z. Pilot y 0..PILOT_LEN (the plain thread stub the thumbnut runs
onto, then the wheel's pilot), collar to y COLLAR_REAR, O5 third-gear seat,
rear section (latch small hub near the knob), knob.

Named datums (blanked, selectable): ``Axis1`` the shaft axis; planes
``SeatCollar`` (seat face), ``CollarRear`` and ``DrivePinFloor`` (the pins'
pressed-end station -- the name the crankshaft's blind floor carries; here it
is the press stop's station inside the through holes); axes ``DrivePinAxis1``
(local +Z) and ``DrivePinAxis2`` (local -Z) through the pin holes -- the same
names the crankshaft MHA-026 carries for the identical seat.

Walls below the 1.5 floor: pin hole to the O9.525 shaft core 1.05
(reported), pin hole to the collar rim (DRIVE_PIN_COLLAR_RIM_NOTE).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_knob_shaft.py
"""

from __future__ import annotations

import math
import sys

import _telemetry
import crankshaft_spec
import transgear_knob_drive_pin_spec as knob_pin
import transgear_removable_spec as removable
from _common import (
    IN,
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
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
from _visibility import blank_reference_geometry

PART_NAME = "transgear-knob-shaft"
MATERIAL = "Brass"

SHAFT_DIA = 0.375 * IN  # 9.525 (low): pilot, thread stub and hub ride
# Pilot + thumbnut stub in front of the seat face. The nut neck stands
# THUMBNUT_AIR in front of the wheel (-157.35..-168.35); the shaft front
# lands 0.45 inside the nut's front face, past its disc mid-depth
# (paper-drive's thumbnut-fit assert pins both).
PILOT_LEN = 13.6
COLLAR_DIA = removable.SEAT_SPIGOT_DIA  # 17.5, the crank's seat spigot
# Seat face to the collar rear (machine -154.3..-149.7), DISC_AIR in front of
# the 120T disc / third gear front face (-148.4).  MHA-078 has no sheet, so
# the collar length carries the title block's .X +/-0.8: the collar is that
# much shorter than the 5.4 that took up the 2026-09-30 seat shift, so at its
# long limit the rear face still stands 0.5 off the disc (paper-drive owns
# the disc station and asserts the worst case).
COLLAR_LEN = 4.6
DISC_AIR = 1.3
SEAT_DIA = 5.0  # turned-down third-gear seat (12T DP38 root < 3/8" surface)
SEAT_LEN = DISC_AIR + 4.0 + 1.5  # air + third gear face 4 + 1.5 (to z -142.9)
REAR_LEN = 12.9  # to the knob face; latch small hub rides z -132.75..-130.15
KNOB_DIA = 20.0  # large brass thumb knob (low)
KNOB_LEN = 6.5

PIN_CIRCLE_RADIUS = removable.PIN_CIRCLE_RADIUS  # 7, the wheel's pin circle
PIN_HOLE_DIA = removable.DRIVE_PIN_HOLE_DIA  # 2.38 reamed for the press
PIN_PRESS_DEPTH = knob_pin.PRESS_DEPTH  # 2.3625, pressed end behind the seat face

# Local stations along +Y.
SEAT_COLLAR = PILOT_LEN  # the seat face (SeatCollar datum)
COLLAR_REAR = SEAT_COLLAR + COLLAR_LEN
DRIVE_PIN_FLOOR = SEAT_COLLAR + PIN_PRESS_DEPTH  # the pins' pressed-end station
PIN_HOLE_DEPTH = COLLAR_LEN  # reamed THROUGH, seat face to rear face
SEAT_END = COLLAR_REAR + SEAT_LEN
KNOB_FACE = SEAT_END + REAR_LEN
TIP = KNOB_FACE + KNOB_LEN

# Drive-pin hole guards.
WALL_FLOOR = 1.5  # drawing-simplicity policy rule 12 hard floor


def pin_hole_meets_wall_floor(collar_len: float, hole_depth: float) -> bool:
    """A drive-pin hole reamed ``hole_depth`` from the seat face into a collar
    ``collar_len`` long either runs through it or leaves at least the wall
    floor between its floor and the collar's rear face (pass print-worst
    values: the longest hole in the shortest collar)."""
    return hole_depth >= collar_len or collar_len - hole_depth >= WALL_FLOOR


def pin_rear_inset(collar_len: float, pin_length: float, proud: float) -> float:
    """How far a pin set ``proud`` out of the seat face keeps its pressed end
    inside the collar's rear face (negative: it stands out of the rear)."""
    return collar_len - (pin_length - proud)


# Wall report (policy 2.0 target / 1.5 floor).
PIN_HOLE_R = PIN_HOLE_DIA / 2.0
WALL_PIN_TO_CORE = PIN_CIRCLE_RADIUS - PIN_HOLE_R - SHAFT_DIA / 2.0  # 1.05
# Pin hole to the O17.5 collar rim: the collar is machined to the crank's seat
# interface, so its print-worst uses the crankshaft's seat bands (rounded DOWN).
DRIVE_PIN_COLLAR_RIM = removable.SEAT_SPIGOT_RIM  # 0.56 nominal
DRIVE_PIN_COLLAR_RIM_WORST = (
    math.floor(
        (
            (COLLAR_DIA + crankshaft_spec.SPIGOT_DIA_BAND[1]) / 2.0
            - PIN_CIRCLE_RADIUS
            - crankshaft_spec.DRIVE_PIN_OFFSET_TOL
            - (PIN_HOLE_DIA + crankshaft_spec.DRIVE_PIN_HOLE_BAND[0]) / 2.0
        )
        * 100.0
        + 1e-9
    )
    / 100.0
)  # 0.48
# Named exception: MHA-078 rim (drawing-simplicity-policy.md, "Named exceptions").
DRIVE_PIN_COLLAR_RIM_NOTE = (
    f"DRIVE-PIN HOLE TO COLLAR RIM {DRIVE_PIN_COLLAR_RIM_WORST:.2f} MIN."
)

if not pin_hole_meets_wall_floor(COLLAR_LEN, PIN_HOLE_DEPTH):
    raise AssertionError("the drive-pin holes leave a floor under the 1.5 wall floor")
# The stop sets the tip, so the longest dowel set lowest reaches furthest
# back.  It must stay inside the collar even with the collar at the title
# block's loosest .X row: behind the rear face lies only DISC_AIR before the
# 120T disc, whose teeth sweep the pin circle.
PIN_REAR_INSET_WORST = pin_rear_inset(
    COLLAR_LEN - crankshaft_spec.STATION_ROW,
    knob_pin.LENGTH + crankshaft_spec.DRIVE_PIN_LENGTH_GRADE,
    min(knob_pin.PROUD_RANGE),
)  # 1.08
if PIN_REAR_INSET_WORST < 0.0:
    raise AssertionError(
        "a pressed knob drive pin stands out of the collar's rear face"
    )
_rim = COLLAR_DIA / 2.0 - PIN_CIRCLE_RADIUS - PIN_HOLE_R
if abs(_rim - DRIVE_PIN_COLLAR_RIM) > 0.01:
    raise AssertionError("knob collar rim disagrees with SEAT_SPIGOT_RIM")
if WALL_PIN_TO_CORE <= 0.0 or DRIVE_PIN_COLLAR_RIM_WORST <= 0.0:
    raise AssertionError("drive-pin holes break into the shaft core or collar rim")

_R_S = SHAFT_DIA / 2.0
_R_C = COLLAR_DIA / 2.0
V_SHAFT = math.pi * (
    _R_S**2 * (PILOT_LEN + REAR_LEN)
    + _R_C**2 * COLLAR_LEN
    + (SEAT_DIA / 2.0) ** 2 * SEAT_LEN
    + (KNOB_DIA / 2.0) ** 2 * KNOB_LEN
)
V_PIN_HOLES = 2.0 * math.pi * PIN_HOLE_R**2 * PIN_HOLE_DEPTH
V_TOTAL = V_SHAFT - V_PIN_HOLES


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        RevolveParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section diameters and axial
    # lengths. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 12.5 =
    # 12.5 in); SHAFT_DIA is already 0.375 in expressed in mm, so it goes in as
    # "9.525mm".
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "PilotLen", f"{PILOT_LEN}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")
    await set_global(adapter, "SeatDia", f"{SEAT_DIA}mm")
    await set_global(adapter, "SeatLen", f"{SEAT_LEN}mm")
    await set_global(adapter, "RearLen", f"{REAR_LEN}mm")
    await set_global(adapter, "KnobDia", f"{KNOB_DIA}mm")
    await set_global(adapter, "KnobLen", f"{KNOB_LEN}mm")
    await set_global(adapter, "PinCircleRadius", f"{PIN_CIRCLE_RADIUS}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinPressDepth", f"{PIN_PRESS_DEPTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("axis centerline", await adapter.add_centerline(0.0, 0.0, 0.0, TIP))
    profile_pts = [
        (0.0, 0.0),
        (_R_S, 0.0),
        (_R_S, SEAT_COLLAR),
        (_R_C, SEAT_COLLAR),
        (_R_C, COLLAR_REAR),
        (SEAT_DIA / 2.0, COLLAR_REAR),
        (SEAT_DIA / 2.0, SEAT_END),
        (_R_S, SEAT_END),
        (_R_S, KNOB_FACE),
        (KNOB_DIA / 2.0, KNOB_FACE),
        (KNOB_DIA / 2.0, TIP),
        (0.0, TIP),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, TIP) profile corners at
    # creation, so the closed chain's own constraints define it too.
    # Emission order (anchor vertex 0 at the origin = 0 dims; segments 0..9,
    # segment 10 closes onto the anchor): one dim per axis-parallel segment.
    # Radial steps are radius DIFFERENCES, driven as derived exprs.
    await define_polygon_chain(
        adapter,
        profile_lines,
        profile_pts,
        label="shaft",
        dims=profile,
        names=[
            "ShaftRadius",
            "PilotLength",
            "CollarStepUp",
            "CollarLand",
            "CollarStepDown",
            "SeatLength",
            "SeatStepUp",
            "RearLength",
            "KnobStep",
            "KnobLength",
            "KnobRadius",
        ],
        drives=[
            '"ShaftDia" / 2',
            '"PilotLen"',
            '("CollarDia" - "ShaftDia") / 2',
            '"CollarLen"',
            '("CollarDia" - "SeatDia") / 2',
            '"SeatLen"',
            '("ShaftDia" - "SeatDia") / 2',
            '"RearLen"',
            '("KnobDia" - "ShaftDia") / 2',
            '"KnobLen"',
            '"KnobDia" / 2',
        ],
    )
    await ensure_fully_defined(adapter, "shaft profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += profile.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")
    await volume_check(adapter, "shaft + seat collar", V_SHAFT, 0.005 * V_SHAFT)

    # Shaft axis first so it stays Axis1 (the pin-hole axes are renamed); the
    # paper-drive mates the T24's Axis1 to it by that name.
    shaft_axis = await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis"
    )
    if shaft_axis != "Axis1":
        raise RuntimeError(
            f"knob shaft axis came out {shaft_axis!r}, mates expect Axis1"
        )

    # Seat datums along the axis, offsets from Top (the y = 0 pilot tip).
    stations = (
        ("SeatCollar", SEAT_COLLAR, '"PilotLen"'),
        ("CollarRear", COLLAR_REAR, '"PilotLen" + "CollarLen"'),
        ("DrivePinFloor", DRIVE_PIN_FLOOR, '"PilotLen" + "PinPressDepth"'),
    )
    for plane, station, expr in stations:
        check(
            f"create_plane {plane} (Top Plane + {station:g})",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset", base_plane="Top Plane", offset=station
                )
            ),
        )
        name_last_feature(adapter, plane)
        station_dim = name_dimensions(adapter, plane, [f"{plane}Station"])
        drive_jobs += [(station_dim[0], expr)]
    blank_reference_geometry(
        adapter, tuple((plane, "PLANE") for plane, _, _ in stations)
    )

    # THROUGH drive-pin holes, sketched on the CollarRear station and cut
    # toward Top (a cut's default runs opposite the sketch normal): the whole
    # collar to the seat face, then out into air over the O9.525 pilot, so the
    # extra millimetre only guarantees a clean break-out (behind the rear face
    # lies only the O5 seat, well inside the holes); the volume gate fails loud
    # on a wrong-side cut.
    holes = SketchDims()
    check("create_sketch pin holes", await adapter.create_sketch("CollarRear"))
    set_sketch_direct_db(adapter, True)
    for label, z in (("PinPos", PIN_CIRCLE_RADIUS), ("PinNeg", -PIN_CIRCLE_RADIUS)):
        await define_circle(
            adapter,
            0.0,
            z,
            PIN_HOLE_R,
            f"drive-pin hole {label}",
            dims=holes,
            names=(f"{label}X", f"{label}Z", f"{label}Dia"),
            drives=(None, '"PinCircleRadius"', '"PinHoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "pin-hole sketch")
    check("exit_sketch pin holes", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += holes.apply(adapter, "PinHoleProfile")
    check(
        "cut pin holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIN_HOLE_DEPTH + 1.0)
        ),
    )
    name_last_feature(adapter, "PinHoles")
    await volume_check(adapter, "collar drive-pin holes", V_TOTAL, 0.1 * V_PIN_HOLES)

    # The pins' axes: DrivePinAxis1 on local +Z (machine -Y once placed
    # Rx+90), DrivePinAxis2 opposite -- the crankshaft's convention.
    for axis_name, z in (
        ("DrivePinAxis1", PIN_CIRCLE_RADIUS),
        ("DrivePinAxis2", -PIN_CIRCLE_RADIUS),
    ):
        await name_bore_axis(
            adapter,
            "Right Plane",
            0.0,
            "Front Plane",
            z,
            axis_name,
            drive_b='"PinCircleRadius"',
            drive_jobs=drive_jobs,
        )
        name_last_feature(adapter, axis_name)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shaft (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _telemetry.info(
        f"seat collar walls (floor 1.5): pin hole to shaft core"
        f" {WALL_PIN_TO_CORE:.2f}; {DRIVE_PIN_COLLAR_RIM_NOTE} (nominal"
        f" {DRIVE_PIN_COLLAR_RIM:.2f}); pin holes reamed through, pins set"
        f" {min(knob_pin.PROUD_RANGE):.2f}..{max(knob_pin.PROUD_RANGE):.2f} proud,"
        f" pressed end {PIN_REAR_INSET_WORST:.4f} min inside the collar rear"
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
