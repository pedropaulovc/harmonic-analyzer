r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 76 above it):

* cone set: a TRUE CONE -- all 20 gears AND the 64T crank-drive gear
  seated perpendicular to the stepped shaft (p.18/p.20 photos), the
  shaft inclined 21.1 deg in PLAN, big-end journal in the black pivot
  post, thin 1/8" tip resting in the green knob post's U-slot.
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-47.5, 126.8) (M6.2 keyway refutation),
  clamped by the south arbor pedestal and (at the north end) the
  rocker-arm-support's boss bore in frame.SLDASM; notches up = cosine
  setup (pp. 66-67).
* crankshaft along Z in the green crank pedestal: crank arm + handle at
  the front, chain sprocket and the 16T DP 16 pinion inboard (the
  removable tapered pin is OMITTED: a tapered pin cannot sit in the
  straight 5 mm cross-holes without solid interference).

TRUE-CONE MESH GEOMETRY (M6.7; supersedes the M6.6 canted-vertical
seats, which satisfied the interference checker but visibly deformed
the cone -- user-flagged against the p.18 photo). A gear seated
perpendicular to a shaft inclined i in plan reaches a parallel-axis
drum only with the tooth at the azimuth facing the drum; that contact
tooth sits r*sin(i) SOUTH (along the shaft) of the gear centre and
reaches x = x_centre - r*cos(i). Meshing every station therefore
needs:

* a centre-x grid stepping by the PROJECTED radius step 2.54*cos(i),
* each centre z at z_drum_j + r_j*sin(i) -- NORTH of its drum plane,
  so the contact tooth lands exactly in that plane.

Those centres lie on ONE straight shaft iff sin(i) = 2.54/Z_PITCH ->
i = 21.0976 deg (the retired arcsin(2.54/7.5) = 19.8 put the tracking
on the wrong leg of the triangle: it produced a 0.44/station z-drift
and 0.15/station radial error -- "most gears not meshing"), with seat
pitch Z_PITCH*cos(i) = 6.5839 along the shaft. The 6.5839 pitch forces
CONE_FACE down to 6.5 (annotated 7 mm faces would overlap 0.42): the
book's annotated cone figures (face 7, pitch 7.5, stack 150) are
mutually inconsistent with the photo-measured drum grid -- the drum
grid wins (it anchors the gates and all channel machinery), and the
150 mm annotation reconciles as gear stack 131.6 + 64T face 10 + air.
Self-consistency: tan(cone half-angle) = 2.54/6.5839 = tan(i), so the
cone's drum-side generator runs PARALLEL to the drum axis -- the p.18
seam.

