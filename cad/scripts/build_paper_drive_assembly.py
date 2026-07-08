r"""Reproduction script: paper-drive subassembly (book ch. 22-23, 25).

The orthogonal time-base of the plotter: the platen carries the recording paper
across the pen as the operator turns the crank, driven through the translational
gearing, in machine coordinates (assembly origin = base origin; base top
y = 50.8; the output side is -Z). Rebuilt against the primary references
(memory/paper-drive-rework.md): ONE support bar, two-piece column clamps, the
hanging platen (guides + locks), and the REAL six-gear power train:

    crank T12 --(belt/chain feature, pitch O 24:48)--> knob T24
      --(LOCK: keyed shaft)--> 12T DP38 third gear
      --(GEAR mate 12:120)--> 120T DP38 reducer disc
      --(LOCK: stud stack)--> 12T DP30 feed pinion
      --(RACK-PINION mate, pi*10.16/rev)--> rack --(LOCK)--> platen

Operational kinematics (default `free` build): the crank-end T12 sprocket spin
is the ONE free operational DOF -- drag it and the whole feed train follows at
1.596 mm of paper per crank revolution (T12/T24 mounted). Every stage is a real
SolidWorks mate on real, geometrically meshed gears (the old NET rack-pinion
shortcut across the fictitious rest gap is gone -- the latch arm pivots ON the
stud, so the 12T:120T mesh is permanent and the old Appendix C #8 riddle
dissolves). `locked` authors the crank-spin park engaged for a 0-DOF snapshot.
Mode: cad/config/machine/build_lock.yaml (``paper_drive``).

* ONE support bar (22 x 9 x 452, book p.62 "the bar that the platen rides on"),
  front face on the platen back, clamped to each column by a FRONT + BACK
  semi-arc pair closed by two long screws whose heads show on the bar front
  (ch30 p002).
* Platen group (HANGS on the bar): platen + two full-width back guide rails
  (above/below the bar band) + 4 lock plates bridging behind the bar + the
  teeth-down rack at the bottom edge (crests 2 below the platen edge) + two
  bright-brass edge clips + the paper sheet + ALL its screws -- everything
  lock-mated to the platen so the whole group feeds together (the old
  grounded-screw float is fixed).
* Transgear group: bracket on the bar's back face (2 slotted screws) carrying
  the stepped stud; on the stud the 120T disc + 12T feed pinion (locked pair,
  O5 seat) and the latch arm's big hub; the arm carries the knob shaft with
  the mounted T24 removable CHAIN-WRAPPED at the z -155 chain plane, the 12T
  DP38 third gear on the shaft's O5 seat, and the thumb knob.
* The roller chain loops both removables (native connected-linkage chain
  component pattern); the sprocket face (2.4) now fits BETWEEN the chain's
  inner plates, so only the roller<->tooth seating is intended contact.
* Spare transgear-removable (T18 chain wheel) stored loose on the base top.

Cross-subassembly fits (checked at the top level): the column-clamp arcs ride
the O25.4 columns (frame.SLDASM); the roller chain spans this sub's knob shaft
and the drive-train crankshaft -- both share the z -155 chain plane.

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the platen group and the gear train are left free and
constrained by mates; transforms asserted by read-back; zero interference.

Dimensions: memory/paper-drive-rework.md; cad/DIMENSIONS.md ch. 22-23, 25.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_paper_drive_assembly.py
"""

from __future__ import annotations

import math
import sys

import _config
from _chain import (
    CENTRELINE_LEN,
    CRANK_CENTRE as CHAIN_CRANK_CENTRE,
    KNOB_CENTRE as CHAIN_KNOB_CENTRE,
    LINK_COUNT,
    LINK_PITCH,
    PITCH_R_T12,
    PITCH_R_T24,
    TIP_R_T12,
    TIP_R_T24,
    centreline_distance,
    loop_point_tangent,
)
from _common import (
    IN,
    check,
    log,
    run_build,
)
from _assembly import (
    angle_driver,
    assert_expected_free_dof,
    assert_free_dof_necessity,
    check_no_interference,
    component_names,
    component_origin,
    component_transform,
    distance_driver,
    gear_mate,
    is_locked_build,
    lock_mate,
    named_ref,
    place_component,
    rack_pinion_mate,
    reledger_to_solved,
    remap_front_to_machine_front,
    save_assembly_and_images,
    set_park_defer,
    write_park_specs,
)
from _transforms import (  # noqa: E402
    IDENTITY,
    ROT_X_NEG90,
    ROT_X_POS90,
    ROT_Y_POS90,
    rot_z_rows,
    rows_from_euler,
)

ASM_NAME = "paper-drive"

# Build mode (cad/config/machine/build_lock.yaml). `free` (default) leaves the
# crank spin a FREE operational DOF (drag the crank sprocket and the whole
# geared feed train follows); `locked` authors the spin-park engaged for a
# byte-reproducible 0-DOF snapshot. Read as a STRING-LITERAL so the accessor
# tokenises to machine/build_lock.yaml in the doit/cache digest (flipping the
# mode rebuilds ONLY paper-drive). `is_locked_build` rejects any value other
# than `free`/`locked`.
LOCK = is_locked_build(_config.machine("build_lock", "paper_drive"))

ROT_Y_180 = [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, -1.0]]
ROT_X_180 = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]

# --- machine anchors ---------------------------------------------------------
from build_support_bar import (  # noqa: E402
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_HOLE_X as BAR_BRACKET_HOLE_X,  # MACHINE-handed (machine -X holes)
    CLAMP_HOLE_X,
)
from build_column_clamp_front import DEPTH as ARC_FRONT_DEPTH  # noqa: E402
from build_transgear_bracket import (  # noqa: E402
    PLATE_THICK as BRACKET_THICK,
    SCREW_HOLE_DX as BRACKET_SCREW_DX,
)

COLUMN_X = 197.0
COLUMN_Z = -112.0
# Depth chain: the front arc's front face (-129.9) carries the bar's back
# face; the bar's front face (-138.9) carries the platen's back face.
BAR_BACK_Z = COLUMN_Z - ARC_FRONT_DEPTH  # -129.9
BAR_FRONT_Z = BAR_BACK_Z - BAR_DEPTH  # -138.9
BAR_Z = (BAR_FRONT_Z + BAR_BACK_Z) / 2.0  # -134.4 bar centre

