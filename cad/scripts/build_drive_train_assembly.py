r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 76 above it):

* crankshaft along Z at (+122.3, 126.8) in the green crank pedestal:
  crank arm + handle at the front, chain sprocket and the 16T DP 16
  pinion inboard (the removable tapered pin is OMITTED: a tapered pin
  cannot sit in the straight 5 mm cross-holes without solid
  interference -- reaming the holes conical is deferred).
* cone set on its stepped shaft, axis inclined 19.8 deg in PLAN
  (arcsin(2.54/7.5), appendix C #3): 20 cone-gear configurations
  T120..T006 at the stack stations, the 64T crank-drive gear 8.5 mm
  outboard of T120, big-end journal in the black pivot post, thin tip
  resting in the green knob post's U-slot.
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-46.0, 126.8) (M6.2 keyway refutation),
  clamped by the two arbor pedestals; notches up = cosine setup
  (pp. 66-67).

Positions per cad/DIMENSIONS.md ch. 13 "Drive-train layout" +
"Drive supports". Tooth phasing: every gear script seeds a TOOTH centred
on local +X (`build_cone_gear.py` profile derivation), so at each mesh
the driven side presents a tooth to the driver's tooth; the drum gears
are pre-rotated +1.5 deg (half a 3 deg pitch) and the crank pinion
+11.25 deg (half of 22.5) to land tooth-in-gap. The cone gears keep
phase 0: their even tooth counts put a tooth at azimuth 180 (toward the
drum) and the line of centres is horizontal, so the rotated drum gap
receives it.

Every component is inserted at its exact final transform and FIXED
(saved state fully defined; the 19.8 deg components cannot be fully
constrained by axis-aligned plane mates, and the meshed/locked gear
phases ARE the book's cosine setup state). Kinematic gear-ratio
verification is deferred to a dedicated motion script that floats the
gears (M6 acceptance). Final asserts: every component fixed or fully
constrained, placement read-back exact, and zero interferences
(tangent/coincident contact allowed -- bores ride their shafts).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_drive_train_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    OUT_SLDPRT,
    assert_component_placed,
    assert_components_fully_defined,
    check,
    check_no_interference,
    log,
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 76.0  # 126.8: crank, cone big end and arbor axes

INCLINE_DEG = math.degrees(math.asin(2.54 / 7.5))  # 19.8: cone plan incline
SIN_I = 2.54 / 7.5
COS_I = math.cos(math.radians(INCLINE_DEG))

SEAT_PITCH = 7.5  # cone stack pitch along the shaft (annotated p.18)
X_T120 = 55.6  # big-end station (DIMENSIONS.md drive-train layout)
Z_T120 = -67.1  # = -19/2 x 7.06: stack centred between the gates
GEAR64_OFFSET = 8.5  # 64T centre toward the pivot from T120: (7 + 10)/2
X_64 = X_T120 + GEAR64_OFFSET * SIN_I  # 58.48
Z_64 = Z_T120 - GEAR64_OFFSET * COS_I  # -75.10
X_CRANK = X_64 + 63.5 + 0.3  # DP16 64T+16T centres + skew-mesh backlash
X_DRUM = X_T120 - 101.6  # -46.0: DP30 120T+120T centres at the big end

# Cone shaft: pivot end at seat station -28.75 from the T120 centre
# (25 journal + half of the first 7.5 seat -- build_cone_gear_shaft.py).
SHAFT_T120_STATION = 28.75
CONE_ORIGIN = [
    X_T120 + SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    Z_T120 - SHAFT_T120_STATION * COS_I,
]

CONE_FACE = 7.0  # cone gear face width (annotated p.18)
GEAR64_FACE = 10.0
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)
PINION_FACE = 12.0

ARBOR_LENGTH = 200.0  # spans z -100..+100
CRANKSHAFT_Z0 = -150.0  # front end; crank-arm hub at +12 (PIN_HOLE_HEIGHT)
CRANK_ARM_Z0 = CRANKSHAFT_Z0 + 8.0  # hub centre 12 - half thickness 4
ARM_C2C = 150.0  # handle pivot from the shaft axis
SPROCKET_Z0 = -81.0  # face 4.5: between pedestal (-85) and pinion (-75.1)
PEDESTAL_Z = -108.0  # crank pedestal centre (front face inside base edge)
ARBOR_PEDESTAL_Z = 92.0  # +/-: clamps at the arbor ends
PIVOT_POST_STATION = 4.0  # shaft station under the pivot post centre
KNOB_POST_STATION = 200.0  # shaft station over the knob post centre

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_Y_INCLINE = [
    [COS_I, 0.0, SIN_I],
    [0.0, 1.0, 0.0],
    [-SIN_I, 0.0, COS_I],
]  # Ry(-19.8), row-vector convention (matches the frame script's Ry rows)


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