The engagement is intentionally PARTIAL ("oblique angle ... partial
engagement, distinct wear", ch. 12): the contact tooth crosses the
3 mm drum face obliquely, penetration varying +-1.5*tan(i) = 0.58
about its centre value; X_PITCH backs the cone off so the DEEPEST
crossing point stays clear of the DP 30 working depth (edge slack
checker-arbitrated, see PEN_EDGE_SLACK) -> tip interleave 0.00..1.14
across each drum face, identical at ALL 20 stations (zero drift, T006
included). Stub-gap caps hold without any per-gear relief: the drum
tips dive at most 0.24 into a cone gap vs the shallowest (T006) stub
cap 0.88. The 16T crank pinion mesh gets the same treatment: the
perpendicular 64T presents its contact tooth 50.8*sin(i) = 18.3 north
of its centre, the pinion is centred on that plane, and X_CRANK backs
off so the +-1.8 oblique dive across the 64T face caps clear of the
DP 16 working depth (PEN16_EDGE_SLACK; the deep south side stays
visibly interleaved at 2.6 of 3.2).

Positions per cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports". Tooth phasing: every gear script seeds a TOOTH centred on
local +X; the cone gears keep phase 0 (even tooth counts put a tooth
at azimuth 180, the contact azimuth) and the drum gears are
pre-rotated +1.5 deg (half a 3 deg pitch) to receive it tooth-in-gap;
the crank pinion +11.25 deg (half of 22.5) likewise.

Every component is inserted at its exact final transform and FIXED
(saved state fully defined; the inclined components cannot be fully
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
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 76.0  # 126.8: crank, cone big end and arbor axes

DP_TRAIN = 30.0  # cone/cylinder train diametral pitch (DIMENSIONS.md ch12)
ADDENDUM = 25.4 / DP_TRAIN  # 0.847
WORKING_DEPTH = 2.0 * ADDENDUM  # 1.693: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 2.54: pitch-radius step per 6 teeth

# Frame-locked machine grid (M6.3 lineage -- the drum planes anchor the
# gates, cams, rockers and bars; nothing here may move them).
Z_PITCH = 7.5 * math.cos(math.asin(2.54 / 7.5))  # 7.0568: drum z-pitch
X_DRUM = -47.5  # rocker-support boss bore + arbor pedestal
Z_DRUM0 = -67.1  # drum gear 0 plane: stack centred between the gates

# True-cone incline (M6.7, exact tracking -- see module docstring).
SIN_I = RADIUS_STEP / Z_PITCH  # 0.35993
COS_I = math.sqrt(1.0 - SIN_I * SIN_I)  # 0.93299
TAN_I = SIN_I / COS_I
SEC_I = 1.0 / COS_I
INCLINE_DEG = math.degrees(math.asin(SIN_I))  # 21.0976
SEAT_PITCH = Z_PITCH * COS_I  # 6.5839: seat pitch along the shaft

CONE_FACE = 6.5  # M6.7 mesh packing (annotated 7 -- build_cone_gear.py)
GEAR64_FACE = 10.0
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)
PINION_FACE = 12.0

# Mesh anchor: X_PITCH is every cone gear's pitch-section x at the
# contact azimuth. The oblique crossing dives (DRUM_FACE/2)*tan(i) past
# the mid-face penetration, so the mid value is capped at working depth
# minus the dive minus the edge slack -> tip interleave 0.00..1.14.
# Slack 0.55 is checker-arbitrated: the oblique crossing distorts the
# flank match beyond plain backlash math, worst at the smallest gears
# (their engagement arc spans a large azimuth, where the off-centre
# teeth barely drift out of the drum band) -- 0.15 left <=0.06 mm^3
# flank slivers at the five smallest stations, 0.35 still skinned the
# last four.
DRUM_TIP_X = X_DRUM + (122.0 / DP_TRAIN) * 25.4 / 2.0  # 4.147
PEN_EDGE_SLACK = 0.55
PEN_MID = WORKING_DEPTH - PEN_EDGE_SLACK - (DRUM_FACE / 2.0) * TAN_I  # 0.565
X_PITCH = DRUM_TIP_X + ADDENDUM * SEC_I - PEN_MID  # 4.490


def cone_seat(j: int) -> tuple[float, float]:
    """(x, z) centre of cone gear j: pitch-projected x, r*sin(i) north."""
    r = 2.0 * 25.4 - RADIUS_STEP * j
    return X_PITCH + r * COS_I, Z_DRUM0 + Z_PITCH * j + r * SIN_I


# Cone shaft: pivot end at seat station -28.25 from the T120 centre
# (25 journal + half of the first 6.5 face -- build_cone_gear_shaft.py).
SHAFT_T120_STATION = 25.0 + CONE_FACE / 2.0  # 28.25
CONE_ORIGIN = [
    cone_seat(0)[0] + SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    cone_seat(0)[1] - SHAFT_T120_STATION * COS_I,
]


def cone_station(s: float) -> list[float]:
    """Machine point of the cone-shaft axis at station s (mm from pivot end)."""
    return [
        CONE_ORIGIN[0] - s * SIN_I,
        Y_DRIVE,
        CONE_ORIGIN[2] + s * COS_I,
    ]


# Exact-tracking self-check: the 20 mesh-derived seats lie on the shaft.
for _j in range(20):
    _x, _z = cone_seat(_j)
    _p = cone_station(SHAFT_T120_STATION + _j * SEAT_PITCH)
    if abs(_p[0] - _x) > 1e-9 or abs(_p[2] - _z) > 1e-9:
        raise AssertionError(f"cone seat {_j} off the shaft line: {(_x, _z)} vs {_p}")

# 64T crank-drive gear: perpendicular on the pivot journal, 0.1 air to
# the T120 south face (p.20: directly beside).
GEAR64_STATION = SHAFT_T120_STATION - (CONE_FACE + GEAR64_FACE) / 2.0 - 0.1  # 19.9
GEAR64_SEAT = cone_station(GEAR64_STATION)  # (54.49, , -56.61)
R64 = 2.0 * 25.4  # DP 16, 64T pitch radius

# Crank: the 64T's contact tooth (azimuth 0, toward +x) sits R64*sin(i)
# north of its centre; the pinion is centred on that plane and the mesh
# backs off so the +-5 oblique dive caps short of working depth. Slack
# 0.90 is checker-arbitrated like the drum mesh's (the long +-1.8 dive
# across the 64T face squeezes flanks: 0.15 left 1.48 mm^3, 0.60 left
# 0.23).
ADD16 = 25.4 / 16.0
WORK16 = 2.0 * ADD16  # 3.175
PEN16_EDGE_SLACK = 0.90
PEN16_MID = WORK16 - PEN16_EDGE_SLACK - (GEAR64_FACE / 2.0) * SIN_I  # 0.475
PINION_TOOTH_Z = GEAR64_SEAT[2] + R64 * SIN_I  # -38.32
X_CRANK = (
    GEAR64_SEAT[0] + R64 * COS_I + 12.7 + (ADD16 * (1.0 + SEC_I) - PEN16_MID)
)  # 117.80 -- photo: pedestal 122 +- 3 (1.4 sigma, see DIMENSIONS.md)

ARBOR_LENGTH = 200.0  # spans z -100..+100
CRANKSHAFT_Z0 = -150.0  # front end; crank-arm hub at +12 (PIN_HOLE_HEIGHT)
CRANKSHAFT_LENGTH = 120.0  # build_crankshaft.py SHAFT_LENGTH
CRANK_ARM_Z0 = CRANKSHAFT_Z0 + 8.0  # hub centre 12 - half thickness 4
ARM_C2C = 150.0  # handle pivot from the shaft axis
SPROCKET_Z0 = -85.6  # face 4.5 against the pedestal north face
PEDESTAL_Z = -108.6  # crank pedestal centre (front face inside base edge)
ARBOR_PEDESTAL_Z = 92.0  # south (-z) end only; north end clamps into the
# rocker-arm-support boss bore at z 74.1..133 (frame.SLDASM, M6.5)

# The pinion must sit fully on the crankshaft.
if PINION_TOOTH_Z + PINION_FACE / 2.0 > CRANKSHAFT_Z0 + CRANKSHAFT_LENGTH:
    raise AssertionError("crankshaft too short for the M6.7 pinion station")

# Posts: the rotated 25x20 pivot block reaches 10*cos+12.5*sin = 13.83
# in machine z from its centre; at station -1.0 its north corner stops
# 1.0 short of the perpendicular 64T's south face, with the shaft
# engaging the first 9 mm of the journal bore (blind-bearing look,
# p.18: the shaft end disappears into the black bracket).
PIVOT_POST_STATION = -1.0
KNOB_POST_STATION = 177.0  # thin-tip journal; z 90.0, x -2.1 (p.18)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_Y_INCLINE = [
    [COS_I, 0.0, SIN_I],
    [0.0, 1.0, 0.0],
    [-SIN_I, 0.0, COS_I],
]  # Ry(-21.1), row-vector convention (matches the frame script's Ry rows)


