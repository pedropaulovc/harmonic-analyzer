r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the stepped cast base, four polished tube
columns seated 22.4 into blind base sockets, the rocker-arm support, and
the top-frame casting. Eight stock 90280A837 cross screws enter from the
front/rear, clear both tube walls, and engage the far casting wall as well as
the near wall. The visible frame pose and evidence-locked top station remain
unchanged.

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28.7 cm
flange depth -- the 27.45 cm pad is set by the column stations, not the ch. 6
"28 cm" callout; see ``fr_harmonic_base_spec.TOP_WIDTH``):

* harmonic-base fixed at the origin, deck at Y=50.8, with four 22.4-deep
  sockets opening on the green land at Y=47.8.
* tube-frame x4 inserted at Y=25.4 near the top-plate corners at
  x +/-197, z +/-112, preserving the prior visible span.
* rocker-arm-support x1 (the windowed trapezoidal NORTH support,
  build_fr_rocker_arm_support.py) at (X, Z) = (+72.9, 0), foot seated on the
  base top. A 192.0 (7.56 in, #1038) long x 177.8 tall cast plate, 63.5 thick (tapering to 16.76 at the
  apex), with the central rounded window; its apex carries the north pivot ball
  mount (ch-channel.SLDASM, at machine z +116.915) and the rocker-pivot SHAFT runs
  along Z. This REPLACES the rocker-arm-portal casting (north + south unified
  portal frame) with the faithful reproduction of the original hand-built
  support -- the NORTH upright ONLY; the south upright and the top/foot rails
  are not part of this casting.

  The part is authored with its big windowed faces normal to its LOCAL Z (the
  thin 63.5 axis) and its 177.8 width along local X. In the machine the window
  must face +/-X -- it reads face-on in the ch. 30 p008 +X side view, exactly
  like the portal it replaces -- so the casting is turned +90 deg about Y
  (ROT_Y_POS90): local Z (window normal) -> machine +X, local X (177.8 width)
  -> machine Z, local Y (height) -> machine Y. The part origin is at the casting
  centre (bbox +/-88.9 in X and Y), so the turned wall spans machine
  Y 50.8..228.6 (foot on the base top, apex at the pivot height) and machine
  Z -88.9..88.9 at its original location. The north pivot ball
  mount (ch-channel.SLDASM) is recentered to z +84.588, so its narrowed
  O13 footprint remains fully seated inside the wall's rear edge -- no cantilever.
  Seat Y = base-top 50.8 + 88.9 (half-height) = 139.7. The pivot x = 72.9, the
  rocker seesaw's mid-span (ch30 GT arm-end triangulation midpoint +72.5; the
  reclosed rod-pin hole 125.890 out reaches the cam centre at -52.990, rods plumb; the old
  "arbor 47.5 + 25.4 rod lever" chain died with the ch30 re-anchor).
  Inserted at its exact authored transform and fixed (``ground=True``).
* top-frame x1: the green one-piece casting at mid-plane Y = 1017.9431 (side
  rails 34.2 wide / front-rear rails 38 wide x 1.437 tall, band
  y 999.6932..1036.193 = 39.358..40.795; corner bosses Ø45 rise to 1040.765),
  bored around the four columns; its east rail (-X) carries the gooseneck hub
  and its west rail top face seats the fulcrum-keeper feet (ch-channel.SLDASM).
* tube-frame-cap x4: intact stock McMaster 9275K141 push-on caps seated on the
  square tube ends, with their skirts sheltered by the top-frame recesses.
* frame-cross-screw x8 + gooseneck-set-screw x1: four lower and four upper
  casting-to-column retainers plus the top-frame hub fastener (3/4 in, through
  the hub boss's spot face, head standing proud), each placed at its shared
  physical station and fixed.
* nameplate x1: the maker's plate (book ch. 26; user ruling 2026-10-09), laid
  FLAT on the WEST (+X) end of the black deck, decorated side up and read by
  an operator west of the machine. Cosmetic; constrained at its shared
  transform and fixed (see fr_nameplate_spec.MOUNT_POS).
* fillister-screw x4 (2026-09-02 ch26 p.71 re-derive): the brass slotted
  round-head screws at the plate's four corners, heads seated on the
  decorated face, shanks down through the plate's #4 clearance holes into the
  base's through #4-40 taps (fr_harmonic_base_fasteners NAMEPLATE_SCREW_XZ -- the same
  fr_nameplate_spec derivation). Fixed like every rigid frame member.

Hold-down: four stock 1/4-20 UNC-2A hex-head screws install from the top,
through the support foot's 5/16 clearance drills, into through 1/4-20 UNC-2B
seats in the base. The foot pattern transforms from local X +/-2.375,
Z +/-.687 to machine x 2.183/3.557, z -2.375/+2.375 in (the base's shared
SUPPORT_HOLD_DOWN_XZ contract). Each McMaster 92240A540 screw bears on the
bottom of its exact vendor-modeled 0.277813 mm under-head washer transition,
crosses the 6.35 mm foot, and inserts 12.422187 mm into the base receiver.
The screws are inserted at exact authored transforms and fixed; they do not
constrain the support. Every rigid frame member is fixed at its authored
transform: the frame has no operational DOF, and a lock mate to the fixed base
would hold only the same pose (it references no part face, so a part edit can
neither re-pose nor dangle it). Transform readback and the save-time pose
ledger remain the fail-loud placement tripwires. Final asserts: every
component fixed or ``swFullyConstrained`` and no uncontracted interference.