def cone_station(s: float) -> list[float]:
    """Machine point of the cone-shaft axis at station s (mm from pivot end)."""
    return [
        CONE_ORIGIN[0] - s * SIN_I,
        Y_DRIVE,
        CONE_ORIGIN[2] + s * COS_I,
    ]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(f"missing part {path}; run build_{name.replace('-', '_')}.py first")
    return str(path)


async def _place(
    adapter,
    part: str,
    position: list[float],
    rotation: list[float],
    rows: list[list[float]],
    configuration: str = "",
    label: str = "",
) -> str:
    """Insert at the exact final transform, fix, and assert the read-back."""
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    label = label or part
    data = check(
        f"insert {label} @ ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})",
        await adapter.insert_component(
            InsertComponentParameters(
                file_path=_part(part),
                position=position,
                rotation=rotation,
                configuration=configuration,
            )
        ),
    )
    name = data["name"]
    if not data.get("fixed"):
        check(
            f"fix {label}",
            await adapter.fix_component(ComponentRefParameters(name=name)),
        )
    assert_component_placed(adapter, name, position, rows)
    return name


async def build(adapter) -> dict[str, str]:
    adapter._attempt(lambda: adapter.swApp.CloseAllDocuments(True), default=None)
    log("CloseAllDocuments (clean session)")
    check("create_assembly", await adapter.create_assembly())

    # --- cone set (all inclined 19.8 deg in plan) ---
    await _place(
        adapter,
        "cone-gear-shaft",
        CONE_ORIGIN,
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )
    centre = cone_station(SHAFT_T120_STATION - GEAR64_OFFSET)
    await _place(
        adapter,
        "crank-drive-gear",
        [
            centre[0] + (GEAR64_FACE / 2.0) * SIN_I,
            Y_DRIVE,
            centre[2] - (GEAR64_FACE / 2.0) * COS_I,
        ],
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )
    for j in range(20):
        teeth = 120 - 6 * j
        centre = cone_station(SHAFT_T120_STATION + SEAT_PITCH * j)
        await _place(
            adapter,
            "cone-gear",
            [
                centre[0] + (CONE_FACE / 2.0) * SIN_I,
                Y_DRIVE,
                centre[2] - (CONE_FACE / 2.0) * COS_I,
            ],
            [0.0, -INCLINE_DEG, 0.0],
            ROT_Y_INCLINE,
            configuration=f"T{teeth:03d}",
            label=f"cone-gear T{teeth:03d}",
        )

    # --- cylinder drum (stationary arbor, free gears locked notch-up) ---
    await _place(
        adapter,
        "cylinder-gear-shaft",
        [X_DRUM, Y_DRIVE, -ARBOR_LENGTH / 2.0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
        label="cylinder arbor",
    )
    for j in range(20):
        z_j = Z_T120 + SEAT_PITCH * COS_I * j
        await _place(
            adapter,
            "cylinder-gear",
            [X_DRUM, Y_DRIVE, z_j - DRUM_FACE / 2.0],
            [0.0, 0.0, 1.5],
            rot_z_rows(1.5),
            label=f"cylinder-gear {j}",
        )

    # --- crank ---
    await _place(
        adapter,
        "crankshaft",
        [X_CRANK, Y_DRIVE, CRANKSHAFT_Z0],
        [90.0, 0.0, 0.0],
        ROT_X_POS90,
    )
    await _place(
        adapter,
        "crank-pinion",
        [X_CRANK, Y_DRIVE, Z_64],  # front face at the 64T centre: the
        [0.0, 0.0, 11.25],  # pinion only overlaps the receding back half
        rot_z_rows(11.25),  # of the skewed 64T (see DIMENSIONS.md)
    )
    await _place(
        adapter,
        "chain-sprocket",
        [X_CRANK, Y_DRIVE, SPROCKET_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    await _place(
        adapter,
        "crank-arm",
        [X_CRANK, Y_DRIVE, CRANK_ARM_Z0],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    await _place(
        adapter,
        "crank-handle",
        [X_CRANK + ARM_C2C, Y_DRIVE, CRANK_ARM_Z0],
        [0.0, 90.0, 0.0],
        ROT_Y_POS90,
    )

    # --- supports ---
    await _place(
        adapter,
        "crank-pedestal",
        [X_CRANK, Y_BASE_TOP, PEDESTAL_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
    )
    for sz in (-1.0, 1.0):
        await _place(
            adapter,
            "arbor-pedestal",
            [X_DRUM, Y_BASE_TOP, sz * ARBOR_PEDESTAL_Z],
            [0.0, 0.0, 0.0],
            IDENTITY,
            label=f"arbor-pedestal z={sz * ARBOR_PEDESTAL_Z:g}",
        )
    post = cone_station(PIVOT_POST_STATION)
    await _place(
        adapter,
        "cone-pivot-post",
        [post[0], Y_BASE_TOP, post[2]],
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )
    post = cone_station(KNOB_POST_STATION)
    await _place(
        adapter,
        "cone-knob-post",
        [post[0], Y_BASE_TOP, post[2]],
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