def rot_z_rows(deg: float) -> list[list[float]]:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]]


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


async def _place_on_shaft(
    adapter, part: str, station: float, face: float, configuration: str = "", label: str = ""
) -> str:
    """Insert a gear perpendicular on the cone shaft, centred at station."""
    centre = cone_station(station)
    return await _place(
        adapter,
        part,
        [
            centre[0] + (face / 2.0) * SIN_I,
            Y_DRIVE,
            centre[2] - (face / 2.0) * COS_I,
        ],
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
        configuration=configuration,
        label=label,
    )


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())

    # --- cone set: true cone, every gear perpendicular on the shaft ---
    await _place(
        adapter,
        "cone-gear-shaft",
        CONE_ORIGIN,
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )
    await _place_on_shaft(
        adapter,
        "crank-drive-gear",
        GEAR64_STATION,
        GEAR64_FACE,
        label="crank-drive-gear (perpendicular, journal seat)",
    )
    for j in range(20):
        teeth = 120 - 6 * j
        cfg = f"T{teeth:03d}"
        await _place_on_shaft(
            adapter,
            "cone-gear",
            SHAFT_T120_STATION + j * SEAT_PITCH,
            CONE_FACE,
            configuration=cfg,
            label=f"cone-gear {cfg}",
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
        z_j = Z_DRUM0 + Z_PITCH * j
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
        [X_CRANK, Y_DRIVE, PINION_TOOTH_Z - PINION_FACE / 2.0],
        [0.0, 0.0, 11.25],  # +11.25 = half pitch, tooth-in-gap
        rot_z_rows(11.25),
        label="crank-pinion (centred on the 64T contact tooth)",
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
    # South pedestal only (M6.5): the arbor's north end clamps into the
    # rocker-arm-support's east-flank boss bore (frame.SLDASM) - the back
    # view (p5) shows the drum running straight into that casting, and a
    # pedestal at z +92 cannot coexist with the frustum footprint.
    await _place(
        adapter,
        "arbor-pedestal",
        [X_DRUM, Y_BASE_TOP, -ARBOR_PEDESTAL_Z],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label=f"arbor-pedestal z={-ARBOR_PEDESTAL_Z:g}",
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