The 20-channel pitch stations live in the channel subassembly.

Dimensions: cad/DIMENSIONS.md ch. 6 (base/column), ch. 14 layout
(supports), "Channel & top-frame layout" (top frame); placements
photo-derived (med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_frame_assembly.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

import _telemetry

from _check import check
from _com import _early_bound
from _explode import Step as ExplodeStep, author_explode_steps, stem_groups
from _custom_properties import apply_custom_properties
from _document_units import apply_package_model_units
from _paths import OUT_SLDPRT
from _session import run_build
from _drawing_marks import DRAWN_BY, mark_dimensions_for_drawing
from _drawing_precision import apply_drawing_precision
from _drawing_tolerances import set_dimension_symmetric_tolerance
from _feature_tree import name_last_feature
from _printed_tolerance import printed_deviations
from _assembly_contract import assembly_contract
from _sketch import (
    SketchDims,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _assembly import (
    activate_assembly_contract,
    assembly_title_properties,
    assert_components_fully_defined,
    author_in_drawing_configurations,
    check_no_interference,
    place_component,
    save_assembly_and_images,
)
from _assembly_patterns import (
    assert_pattern_targets,
    grid_component_pattern,
    PatternDirection,
)
from _transforms import (
    ROT_X_NEG90,
    ROT_X_POS90,
    ROT_Y_POS90,
    rot_z_rows,
    rows_from_euler,
)
from fr_harmonic_base_fasteners import (
    BASE_CROSS_TAP_SPEC,
    EDGE_BREAK_MAX_MM,
    HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_INSERTION_MAX_MM,
    HOLD_DOWN_INSERTION_MIN_MM,
    HOLD_DOWN_SEAT_SPEC,
    HOLD_DOWN_THREAD,
    HOLD_DOWN_THREAD_CLASS,
    NAMEPLATE_INSTALLED_FULL_THREAD_MIN,
    NAMEPLATE_SEAT_SPEC,
    NAMEPLATE_SCREW_XZ,
    require_through_seat_fit,
    through_seat_material,
)
from _fr_frame_interference import ALLOWED_PAIRS
from _cone_axis_constants import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
)
from sh_vn_brass_fillister_screw_spec import SHANK_LEN as NAMEPLATE_SCREW_SHANK_LEN
from fr_nameplate_spec import (
    MOUNT_EULER as NAMEPLATE_EULER,
    MOUNT_FRONT_Y as NAMEPLATE_FRONT_Y,
    MOUNT_HOLE_XZ as NAMEPLATE_SCREW_STATIONS,
    MOUNT_POS as NAMEPLATE_POS,
    MOUNT_ROWS as NAMEPLATE_ROWS,
    PLATE_HEIGHT as NAMEPLATE_HEIGHT,
    PLATE_THICKNESS as NAMEPLATE_THICKNESS,
    PLATE_THICKNESS_PRECISION as NAMEPLATE_THICKNESS_PRECISION,
    UNIT as NAMEPLATE_UNIT,
)
from fr_rocker_arm_support_section_spec import FOOT_THICKNESS as LAG_FOOT_THICKNESS
from fr_rocker_arm_support_spec import (
    HOLE_DIA as LAG_SUPPORT_CLEARANCE_DIA,
    SUPPORT_HOLD_DOWN_XZ,
    SUPPORT_WORLD_SEAT_Y,
    SUPPORT_WORLD_X,
    SUPPORT_WORLD_Z,
)
from _mcmaster_91410a540 import SHANK_LEN as GOOSENECK_SHANK_LEN
from fr_vn_frame_cross_screw_spec import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    SHANK_DIA as CROSS_SCREW_SHANK_DIA,
    SHANK_LEN as CROSS_SCREW_SHANK_LEN,
    THREAD as CROSS_SCREW_THREAD,
    THREAD_CLASS as CROSS_SCREW_THREAD_CLASS,
)
from fr_vn_lag_screw_spec import (
    BEARING_OFFSET as LAG_BEARING_OFFSET,
    HEAD_AF as LAG_HEAD_AF,
    SHANK_DIA as LAG_SHANK_DIA,
    SHANK_LEN as LAG_SHANK_LEN,
    THREAD_CLASS as LAG_THREAD_CLASS,
    THREAD_LEN as LAG_THREAD_LEN,
    THREAD_SIZE as LAG_THREAD_SIZE,
    TIP_CHAMFER as LAG_TIP_CHAMFER,
)
from build_fr_top_frame import (
    GOOSENECK_X as TOP_GOOSENECK_X,
    SET_SPOT_FACE_X as TOP_SET_SPOT_FACE_X,
    SIDE_TAP_SPEC as TOP_CROSS_TAP_SPEC,
)
from fr_frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    CAP_MOUTH_Y,
    CAP_TOP_Y,
    CASTING_FULL_THREAD_DEPTH,
    COLUMN_BOTTOM_Y,
    COLUMN_SOCKET_DIAMETER,
    TOP_AXIS_HEIGHT_DIMENSION,
    TOP_AXIS_HEIGHT_PLACES,
    TOP_AXIS_SETTING_FEATURE,
    TOP_FRAME_MID_Y,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from fr_harmonic_base_spec import STACK_HEIGHT