# --- platen (hangs on the bar) ----------------------------------------------
from build_platen import (  # noqa: E402
    CBORE_DEPTH as PLATEN_CBORE_DEPTH,
    GUIDE_HOLE_X as PLATEN_GUIDE_HOLE_X,
    GUIDE_HOLE_Y as PLATEN_GUIDE_HOLE_Y,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SOCKET_XY as PLATEN_SOCKET_XY,
)
from build_platen_guide import (  # noqa: E402
    GUIDE_DEPTH,
    GUIDE_HEIGHT,
    HOLE_X as GUIDE_LOCK_HOLE_X,
    LOCK_STATION_X,
    SCREW_STATION_X as GUIDE_SCREW_STATION_X,
)
from build_guide_lock import LOCK_WIDTH  # noqa: E402
from build_platen_clip import (  # noqa: E402
    CLIP_LENGTH,
    CLIP_THICKNESS,
    CLIP_WIDTH,
    HOLE_INSET as CLIP_HOLE_INSET,
)
from build_platen_rack import (  # noqa: E402
    ADDENDUM as RACK_ADDENDUM,
    BAR_HEIGHT as RACK_BAR_HEIGHT,
    FIRST_GAP_X as RACK_FIRST_GAP_X,
    PITCH as RACK_PITCH,
)

PLATE_X0 = -150.0  # centred between the columns (ch30 rest pose)
PLATE_Y0 = 305.0
PLATE_FRONT_Z = BAR_FRONT_Z - PLATE_THICKNESS  # -142.9

# The platen hangs: the bar's top edge carries the top guide's underside.
GUIDE_Y = (315.5, 349.5)  # bottom / top rail seats (machine y)
BAR_TOP_Y = GUIDE_Y[1]  # 349.5
BAR_CY = BAR_TOP_Y - BAR_HEIGHT / 2.0  # 338.5
LOCK_Z0 = BAR_FRONT_Z + GUIDE_DEPTH  # -128.9: lock plates on the guide backs,
# 1.0 behind the bar's back face -- they bridge the bar so the platen cannot
# fall off it.

# Rack: teeth-down at the platen's bottom edge, crests protruding 2 below it.
RACK_TIP_Y = PLATE_Y0 - 2.0  # 303
RACK_PITCH_Y = RACK_TIP_Y + RACK_ADDENDUM  # 303.8467
RACK_Y0 = RACK_TIP_Y + RACK_BAR_HEIGHT  # 315 (Rz180: local y 0..12 maps down)

# --- transgear (the real six-gear train) -------------------------------------
from build_rack_pinion import (  # noqa: E402
    DP as DISC_DP,
    FACE_WIDTH as DISC_FACE,
    TEETH as DISC_TEETH,
)
from build_transgear_feed_pinion import (  # noqa: E402
    DP as FEED_DP,
    FACE_WIDTH as FEED_FACE,
    TEETH as FEED_TEETH,
)
from build_transgear_latch import C2C as LATCH_C2C, THICKNESS as LATCH_THICK  # noqa: E402
from build_transgear_pinion import (  # noqa: E402
    DP as THIRD_DP,
    FACE_WIDTH as THIRD_FACE,
    TEETH as THIRD_TEETH,
)

FEED_PD = FEED_TEETH / FEED_DP * IN  # 10.16 -- meshes the DP30 rack
# Centre extension of the feed-pinion/rack mesh: the _gear recipe cuts tooth
# gaps down to the BASE circle (rb = 4.918 for 12T DP30), which sits above the
# rack crests' reach at nominal centres -- extend like the drive-train's
# checker-arbitrated mesh slacks (rb - (PD/2 - addendum) = 0.685, +0.115).
RACK_MESH_EXT = 0.8
STUD_XY = (-12.0, RACK_PITCH_Y - FEED_PD / 2.0 - RACK_MESH_EXT)  # machine (-12, 297.9667)
LATCH_ANGLE_DEG = -162.0  # knob swung low toward the crank at machine -X (ch30
# p002); the machine reflection of the pre-mirror -18 deg (theta -> 180 - theta,
# x -> -x), so the arm reaches west/-X and down from the stud.
KNOB_SHAFT_XY = (
    STUD_XY[0] + LATCH_C2C * math.cos(math.radians(LATCH_ANGLE_DEG)),
    STUD_XY[1] + LATCH_C2C * math.sin(math.radians(LATCH_ANGLE_DEG)),
)  # machine (-54.575, 284.133)

# z stack on the stud (front -> back): collar | disc | feed pinion | latch arm
# | bracket. The disc window clears the platen furniture: the guide-screw
# heads are counterbored sub-flush (crowns -142.7), so the deepest reach near
# the cluster is the paper plane at -143.4 -- 2.0 in front of the disc back.
DISC_Z0 = -148.4  # disc -148.4..-145.4
THIRD_Z0 = DISC_Z0  # third gear -148.4..-144.4 (full mesh overlap 3.0)
FEED_Z0 = DISC_Z0 + DISC_FACE  # -145.4; face 9.5 reaches the rack band 3.0 deep
RACK_BACK_Z = BAR_FRONT_Z + 6.0  # -132.9 (rack thickness 6 on the platen back)
ARM_Z = (RACK_BACK_Z + BAR_BACK_Z) / 2.0  # -131.4: the arm's 2.6 band fits the
# 3.0 slot between the rack's back face and the bar-front/bracket plane
BRACKET_Z0 = BAR_BACK_Z  # plate -129.9..-125.9 on the bar's back face
STUB_Z0 = BRACKET_Z0 + BRACKET_THICK  # -125.9 (Rx-90: local +Y -> -Z)
KNOB_SHAFT_Z0 = -157.5  # Rx+90: local +Y -> +Z (stack runs to the knob at the back)

REMOVABLE_Z0 = -156.2  # mounted removables: face 2.4 about the -155 chain plane
T24_MID_Z = REMOVABLE_Z0 + 1.2  # -155.0
CHAIN_MID_Z = -155.0  # both wheels coplanar; the crank T12 matches (drive-train)
REMOVABLE_TIP_R = {"T12": 14.0, "T18": 20.0, "T24": 26.0}  # m2: OD (T+2)*2

# Mesh phasing. build_fixed_gear seeds every gear with a TOOTH centred on
# local +X (the seed gap spans +pi/(2N)..gamma-pi/(2N)), and teeth repeat
# every gamma = 360/N. The disc keeps identity spin (LATCH_ANGLE is a
# multiple of its 3-deg pitch, so a disc TOOTH points along the c2c line);
# the third gear is spun so a GAP faces back along that line.
THIRD_GAMMA = 360.0 / THIRD_TEETH  # 30
_MESH_AZ = 180.0 + LATCH_ANGLE_DEG  # 18: from the knob axis toward the stud
THIRD_PHASE_DEG = (_MESH_AZ - THIRD_GAMMA / 2.0) % THIRD_GAMMA  # 27
if THIRD_PHASE_DEG > THIRD_GAMMA / 2.0:
    THIRD_PHASE_DEG -= THIRD_GAMMA  # -3: nearest representative
# The feed pinion keeps identity spin: its mesh line points straight up
# (+90 deg is a tooth azimuth for 12T -- 90 = 3 * 30), and the rack is
# phased so a GAP centre sits exactly on the stud's x (see RACK_X0).
# Machine-handed: the rack is teeth-down (Rx180), its tooth pattern marching +X
# from RACK_X0, so a GAP sits over the machine stud (-X) near the platen's left
# (-X) edge -- the reflection of the pre-mirror right-edge phasing.
_k = math.floor((STUD_XY[0] - RACK_FIRST_GAP_X - PLATE_X0) / RACK_PITCH)
RACK_X0 = STUD_XY[0] - RACK_FIRST_GAP_X - _k * RACK_PITCH  # -148.985: gap on the
# stud, left edge ~1 east of the platen's

