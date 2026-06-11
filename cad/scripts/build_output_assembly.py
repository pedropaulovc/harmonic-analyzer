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
* Transgear group: a-frame + pinion-bar (y 253.5, z -105..-117),
  transgear-stub carrying rack-pinion (96T) + fixed transgear-pinion +
  latch big hub; the latch (at -20 deg, so the knob shaft clears the
  pinion bar) carries the knob shaft with the chain sprocket at the
  drive-train chain plane (mid z -78.75) and the brass knob outboard.
* Pen group: pen-hanger on the wheel bar, pen-rod (guide hole at
  (-3, z -151.5)), pen-v-block, pen-marker (vertical), pen-frame ring
  around the rod on the v-block top, pen-set-screw in its bottom rail.
* Loose hardware on the base top: measuring-stick, one spare
  transgear-removable (T24).

Default-state notes / documented simplifications (Appendix C):
* The pen marker hangs VERTICAL with its tip 8.6 in front of the paper
  plane (plate front z -142.9): the real pen tilts ~12 deg in angled
  v-block bores; our bores are vertical, so a tilted marker would cut
  the bore walls. Pen-to-paper contact is therefore not modeled.
* The removable speed-change gears cannot mesh the fixed DP30 pinion
  (they are module 2 / DP 12.7 -- mixed pitches collide over the ~70 deg
  overlap arc), so no removable gear is mounted; one T24 lies on the
  base as a spare.
* The magnifying clamp's thumb screw is modeled backed-out: its shank
  tip is tangent to the lever rod (a seated screw would overlap the rod
  it pinches). The output fixture's clamp screw is omitted entirely (its
  cross hole doubles as the wire hook).
* Wires (lever rod -> wheel hub, wheel rim -> pen rod), the drive chain
  and the recording paper are flexible elements, not modeled.
* The knife-stay strap crosses the channel-lever plane east of the lever
  bank (x > -22); verified against channel.SLDASM geometry here, but the
  cross-assembly fit is re-checked at the top level (M6.5).
* The pinion bar's east end is unsupported (the book's east column
  bracket is not modeled; the A-frame holds the west end).

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
    BLOCK_HEIGHT as CLAMP_HEIGHT,
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
from build_wheel_axle import FLANGE_LEN, STUD_LEN  # noqa: E402

WHEEL_MID_Z = BAR_FRONT_Z - FLANGE_LEN - (STUD_LEN - 4.0) / 2.0  # -146.9:
# the 10-wide hub sits flush between the flange face and the tip collar

# --- platen ------------------------------------------------------------------
from build_platen import PLATE_HEIGHT, PLATE_THICKNESS, PLATE_WIDTH  # noqa: E402
from build_platen_rack import (  # noqa: E402
    BAR_THICKNESS as RACK_T,
    PITCH as RACK_PITCH,
    PITCH_LINE_Y as RACK_PITCH_LINE_Y,
)
from build_rack_pinion import TEETH as RACK_PINION_TEETH  # noqa: E402

PLATE_X0 = -258.0  # right edge +42 (photo position)
PLATE_Y0 = 305.0
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.9
PINION_AXIS = (0.0, 253.5)  # transgear stud on the pinion bar
PINION_PD_R = RACK_PINION_TEETH / 30.0 * IN / 2.0  # 40.64 (DP 30)
RACK_BACKLASH = 0.8  # 0.3 left eight small flank overlaps off the pitch point
# (involute vs straight rack flanks); 0.8 separates every tooth pair
# Rz(180) placement: machine x = RACK_X0 - x_local, y = RACK_Y0 - y_local.
# Tooth centres sit at x_local = k * PITCH, so RACK_X0 = 15 * PITCH puts a
# rack tooth dead on x = 0 -- straight into the 96T gear's bottom gap (the
# seed gap is at +X and 96/4 puts gap #24 at the bottom).
RACK_X0 = 15.0 * RACK_PITCH  # 39.90 (right edge 2.1 west of the plate's)
RACK_Y0 = PINION_AXIS[1] + PINION_PD_R + RACK_BACKLASH + RACK_PITCH_LINE_Y

CLIP_Y0 = 312.0
CLIP_FRONT_DX = (18.0, 290.0)  # clip x bands (p - 10 .. p) inside the plate;
# the right clip sits east of the pen v-block's x band (-24..8)

# --- transgear ---------------------------------------------------------------
from build_transgear_latch import C2C as LATCH_C2C  # noqa: E402