from frame_column_stations import COLUMN_X
from fr_vn_tube_frame_cap_spec import (
    INSIDE_HEIGHT as CAP_INSIDE_HEIGHT,
    TOTAL_HEIGHT as CAP_TOTAL_HEIGHT,
)
from fr_tube_frame_spec import COLUMN_LENGTH, OUTER_DIA as COLUMN_OUTER_DIA
from sm_gooseneck_geom import TUBE_DIA as GOOSENECK_TUBE_DIA
import fr_frame_explode_spec as explode
from fr_frame_setting_bands import TOP_AXIS_HEIGHT_BAND_MM

ASM_NAME = "fr-frame"
FRAME_EXPLODED = "FRAME_EXPLODED"

BASE_TOP_Y = STACK_HEIGHT
FRONT_COLUMN_Z = FRAME_FRONT_COLUMN_Z
REAR_COLUMN_Z = FRAME_REAR_COLUMN_Z
SUPPORT_X = SUPPORT_WORLD_X  # rocker pivot x: the seesaw mid-span (ch30 GT arm-end
# triangulation midpoint +72.5; M6.8 mirror). Rod-side tip reaches the drum.
SUPPORT_Z = SUPPORT_WORLD_Z
SUPPORT_SEAT_Y = SUPPORT_WORLD_SEAT_Y  # rocker-arm-support's origin is
# at the casting centre (bbox Y +/-88.9), so seating its foot on the base top
# lifts the origin by the 88.9 foot half-height.
# Turn the support +90deg about Y so its big windowed faces (local Z normal)
# point along machine +/-X (face-on in the ch. 30 p008 +X side view), matching
# the portal it replaces; local X (177.8 width) maps to machine Z.
SUPPORT_EULER = [0.0, 90.0, 0.0]
SUPPORT_ROWS = ROT_Y_POS90

# Rocker-support hold-down: four stock 1/4-20 x 3/4 hex-head screws,
# coaxial with the support clearance drills and through base taps via authored
# transforms; one fixed seed and a native grid retain that placement.
# Stations are the foot pattern in the machine frame: local X +/-60.32,
# Z +/-17.46 turned +90 degrees about Y -> machine x 55.44/90.36 and
# z SUPPORT_Z +/-60.32. The screw's actual bearing face lies
# LAG_BEARING_OFFSET below its model origin. Raising that origin by the exact
# vendor offset seats the washer face on the support without solid overlap;
# head remains above +Y and shank/tip along -Y.
LAG_SCREW_XZ = SUPPORT_HOLD_DOWN_XZ
LAG_SCREW_UNDER_HEAD_Y = BASE_TOP_Y + LAG_FOOT_THICKNESS + LAG_BEARING_OFFSET
LAG_SCREW_TIP_Y = LAG_SCREW_UNDER_HEAD_Y - LAG_SHANK_LEN
LAG_BASE_ENGAGEMENT = BASE_TOP_Y - LAG_SCREW_TIP_Y
if LAG_THREAD_SIZE != HOLD_DOWN_THREAD:
    raise AssertionError("stock hold-down and base tap nominal threads must match")
if (LAG_THREAD_CLASS, HOLD_DOWN_THREAD_CLASS) != ("2A", "2B"):
    raise AssertionError(
        "stock hold-down requires class 2A external / 2B internal threads"
    )
if LAG_SUPPORT_CLEARANCE_DIA <= LAG_SHANK_DIA:
    raise AssertionError("support clearance drill must clear the stock hold-down shank")
if LAG_HEAD_AF <= LAG_SUPPORT_CLEARANCE_DIA:
    raise AssertionError("stock hex head must bear on the support foot")
if LAG_THREAD_LEN < LAG_SHANK_LEN:
    raise AssertionError("selected support hold-down must be fully threaded")
if not math.isclose(LAG_BASE_ENGAGEMENT, HOLD_DOWN_ENGAGEMENT, abs_tol=1e-9):
    raise AssertionError(
        "stock hold-down engagement must follow its exact bearing-face geometry"
    )
# Use the same stock-length/printed-foot window as the base receiver; tip
# loss remains the harvested source-model geometry, not a stock-tip limit.
LAG_BASE_THREAD_FITS = tuple(
    require_through_seat_fit(
        "rocker support",
        HOLD_DOWN_SEAT_SPEC,
        through_seat_material(HOLD_DOWN_SEAT_SPEC, xz),
        insertion_min_mm=HOLD_DOWN_INSERTION_MIN_MM,
        insertion_max_mm=HOLD_DOWN_INSERTION_MAX_MM,
        tip_loss_mm=LAG_TIP_CHAMFER,
    )
    for xz in LAG_SCREW_XZ
)