# Net platen feed per CRANK revolution through the real train (T12/T24
# mounted): 0.5 chain * (12/120) gear * pi*PD rack = 1.596 mm. Every stage is
# a real mate; this constant only documents the law for the kinematics probe.
NET_RACK_TRAVEL_PER_CRANK_REV = (
    0.5 * (THIRD_TEETH / DISC_TEETH) * math.pi * FEED_PD
)  # 1.596 mm

# Spare T18 removable: the swap chain wheel, stored flat on the base top
# (y 50.8 + the 2.4 face), well west of the platen, axis +Z laid flat ->
# Rx(-90). A spare for this subsystem, so it rides here as a flat sibling of
# the mounted T24; placing it loose at the TOP level would clash on leaf name
# with the T12/T24 instances nested in drive-train / this sub.
SPARE_GEAR_POS = (160.0, 53.2, -15.0)  # machine +X (west) of the platen

# --- fasteners ----------------------------------------------------------------
# Platen-clip screws: through the clips' O3 end holes into the platen's edge
# sockets (pre-mirror machine coords = platen-local + plate origin).
CLIP_SCREW_XY = tuple(
    (PLATE_X0 + sx, PLATE_Y0 + sy) for sx, sy in PLATEN_SOCKET_XY
)
# The clips run from the platen's top edge down; their end holes (inset
# CLIP_HOLE_INSET) must land exactly on the platen's edge sockets.
_CLIP_Y0_LOCAL = PLATE_HEIGHT - CLIP_LENGTH  # 15
assert PLATEN_SOCKET_XY[0][1] == _CLIP_Y0_LOCAL + CLIP_HOLE_INSET
assert PLATEN_SOCKET_XY[1][1] == PLATE_HEIGHT - CLIP_HOLE_INSET
# Guide screws: 2 rows of 5, heads counterbored 0.2 sub-flush of the platen
# front (ch22 front photo shows the slotted heads; the paper lies flat over
# them), shanks threading 2.4 into the rails' blind holes.
assert GUIDE_SCREW_STATION_X == PLATEN_GUIDE_HOLE_X
GUIDE_SCREW_XY = tuple(
    (PLATE_X0 + x, PLATE_Y0 + y)
    for y in PLATEN_GUIDE_HOLE_Y
    for x in PLATEN_GUIDE_HOLE_X
)
# Lock screws: 2 per lock plate, heads on the lock backs, into the guides.
LOCK_SCREW_XY = tuple(
    (PLATE_X0 + x, gy + GUIDE_HEIGHT / 2.0)
    for gy in GUIDE_Y
    for x in GUIDE_LOCK_HOLE_X
)


def _assert_rack_mesh() -> None:
    """Feed-pinion/rack law: centre extension and tooth-on-gap phasing."""
    ext = RACK_PITCH_Y - (STUD_XY[1] + FEED_PD / 2.0)
    if abs(ext - RACK_MESH_EXT) > 1e-9:
        raise RuntimeError(f"rack mesh extension {ext:.3f} != {RACK_MESH_EXT}")
    # A rack GAP centre must sit exactly over the stud (the pinion's +90-deg
    # tooth): teeth-down Rx180, gap centres march +X at RACK_X0 + FIRST_GAP_X
    # + k*PITCH (machine frame).
    phase = math.remainder(STUD_XY[0] - RACK_X0 - RACK_FIRST_GAP_X, RACK_PITCH)
    if abs(phase) > 1e-9:
        raise RuntimeError(f"rack gap phase {phase:.4f} != 0 over the stud")
    if FEED_TEETH % 4:
        raise RuntimeError("feed-pinion top-tooth alignment needs teeth % 4 == 0")
    z_overlap = (FEED_Z0 + FEED_FACE) - BAR_FRONT_Z  # pinion face into the rack band
    if z_overlap < 2.5:
        raise RuntimeError(f"feed pinion reaches only {z_overlap:.2f} into the rack band")
    # Radial safety: the rack crests must clear the pinion's base-circle gap
    # floor, and the pinion tips the rack's root line.
    rb = FEED_PD / 2.0 * math.cos(math.radians(14.5))
    crest_reach = FEED_PD / 2.0 + RACK_MESH_EXT - RACK_ADDENDUM
    if crest_reach <= rb + 0.05:
        raise RuntimeError(f"rack crests reach {crest_reach:.3f} into the pinion"
                           f" gap floor at rb {rb:.3f}")
    log(f"rack mesh: pitch line y {RACK_PITCH_Y:.2f}, extension {ext:.2f},"
        f" rack gap centred over the stud, crest/floor margin"
        f" {crest_reach - rb:.3f}")


def _assert_gear_mesh() -> None:
    """Third-gear/disc mesh: same DP, c2c on the latch, phased tooth-on-gap."""
    if THIRD_DP != DISC_DP:
        raise RuntimeError(f"third gear DP {THIRD_DP} != disc DP {DISC_DP}")
    c2c_nominal = (THIRD_TEETH + DISC_TEETH) / (2.0 * DISC_DP) * IN  # 44.116
    ext = LATCH_C2C - c2c_nominal
    if not (0.5 <= ext <= 0.8):
        raise RuntimeError(
            f"gear mesh extension {ext:.3f} outside the 0.5..0.8 gap-floor window"
        )
    # The disc's teeth repeat every 3 deg, so a tooth must point along the c2c
    # line at the latch angle for the third gear's phased gap to receive it.
    disc_gamma = 360.0 / DISC_TEETH
    if abs(math.remainder(LATCH_ANGLE_DEG, disc_gamma)) > 1e-9:
        raise RuntimeError(
            f"latch angle {LATCH_ANGLE_DEG} is not a multiple of the disc pitch"
            f" {disc_gamma}"
        )
    # Radial: the disc tooth tips must clear the third gear's base-circle gap
    # floor (the same law the latch C2C extension exists for).
    rb3 = THIRD_TEETH / THIRD_DP * IN / 2.0 * math.cos(math.radians(14.5))
    disc_ra = (DISC_TEETH + 2.0) / DISC_DP * IN / 2.0
    tip_reach = LATCH_C2C - disc_ra
    if tip_reach <= rb3 + 0.05:
        raise RuntimeError(
            f"disc tips reach {tip_reach:.3f}, third-gear gap floor {rb3:.3f}"
        )
    z_overlap = min(THIRD_Z0 + THIRD_FACE, DISC_Z0 + DISC_FACE) - max(THIRD_Z0, DISC_Z0)
    if z_overlap < 2.5:
        raise RuntimeError(f"third gear/disc z overlap {z_overlap:.2f} < 2.5")
    # The latch arm must fit its slot between the rack back and the bar front.
    slot = BAR_BACK_Z - RACK_BACK_Z
    if LATCH_THICK > slot - 0.3:
        raise RuntimeError(f"latch arm {LATCH_THICK} too thick for the {slot:.1f} slot")
    # The bar's MACHINE-handed bracket sockets must land under the bracket-screw
    # line: both are the machine frame now, so stud +- dx matches directly.
    expected = {round(STUD_XY[0] + dx, 6) for dx in (-BRACKET_SCREW_DX, BRACKET_SCREW_DX)}
    if expected != {round(x, 6) for x in BAR_BRACKET_HOLE_X}:
        raise RuntimeError(
            f"support-bar bracket holes {BAR_BRACKET_HOLE_X} != screw"
            f" line {sorted(expected)}"
        )
    log(f"gear mesh 12:120 DP38: c2c {LATCH_C2C} (ext {ext:.2f}), third gear"
        f" phased {THIRD_PHASE_DEG:+.1f} deg, tip/floor margin {tip_reach - rb3:.3f}")


