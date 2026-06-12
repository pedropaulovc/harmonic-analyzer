r"""Reproduction script: output subassembly (book ch. 18-24).

Everything downstream of the channel springs, in machine coordinates
(assembly origin = base origin; base top y = 50.8; channels along Z with
z_j = -67.1 + 7.0565 j; the output side is -Z). 46 components:

* Summing group (z ~ 0): summing-lever on its knife line (15, 990, 0),
  knife-mount + top-crossbar + knife-stay hanging it from the top frame,
  boss-hook + counter-spring + gooseneck + gooseneck-clamp counter-
  balancing it from above.
* Magnifying group: magnifying-bracket (collar (-40, 985, -85)) holding
  the 165 lever rod (x -200..-35), sliding clamp at x -150 with the
  thumb screw, vertical rod descending at z -91.5 to the output fixture.
* Support bars (front of the columns, centres z -133.9): wheel bar
  (y 565), platen top rail (y 440), platen bottom rail (y 334), each
  clamped by a column-clamp pair at x +-197.
* Magnifying wheel on its axle at (-53, 565), mid-plane z -146.9.
* Platen group: platen (x -258..42, y 305..445, z -142.9..-138.9)
  face-flush on the rails, platen-rack on its back (teeth down, meshing
  the rack pinion with 0.3 backlash and tooth-on-gap phasing), two
  platen-clips on the paper face.
* Transgear group (ch. 23 topology, M6.8): a-frame (M6.5: its clevis
  grips the SOUTH PIVOT BALL MOUNT from channel.SLDASM - the front stand
  doubles as the rocker-shaft support; ball-mount seat at machine 228.6)
  + pinion-bar (y 253.5, z -105..-117, x -58..+178: west end floats just
  east of the clevis), transgear-stub carrying rack-pinion (96T disc) +
  latch big hub; the latch (c2c 66.05, ch30 rest state) carries the knob
  shaft with the mounted T24 removable CHAIN-WRAPPED at the drive-train
  chain plane (the bead chain rides the removable's m2 teeth -- that is
  how gear swaps change the platen ratio), the fine 24T DP30
  transgear-pinion near the front (engageable on the disc), and the
  brass knob outboard.
* Pen group: pen-hanger on the wheel bar, pen-rod (guide hole at
  (-3, z -151.5)), pen-v-block, pen-marker (vertical), pen-frame ring
  around the rod on the v-block top, pen-set-screw in its bottom rail.
* Loose hardware on the base top: measuring-stick, one spare
  transgear-removable (T18 -- the T24 is mounted on the knob shaft;
  the T12 rides the crankshaft in drive-train.SLDASM).

Default-state notes / documented simplifications (Appendix C):
* The pen marker hangs VERTICAL with its tip 8.6 in front of the paper
  plane (plate front z -142.9): the real pen tilts ~12 deg in angled
  v-block bores; our bores are vertical, so a tilted marker would cut
  the bore walls. Pen-to-paper contact is therefore not modeled.
* The transgear is modeled in the ch30 REST (disengaged) state: the
  latch parks the knob shaft at c2c 66.05 from the stud, so the fine
  24T pinion sits 13.1 clear of the disc tips. The mounted removables
  are CHAIN wheels (m2 teeth carry the bead chain, ch. 23), so they
  never mesh another gear; the T24's tips overlap the disc rim in XY
  projection only (chain plane z -81.5..-76.5 vs disc -137.5..-134.5),
  exactly as the ch30 plates show. The ENGAGED pose (pinion on the
  disc, c2c 51.0) and the swing path between the two are not modeled --
  a single rigid arm cannot serve both centre distances (DIMENSIONS.md
  Appendix C #8, unresolved pivot kinematics).
* The magnifying clamp's thumb screw is modeled backed-out: its shank
  tip is tangent to the lever rod (a seated screw would overlap the rod
  it pinches). The output fixture's clamp screw is omitted entirely (its
  cross hole doubles as the wire hook).
* Wires (lever rod -> wheel hub, wheel rim -> pen rod), the drive chain
  and the recording paper are flexible elements, not modeled.
* The knife-stay strap crosses the channel-lever plane east of the lever
  tab TIPS (x > -14.1 including the 8 mm overhang past the spring-hole
  line; M6.5 moved the rod hook -40 -> -10 after the strap clipped the
  two tab overhangs nearest z 0); the cross-assembly fit is re-checked
  at the top level.
* Both pinion-bar ends float: in the real machine the west end is
  carried by the ball-mount housing at the A-frame clevis (ch. 30 front
  view) and the east end by a column bracket; neither fitting is modeled.

Fix-all strategy (M6.2): every component inserted at its exact final
transform and fixed; transforms asserted by read-back; zero interference
(face-flush and tangent contacts allowed).

Dimensions: cad/DIMENSIONS.md ch. 18-24 (M6.4 revision).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_output_assembly.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    OUT_SLDPRT,
    assert_component_placed,
    assert_components_fully_defined,
    check,
    check_no_interference,
    log,
    mirror_placement,
    run_build,
    save_assembly_and_images,
)

ASM_NAME = "output"

# --- machine anchors ---------------------------------------------------------
KNIFE = (15.0, 990.0)  # summing-lever knife-edge line (x, y), along Z
BAR_Z = -133.9  # support-bar centres: column line -112 - clamp offset 21.9
BAR_FRONT_Z = BAR_Z - 5.0  # -138.9: bar front face = platen back face
WHEEL_BAR_Y = 565.0
TOP_RAIL_Y = 440.0  # touches the platen back near its top edge (445)
BOT_RAIL_Y = 334.0  # above the rack band (top 323.6); clamp bottom 326
COLUMN_X = 197.0
COLUMN_Z = -112.0

# --- counter-spring chain (build_boss_hook / build_counter_spring) ----------
from build_boss_hook import ELBOW_R, ROD_DIA as HOOK_ROD_DIA, SHANK_RISE  # noqa: E402
from build_counter_spring import (  # noqa: E402
    BOTTOM_LEAD as CS_BOTTOM_LEAD,
    COIL_OD as CS_COIL_OD,
    WIRE_DIA as CS_WIRE_DIA,
)

BOSS_HOOK_POS = (90.5, 1000.0, 0.0)
SPRING_POS = (95.0, 1052.1, 0.0)  # coil-bottom origin; ring at y 1012.1
# (1052.0 left the hook rod poking 0.05 past the ring inner top)

# --- magnifying group --------------------------------------------------------
LEVER_ROD_Y = 985.0
LEVER_ROD_Z = -85.0
CLAMP_X = -150.0  # sliding clamp default position (p.46/48 insets)
from build_magnifying_clamp import (  # noqa: E402
    BLOCK_DEPTH as CLAMP_DEPTH,
    LEVER_BORE_Y as CLAMP_BORE_Y,
    ROD_BORE_X as CLAMP_ROD_DX,
)

CLAMP_POS = (
    CLAMP_X - CLAMP_DEPTH / 2.0,  # local z 0..12 -> machine x (Ry+90)
    LEVER_ROD_Y - CLAMP_BORE_Y,
    LEVER_ROD_Z,
)
VROD_Z = LEVER_ROD_Z - CLAMP_ROD_DX  # -91.5 (local +x -> machine -z)
VROD_TOP_Y = 990.0  # dome inside the clamp's rod bore
FIXTURE_Y0 = 926.0  # collar y 926..934 on the vertical rod

# --- wheel -------------------------------------------------------------------
WHEEL_X = -53.0
WHEEL_BAR_X0 = -92.0  # wheel-bar centre: span -192 (west clamp) .. +8
from build_wheel_axle import FLANGE_LEN, STUD_LEN  # noqa: E402

WHEEL_MID_Z = BAR_FRONT_Z - FLANGE_LEN - (STUD_LEN - 4.0) / 2.0  # -146.9:
# the 10-wide hub sits flush between the flange face and the tip collar

# --- platen ------------------------------------------------------------------
from build_platen import PLATE_THICKNESS  # noqa: E402
from build_platen_rack import (  # noqa: E402
    PITCH as RACK_PITCH,
    PITCH_LINE_Y as RACK_PITCH_LINE_Y,
)
from build_rack_pinion import TEETH as RACK_PINION_TEETH  # noqa: E402

PLATE_X0 = -258.0  # right edge +42 (photo position)
PLATE_Y0 = 305.0
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.9
PINION_AXIS = (0.0, 253.5)  # transgear stud on the pinion bar
PINION_PD_R = RACK_PINION_TEETH / 30.0 * IN / 2.0  # 40.64 (DP 30)
RACK_BACKLASH = 0.3
# Rz(180) placement: machine x = RACK_X0 - x_local, y = RACK_Y0 - y_local.
# Tooth centres sit at x_local = k * PITCH. The gear's seed gap is centred
# at +gamma/2 (the _gear.py flanks cross the pitch circle at +pi/(2N) and
# gamma - pi/(2N)), so a TOOTH -- not a gap -- sits at bottom dead centre
# and the gaps flank it at x = +-PITCH/2. RACK_X0 = 15.5 * PITCH puts rack
# teeth onto those gaps (the original 15 * PITCH was tip-to-tip: one max
# overlap dead centre decaying by the tip-circle sagitta at +-1..3 teeth).
RACK_X0 = 15.5 * RACK_PITCH  # 41.23 (right edge 0.77 west of the plate's)
RACK_Y0 = PINION_AXIS[1] + PINION_PD_R + RACK_BACKLASH + RACK_PITCH_LINE_Y

CLIP_Y0 = 312.0
CLIP_FRONT_DX = (18.0, 290.0)  # clip x bands (p - 10 .. p) inside the plate;
# the right clip sits east of the pen v-block's x band (-24..8)

# --- transgear ---------------------------------------------------------------
from build_transgear_latch import C2C as LATCH_C2C  # noqa: E402

# Ch30 rest state (M6.8): the plates show the knob-shaft cluster parked at
# post-mirror (-65, ~248 +- 3, chain-plane parallax); y is clamped to 241.78
# so the shaft top (246.5) keeps clearing the pinion bar's underside (247.5).
KNOB_SHAFT_XY = (65.0, 241.78)
LATCH_ANGLE_DEG = math.degrees(
    math.atan2(KNOB_SHAFT_XY[1] - PINION_AXIS[1], KNOB_SHAFT_XY[0] - PINION_AXIS[0])
)  # -10.22: small hub swung low toward the crank
REMOVABLE_Z0 = -81.5  # mounted T24 band -81.5..-76.5, flush with the shaft's
# chain end; the crank-end T12 sits south (drive-train REMOVABLE_Z0 -85.6,
# mid -83.1) -- the real chain bridges the 4.35 offset with a ~1.7 deg skew
CHAIN_Z0 = -83.3  # flat drive-chain band -83.3..-78.8 splits the two wrap
# mid-planes; the band floats radially outside the tooth tips so the z
# overlap with either chain wheel cannot interfere
REMOVABLE_TIP_R = {"T12": 14.0, "T18": 20.0, "T24": 26.0}  # m2: OD (T+2)*2

# --- pen ---------------------------------------------------------------------
PEN_ROD_X = -3.0
PEN_Z_MID = -151.5  # pen-rod / v-block bore plane (v-block back face -143.5
# clears the plate front -142.9 by 0.6)
HANGER_POS = (PEN_ROD_X, 505.0, PEN_Z_MID)
PEN_ROD_POS = (PEN_ROD_X, 398.0, PEN_Z_MID - 2.5)  # rod z -154..-149
VBLOCK_POS = (-24.0, 390.0, -159.5)  # rod bore (local x 21) at (-3, -151.5)
MARKER_X = -13.0  # marker bore (local x 11)
MARKER_TIP_Y = 368.0
# Frame flat on the v-block top (y 408), long axis along X so its window
# (machine x -25..+7, z -161..-147) spans the marker barrel (-17..-9,
# z -155.5..-147.5) and the pen rod (-5.5..-0.5, z -154..-149). Mapping:
# machine x = -29 + local y, machine y = 418 - local z, machine z =
# -143 - local x; the ring's near rail is trimmed to local x 0.75
# (build_pen_frame TRIM_NEAR) so its edge (z -143.75) clears the recording
# paper's front face (-143.4) by 0.35. The screw hole (local x 11, z 5)
# lands at machine (y 413, z -154), axis along X through the west end rail.
FRAME_POS = (-29.0, 418.0, -143.0)
FRAME_ROWS = [[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]
# Set screw along +X (the part's own axis): knob x -38..-33, shank tip at
# x -18, 1 short of the marker barrel's west face (-17).
SET_SCREW_POS = (-38.0, 413.0, -154.0)

# --- loose hardware ----------------------------------------------------------
STICK_POS = (-158.0, 53.8, -133.0)  # flat on the base, graduations up;
# Rx+90 footprint x -158..+42, z -133..-118: west end 2.5 east of the SW
# corner-bracket foot tip (x -160.5, M6.5 - the old -175 ran the stick
# through the bracket's plate + foot, 271 mm^3), z band fully on the top
# plate (edge -133.35) and 3 clear of the a-frame foot (z -115..-107)
SPARE_GEAR_POS = (-160.0, 55.8, -15.0)  # plan circle r 26 (T24 OD 52,
# conservative for the T18) about (-160, -15): 14 west of the ch25
# pinion strip (pivot blocks/straps to x -132.3, z -80..+80 in
# drive-train.SLDASM -- the M6.5 spot (-133, -80) sat exactly under the
# front pivot block and the torque-shaft ball), 12 north of the
# measuring stick band (z <= -118 is far away anyway), tube columns
# (x <= -179) only start beyond z +-94, and y-separated from the
# engage lever (rod bottom y 60.8 vs gear top y 55.8)

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
ROT_Y_POS90 = [[0.0, 0.0, -1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
ROT_Y_NEG90 = [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]
ROT_X_POS90 = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
ROT_X_NEG90 = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]


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
    """Insert at the exact final transform, fix, and assert the read-back.

    All placements are derived in the original (pre-M6.8) frame and mirrored
    about the machine YZ plane here, at the insert boundary."""
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    position, rotation, rows = mirror_placement(
        part, position, rotation, rows, configuration
    )
    label = label or part
    data = check(
        f"insert {label} @ ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})",
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


def _assert_counter_spring_hang() -> None:
    """Bottom ring around the boss-hook arm, a hair of air above the rod.

    Physical hanging would put the ring's inner top ON the rod (contact);
    we model a 0..0.5 air gap instead so the interference check stays
    zero (the original sense -- rod top ABOVE the ring inner top -- was
    inverted and encoded a 0.05 wire/rod overlap)."""
    ring_y = SPRING_POS[1] - CS_BOTTOM_LEAD  # 1012.1
    ring_inner_top = ring_y + (CS_COIL_OD - CS_WIRE_DIA) / 2.0 - CS_WIRE_DIA / 2.0
    rod_top = BOSS_HOOK_POS[1] + SHANK_RISE + ELBOW_R + HOOK_ROD_DIA / 2.0
    gap = ring_inner_top - rod_top
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring ring/rod air gap {gap:.3f} not in (0, 0.5)")
    log(f"counter-spring hang: ring inner top {ring_inner_top:.2f}, rod top"
        f" {rod_top:.2f}, air gap {gap:.2f}")


def _assert_rack_mesh() -> None:
    """Pitch-line backlash and tooth-on-gap phasing at x = 0."""
    rack_pitch_y = RACK_Y0 - RACK_PITCH_LINE_Y
    backlash = rack_pitch_y - (PINION_AXIS[1] + PINION_PD_R)
    if abs(backlash - RACK_BACKLASH) > 1e-9:
        raise RuntimeError(f"rack backlash {backlash:.3f} != {RACK_BACKLASH}")
    phase = math.remainder(RACK_X0, RACK_PITCH)  # tooth centres at +-p/2
    if abs(abs(phase) - RACK_PITCH / 2.0) > 1e-9:
        raise RuntimeError(
            f"rack tooth phase {phase:.4f} != +-p/2: the gear gaps sit at"
            f" +-PITCH/2 about bottom dead centre (tooth at the bottom)"
        )
    if RACK_PINION_TEETH % 4:
        raise RuntimeError("96T bottom-tooth alignment needs a multiple of 4")
    log(f"rack mesh: pitch line y {rack_pitch_y:.2f}, backlash {backlash:.2f},"
        f" rack teeth on the gaps flanking the gear's bottom tooth")


def _assert_knob_shaft_clearance() -> None:
    """The knob shaft must run under the pinion bar (z -105..-117 band),
    on the latch arm's exact c2c, with the rest-state air gaps intact."""
    arm = math.hypot(
        KNOB_SHAFT_XY[0] - PINION_AXIS[0], KNOB_SHAFT_XY[1] - PINION_AXIS[1]
    )
    if abs(arm - LATCH_C2C) > 1e-3:
        raise RuntimeError(f"knob shaft sits {arm:.4f} from the stud, latch c2c"
                           f" is {LATCH_C2C}")
    shaft_top = KNOB_SHAFT_XY[1] + 0.375 * IN / 2.0
    bar_bottom = PINION_AXIS[1] - 6.0
    if shaft_top >= bar_bottom - 0.5:
        raise RuntimeError(
            f"knob shaft top {shaft_top:.2f} too close to the pinion bar"
            f" underside {bar_bottom:.2f}"
        )
    # Rest state: the fine pinion (tip r 11) stays clear of the disc tips,
    # and the chain-plane T24 clears the STUB shaft (O14) it floats past.
    pinion_gap = arm - (41.49 + 11.0)  # disc tip r + pinion tip r
    if pinion_gap < 5.0:
        raise RuntimeError(f"rest-state pinion/disc tip gap {pinion_gap:.2f} < 5")
    t24_stub_gap = arm - (26.0 + 7.0)  # T24 tip r + stub shaft r
    if t24_stub_gap < 0.5:
        raise RuntimeError(f"mounted T24 to stub-shaft gap {t24_stub_gap:.2f} < 0.5")
    log(f"knob shaft at ({KNOB_SHAFT_XY[0]:.2f}, {KNOB_SHAFT_XY[1]:.2f}),"
        f" {bar_bottom - shaft_top:.2f} under the bar; rest-state gaps:"
        f" pinion/disc {pinion_gap:.1f}, T24/stub {t24_stub_gap:.1f}")


