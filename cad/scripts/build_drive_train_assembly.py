r"""Reproduction script: drive-train subassembly (book ch. 11-13, 30).

The complete drive train in machine coordinates (assembly origin = base
origin; base top face at y = 50.8, drive height 76 above it):

* crankshaft along Z at (+122.25, 126.8) in the green crank pedestal:
  crank arm + handle at the front, chain sprocket and the 16T DP 16
  pinion inboard (the removable tapered pin is OMITTED: a tapered pin
  cannot sit in the straight 5 mm cross-holes without solid
  interference -- reaming the holes conical is deferred).
* cone set on its stepped shaft, SHAFT axis inclined 19.8 deg in PLAN
  (arcsin(2.54/7.5), appendix C #3): 20 cone-gear configurations
  T120..T006 at the stack stations, the 64T crank-drive gear outboard
  of T120, big-end journal in the black pivot post, thin tip resting
  in the green knob post's U-slot.
* cylinder drum: 20 identical 120T gears spinning freely on the
  stationary arbor along Z at (-47.5, 126.8) (M6.2 keyway refutation),
  clamped by the south arbor pedestal and (at the north end) the
  rocker-arm-support's boss bore in frame.SLDASM; notches up = cosine setup
  (pp. 66-67).

CANTED GEAR SEATS (M6.6 -- "most gears not meshing" fix). A spur gear
seated perpendicular to the 19.8 deg shaft CANNOT mesh the drum: its
projected radius toward the drum shrinks by cos(19.8) (3.0 mm at T120 --
nearly 2x the whole DP 30 working depth of 1.69 mm) and its closest
point sits r*sin(19.8) south in z (17 mm = 2.4 channels at T120), so no
centre-distance choice engages more than a few stations (the retired
DRUM_BACKLASH=1.5 split that error and left air gaps at 17+ of 21
meshes). The book's own mesh condition -- centre distance shrinking
2.54/station to match the 6-teeth radius step -- closes EXACTLY when the
gear DISC stays square to the drum (vertical) and only the shaft
inclines. So gears T120..T012 and the 64T are seated canted-vertical
(bores sized by build_cone_gear.bore_dia_in to clear the inclined
shaft's ELLIPTICAL constant-z cross-section -- semi-axis r/cos(19.8),
not r -- everywhere in each slab; the real machine's small-gear seats
were solder-filled, p.21), every station meshing at
101.6 - 2.54j + MESH_BACKLASH. Physically a rigid canted gear would
wobble when the shaft turns -- this is a display-state model (the saved
gear phases ARE the cosine setup); the book's "oblique ... partial
engagement, distinct wear" (ch. 12) records how the real, perpendicular-
seated train coped, which rigid CAD cannot (the dims are mutually
inconsistent at the few-mm level; see DIMENSIONS.md ch. 13 notes).
Two tooth-form caps, from the part's stub simplification (gap floor at
the BASE circle, build_cone_gear.py): gears T054 and smaller get an
eastward `mesh_relief` so the drum tips never bottom in their shallow
gaps, and T006 (6T -- below minimum tooth count, cannot mesh a 120T with
any seating) stays perpendicular, parked NORTH past its drum gear on the
0.08" tip (T006_STATION). The 16T crank pinion mesh gets the same
treatment via CRANK_BACKOFF (16T stub gaps are 1.99 mm deep vs the
3.18 mm DP 16 working depth).

Positions per cad/DIMENSIONS.md ch. 13 "Drive-train layout" +
"Drive supports". Tooth phasing: every gear script seeds a TOOTH centred
on local +X (`build_cone_gear.py` profile derivation), so at each mesh
the driven side presents a tooth to the driver's tooth; the drum gears
are pre-rotated +1.5 deg (half a 3 deg pitch) and the crank pinion
+11.25 deg (half of 22.5) to land tooth-in-gap. The cone gears keep
phase 0: their even tooth counts put a tooth at azimuth 180 (toward the
drum), and the canted-vertical seats keep the line of centres in the
gear plane, so the rotated drum gap receives it.

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
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "drive-train"

Y_BASE_TOP = 50.8  # harmonic-base top face
Y_DRIVE = Y_BASE_TOP + 76.0  # 126.8: crank, cone big end and arbor axes

INCLINE_DEG = math.degrees(math.asin(2.54 / 7.5))  # 19.8: SHAFT plan incline
SIN_I = 2.54 / 7.5
COS_I = math.cos(math.radians(INCLINE_DEG))
TAN_I = SIN_I / COS_I

SEAT_PITCH = 7.5  # cone stack pitch along the shaft (annotated p.18)
DP_TRAIN = 30.0  # cone/cylinder train diametral pitch (DIMENSIONS.md ch12)
PA_DEG = 14.5  # pressure angle (build_cone_gear.py)
ADDENDUM = 25.4 / DP_TRAIN  # 0.847
WORKING_DEPTH = 2.0 * ADDENDUM  # 1.693: full tooth interleave depth
RADIUS_STEP = 3.0 * 25.4 / DP_TRAIN  # 2.54: pitch-radius step per 6 teeth
MESH_BACKLASH = 0.15  # radial slack so tessellated involute flanks clear

X_DRUM = -47.5  # frame-locked: rocker-support boss bore + arbor pedestal
X_T120 = X_DRUM + 4.0 * 25.4 + MESH_BACKLASH  # 54.25: 50.8 + 50.8 mesh
Z_T120 = -67.1  # = -19/2 x 7.06: stack centred between the gates

# 64T crank-drive gear (canted vertical like the rest): z packing between
# the T120 south face (-70.6), the sprocket and the pedestal north face
# fixes its offset -- 0.25 air to T120, 0.25 to the sprocket.
GEAR64_ZOFF = 8.75  # 64T centre south of T120 (book p.20: directly beside)
X_64 = X_T120 + GEAR64_ZOFF * TAN_I  # 57.40: 64T seat on the shaft line
Z_64 = Z_T120 - GEAR64_ZOFF  # -75.85
CRANK_BACKOFF = 1.35  # DP16 relief: 16T stub gaps 1.99 deep vs 3.18 working
X_CRANK = X_64 + 63.5 + CRANK_BACKOFF  # 122.25 -- photo: 122 +- 3

# Cone shaft: pivot end at seat station -28.75 from the T120 centre
# (25 journal + half of the first 7.5 seat -- build_cone_gear_shaft.py).
SHAFT_T120_STATION = 28.75
CONE_ORIGIN = [
    X_T120 + SHAFT_T120_STATION * SIN_I,
    Y_DRIVE,
    Z_T120 - SHAFT_T120_STATION * COS_I,
]

# T006 cannot mesh (6T stub involute, below minimum tooth count): it stays
# perpendicular on the 0.08" tip, parked 6.75 mm NORTH of its nominal seat
# -- retracting south instead would thread its tilted rim through T012's
# slab. At 178 its rim band sits 0.41 clear of its drum gear's north face
# and 0.26 clear of the knob post's plan circle.
T006_STATION = 178.0

CONE_FACE = 7.0  # cone gear face width (annotated p.18)
GEAR64_FACE = 10.0
DRUM_FACE = 3.0  # cylinder gear face (gear z = 0..3, cam 3..6.5)
PINION_FACE = 12.0

ARBOR_LENGTH = 200.0  # spans z -100..+100
CRANKSHAFT_Z0 = -150.0  # front end; crank-arm hub at +12 (PIN_HOLE_HEIGHT)
CRANK_ARM_Z0 = CRANKSHAFT_Z0 + 8.0  # hub centre 12 - half thickness 4
ARM_C2C = 150.0  # handle pivot from the shaft axis
SPROCKET_Z0 = -85.6  # face 4.5 against the pedestal; 0.25 air to the 64T.
# M6.4/M6.6 note: engineerguy v4_transgear_020 shows the real sprocket
# OUTBOARD at a pedestal front boss, but with our plain O46 pedestal
# column and the crank-arm hub (-134..-142) no outboard slot exists; the
# canted 64T (M6.6) pushes the chain plane further south to -83.35 vs the
# transgear sprocket at -81 (documented discrepancy, Appendix C).
PEDESTAL_Z = -108.6  # crank pedestal centre (front face inside base edge)
ARBOR_PEDESTAL_Z = 92.0  # south (-z) end only; north end clamps into the
# rocker-arm-support boss bore at z 74.1..133 (frame.SLDASM, M6.5)
# Post centre station: the rotated 25x20 block reaches 13.64 in machine z
# from its centre (10*cos + 12.5*sin); at -1.0 its north corner stops 0.60
# short of the canted 64T's south face, with the shaft engaging the first
# 9 mm of the journal bore (blind-bearing look, p.18: the shaft end
# disappears into the black bracket).
PIVOT_POST_STATION = -1.0  # shaft station under the pivot post centre
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


def stub_gap_depth(r_pitch: float) -> float:
    """Radial depth of a tooth gap whose floor sits at the BASE circle
    (build_cone_gear.py stub simplification): tip radius - base radius."""
    return ADDENDUM + r_pitch * (1.0 - math.cos(math.radians(PA_DEG)))


def mesh_relief(j: int) -> float:
    """Extra eastward centre-distance relief for canted cone gear j so the
    120T drum tips never bottom in its stub gap (0.05 floor margin) --
    nonzero from T054 (j=11, 0.02) growing to T012 (j=18, 0.58)."""
    penetration = WORKING_DEPTH - MESH_BACKLASH
    cap = stub_gap_depth(2.0 * 25.4 - RADIUS_STEP * j) - 0.05
    return max(0.0, penetration - cap)


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
    check("create_assembly", await adapter.create_assembly())

    # --- cone set (shaft inclined 19.8 deg in plan; gears canted vertical
    # at the exact DP30 mesh grid, except the parked perpendicular T006) ---
    await _place(
        adapter,
        "cone-gear-shaft",
        CONE_ORIGIN,
        [0.0, -INCLINE_DEG, 0.0],
        ROT_Y_INCLINE,
    )
    await _place(
        adapter,
        "crank-drive-gear",
        [X_64, Y_DRIVE, Z_64 - GEAR64_FACE / 2.0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="crank-drive-gear (canted vertical)",
    )
    for j in range(20):
        teeth = 120 - 6 * j
        cfg = f"T{teeth:03d}"
        if teeth == 6:
            centre = cone_station(T006_STATION)
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
                configuration=cfg,
                label=f"cone-gear {cfg} (perpendicular, parked clear)",
            )
            continue
        await _place(
            adapter,
            "cone-gear",
            [
                X_T120 - RADIUS_STEP * j + mesh_relief(j),
                Y_DRIVE,
                Z_T120 + SEAT_PITCH * COS_I * j - CONE_FACE / 2.0,
            ],
            [0.0, 0.0, 0.0],
            IDENTITY,
            configuration=cfg,
            label=f"cone-gear {cfg} (canted vertical)",
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
        [X_CRANK, Y_DRIVE, Z_64],  # south face at the 64T centre: the 12
        [0.0, 0.0, 11.25],  # face overlaps the vertical 64T's north half
        rot_z_rows(11.25),  # (5 mm engaged band); +11.25 = half pitch
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