def _assert_knob_shaft_clearance() -> None:
    """The knob cluster must ride the latch's exact c2c with its air gaps."""
    arm = math.hypot(
        KNOB_SHAFT_XY[0] - STUD_XY[0], KNOB_SHAFT_XY[1] - STUD_XY[1]
    )
    if abs(arm - LATCH_C2C) > 1e-6:
        raise RuntimeError(f"knob shaft sits {arm:.4f} from the stud, latch c2c"
                           f" is {LATCH_C2C}")
    shaft_top = KNOB_SHAFT_XY[1] + 0.375 * IN / 2.0
    if shaft_top >= PLATE_Y0 - 0.5:
        raise RuntimeError(
            f"knob shaft top {shaft_top:.2f} too close to the platen bottom"
            f" edge {PLATE_Y0}"
        )
    t24_collar_gap = arm - (REMOVABLE_TIP_R["T24"] + 7.0)  # T24 tip r + collar r
    if t24_collar_gap < 0.5:
        raise RuntimeError(f"mounted T24 to stub-collar gap {t24_collar_gap:.2f} < 0.5")
    # The T24 overlaps the disc rim in XY -- they must stay z-separated.
    t24_front = REMOVABLE_Z0 + 2.4
    z_gap = DISC_Z0 - t24_front  # -148.4 - (-153.8) = 5.4
    if z_gap < 2.0:
        raise RuntimeError(f"T24/disc z gap {z_gap:.2f} < 2.0")
    log(f"knob shaft at ({KNOB_SHAFT_XY[0]:.3f}, {KNOB_SHAFT_XY[1]:.3f}),"
        f" {PLATE_Y0 - shaft_top:.2f} under the platen edge; gaps:"
        f" T24/collar {t24_collar_gap:.1f}, T24/disc z {z_gap:.1f}")


def _assert_chain_layout() -> None:
    """_chain.py holds the loop in the PRE-MIRROR frame (its KNOB/CRANK centres
    sit at machine +X); pin it to the reflection of OUR machine anchors so the
    mirror_x=True loop lands on the machine (-X) chain wheels."""
    knob_pre = (-KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1])
    knob_err = max(abs(a - b) for a, b in zip(CHAIN_KNOB_CENTRE, knob_pre))
    if knob_err > 1e-3:
        raise RuntimeError(
            f"_chain KNOB_CENTRE {CHAIN_KNOB_CENTRE} != -KNOB_SHAFT_XY"
            f" ({knob_pre[0]:.4f}, {knob_pre[1]:.4f})"
        )
    from build_drive_train_assembly import X_CRANK, Y_CRANK
    if CHAIN_CRANK_CENTRE != (-X_CRANK, Y_CRANK):
        raise RuntimeError(
            f"_chain CRANK_CENTRE {CHAIN_CRANK_CENTRE} != -drive-train crank"
            f" ({-X_CRANK}, {Y_CRANK})"
        )
    if (TIP_R_T24, TIP_R_T12) != (REMOVABLE_TIP_R["T24"], REMOVABLE_TIP_R["T12"]):
        raise RuntimeError("_chain tip radii diverged from REMOVABLE_TIP_R")
    log(
        f"roller chain layout: loop {CENTRELINE_LEN:.2f}, {LINK_COUNT} links at"
        f" {LINK_PITCH:.4f}, seated on pitch circles ({PITCH_R_T24}/{PITCH_R_T12}),"
        f" plane z {CHAIN_MID_Z}"
    )


async def _place_chain_seed(adapter, part: str, station: int) -> str:
    """Seat ONE chain-pattern seed link at path ``station``, oriented along the
    forward CHORD (pin0->pin1) so both pin axes sit ~on the loop -- the connected
    -linkage chain pattern then fills the rest of the loop. ``_chain`` holds the
    loop in the PRE-MIRROR frame (anchor ``CHAIN_KNOB_CENTRE`` at machine +X), so
    ``mirror_x=True`` reflects each point to the machine (-X) chain plane -- the
    exact machine pose place_component now inserts directly (no mirror layer). The
    achiral link's local-z symmetry keeps that a pure-Z rotation, so the plates
    stay flat in the chain plane. Returns the instance name."""
    x0, y0, _ = loop_point_tangent(
        station * LINK_PITCH, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True
    )
    x1, y1, _ = loop_point_tangent(
        (station + 1) * LINK_PITCH, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True
    )
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
    return await place_component(
        adapter, part, [x0, y0, CHAIN_MID_Z], [0.0, 0.0, ang], rot_z_rows(ang),
        ground=True, label=f"{part} seed @ station {station}",
    )