# --- Frame cross-screw stack -------------------------------------------------
# The stock screw origin is its under-head seat and its shank runs along local
# -Y. Front placements rotate it toward +Z; rear placements toward -Z. Each
# 1.750-in shank crosses both Ø.197 tube walls and the near casting's #10
# close clearance (owner ruling 2026-11-05, both castings) and reaches at
# least one major diameter into the far casting while retaining .060 of full
# thread beyond the tip in the 1.81-deep far-wall tap.
COLUMN_RADIUS = COLUMN_OUTER_DIA / 2.0
SOCKET_RADIUS = COLUMN_SOCKET_DIAMETER / 2.0
BASE_CROSS_SCREW_TIP_Z = BASE_SCREW_SEAT_Z - CROSS_SCREW_SHANK_LEN
TOP_CROSS_SCREW_TIP_Z = TOP_SCREW_SEAT_Z - CROSS_SCREW_SHANK_LEN
BASE_FAR_CASTING_ENGAGEMENT = (
    abs(REAR_COLUMN_Z) - SOCKET_RADIUS - BASE_CROSS_SCREW_TIP_Z
)
TOP_FAR_CASTING_ENGAGEMENT = abs(REAR_COLUMN_Z) - SOCKET_RADIUS - TOP_CROSS_SCREW_TIP_Z
CROSS_SCREW_THREAD_RESERVE = CASTING_FULL_THREAD_DEPTH - CROSS_SCREW_SHANK_LEN
if TUBE_CROSS_HOLE_DIAMETER <= CROSS_SCREW_SHANK_DIA:
    raise AssertionError("tube cross drilling does not clear the stock cross screw")
if CROSS_SCREW_HEAD_DIA <= 5.0:
    raise AssertionError("stock cross-screw head cannot bear on its Ø9 seat")
if (CROSS_SCREW_THREAD_CLASS, BASE_CROSS_TAP_SPEC.thread_class) != ("2A", "2B"):
    raise AssertionError("lower cross screw requires class 2A/2B thread pairing")
if (CROSS_SCREW_THREAD_CLASS, TOP_CROSS_TAP_SPEC.thread_class) != ("2A", "2B"):
    raise AssertionError("upper cross screw requires class 2A/2B thread pairing")
if (
    BASE_CROSS_TAP_SPEC.size != CROSS_SCREW_THREAD
    or TOP_CROSS_TAP_SPEC.size != CROSS_SCREW_THREAD
):
    raise AssertionError("cross-screw and casting tap thread designations differ")
if min(BASE_FAR_CASTING_ENGAGEMENT, TOP_FAR_CASTING_ENGAGEMENT) < CROSS_SCREW_SHANK_DIA:
    raise AssertionError(
        "seated cross screw does not reach one diameter into far casting"
    )
if CROSS_SCREW_THREAD_RESERVE <= 0.0:
    raise AssertionError("seated cross screw exhausts the specified full thread")

# Cap geometry is authored opening-first along local +Y. The intact stock cap
# seats internally on the tube's square top, while its outer crown establishes
# the preserved overall frame height. The recessed boss only shelters the
# skirt; it is not the axial seat.
COLUMN_TOP_Y = COLUMN_BOTTOM_Y + COLUMN_LENGTH
if not math.isclose(CAP_MOUTH_Y + CAP_INSIDE_HEIGHT, COLUMN_TOP_Y, abs_tol=1e-9):
    raise AssertionError("cap must seat on the tube end, not the recess floor")
if not math.isclose(CAP_MOUTH_Y + CAP_TOTAL_HEIGHT, CAP_TOP_Y, abs_tol=1e-9):
    raise AssertionError("cap placement does not preserve the finished frame top")
#
# gooseneck-set-screw: 1x McMaster 91410A540 1/4-20 x 3/4 square-head cup-point
# set screw gripping the gooseneck's bare leg through the casting's east-hub boss,
# axis along X at (y TOP_SCREW_Y, z 3.088 -- the hub/post centreline).
# Entered through the boss's spot face x -218.08 (21.08 from the bore axis):
# local +Y -> -X (rot_z_rows(90), euler [0,0,90]) points the exact stock shank
# inboard while retaining its cup tip at x -203.56, 0.21 clear (outboard) of
# the gooseneck's Ø12.70 tube surface at x -203.35 (owner ruling 2026-11-08
# (Pedro), #2315: the Ø.520 hub bore takes the bare leg). The under-head face
# is the tip less the shank, x -222.61: the head stands 4.5 proud of the spot
# face, so the cup point reaches the leg before the head could bottom.
GOOSENECK_HUB_Z = 3.088  # gooseneck bore centreline (unchanged position)
SET_SCREW_TUBE_GAP = 0.21  # cup tip outboard of the nominal tube surface
SET_SCREW_TIP_X = TOP_GOOSENECK_X - GOOSENECK_TUBE_DIA / 2.0 - SET_SCREW_TUBE_GAP
SET_SCREW_UNDER_HEAD_X = SET_SCREW_TIP_X - GOOSENECK_SHANK_LEN
if not SET_SCREW_UNDER_HEAD_X < TOP_SET_SPOT_FACE_X < SET_SCREW_TIP_X:
    raise AssertionError(
        "gooseneck set screw must cross the spot face with its head proud of it"
    )