async def build(adapter) -> dict[str, str]:
    _assert_counter_spring_hang()
    _assert_rack_mesh()
    _assert_knob_shaft_clearance()

    check("create_assembly", await adapter.create_assembly())

    # --- summing group (first insert auto-fixes) ----------------------------
    await _place(adapter, "summing-lever", [KNIFE[0], KNIFE[1], 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "knife-mount", [KNIFE[0], KNIFE[1], 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Crossbar band y 1010..1051: 0.5 above the summing-lever tube top
    # (1009.5), ends face-flush on the ring rail inner faces (y to 1040.7),
    # stud pokes 14 above for the nut seat.
    await _place(adapter, "top-crossbar", [KNIFE[0], 1010.0, 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "knife-stay", [0.0, 1086.0, 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "boss-hook", list(BOSS_HOOK_POS),
                 [0.0, 0.0, 0.0], IDENTITY)
    # Ry(+90): the end loops land in the YZ plane, encircling the hook arm
    # (bottom) and the gooseneck pin (top) nail-through-ring style.
    await _place(adapter, "counter-spring", list(SPRING_POS),
                 [0.0, 90.0, 0.0], ROT_Y_POS90)
    await _place(adapter, "gooseneck", [COLUMN_X, 1210.0, 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "gooseneck-clamp", [COLUMN_X, 1040.7, 0.0],
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- magnifying group ----------------------------------------------------
    await _place(adapter, "magnifying-bracket", [-40.0, LEVER_ROD_Y, LEVER_ROD_Z],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "magnifying-lever", [-200.0, LEVER_ROD_Y, LEVER_ROD_Z],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Ry(+90): the clamp's lever bore (local Z) turns onto the rod axis (X).
    await _place(adapter, "magnifying-clamp", list(CLAMP_POS),
                 [0.0, 90.0, 0.0], ROT_Y_POS90)
    # Backed-out thumb screw: shank tip tangent to the rod top (a seated
    # screw would overlap the rod it pinches -- see module docstring).
    await _place(adapter, "thumb-screw",
                 [CLAMP_X, LEVER_ROD_Y + 3.0 + 12.0 + 5.0, LEVER_ROD_Z],
                 [0.0, 0.0, -90.0], rot_z_rows(-90.0), label="thumb-screw (clamp)")
    await _place(adapter, "magnifying-vertical-rod", [CLAMP_X, VROD_TOP_Y, VROD_Z],
                 [0.0, 0.0, -90.0], rot_z_rows(-90.0))
    await _place(adapter, "output-fixture", [CLAMP_X, FIXTURE_Y0, VROD_Z],
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- support bars + clamps -----------------------------------------------
    for label, bar_y in (("top-rail", TOP_RAIL_Y), ("bot-rail", BOT_RAIL_Y)):
        await _place(adapter, "support-bar", [0.0, bar_y, BAR_Z],
                     [0.0, 0.0, 0.0], IDENTITY, label=f"support-bar ({label})")
        for sx in (-1.0, 1.0):
            # Ry(+90): the clamp's front channel (local +X) faces -Z.
            await _place(adapter, "column-clamp", [sx * COLUMN_X, bar_y, COLUMN_Z],
                         [0.0, 90.0, 0.0], ROT_Y_POS90,
                         label=f"column-clamp ({label} x{sx * COLUMN_X:+.0f})")
    # Magnifying-wheel bar: HALF-width (every ch30 plate shows it clamped
    # at ONE column with a free end just past the pen hanger -- M6.8
    # 8-view pass). Span -192..+8 covers the axle (-53) and the hanger
    # strap top (-19..-3).
    await _place(adapter, "wheel-bar", [WHEEL_BAR_X0, WHEEL_BAR_Y, BAR_Z],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "column-clamp", [-COLUMN_X, WHEEL_BAR_Y, COLUMN_Z],
                 [0.0, 90.0, 0.0], ROT_Y_POS90,
                 label=f"column-clamp (wheel x{-COLUMN_X:.0f})")

    # --- magnifying wheel -----------------------------------------------------
    # Rx(-90): the axle's +Y axis points -Z (flange on the bar front face).
    await _place(adapter, "wheel-axle", [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z],
                 [-90.0, 0.0, 0.0], ROT_X_NEG90)
    await _place(adapter, "magnifying-wheel", [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z],
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- platen group ---------------------------------------------------------
    await _place(adapter, "platen", [PLATE_X0, PLATE_Y0, PLATE_FRONT_Z],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Rz(180): teeth point down at the rack pinion below.
    await _place(adapter, "platen-rack", [RACK_X0, RACK_Y0, BAR_FRONT_Z],
                 [0.0, 0.0, 180.0], rot_z_rows(180.0))
    for dx in CLIP_FRONT_DX:
        # Rz(+90): the clip strip stands vertical on the paper face.
        await _place(adapter, "platen-clip",
                     [PLATE_X0 + dx, CLIP_Y0, PLATE_FRONT_Z - 1.2],
                     [0.0, 0.0, 90.0], rot_z_rows(90.0),
                     label=f"platen-clip x{PLATE_X0 + dx:+.0f}")
    # Recording paper on the platen front face (ch30 p002/p003/p009): 0.5
    # proud of the platen, 2.25 clear of each clip band, 6 top/bottom margin.
    await _place(adapter, "platen-paper",
                 [PLATE_X0 + 20.25, PLATE_Y0 + 6.0, PLATE_FRONT_Z - 0.5],
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- transgear group ------------------------------------------------------
    await _place(adapter, "a-frame", [0.0, 50.8, -111.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "pinion-bar", [PINION_AXIS[0], PINION_AXIS[1], -111.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Rx(-90): stud +Y -> -Z; shaft z -101.5..-137.5, collar to -141.5.
    await _place(adapter, "transgear-stub", [PINION_AXIS[0], PINION_AXIS[1], -101.5],
                 [-90.0, 0.0, 0.0], ROT_X_NEG90)
    await _place(adapter, "rack-pinion", [PINION_AXIS[0], PINION_AXIS[1], -137.5],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "transgear-latch", [PINION_AXIS[0], PINION_AXIS[1], -122.5],
                 [0.0, 0.0, LATCH_ANGLE_DEG], rot_z_rows(LATCH_ANGLE_DEG))
    await _place(adapter, "transgear-knob-shaft",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], -76.5],
                 [-90.0, 0.0, 0.0], ROT_X_NEG90)
    # Fine 24T DP30 pinion on the knob shaft, just behind the knob face
    # (z -134..-128): engageable on the disc, parked clear in the rest state.
    await _place(adapter, "transgear-pinion",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], -134.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Mounted T24 removable = the knob-end chain wheel (ch. 23: the bead
    # chain rides the removable's teeth; swapping removables changes the
    # platen ratio). Band -81.5..-76.5, flush with the shaft's chain end.
    await _place(adapter, "transgear-removable",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], REMOVABLE_Z0],
                 [0.0, 0.0, 0.0], IDENTITY, configuration="T24",
                 label="transgear-removable (mounted T24)")
    # Local origin = knob wrap centre; the crank-side wrap reaches the
    # drive-train T12 at (118, 126.8) (build_drive_chain KNOB_CENTRE/
    # CRANK_CENTRE/WRAP radii -- keep in sync with KNOB_SHAFT_XY and
    # REMOVABLE_TIP_R).
    await _place(adapter, "drive-chain",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], CHAIN_Z0],
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- pen group ------------------------------------------------------------
    await _place(adapter, "pen-hanger", list(HANGER_POS),
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "pen-rod", list(PEN_ROD_POS),
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "pen-v-block", list(VBLOCK_POS),
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "pen-marker", [MARKER_X, MARKER_TIP_Y, PEN_Z_MID],
                 [0.0, 0.0, 0.0], IDENTITY)
    # Ry(+90)*Rx(+90): the ring lies flat on the v-block top, long axis
    # along X, window over the marker + pen rod (see FRAME_POS comment).
    await _place(adapter, "pen-frame", list(FRAME_POS),
                 [90.0, 90.0, 0.0], FRAME_ROWS)
    # No rotation: the screw's own +X axis presses east through the frame's
    # west end-rail hole toward the marker barrel.
    await _place(adapter, "pen-set-screw", list(SET_SCREW_POS),
                 [0.0, 0.0, 0.0], IDENTITY)

    # --- loose hardware -------------------------------------------------------
    # Rx(+90): the stick lies flat, graduated face up.
    await _place(adapter, "measuring-stick", list(STICK_POS),
                 [90.0, 0.0, 0.0], ROT_X_POS90)
    # Rx(-90): the spare T18 gear lies flat on the base top (the T24 is
    # mounted on the knob shaft, the T12 on the crankshaft; clearances in
    # the SPARE_GEAR_POS comment were computed for the larger T24, so the
    # T18's r 20 plan circle keeps them all with 6 mm to spare).
    await _place(adapter, "transgear-removable", list(SPARE_GEAR_POS),
                 [-90.0, 0.0, 0.0], ROT_X_NEG90, configuration="T18",
                 label="transgear-removable (spare T18)")

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