async def _insert_roller_chain(adapter) -> None:
    """The drive chain: a native CHAIN COMPONENT PATTERN (connected linkage) of
    alternating inner/outer links along the _chain.py loop.

    Ch. 23: the chain rides the two mounted removables' m2 teeth (T24 knob shaft,
    T12 crank shaft). The loop centreline is authored as a single CLOSED SPLINE
    (one sketch segment) on an offset plane at the chain plane (z = CHAIN_MID_Z);
    two seed links (chain-inner-link @ station 0, chain-outer-link @ station 1)
    are placed tangent; SolidWorks' native ``FeatureChainPattern`` (connected
    linkage, via ``adapter.pattern_components_chain``) fills the loop with the
    alternating INNER (plates + bushings) / OUTER (plates + pins) links. Each
    link's two pin axes (Axis1/Axis2) are the group's path-links, so the pattern
    keeps every plate flat in the chain plane and tangent to the loop.

    The path MUST be one connected segment: SolidWorks never treats the 3-arc +
    taut-line contour as connected (the segments share coordinates but carry no
    coincidence relations, so MakeSketchChain forms 0 paths), hence the spline
    through dense loop samples. The dedicated ``FeatureChainPattern`` one-call API
    is used because the documented CreateDefinition/CreateFeature route returns
    null under pywin32 late binding. See memory/chain-pattern-not-createable-
    late-bound.md.

    Gates: the pattern produced EXACTLY LINK_COUNT links (the loop is sized
    CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with LINK_COUNT even, so the two
    interleaved groups close it seamlessly), every instance sits on the chain
    plane, and its origin (pin0) reads back onto the loop centreline.
    """
    from solidworks_mcp.adapters.base import (
        ComponentChainPatternParameters,
        CreatePlaneParameters,
        RenameFeatureParameters,
    )

    # 1. Path: a single CLOSED SPLINE on an offset plane at the chain plane.
    plane = check(
        f"chain path plane @ z={CHAIN_MID_Z}",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane",
                                  offset=CHAIN_MID_Z)))
    plane_name = getattr(plane, "name", plane)
    sk = check("chain path sketch", await adapter.create_sketch(plane_name))
    sketch_name = getattr(sk, "data", sk) if not isinstance(sk, str) else sk
    n_samples = 96
    pts = []
    for i in range(n_samples):
        s = i * CENTRELINE_LEN / n_samples
        x, y, _ = loop_point_tangent(
            s, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True)
        pts.append({"x": x, "y": y})
    pts.append(pts[0])  # close the loop
    check("chain path spline", await adapter.add_spline(pts))
    check("chain path exit", await adapter.exit_sketch())
    # Give the auto-named path sketch a stable, human-readable name so the
    # pattern selects "Spline1@chain-path" independent of feature order.
    check("rename chain path sketch",
          await adapter.rename_feature(
              RenameFeatureParameters(old_name=sketch_name, new_name="chain-path")))
    sketch_name = "chain-path"

    # 2. Two seed links, tangent at the first two stations.
    inner = await _place_chain_seed(adapter, "chain-inner-link", 0)
    outer = await _place_chain_seed(adapter, "chain-outer-link", 1)

    # 3. Native connected-linkage chain pattern fills the loop.
    pattern = check(
        "roller chain (native chain component pattern)",
        await adapter.pattern_components_chain(
            ComponentChainPatternParameters(
                path_segment=f"Spline1@{sketch_name}",
                group1_component=inner,
                group1_link1=f"Axis1@{inner}", group1_link2=f"Axis2@{inner}",
                group1_plane=f"Front Plane@{inner}",
                group2_component=outer,
                group2_link1=f"Axis1@{outer}", group2_link2=f"Axis2@{outer}",
                group2_plane=f"Front Plane@{outer}",
                # Explicit count (NOT fill_path): _chain sizes CENTRELINE_LEN =
                # LINK_COUNT * LINK_PITCH with LINK_COUNT even, so LINK_COUNT links
                # close the loop seamlessly; fill_path undershoots (leaves a ~2-link
                # seam) because it reserves clearance. For connected linkage the
                # count is PER GROUP and the two groups interleave, so each group
                # gets LINK_COUNT // 2.
                pitch_method="connected_linkage", fill_path=False,
                count=LINK_COUNT // 2, spacing=LINK_PITCH,
                align_method="tangent", options="dynamic")))
    # Rename the auto-named pattern feature (e.g. "LocalChainPattern1") to a
    # stable, human-readable name in the tree.
    pat_name = getattr(pattern, "name", None)
    if pat_name:
        check("rename chain pattern",
              await adapter.rename_feature(
                  RenameFeatureParameters(old_name=pat_name, new_name="roller-chain")))

    # The pattern OWNS the seed links' tangent alignment: it re-solves each off
    # the provisional authored chord angle (chord < arc on the wrap, so the two
    # pin axes pull the seed straight -- a fraction of a degree on the tight
    # pitch-circle wrap). Re-anchor the two seeds' pose-ledger entries to that
    # solved pose so the save-time gate checks the intended persistent pose.
    reledger_to_solved(adapter, inner)
    reledger_to_solved(adapter, outer)

    # Hide the path spline: it is construction scaffolding for the pattern, not a
    # rendered feature.
    check("blank chain path sketch", await adapter.blank_sketch("chain-path"))

    # 4. Gates: enough links, on the chain plane, on the loop centreline.
    links = [
        n
        for n in component_names(adapter)
        if n.startswith(("chain-inner-link", "chain-outer-link"))
    ]
    # EXACT closure: _chain sizes CENTRELINE_LEN = LINK_COUNT * LINK_PITCH with
    # LINK_COUNT even, so the connected-linkage pattern (LINK_COUNT // 2 per group)
    # fills the loop with EXACTLY LINK_COUNT links -- no seam, no band.
    if len(links) != LINK_COUNT:
        raise RuntimeError(
            f"chain pattern produced {len(links)} links, expected exactly {LINK_COUNT}")
    worst = 0.0
    for name in links:
        array = component_transform(adapter, name)
        x, y, z = (array[9] * 1000.0, array[10] * 1000.0, array[11] * 1000.0)
        if abs(z - CHAIN_MID_Z) > 0.5:
            raise RuntimeError(f"{name}: link z {z:.3f} off the chain plane {CHAIN_MID_Z}")
        dist = centreline_distance(
            x, y, dx=CHAIN_KNOB_CENTRE[0], dy=CHAIN_KNOB_CENTRE[1], mirror_x=True)
        worst = max(worst, dist)
    if worst > 2.0:
        raise RuntimeError(f"chain links sit up to {worst:.2f} mm off the loop centreline")
    log(f"roller chain: native connected-linkage chain pattern, {len(links)} links"
        f" (worst off-loop {worst:.2f} mm)")