# Maker's nameplate (ch.26 p.71; user ruling 2026-10-09): its traced outer edge
# defines the brass plate, flat on the black deck's WEST (+X) end, decorated up.
# The transform (NAMEPLATE_POS / _EULER / _ROWS, formerly authored here) now lives
# in fr_nameplate_spec -- the pure-data contract build_fr_harmonic_base reads to
# derive the tapped seats under the plate's corner screws -- so the plate, the
# base taps and the screws below derive from ONE source; the provenance and
# the axis mapping are documented there. The literal rows are re-proved
# against the euler at import (rows_from_euler is what assert_component_placed
# reads back).
if any(
    abs(a - b) > 1e-12
    for ra, rb in zip(rows_from_euler(NAMEPLATE_EULER), NAMEPLATE_ROWS)
    for a, b in zip(ra, rb)
):
    raise AssertionError(
        f"fr_nameplate_spec.MOUNT_ROWS {NAMEPLATE_ROWS} != rows_from_euler({NAMEPLATE_EULER})"
    )
#
# nameplate screws (2026-09-02 ch26 p.71 re-derive): 4x #4-40 brass
# fillister-screw, one per plate corner, screwed DOWN into the base's through
# #4-40 taps (fr_harmonic_base_fasteners NAMEPLATE_SCREW_XZ -- the plate's own
# DXF-mark holes carried through the shared mount transform). The part is
# authored axis along local +Z with the origin at the UNDER-HEAD bearing plane,
# head at -Z. The stock wrapper preserves that frame, so the placement point is
# the under-head seat on the plate's decorated face (y NAMEPLATE_FRONT_Y) and
# ROT_X_POS90 (euler [90,0,0]) turns local +Z -> -Y. The stock shank passes
# through NAMEPLATE_THICKNESS into the existing base threads; the head sits
# above the decorated face.
# The under-head plane seats FLUSH on the plate face. The stock external
# thread engages the matching #4-40 base seat rather than using a
# tap-drill-sized simplified shank.
NAMEPLATE_SCREW_EULER = [90.0, 0.0, 0.0]
NAMEPLATE_SCREW_ROWS = ROT_X_POS90
if NAMEPLATE_SCREW_STATIONS != NAMEPLATE_SCREW_XZ:
    raise AssertionError(
        f"nameplate screw stations {NAMEPLATE_SCREW_STATIONS} != base taps {NAMEPLATE_SCREW_XZ}"
    )
if NAMEPLATE_SCREW_SHANK_LEN < NAMEPLATE_THICKNESS + 2.0:
    raise AssertionError(
        f"fillister-screw shank {NAMEPLATE_SCREW_SHANK_LEN} cannot pass the "
        f"{NAMEPLATE_THICKNESS} nameplate with 2.0 thread engagement"
    )
# RV-03 states the installed overlap of the screw's external full form with
# the receiver's full female thread (NAMEPLATE_BASE_FULL_FORM_MIN, owned by
# fr_harmonic_base_fasteners), past the female entrance break; still under 1.5D.
_NAMEPLATE_THICKNESS_LOW = printed_deviations(
    NAMEPLATE_THICKNESS, NAMEPLATE_THICKNESS_PRECISION, unit=NAMEPLATE_UNIT,
)[0]
NAMEPLATE_SCREW_MAX_INSERTION = (
    NAMEPLATE_SCREW_SHANK_LEN - NAMEPLATE_THICKNESS - _NAMEPLATE_THICKNESS_LOW
)
NAMEPLATE_BASE_MATERIALS = tuple(
    through_seat_material(NAMEPLATE_SEAT_SPEC, xz)
    for xz in NAMEPLATE_SCREW_XZ
)
for _material in NAMEPLATE_BASE_MATERIALS:
    if not any(
        start <= EDGE_BREAK_MAX_MM + 1e-9
        and end >= NAMEPLATE_SCREW_MAX_INSERTION - 1e-9
        for start, end in _material.guaranteed_segments_mm
    ):
        raise AssertionError("nameplate through receiver reduces existing usable thread")
NAMEPLATE_BASE_FULL_FORM_MIN = NAMEPLATE_INSTALLED_FULL_THREAD_MIN
NAMEPLATE_TIP_CLEARANCE_MIN = min(
    material.deck_height_min_mm - NAMEPLATE_SCREW_MAX_INSERTION
    for material in NAMEPLATE_BASE_MATERIALS
)
if NAMEPLATE_TIP_CLEARANCE_MIN <= 0.0:
    raise AssertionError("nameplate screw tip reaches the base underside clearance floor")

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{name.replace('-', '_')}.py first"
        )
    return str(path)


_FRAME_QUANTITIES = {
    "fr-harmonic-base": 1, "fr-tube-frame": 4, "fr-vn-tube-frame-cap": 4,
    "fr-top-frame": 1, "fr-rocker-arm-support": 1, "fr-vn-lag-screw": 4,
    "fr-nameplate": 1, "sh-vn-brass-fillister-screw": 4, "fr-vn-frame-cross-screw": 8,
    "fr-vn-gooseneck-set-screw": 1,
}