LATCH_ANGLE_DEG = -20.0  # small hub swung low: the knob shaft's top surface
# (y 241.78 + 4.76 = 246.5) clears the pinion bar's underside (247.5)
KNOB_SHAFT_XY = (
    PINION_AXIS[0] + LATCH_C2C * math.cos(math.radians(LATCH_ANGLE_DEG)),
    PINION_AXIS[1] + LATCH_C2C * math.sin(math.radians(LATCH_ANGLE_DEG)),
)
SPROCKET_Z0 = -81.0  # = drive-train SPROCKET_Z0: shared chain plane -78.75

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
# -143 - local x; the plate's near edge (z -143) stops 0.1 short of the
# platen front face (-142.9). The screw hole (local x 11, z 5) lands at
# machine (y 413, z -154), axis along X through the west end rail.
FRAME_POS = (-29.0, 418.0, -143.0)
FRAME_ROWS = [[0.0, 0.0, -1.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]
# Set screw along +X (the part's own axis): knob x -38..-33, shank tip at
# x -18, 1 short of the marker barrel's west face (-17).
SET_SCREW_POS = (-38.0, 413.0, -154.0)

# --- loose hardware ----------------------------------------------------------
STICK_POS = (-175.0, 53.8, -135.0)  # flat on the base, graduations up
SPARE_GEAR_POS = (-150.0, 55.8, -93.0)  # T24 lying flat west of the A-frame

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
    label: str = "",
) -> str:
    """Insert at the exact final transform, fix, and assert the read-back."""
    from solidworks_mcp.adapters.base import (
        ComponentRefParameters,
        InsertComponentParameters,
    )

    label = label or part
    data = check(
        f"insert {label} @ ({position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f})",
        await adapter.insert_component(
            InsertComponentParameters(
                file_path=_part(part), position=position, rotation=rotation
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
    """Bottom ring on the boss-hook arm, hanging with a hair gap."""
    ring_y = SPRING_POS[1] - CS_BOTTOM_LEAD  # 1012
    ring_inner_top = ring_y + (CS_COIL_OD - CS_WIRE_DIA) / 2.0 - CS_WIRE_DIA / 2.0
    rod_top = BOSS_HOOK_POS[1] + SHANK_RISE + ELBOW_R + HOOK_ROD_DIA / 2.0
    gap = rod_top - ring_inner_top
    if not 0.0 < gap < 0.5:
        raise RuntimeError(f"counter-spring ring/rod hang gap {gap:.3f} not in (0, 0.5)")
    log(f"counter-spring hang: ring inner top {ring_inner_top:.2f}, rod top"
        f" {rod_top:.2f}, gap {gap:.2f}")


def _assert_rack_mesh() -> None:
    """Pitch-line backlash and tooth-on-gap phasing at x = 0."""
    rack_pitch_y = RACK_Y0 - RACK_PITCH_LINE_Y
    backlash = rack_pitch_y - (PINION_AXIS[1] + PINION_PD_R)
    if abs(backlash - RACK_BACKLASH) > 1e-9:
        raise RuntimeError(f"rack backlash {backlash:.3f} != {RACK_BACKLASH}")
    phase = math.remainder(RACK_X0, RACK_PITCH)  # tooth centre at x = 0
    if abs(phase) > 1e-9:
        raise RuntimeError(f"rack tooth phase {phase:.4f} != 0 at the pinion")
    if RACK_PINION_TEETH % 4:
        raise RuntimeError("96T bottom-gap alignment needs a multiple of 4")
    log(f"rack mesh: pitch line y {rack_pitch_y:.2f}, backlash {backlash:.2f},"
        f" tooth centred on the bottom gap")


def _assert_knob_shaft_clearance() -> None:
    """The knob shaft must run under the pinion bar (z -105..-117 band)."""
    shaft_top = KNOB_SHAFT_XY[1] + 0.375 * IN / 2.0
    bar_bottom = PINION_AXIS[1] - 6.0
    if shaft_top >= bar_bottom - 0.5:
        raise RuntimeError(
            f"knob shaft top {shaft_top:.2f} too close to the pinion bar"
            f" underside {bar_bottom:.2f}"
        )
    log(f"knob shaft at ({KNOB_SHAFT_XY[0]:.2f}, {KNOB_SHAFT_XY[1]:.2f}),"
        f" {bar_bottom - shaft_top:.2f} under the bar")


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
    for label, bar_y in (("wheel", WHEEL_BAR_Y), ("top-rail", TOP_RAIL_Y),
                         ("bot-rail", BOT_RAIL_Y)):
        await _place(adapter, "support-bar", [0.0, bar_y, BAR_Z],
                     [0.0, 0.0, 0.0], IDENTITY, label=f"support-bar ({label})")
        for sx in (-1.0, 1.0):
            # Ry(+90): the clamp's front channel (local +X) faces -Z.
            await _place(adapter, "column-clamp", [sx * COLUMN_X, bar_y, COLUMN_Z],
                         [0.0, 90.0, 0.0], ROT_Y_POS90,
                         label=f"column-clamp ({label} x{sx * COLUMN_X:+.0f})")

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
    await _place(adapter, "transgear-pinion", [PINION_AXIS[0], PINION_AXIS[1], -134.0],
                 [0.0, 0.0, 0.0], IDENTITY)
    await _place(adapter, "transgear-latch", [PINION_AXIS[0], PINION_AXIS[1], -122.5],
                 [0.0, 0.0, LATCH_ANGLE_DEG], rot_z_rows(LATCH_ANGLE_DEG))
    await _place(adapter, "transgear-knob-shaft",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], -76.5],
                 [-90.0, 0.0, 0.0], ROT_X_NEG90)
    await _place(adapter, "chain-sprocket",
                 [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], SPROCKET_Z0],
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
    # Rx(-90): the spare T24 gear lies flat on the base top.
    await _place(adapter, "transgear-removable", list(SPARE_GEAR_POS),
                 [-90.0, 0.0, 0.0], ROT_X_NEG90, label="transgear-removable (spare)")

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