async def _sprocket_revolute(adapter, name: str, label: str) -> None:
    """Constrain a free-spinning wheel to a fixed Z spin-axis, leaving the
    spin free (the operational/coupled DOF).

    Two axis-to-plane distances pin the central Axis1 (a Z line) in XY -- height
    (Top plane = y) and lateral (Right plane = x) -- and keep it parallel to Z;
    a Front-plane distance pins the axial z. The wheel is a symmetric spur
    gear, so its origin is spin-invariant and the origin ``verify`` passes at
    any spin angle (the spin is pinned separately, or left free + coupled)."""
    o = component_origin(adapter, name)
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), o[1],
                          label=f"{label} axis height", verify=(name, o))
    await distance_driver(adapter, named_ref(f"Axis1@{name}", "AXIS"),
                          named_ref("Right Plane", "PLANE"), o[0],
                          label=f"{label} axis lateral", verify=(name, o))
    await distance_driver(adapter, named_ref(f"Front Plane@{name}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), o[2],
                          label=f"{label} axial", verify=(name, o))


async def build(adapter) -> dict[str, str]:
    _assert_rack_mesh()
    _assert_gear_mesh()
    _assert_knob_shaft_clearance()
    _assert_chain_layout()

    # `free` (default) DEFERS the freed crank-spin park driver (records, does not
    # author); `locked` authors it engaged. Set before any *_driver(free_dof_key=).
    set_park_defer(not LOCK)
    check("create_assembly", await adapter.create_assembly())

    # --- support bar + two-piece clamps ---------------------------------------
    # The bar is FIRST so the auto-fixed seed is structure, not the mated platen.
    # Symmetric about machine x=0; its bracket-screw holes flank the stud at
    # machine -12 (see build_support_bar.py).
    await place_component(adapter, "support-bar", [0.0, BAR_CY, BAR_Z],
                          [0.0, 0.0, 0.0], IDENTITY,
                          label="support-bar (the platen bar)")
    # Machine columns at +-197 (west first, to match the pose ledger's -1/-2).
    for sx in (1.0, -1.0):
        # Ry(+90): the arcs' local +X (their depth axis) faces machine -Z.
        for arc in ("column-clamp-front", "column-clamp-back"):
            await place_component(adapter, arc, [sx * COLUMN_X, BAR_CY, COLUMN_Z],
                                  [0.0, 90.0, 0.0], ROT_Y_POS90,
                                  label=f"{arc} (x{sx * COLUMN_X:+.0f})")
    # Clamp screws: heads on the bar's FRONT face flanking each column (ch30
    # p002), shanks through bar + front arc, threading into the back arc. The
    # support-bar hole list is pre-mirror-ordered; negate to the machine hole.
    for x in CLAMP_HOLE_X:
        await place_component(adapter, "clamp-screw", [-x, BAR_CY, BAR_FRONT_Z],
                              [0.0, 0.0, 0.0], IDENTITY,
                              label=f"clamp-screw (x{-x:+.1f})")

    # --- platen group (hangs on the bar) ---------------------------------------
    # The platen runs as a prismatic slider along X (the paper feed): its local
    # slide axis is held parallel to the Top + Front planes at the slide-line
    # offsets (axis-to-plane distance, no rotational redundancy) and an angle
    # snapshot kills the residual spin. The rack, guides, locks, clips, paper
    # and EVERY platen-riding screw ride it via Lock mates (the old grounded
    # clip screws floated in space while the platen fed -- rework E5). The feed
    # position is COUPLED to the crank through the real gear train below.
    platen = await place_component(adapter, "platen",
                                   [PLATE_X0, PLATE_Y0, PLATE_FRONT_Z],
                                   [0.0, 0.0, 0.0], IDENTITY, ground=False)
    pl_o = component_origin(adapter, platen)
    await distance_driver(adapter, named_ref(f"Axis1@{platen}", "AXIS"),
                          named_ref("Top Plane", "PLANE"), pl_o[1],
                          label="platen slide height", verify=(platen, pl_o))
    await distance_driver(adapter, named_ref(f"Axis1@{platen}", "AXIS"),
                          named_ref("Front Plane", "PLANE"), pl_o[2],
                          label="platen slide depth", verify=(platen, pl_o))
    await angle_driver(adapter, named_ref(f"Top Plane@{platen}", "PLANE"),
                       named_ref("Top Plane", "PLANE"), 0.0,
                       label="platen spin snapshot", verify=(platen, pl_o))

    async def _lock_to_platen(name: str, label: str) -> None:
        await lock_mate(adapter, named_ref(f"Front Plane@{name}", "PLANE"),
                        named_ref(f"Front Plane@{platen}", "PLANE"),
                        label=f"{label} locked to platen")

    # Rack: Rx(180) -> teeth point down, crests 2 below the platen edge (the
    # machine reflection of the pre-mirror Rz180; z origin on the rack back).
    rack = await place_component(adapter, "platen-rack",
                                 [RACK_X0, RACK_Y0, RACK_BACK_Z],
                                 [180.0, 0.0, 0.0], ROT_X_180, ground=False)
    await _lock_to_platen(rack, "platen-rack")
    # Guide rails on the platen back, above/below the bar band -- the platen
    # HANGS by the top rail's underside on the bar's top edge.
    guides = []
    for gy in GUIDE_Y:
        guide = await place_component(adapter, "platen-guide",
                                      [PLATE_X0, gy, BAR_FRONT_Z],
                                      [0.0, 0.0, 0.0], IDENTITY, ground=False,
                                      label=f"platen-guide (y{gy:.1f})")
        await _lock_to_platen(guide, f"platen-guide y{gy:.1f}")
        guides.append(guide)
    # Lock plates on the guide backs, bridging BEHIND the bar (1.0 clear of its
    # back face): top-rail locks hang DOWN over the bar (Rz180, 14 overlap),
    # bottom-rail locks bridge UP across the 7 open channel onto the bar band
    # (identity, 7 overlap -- the 19-tall plate is sized by this station); the
    # two rows clear each other by 1.0 in y.
    for x_c in LOCK_STATION_X:
        # Machine: the station is measured from the platen's +X edge (the mirror
        # of the pre-mirror left-edge station PLATE_X0 + x_c).
        station = PLATE_X0 + PLATE_WIDTH - x_c
        top = await place_component(
            adapter, "guide-lock",
            [station + LOCK_WIDTH / 2.0, GUIDE_Y[1] + GUIDE_HEIGHT, LOCK_Z0],
            [0.0, 0.0, 180.0], rot_z_rows(180.0), ground=False,
            label=f"guide-lock (top x{x_c:.0f})")
        await _lock_to_platen(top, f"guide-lock top x{x_c:.0f}")
        bot = await place_component(
            adapter, "guide-lock",
            [station - LOCK_WIDTH / 2.0, GUIDE_Y[0], LOCK_Z0],
            [0.0, 0.0, 0.0], IDENTITY, ground=False,
            label=f"guide-lock (bottom x{x_c:.0f})")
        await _lock_to_platen(bot, f"guide-lock bottom x{x_c:.0f}")
    # Paper clips: bright brass strips hugging the platen's left/right edges
    # from the top edge down (ch22 front photo). Rz(-90) stands the +X-authored
    # strip vertical (the machine reflection of the pre-mirror Rz+90); each lands
    # 1 inside its edge with its holes on the platen's edge sockets.
    for sx in (PLATEN_SOCKET_XY[0][0], PLATEN_SOCKET_XY[2][0]):
        # pre-mirror hole line -> strip edge, negated to the machine (-X) frame.
        clip_x = -(PLATE_X0 + sx + CLIP_WIDTH / 2.0)
        # Rz(-90) hangs the strip from its top-edge origin (the pre-mirror Rz+90
        # rose from the bottom; the reflection swaps the origin end).
        clip = await place_component(
            adapter, "platen-clip",
            [clip_x, PLATE_Y0 + PLATE_HEIGHT, PLATE_FRONT_Z - CLIP_THICKNESS],
            [0.0, 0.0, -90.0], rot_z_rows(-90.0), ground=False,
            label=f"platen-clip (x{clip_x:+.0f})")
        await _lock_to_platen(clip, f"platen-clip x{clip_x:+.0f}")
    # Recording paper over the platen front face: front 0.5 proud, clear of the
    # edge clips, 6 top/bottom margin. The 0.25-thick sheet leaves 0.25 air
    # behind it (build_platen_paper) so no face lands coplanar on the platen.
    paper = await place_component(adapter, "platen-paper",
                                  [PLATE_X0 + 20.25, PLATE_Y0 + 6.0, PLATE_FRONT_Z - 0.5],
                                  [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await _lock_to_platen(paper, "platen-paper")

    # --- platen-riding fasteners (ALL lock-mated -- rework E5) -----------------
    # The socket lists are pre-mirror-ordered; negate x to the machine frame.
    for x, y in CLIP_SCREW_XY:
        screw = await place_component(
            adapter, "fillister-screw", [-x, y, PLATE_FRONT_Z - CLIP_THICKNESS],
            [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label=f"fillister-screw (clip x{-x:+.0f} y{y:.0f})")
        await _lock_to_platen(screw, f"clip screw x{-x:+.0f} y{y:.0f}")
    for x, y in GUIDE_SCREW_XY:
        # Seated on the counterbore floor: crown 0.2 sub-flush so the paper
        # lies flat; shank threads 2.4 into the rail's blind hole.
        screw = await place_component(
            adapter, "fillister-screw", [-x, y, PLATE_FRONT_Z + PLATEN_CBORE_DEPTH],
            [0.0, 0.0, 0.0], IDENTITY,
            ground=False, label=f"fillister-screw (guide x{-x:+.0f} y{y:.0f})")
        await _lock_to_platen(screw, f"guide screw x{-x:+.0f} y{y:.0f}")
    for x, y in LOCK_SCREW_XY:
        # Ry(180): shank points machine -Z, head on the lock plate's back.
        screw = await place_component(
            adapter, "fillister-screw", [-x, y, LOCK_Z0 + 2.0],
            [0.0, 180.0, 0.0], ROT_Y_180,
            ground=False, label=f"fillister-screw (lock x{-x:+.0f} y{y:.0f})")
        await _lock_to_platen(screw, f"lock screw x{-x:+.0f} y{y:.0f}")

    # --- transgear group (the real train) --------------------------------------
    # Bracket on the bar's back face, stud bore below the bar.
    await place_component(adapter, "transgear-bracket",
                          [STUD_XY[0], STUD_XY[1], BRACKET_Z0],
                          [0.0, 0.0, 0.0], IDENTITY)
    # +dx first (screw at machine -2), to match the pose ledger's -1/-2.
    for dx in (BRACKET_SCREW_DX, -BRACKET_SCREW_DX):
        # Ry(180): shank forward into the bar, head on the bracket back.
        await place_component(adapter, "bracket-screw",
                              [STUD_XY[0] + dx, BAR_CY, STUB_Z0],
                              [0.0, 180.0, 0.0], ROT_Y_180,
                              label=f"bracket-screw (x{STUD_XY[0] + dx:+.0f})")
    # Rx(-90): stud +Y -> -Z; base z -125.9..-135, O5 seat to -148.8, collar
    # to -152.8.
    await place_component(adapter, "transgear-stub", [STUD_XY[0], STUD_XY[1], STUB_Z0],
                          [-90.0, 0.0, 0.0], ROT_X_NEG90)
    # Latch arm in the slot between the rack's back face and the bar front,
    # swung to the knob at LATCH_ANGLE (thickness centred about ARM_Z). The 'z'-
    # plane machine reflection flips the flat arm front-to-back, so the machine
    # rows are Rx(180) . Rz(LATCH_ANGLE) -- euler [180, 0, LATCH_ANGLE_DEG].
    await place_component(adapter, "transgear-latch", [STUD_XY[0], STUD_XY[1], ARM_Z],
                          [180.0, 0.0, LATCH_ANGLE_DEG],
                          rows_from_euler([180.0, 0.0, LATCH_ANGLE_DEG]))
    # 120T DP38 reducer disc on the stud's O5 seat, FREE (revolute below) --
    # gear-mated to the third gear. Identity spin: a tooth points along the
    # c2c line (LATCH_ANGLE is a multiple of its 3-deg pitch).
    disc = await place_component(adapter, "rack-pinion",
                                 [STUD_XY[0], STUD_XY[1], DISC_Z0],
                                 [0.0, 0.0, 0.0], IDENTITY, ground=False,
                                 label="rack-pinion (120T reducer disc)")
    await _sprocket_revolute(adapter, disc, "reducer disc")
    # 12T DP30 feed pinion locked coaxially behind the disc ("behind and
    # attached to the fourth gear is the fifth gear" -- 4/4 video); its long
    # face bridges back to the rack band and meshes the teeth-down rack.
    feed = await place_component(adapter, "transgear-feed-pinion",
                                 [STUD_XY[0], STUD_XY[1], FEED_Z0],
                                 [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{feed}", "PLANE"),
                    named_ref(f"Front Plane@{disc}", "PLANE"),
                    label="feed pinion locked to the disc")
    # Knob shaft on the latch's small hub: Rx(+90) runs local +Y to machine +Z
    # (removable seat at the chain plane, O5 third-gear seat, hub ride, knob).
    knob_shaft = await place_component(adapter, "transgear-knob-shaft",
                                       [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], KNOB_SHAFT_Z0],
                                       [90.0, 0.0, 0.0], ROT_X_POS90, ground=False)
    # 12T DP38 third gear on the O5 seat, phased so a GAP faces the disc's
    # tooth along the c2c line.
    third = await place_component(adapter, "transgear-pinion",
                                  [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], THIRD_Z0],
                                  [0.0, 0.0, THIRD_PHASE_DEG],
                                  rot_z_rows(THIRD_PHASE_DEG), ground=False,
                                  label="transgear-pinion (12T third gear)")
    # Mounted T24 removable = the knob-end chain wheel (ch. 23: the roller
    # chain rides the removable's teeth; swapping removables changes the
    # platen ratio). FREE to spin: the belt/chain feature couples it to the
    # crank T12.
    t24 = await place_component(adapter, "transgear-removable",
                                [KNOB_SHAFT_XY[0], KNOB_SHAFT_XY[1], REMOVABLE_Z0],
                                [0.0, 0.0, 0.0], IDENTITY, configuration="T24",
                                ground=False,
                                label="transgear-removable (mounted T24)")
    await _sprocket_revolute(adapter, t24, "T24 knob wheel")
    # Key the knob cluster to spin as ONE rigid body: LOCK the knob shaft and
    # the third gear to the (free-spinning) T24 wheel -- all three ride the
    # same physical knob shaft. Net DOF unchanged: freeing shaft + third
    # (+12 DOF) is removed by the two 6-DOF Lock mates; the cluster keeps
    # T24's single free spin.
    await lock_mate(adapter, named_ref(f"Front Plane@{knob_shaft}", "PLANE"),
                    named_ref(f"Front Plane@{t24}", "PLANE"),
                    label="knob cluster: knob shaft locked to T24")
    await lock_mate(adapter, named_ref(f"Front Plane@{third}", "PLANE"),
                    named_ref(f"Front Plane@{t24}", "PLANE"),
                    label="knob cluster: third gear locked to T24")
    # Crank-end T12 removable = the crank-shaft chain wheel, brought over from
    # drive-train so the chain seats on BOTH sprockets locally. Placed at the
    # MACHINE crank centre = -CHAIN_CRANK_CENTRE (the pre-mirror _chain anchor,
    # == -drive-train (X_CRANK, Y_CRANK); _assert_chain_layout pins this).
    # Coplanar with the T24 on the -155 chain plane; a spur gear is symmetric so
    # identity rotation. FREE to spin -- this is the crank input, the single
    # operational DOF.
    t12 = await place_component(adapter, "transgear-removable",
                                [-CHAIN_CRANK_CENTRE[0], CHAIN_CRANK_CENTRE[1], REMOVABLE_Z0],
                                [0.0, 0.0, 0.0], IDENTITY, configuration="T12",
                                ground=False,
                                label="transgear-removable (crank chain wheel T12)")
    await _sprocket_revolute(adapter, t12, "T12 crank wheel")
    # The roller chain looping both removables (_assert_chain_layout pins the
    # _chain.py anchors to KNOB_SHAFT_XY / the drive-train crank).
    await _insert_roller_chain(adapter)

    # --- operational coupling (every stage a real mate) ------------------------
    # (1) The native Belt/Chain assembly feature couples the crank T12 <-> knob
    # T24 exactly as the roller chain physically does: SAME rotation sense (both
    # sprockets turn the same way -- a gear mate models an external mesh and
    # REVERSES) at the pitch-diameter ratio 24:48 = 12:24 teeth = 0.500 (each
    # link engages one tooth, so rev_T12 * 12 == rev_T24 * 24). The pulley
    # members are each sprocket's Axis1 DATUM AXIS, not a face: with a face
    # member SW bakes the picked face's diameter -- on these sprockets the
    # tooth-TIP cylinder (28:52 = 0.538, a ~7.7% feed error) -- into the
    # EngageBelt coupling mate and no definition-level route rewrites it; an
    # axis has no diameter to steal, so the typed pitch diameters drive the
    # mate exactly (probed live 2026-07-06, ratio +0.5000; see
    # memory/belt-chain-feature-com-binding.md). The adapter reads the mate's
    # own D1/D2 back and fails loud on a mismatch. EngageBelt authors the
    # coupling mates; CreateBeltPart stays off -- the roller-chain component
    # pattern above is the visual. Both sprockets stay FREE (Axis1 pinned,
    # spin-only via _sprocket_revolute), so the belt constrains only their
    # relative rotation -- 0 net free DOF added.
    from solidworks_mcp.adapters.base import BeltChainParameters
    check(
        "chain coupling T12<->T24 (belt/chain feature, pitch 24:48)",
        await adapter.insert_belt_chain(BeltChainParameters(
            pulley_components=[t12, t24],
            pulley_diameters=[2.0 * PITCH_R_T12, 2.0 * PITCH_R_T24],  # mm
            pulley_member_axes=[f"Axis1@{t12}", f"Axis1@{t24}"],
            location_plane="Front Plane",
            engage_belt=True, create_belt_part=False, blank_sketch=True)))
    # (2) GEAR mate 12:120: the third gear (in the knob cluster) drives the
    # reducer disc -- the permanent DP38 mesh the latch arm exists to hold.
    await gear_mate(
        adapter,
        named_ref(f"Axis1@{third}", "AXIS"),
        named_ref(f"Axis1@{disc}", "AXIS"),
        [THIRD_TEETH, DISC_TEETH],
        label="third gear 12T : disc 120T (DP38)")
    # (3) RACK-PINION mate: the feed pinion (locked to the disc) feeds the
    # platen at its own pitch circumference -- pi * 10.16 per rev. The rack
    # linear reference is the RACK's own pitch-line Axis1 (the physical
    # engagement line; the platen follows through its lock mate), the pinion
    # reference is the stud axis. The engagement SENSE is calibrated from the
    # verify:kinematics signed feed assert (2026-07-07 field report: the
    # platen-axis-referenced default fed the paper backward vs the tooth
    # contact; the pitch-axis re-reference still solved reversed at flip=False
    # -- the live gate measured +0.133 mm for feed Z -1.50 deg). flip=True
    # lands the physical sense; recalibrate HERE (never the probe's FEED_SIGN)
    # if the gate ever fails on sign again.
    await rack_pinion_mate(
        adapter,
        named_ref(f"Axis1@{rack}", "AXIS"),
        named_ref(f"Axis1@{feed}", "AXIS"),
        rack_travel_per_revolution=math.pi * FEED_PD,
        flip=True,
        label="platen feed (feed pinion on the rack)")
    # (4) The crank spin is the FREED operational-DOF park driver. Deferred in
    # the default `free` build (recorded, not authored) -> T12 spins free and
    # drives the whole gear+rack train; authored + PARK_crank_spin in a
    # `locked` build. A spur sprocket is symmetric so the spin pose is
    # cosmetic; pin the local Right-plane dihedral (read live) like
    # drive-train's crank_angle.
    t12_o = component_origin(adapter, t12)
    a_t12 = component_transform(adapter, t12)
    crank_dihedral = math.degrees(math.acos(max(-1.0, min(1.0, a_t12[0]))))
    await angle_driver(
        adapter,
        named_ref(f"Right Plane@{t12}", "PLANE"), named_ref("Right Plane", "PLANE"),
        crank_dihedral,
        label=f"crank spin PARK driver (freed in default build; a={crank_dihedral:.2f})",
        verify=(t12, t12_o), free_dof_key="crank_spin")

    # Spare T18 removable: the swap chain wheel resting loose on the base, west
    # of the platen (a flat sibling of the mounted T24 above).
    await place_component(adapter, "transgear-removable", list(SPARE_GEAR_POS),
                          [-90.0, 0.0, 0.0], ROT_X_NEG90, configuration="T18",
                          label="transgear-removable (spare T18)")

    # Certify the AS-BUILT model. `free` -> necessity only (the crank spin is
    # genuinely free; the exact-count 0-DOF closure runs in the release preflight,
    # where the recorded spec is replayed). `locked` -> strict 0-DOF. All other
    # checks run on the as-built model unchanged.
    if LOCK:
        await assert_expected_free_dof(adapter, 0)
    else:
        # ONE freed operational DOF: the crank spin (the deferred PARK driver
        # above), which drives the chain-coupled knob cluster, the gear-mated
        # disc + feed pinion, and the rack-fed platen. Target the SPECIFIC T12
        # crank instance (not the shared ``transgear-removable`` stem: the T24
        # knob + T18 spare share it, so a stem check would pass even if T24
        # were free and the crank T12 pinned -- codex #189).
        assert_free_dof_necessity(
            adapter, 1, required_instances=(t12,))
        write_park_specs(ASM_NAME)
    check_no_interference(adapter)
    # Machine coords put the output/paper side at -Z, so SolidWorks' native Front
    # renders the machine BACK (chain and transgear cluster mirrored). Re-base the
    # standard views (same as the top assembly) so the saved doc and the _front
    # render show the true machine front. Geometry untouched.
    remap_front_to_machine_front(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