def _frame_explode_plan(_model: Any, components: Any, baseline: Any) -> list[ExplodeStep]:
    """Twelve global translations; the cross screws split by their saved
    station (top/base Y, front/rear Z)."""
    groups = stem_groups(components, _FRAME_QUANTITIES)
    front, rear, upper, lower = [], [], [], []
    for name in groups["fr-vn-frame-cross-screw"]:
        _, y, z = baseline[name][9:12]
        if abs(y * 1000.0 - TOP_SCREW_Y) <= 1e-3:
            upper.append(name)
        elif abs(y * 1000.0 - BASE_SCREW_Y) <= 1e-3:
            lower.append(name)
        else:
            raise ValueError(f"{name}: unexpected cross-screw Y {y * 1000.0:g} mm")
        if z == 0.0:
            raise ValueError(f"{name}: cross screw on assembly mid-plane")
        (front if z < 0.0 else rear).append(name)
    if tuple(map(len, (front, rear, upper, lower))) != (4, 4, 4, 4):
        raise ValueError("cross-screw station split is not 4/4/4/4")
    support = [*groups["fr-rocker-arm-support"], *groups["fr-vn-lag-screw"]]
    nameplate = [*groups["fr-nameplate"], *groups["sh-vn-brass-fillister-screw"]]
    return [
        ExplodeStep(label, tuple(names), key, distance_mm)
        for label, names, key, distance_mm in (
            ("tube caps lift", groups["fr-vn-tube-frame-cap"], "y", 250.0),
            ("top frame clears columns", [*groups["fr-top-frame"], *upper, *groups["fr-vn-gooseneck-set-screw"]], "y", 150.0),
            ("front cross screws withdraw", front, "z", -50.0),
            ("rear cross screws withdraw", rear, "z", 50.0),
            ("gooseneck screw withdraws", groups["fr-vn-gooseneck-set-screw"], "x", -50.0),
            ("columns clear base seats", groups["fr-tube-frame"], "y", 60.0),
            ("support lifts from deck", support, "y", explode.SUPPORT_LIFT),
            ("support moves beside base", support, "x", explode.SUPPORT_ASIDE_X),
            ("support screws withdraw", groups["fr-vn-lag-screw"], "y", explode.SUPPORT_SCREW_WITHDRAW),
            ("nameplate lifts from deck", nameplate, "y", explode.NAMEPLATE_LIFT),
            ("nameplate moves beside base", nameplate, "x", explode.NAMEPLATE_ASIDE_X),
            ("nameplate screws withdraw", groups["sh-vn-brass-fillister-screw"], "y", explode.NAMEPLATE_SCREW_WITHDRAW),
        )
    ]


def _create_frame_explode(adapter: Any, configuration_name: str) -> None:
    """Author FRAME_EXPLODED in the active ``configuration_name`` (Default or
    Default Simplified; the drawing's small exploded view references the
    teeth/thread-free one) and leave the operational model collapsed."""
    author_explode_steps(
        adapter,
        configuration_name,
        view=FRAME_EXPLODED,
        source="Default",
        step_prefix="FRAME",
        plan=_frame_explode_plan,
    )


@_telemetry.traced("assembly.frame_top_axis_setting")
def _author_top_axis_setting(adapter: Any) -> None:
    """MHA-FR-00 step 3's controlling height: a vertical construction line on
    the Front plane (sketch u, v = machine X, Y) up the +X column's axis, from
    the base underside to the top cross-bore axis. Its length carries the
    setting's band and places for the drawing to import. No solid or pose
    edits; the sketch is blanked."""
    dims = SketchDims()
    check("create top-axis setting sketch", adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    line = check(
        "top-axis setting line",
        adapter.add_line(COLUMN_X, 0.0, COLUMN_X, TOP_SCREW_Y),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("top-axis setting line is not construction")
    check(
        "top-axis setting vertical",
        adapter.add_sketch_constraint(line, None, "vertical"),
    )
    anchor_point_to_origin(
        adapter, f"{line}.start", COLUMN_X, 0.0, "base underside on the column axis"
    )
    dims.record("TopAxisColumnX")
    dimension_between(
        adapter,
        f"{line}.start",
        f"{line}.end",
        "vertical_distance",
        TOP_SCREW_Y,
        "top cross-bore axis above the base underside",
    )
    dims.record(TOP_AXIS_HEIGHT_DIMENSION)
    ensure_fully_defined(adapter, "top-axis setting")
    check("exit top-axis setting sketch", adapter.exit_sketch())
    name_last_feature(adapter, TOP_AXIS_SETTING_FEATURE)
    dims.apply(adapter, TOP_AXIS_SETTING_FEATURE)
    set_dimension_symmetric_tolerance(
        adapter,
        TOP_AXIS_SETTING_FEATURE,
        TOP_AXIS_HEIGHT_DIMENSION,
        TOP_AXIS_HEIGHT_BAND_MM,
        places=TOP_AXIS_HEIGHT_PLACES,
        display_unit=assembly_contract(ASM_NAME).drawing_unit,
    )
    apply_drawing_precision(
        adapter,
        {TOP_AXIS_SETTING_FEATURE: {TOP_AXIS_HEIGHT_DIMENSION: TOP_AXIS_HEIGHT_PLACES}},
    )
    mark_dimensions_for_drawing(
        adapter, TOP_AXIS_SETTING_FEATURE, {TOP_AXIS_HEIGHT_DIMENSION}
    )
    blank_sketch(adapter, TOP_AXIS_SETTING_FEATURE)


def build(adapter) -> dict[str, str]:
    # Flip seeds + free-DOF contract: cad/config/assemblies/<ASM_NAME>.yaml.
    activate_assembly_contract(ASM_NAME)
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("fr-harmonic-base")
    _part("fr-tube-frame")  # column seed; placed via place_component below
    _part("fr-rocker-arm-support")  # placed via place_component below; assert it exists
    _part("fr-vn-lag-screw")  # support hold-down; placed via place_component below
    _part("fr-vn-frame-cross-screw")  # eight casting/column retainers
    _part("fr-vn-gooseneck-set-screw")  # west-hub set screw; placed via place_component
    _part("sh-vn-brass-fillister-screw")  # nameplate corner screws; placed via place_component
    _part("fr-vn-tube-frame-cap")  # four intact stock push-on caps
    _part("fr-top-frame")  # placed via place_component below

    check("create_assembly", adapter.create_assembly())
    apply_package_model_units(adapter, assembly_contract(ASM_NAME).drawing_unit, label=ASM_NAME)

    # Base: first insert is auto-fixed by SolidWorks.
    res = adapter.insert_component(InsertComponentParameters(file_path=base_path))
    check("insert_component harmonic-base (auto-fixed)", res)
    if not res.data.get("fixed"):
        raise RuntimeError("base component was not auto-fixed")

    # Columns seat 22.4 into the four base sockets, whose mouths open on the
    # green land. Lowering the authored origin to COLUMN_BOTTOM_Y (y 25.4, the
    # socket floor) preserves the exposed span and every upper attachment
    # station.
    column_target = [COLUMN_X, COLUMN_BOTTOM_Y, REAR_COLUMN_Z]
    column_name = place_component(
        adapter,
        "fr-tube-frame",
        column_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="tube-frame column seed",
    )
    column_instances = grid_component_pattern(
        adapter,
        [column_name],
        axis1="x",
        spacing1_mm=2.0 * COLUMN_X,
        instances1=2,
        axis2="z",
        spacing2_mm=REAR_COLUMN_Z - FRONT_COLUMN_Z,
        instances2=2,
        direction1=PatternDirection.FORWARD,
        direction2=PatternDirection.REVERSE,
        label="tube-frame column grid",
    )
    assert_pattern_targets(
        adapter,
        column_instances,
        [
            [-COLUMN_X, COLUMN_BOTTOM_Y, REAR_COLUMN_Z],
            [COLUMN_X, COLUMN_BOTTOM_Y, FRONT_COLUMN_Z],
            [-COLUMN_X, COLUMN_BOTTOM_Y, FRONT_COLUMN_Z],
        ],
        IDENTITY,
        "tube-frame column grid",
    )

    # Rocker-pivot support: the windowed trapezoidal NORTH support
    # (build_fr_rocker_arm_support.py), the faithful reproduction of the original
    # hand-built casting that REPLACES the unified rocker-arm-portal. Turned
    # +90deg about Y (SUPPORT_ROWS) so its big windowed faces point along
    # machine +/-X (face-on in the ch. 30 p008 side view), with local X (177.8
    # width) -> machine Z and the foot on the base top. Its origin is the casting
    # centre.
    #
    # Inserted on-solution (a single machine-handed casting) and fixed. Its
    # authored transform places the physical foot on the base top.
    place_component(
        adapter,
        "fr-rocker-arm-support",
        [SUPPORT_X, SUPPORT_SEAT_Y, SUPPORT_Z],
        SUPPORT_EULER,
        SUPPORT_ROWS,
        label="rocker-arm-support",
    )

    # Hold-down: four stock 1/4-20 hex-head screws install top-down through the
    # support foot's 5/16 clearance drills into the base's through UNC-2B seats.
    # The authored support pose seats its foot exactly on the base top at the
    # derived machine stations. IDENTITY keeps each screw head above the foot,
    # its shank along -Y, and its vendor-modeled washer face on the support;
    # there is no underside counterbore. The fixed seed's exact transform carries
    # physical coaxiality and head-seat position. One seed and one native
    # two-direction grid populate the other three holes; both spacings derive
    # from the same foot-pattern constants as the base hole grid.
    bx, bz = LAG_SCREW_XZ[0]
    screw_name = place_component(
        adapter,
        "fr-vn-lag-screw",
        [bx, LAG_SCREW_UNDER_HEAD_Y, bz],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label=f"lag-screw hold-down ({bx:.2f}, {bz:+.2f})",
    )
    pattern_instances = grid_component_pattern(
        adapter,
        [screw_name],
        axis1="x",
        spacing1_mm=LAG_SCREW_XZ[2][0] - LAG_SCREW_XZ[0][0],
        instances1=2,
        axis2="z",
        spacing2_mm=LAG_SCREW_XZ[0][1] - LAG_SCREW_XZ[1][1],
        instances2=2,
        direction1=PatternDirection.REVERSE,
        direction2=PatternDirection.REVERSE,
        label="lag-screw hold-down grid",
    )
    assert_pattern_targets(
        adapter,
        pattern_instances,
        [[x, LAG_SCREW_UNDER_HEAD_Y, z] for x, z in LAG_SCREW_XZ[1:]],
        IDENTITY,
        "lag-screw hold-down grid",
    )

    # Top-frame casting clamped around the four columns, at its insert plane.
    place_component(
        adapter,
        "fr-top-frame",
        [0.0, TOP_FRAME_MID_Y, 0.0],
        [0.0, 0.0, 0.0],
        IDENTITY,
        label="top-frame",
    )

    # Four intact stock caps, opening at CAP_MOUTH_Y and crown toward +Y.
    # Their internal shoulders seat on the square tube ends; the top-frame
    # counterbores provide radial skirt clearance only.
    for tag, cx, cz in (
        ("rear west", -COLUMN_X, REAR_COLUMN_Z),
        ("rear east", COLUMN_X, REAR_COLUMN_Z),
        ("front west", -COLUMN_X, FRONT_COLUMN_Z),
        ("front east", COLUMN_X, FRONT_COLUMN_Z),
    ):
        place_component(
            adapter,
            "fr-vn-tube-frame-cap",
            [cx, CAP_MOUTH_Y, cz],
            [0.0, 0.0, 0.0],
            IDENTITY,
            label=f"tube-frame-cap ({tag})",
        )

    # Maker's nameplate: flat on the WEST end of the black base deck, decorated
    # face up, centred front-back (see NAMEPLATE_POS / NAMEPLATE_ROWS).
    # Cosmetic + rigid -> fixed.
    place_component(
        adapter,
        "fr-nameplate",
        NAMEPLATE_POS,
        NAMEPLATE_EULER,
        NAMEPLATE_ROWS,
        label="nameplate",
    )

    # Nameplate corner screws: one #4-40 brass fillister per corner, under-head
    # plane flush on the decorated face, shank down into the base tap (see
    # NAMEPLATE_SCREW_* constants). Rigid fasteners -> fixed, like the
    # frame-side screws below.
    for nx, nz in NAMEPLATE_SCREW_STATIONS:
        tag = (
            f"{'rear' if nz > 0 else 'front'} "
            f"{'west' if nx > NAMEPLATE_POS[0] - NAMEPLATE_HEIGHT / 2.0 else 'east'}"
        )
        place_component(
            adapter,
            "sh-vn-brass-fillister-screw",
            [nx, NAMEPLATE_FRONT_Y, nz],
            NAMEPLATE_SCREW_EULER,
            NAMEPLATE_SCREW_ROWS,
            label=f"fillister-screw (nameplate {tag})",
        )

    # Eight stock cross screws: four at the lower base sockets and four at the
    # top-frame bosses. Each under-head plane seats on its Ø9 floor: a spotface
    # on the base, a flush counterbore on the top frame. Front
    # screws point +Z; rear screws point -Z, traversing both Ø5 tube walls and
    # reaching the far casting wall.
    for joint, screw_y, seat_z in (
        ("lower", BASE_SCREW_Y, BASE_SCREW_SEAT_Z),
        ("upper", TOP_SCREW_Y, TOP_SCREW_SEAT_Z),
    ):
        for tag, sx, sz, s_euler, s_rows in (
            ("front west", -COLUMN_X, -seat_z, [-90.0, 0.0, 0.0], ROT_X_NEG90),
            ("front east", COLUMN_X, -seat_z, [-90.0, 0.0, 0.0], ROT_X_NEG90),
            ("rear west", -COLUMN_X, seat_z, [90.0, 0.0, 0.0], ROT_X_POS90),
            ("rear east", COLUMN_X, seat_z, [90.0, 0.0, 0.0], ROT_X_POS90),
        ):
            place_component(
                adapter,
                "fr-vn-frame-cross-screw",
                [sx, screw_y, sz],
                s_euler,
                s_rows,
                label=f"frame-cross-screw ({joint} {tag})",
            )

    # Gooseneck set screw: 1/4-20 x 3/4 square head through the hub boss's tap
    # hole along +X at the hub centreline; tip 0.21 clear of the Ø12.70 tube
    # (see SET_SCREW_* constants). Fixed likewise.
    place_component(
        adapter,
        "fr-vn-gooseneck-set-screw",
        [SET_SCREW_UNDER_HEAD_X, TOP_SCREW_Y, GOOSENECK_HUB_Z],
        [0.0, 0.0, 90.0],
        rot_z_rows(90.0),
        label="gooseneck-set-screw (west hub)",
    )

    assert_components_fully_defined(adapter)
    check_no_interference(
        adapter,
        allowed_pairs=ALLOWED_PAIRS,
    )
    _author_top_axis_setting(adapter)
    # Title-block identity for the assembly drawing (draw_fr_frame_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # Both drawing configurations own the explode: the drawing's small
    # exploded view references Default Simplified.
    author_in_drawing_configurations(
        adapter, ASM_NAME, lambda configuration: _create_frame_explode(adapter, configuration)
    )
    return save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
