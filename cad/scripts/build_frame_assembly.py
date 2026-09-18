r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the stepped cast base, four polished tube
columns seated one inch into blind base sockets, the rocker-arm support, and
the top-frame casting. Eight stock 90280A837 cross screws enter from the
front/rear, clear both tube walls, and engage the far casting wall as well as
the near wall. The visible frame pose and evidence-locked top station remain
unchanged.

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28.7 cm
flange depth -- the 27.45 cm pad is set by the column stations, not the ch. 6
"28 cm" callout; see ``harmonic_base_spec.TOP_WIDTH``):

* harmonic-base fixed at the origin, deck at Y=50.8, with four 25.4-deep
  sockets.
* tube-frame x4 inserted at Y=25.4 near the top-plate corners at
  x +/-197, z +/-112, preserving the prior visible span.
* rocker-arm-support x1 (the windowed trapezoidal NORTH support,
  build_rocker_arm_support.py) at (X, Z) = (+72.9, 0), foot seated on the
  base top. A 177.8 x 177.8 cast plate, 63.5 thick (tapering to 16.94 at the
  apex), with the central rounded window; its apex carries the north pivot ball
  mount (channel.SLDASM, at machine z +116.915) and the rocker-pivot SHAFT runs
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
  mount (channel.SLDASM) is recentered to z +84.588, so its narrowed
  O13 footprint remains fully seated inside the wall's rear edge -- no cantilever.
  Seat Y = base-top 50.8 + 88.9 (half-height) = 139.7. The pivot x = 72.9, the
  rocker seesaw's mid-span (ch30 GT arm-end triangulation midpoint +72.5; the
  reclosed rod-pin hole 125.890 out reaches the cam centre at -52.990, rods plumb; the old
  "arbor 47.5 + 25.4 rod lever" chain died with the ch30 re-anchor).
  Inserted at its exact authored transform and locked to the fixed base.
* top-frame x1: the green one-piece casting at mid-plane Y = 1017.95 (side
  rails 34.2 wide / front-rear rails 38 wide x 36.5 tall, band
  y 999.7..1036.2; corner bosses Ø52.2 rise to 1040.7), bored around the
  four columns; its east rail (-X) carries the gooseneck hub and its west
  rail top face seats the fulcrum-keeper feet (channel.SLDASM).
* tube-frame-cap x4: intact stock McMaster 9275K141 push-on caps seated on the
  square tube ends, with their skirts sheltered by the top-frame recesses.
* frame-cross-screw x8 + gooseneck-set-screw x1: four lower and four upper
  casting-to-column retainers plus the top-frame hub fastener, each placed at
  its shared physical station and locked to the fixed base.
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic; constrained
  at its measured transform and locked to the fixed base (see
  nameplate_spec.MOUNT_POS).
* fillister-screw x4 (2026-09-02 ch26 p.71 re-derive): the brass slotted
  round-head screws at the plate's four corners, heads seated on the
  decorated face, shanks down through the plate's #4 clearance holes into the
  base's blind #4-40 taps (build_harmonic_base NAMEPLATE_SCREW_XZ -- the same
  nameplate_spec derivation). Same single-mate fix-all treatment.

Hold-down: four stock 1/4-20 UNC-2A hex-head screws install from the top,
through the support foot's 5/16 clearance drills, into blind 1/4-20 UNC-2B
seats in the base. The foot pattern transforms from local X +/-60.32,
Z +/-17.46 to machine x 55.44/90.36, z -60.32/+60.32 (the base's shared
SUPPORT_HOLD_DOWN_XZ contract). Each McMaster 92240A539 screw bears on the
bottom of its exact vendor-modeled 0.277813 mm under-head washer transition,
crosses the 6.35 mm foot, and engages 9.247187 mm = 1.456D in the base. The
screws are inserted at exact authored transforms and locked to the fixed base;
they do not constrain the support. Every rigid frame member uses this
same single-mate strategy; transform readback remains the fail-loud placement
tripwire. Final asserts: every component fixed or ``swFullyConstrained`` and no
uncontracted interference.

The 20-channel pitch stations live in the channel subassembly.

Dimensions: cad/DIMENSIONS.md ch. 6 (base/column), ch. 14 layout
(supports), "Channel & top-frame layout" (top frame); placements
photo-derived (med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_frame_assembly.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import _telemetry

from _common import (
    OUT_SLDPRT,
    _early_bound,
    apply_custom_properties,
    apply_summary_info,
    check,
    run_build,
)
from _drawing_marks import DRAWN_BY
from _assembly import (
    assembly_title_properties,
    assert_component_placed,
    assert_components_fully_defined,
    check_no_interference,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
)
from _assembly_patterns import (
    assert_pattern_targets,
    grid_component_pattern,
    ensure_global_pattern_axis,
    PatternDirection,
)
from _transforms import (
    ROT_X_NEG90,
    ROT_X_POS90,
    ROT_Y_POS90,
    rot_z_rows,
    rows_from_euler,
)
from build_harmonic_base import (
    BASE_CROSS_TAP_SPEC,
    HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_THREAD,
    HOLD_DOWN_THREAD_CLASS,
    NAMEPLATE_SCREW_HOLE_DEPTH,
    NAMEPLATE_SCREW_XZ,
)
from _interference_contracts import allowed_interference_pairs
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    FRAME_REAR_COLUMN_Z,
)
from build_fillister_screw import SHANK_LEN as NAMEPLATE_SCREW_SHANK_LEN
from nameplate_spec import (
    MOUNT_EULER as NAMEPLATE_EULER,
    MOUNT_FRONT_Y as NAMEPLATE_FRONT_Y,
    MOUNT_HOLE_XZ as NAMEPLATE_SCREW_STATIONS,
    MOUNT_POS as NAMEPLATE_POS,
    MOUNT_ROWS as NAMEPLATE_ROWS,
    PLATE_THICKNESS as NAMEPLATE_THICKNESS,
)
from rocker_arm_support_spec import (
    SUPPORT_HOLD_DOWN_XZ,
    SUPPORT_WORLD_SEAT_Y,
    SUPPORT_WORLD_X,
    SUPPORT_WORLD_Z,
)
from build_gooseneck_set_screw import SHANK_LEN as GOOSENECK_SHANK_LEN
from frame_cross_screw_spec import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    SHANK_DIA as CROSS_SCREW_SHANK_DIA,
    SHANK_LEN as CROSS_SCREW_SHANK_LEN,
    THREAD as CROSS_SCREW_THREAD,
    THREAD_CLASS as CROSS_SCREW_THREAD_CLASS,
)
from build_lag_screw import (
    BEARING_OFFSET as LAG_BEARING_OFFSET,
    HEAD_AF as LAG_HEAD_AF,
    SHANK_DIA as LAG_SHANK_DIA,
    SHANK_LEN as LAG_SHANK_LEN,
    THREAD_CLASS as LAG_THREAD_CLASS,
    THREAD_LEN as LAG_THREAD_LEN,
    THREAD_SIZE as LAG_THREAD_SIZE,
)
from build_rocker_arm_support import (
    FOOT_THICKNESS as LAG_FOOT_THICKNESS,
    HOLE_DIA as LAG_SUPPORT_CLEARANCE_DIA,
)

from build_top_frame import SIDE_TAP_SPEC as TOP_CROSS_TAP_SPEC
from frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    CAP_MOUTH_Y,
    CAP_TOP_Y,
    CASTING_FULL_THREAD_DEPTH,
    COLUMN_BOTTOM_Y,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from harmonic_base_spec import STACK_HEIGHT
from tube_frame_cap_spec import (
    INSIDE_HEIGHT as CAP_INSIDE_HEIGHT,
    TOTAL_HEIGHT as CAP_TOTAL_HEIGHT,
)
from tube_frame_spec import COLUMN_LENGTH, OUTER_DIA as COLUMN_OUTER_DIA

ASM_NAME = "frame"
FRAME_EXPLODED = "FRAME_EXPLODED"

BASE_TOP_Y = STACK_HEIGHT
COLUMN_X = 197.0
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

# Rocker-support hold-down: four stock 1/4-20 x 5/8 hex-head screws,
# coaxial with the support clearance drills and blind base taps via authored
# transforms; one seed lock mate and a native grid retain that placement.
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

TOP_FRAME_MID_Y = TOP_SCREW_Y

# --- Frame cross-screw stack -------------------------------------------------
# The stock screw origin is its under-head seat and its shank runs along local
# -Y. Front placements rotate it toward +Z; rear placements toward -Z. Each
# 44.45-mm shank crosses the near casting, both Ø5 tube walls, and at least one
# major diameter of far casting while retaining 1.55 mm of full thread beyond
# the tip in the 46-mm interrupted tap.
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
    raise AssertionError("stock cross-screw head cannot bear on the spot seat")
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
# gooseneck-set-screw: 1x 1/4-20 UNC square-head set screw gripping the
# gooseneck post through the casting's east-hub tapped rib hole, axis along X
# at (y TOP_FRAME_MID_Y, z 3.088 -- the hub/post centreline). Entered from the
# east outer face x -214.1: local +Y -> -X (rot_z_rows(90), euler [0,0,90])
# points the exact stock shank inboard while retaining its cup tip at x -205.15,
# 0.15 clear (outboard) of the Ø16 post surface at x -205.
GOOSENECK_HUB_Z = 3.088  # gooseneck bore centreline (unchanged position)
SET_SCREW_TIP_X = -205.15  # 0.15 clear (outboard) of the Ø16 post surface -205
SET_SCREW_UNDER_HEAD_X = SET_SCREW_TIP_X - GOOSENECK_SHANK_LEN

# Maker's nameplate (book ch. 26, pp. 70-71): the 100 x 55 brass plate lies FLAT
# on the base top, decorated side up, on the EAST (+X) face. The mount
# transform (NAMEPLATE_POS / _EULER / _ROWS, formerly authored here) now lives
# in nameplate_spec -- the pure-data contract build_harmonic_base reads to
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
        f"nameplate_spec.MOUNT_ROWS {NAMEPLATE_ROWS} != rows_from_euler({NAMEPLATE_EULER})"
    )
#
# nameplate screws (2026-09-02 ch26 p.71 re-derive): 4x #4-40 brass
# fillister-screw, one per plate corner, screwed DOWN into the base's blind
# #4-40 taps (build_harmonic_base NAMEPLATE_SCREW_XZ -- the plate's own
# corner holes carried through the mount transform: x 209.75/163.75,
# z +/-45.5). The part is authored axis along local +Z with the origin at the
# UNDER-HEAD bearing plane, head at -Z. The stock wrapper preserves that frame,
# so the placement point is the under-head seat on the plate's decorated face
# (y NAMEPLATE_FRONT_Y 52.3) and ROT_X_POS90 (euler [90,0,0]) turns local +Z
# -> -Y. The stock 6.35 shank passes through the 1.5 plate with 4.85 engaged
# in the existing 6.0 thread; the 2.7178 head sits above the deck rim.
# The under-head plane seats FLUSH on the plate face, exactly as the
# paper-drive seats the same screw on its clips. The stock external thread
# engages the matching #4-40 base seat rather than using a tap-drill-sized
# simplified shank.
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
if NAMEPLATE_SCREW_HOLE_DEPTH < NAMEPLATE_SCREW_SHANK_LEN - NAMEPLATE_THICKNESS + 0.5:
    raise AssertionError(
        f"base nameplate tap thread depth {NAMEPLATE_SCREW_HOLE_DEPTH} bottoms the "
        f"{NAMEPLATE_SCREW_SHANK_LEN} shank (needs "
        f"{NAMEPLATE_SCREW_SHANK_LEN - NAMEPLATE_THICKNESS + 0.5})"
    )

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(
            f"missing part {path}; run build_{name.replace('-', '_')}.py first"
        )
    return str(path)


def _explode_transform(component: Any) -> tuple[float, ...]:
    transform = _early_bound(component.GetTotalTransform(True), "IMathTransform")
    if transform is None:
        raise RuntimeError(f"{component.Name2}: missing total presentation transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16 or not all(math.isfinite(value) for value in values):
        raise RuntimeError(f"{component.Name2}: invalid presentation transform {values!r}")
    return values


@_telemetry.traced("assembly.frame_explode")
def _create_frame_explode(adapter: Any) -> None:
    """Author twelve global translations; leave the operational model collapsed."""
    from solidworks_mcp.adapters.com_variant import null_callout

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    assembly = _early_bound(model, "IAssemblyDoc")
    manager = _early_bound(model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != "Default":
        raise RuntimeError("FRAME_EXPLODED requires the builder's Default configuration")
    if int(assembly.GetExplodedViewCount2("Default")):
        raise RuntimeError("new frame assembly unexpectedly contains exploded views")

    quantities = {
        "harmonic-base": 1, "tube-frame": 4, "tube-frame-cap": 4,
        "top-frame": 1, "rocker-arm-support": 1, "lag-screw": 4,
        "nameplate": 1, "fillister-screw": 4, "frame-cross-screw": 8,
        "gooseneck-set-screw": 1,
    }
    components = tuple(
        _early_bound(component, "IComponent2")
        for component in (assembly.GetComponents(True) or ())
    )
    groups: dict[str, list[Any]] = {stem: [] for stem in quantities}
    for component in components:
        stem = Path(str(component.GetPathName() or "")).stem.casefold()
        if stem not in groups:
            raise RuntimeError(f"FRAME_EXPLODED: unexpected component {component.Name2}: {stem}")
        groups[stem].append(component)
    actual_counts = {stem: len(group) for stem, group in groups.items()}
    if actual_counts != quantities:
        raise RuntimeError(f"FRAME_EXPLODED component counts: {actual_counts!r} != {quantities!r}")
    for group in groups.values():
        group.sort(key=lambda component: str(component.Name2))
    baseline = {str(component.Name2): _explode_transform(component) for component in components}
    if len(baseline) != sum(quantities.values()):
        raise RuntimeError("FRAME_EXPLODED: duplicate component identities")
    expected = {name: [0.0, 0.0, 0.0] for name in baseline}
    front, rear, upper, lower = [], [], [], []
    for component in groups["frame-cross-screw"]:
        _, y, z = baseline[str(component.Name2)][9:12]
        if abs(y * 1000.0 - TOP_SCREW_Y) <= 1e-3:
            upper.append(component)
        elif abs(y * 1000.0 - BASE_SCREW_Y) <= 1e-3:
            lower.append(component)
        else:
            raise RuntimeError(f"{component.Name2}: unexpected cross-screw Y {y * 1000.0:g} mm")
        if z == 0.0:
            raise RuntimeError(f"{component.Name2}: cross screw on assembly mid-plane")
        (front if z < 0.0 else rear).append(component)
    if tuple(map(len, (front, rear, upper, lower))) != (4, 4, 4, 4):
        raise RuntimeError("FRAME_EXPLODED: cross-screw station split is not 4/4/4/4")
    plans = (
        ("tube caps lift", groups["tube-frame-cap"], "y", 0.250),
        ("top frame clears columns", [*groups["top-frame"], *upper, *groups["gooseneck-set-screw"]], "y", 0.150),
        ("front cross screws withdraw", front, "z", -0.050),
        ("rear cross screws withdraw", rear, "z", 0.050),
        ("gooseneck screw withdraws", groups["gooseneck-set-screw"], "x", -0.050),
        ("columns clear base seats", groups["tube-frame"], "y", 0.060),
        ("support lifts from deck", [*groups["rocker-arm-support"], *groups["lag-screw"]], "y", 0.035),
        ("support moves beside base", [*groups["rocker-arm-support"], *groups["lag-screw"]], "x", -0.320),
        ("support screws withdraw", groups["lag-screw"], "y", 0.050),
        ("nameplate lifts from deck", [*groups["nameplate"], *groups["fillister-screw"]], "y", 0.025),
        ("nameplate moves beside base", [*groups["nameplate"], *groups["fillister-screw"]], "x", 0.080),
        ("nameplate screws withdraw", groups["fillister-screw"], "y", 0.035),
    )
    # Reuse the native assembly axes already used by component patterns. Unlike
    # manipulator indices, Mark=2 direction entities are independent of each
    # selected component's local frame. Verify their geometry and signed sense.
    axes = {}
    for index, key in enumerate("xyz"):
        axis_name = ensure_global_pattern_axis(adapter, key)
        feature = _early_bound(assembly.FeatureByName(axis_name), "IFeature")
        if feature is None or str(feature.GetTypeName2()) != "RefAxis":
            raise RuntimeError(f"FRAME_EXPLODED: missing reference axis {axis_name}")
        axis = _early_bound(feature.GetSpecificFeature2(), "IRefAxis")
        points = tuple(float(value) for value in axis.GetRefAxisParams())
        if len(points) != 6 or not all(math.isfinite(value) for value in points):
            raise RuntimeError(f"{axis_name}: invalid axis endpoints {points!r}")
        vector = tuple(points[i + 3] - points[i] for i in range(3))
        length = math.sqrt(sum(value * value for value in vector))
        if length <= 1e-12 or any(
            abs(vector[i] / length) > 1e-9 for i in range(3) if i != index
        ):
            raise RuntimeError(f"{axis_name}: not aligned with world {key.upper()}: {vector!r}")
        axes[key] = (axis_name, vector[index] > 0.0)

    if not assembly.CreateExplodedView():
        raise RuntimeError("FRAME_EXPLODED: CreateExplodedView failed")
    names = tuple(assembly.GetExplodedViewNames2("Default") or ())
    if len(names) != 1:
        raise RuntimeError(f"FRAME_EXPLODED: unexpected created views {names!r}")
    # Exploded views are configuration-tree AsmExploder features, not ordinary
    # assembly features discoverable through FeatureByName.
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        str(names[0]), "EXPLODEDVIEWS", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"FRAME_EXPLODED: cannot select created exploded view {names[0]!r}")
    selection = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectType3(1, 0)) != 43:  # swSelEXPLVIEWS
        raise RuntimeError("FRAME_EXPLODED: selection is not an exploded-view feature")
    feature = _early_bound(selection.GetSelectedObject6(1, 0), "IFeature")
    if feature is None or str(feature.GetTypeName2()) != "AsmExploder":
        raise RuntimeError("FRAME_EXPLODED: selected object is not an AsmExploder")
    feature.Name = FRAME_EXPLODED
    model.ClearSelection2(True)
    if not model.EditRebuild3() or tuple(assembly.GetExplodedViewNames2("Default") or ()) != (FRAME_EXPLODED,):
        raise RuntimeError("FRAME_EXPLODED: exploded-view feature rename did not persist")
    if not assembly.ShowExploded2(True, FRAME_EXPLODED):
        raise RuntimeError("FRAME_EXPLODED: cannot activate authored view")
    try:
        for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
            seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
            if seed is None or not configuration.DeleteExplodeStep(str(seed.Name)):
                raise RuntimeError(f"FRAME_EXPLODED: cannot remove auto step {index}")
        if int(configuration.GetNumberOfExplodeSteps()) != 0:
            raise RuntimeError("FRAME_EXPLODED: auto steps remain")
        for step_index, (label, moved, key, distance) in enumerate(plans, 1):
            with _telemetry.span("assembly.frame_explode.step", label=label):
                model.ClearSelection2(True)
                selection = _early_bound(model.SelectionManager, "ISelectionMgr")
                data = _early_bound(selection.CreateSelectData(), "ISelectData")
                if data is None:
                    raise RuntimeError(f"{label}: cannot create component selection data")
                data.Mark = 1
                for component in moved:
                    if not component.Select4(True, data, False):
                        raise RuntimeError(f"{label}: cannot select {component.Name2}")
                axis_name, positive = axes[key]
                if not model.Extension.SelectByID2(
                    axis_name, "AXIS", 0.0, 0.0, 0.0, True, 2, null_callout(), 0
                ):
                    raise RuntimeError(f"{label}: cannot select global direction {axis_name} with mark 2")
                # Explicit entity only; -1 omits the component-local manipulator.
                # Early-bound wrapper returns (IExplodeStep, error); omit [out].
                result = configuration.AddExplodeStep2(
                    abs(distance), -1, (distance > 0.0) != positive,
                    0.0, -1, False, True, False,
                )
                model.ClearSelection2(True)
                if not isinstance(result, tuple) or len(result) != 2:
                    raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
                raw_step, error = result
                if int(error) != 0 or raw_step is None:
                    raise RuntimeError(f"{label}: AddExplodeStep2 error {error!r}")
                step = _early_bound(raw_step, "IExplodeStep")
                step.Name = f"FRAME {label.upper()}"
                if str(step.Name) != f"FRAME {label.upper()}" or not model.EditRebuild3():
                    raise RuntimeError(f"{label}: step name/rebuild failed")
                if int(configuration.GetNumberOfExplodeSteps()) != step_index:
                    raise RuntimeError(f"{label}: authored step count is not {step_index}")
                actual = {
                    str(_early_bound(component, "IComponent2").Name2)
                    for component in (step.GetComponents() or ())
                }
                intended = {str(component.Name2) for component in moved}
                if actual != intended or abs(float(step.ExplodeDistance) - abs(distance)) > 1e-9:
                    raise RuntimeError(f"{label}: step component/distance readback mismatch: {actual!r}")
                for name in intended:
                    expected[name]["xyz".index(key)] += distance
                # Read every instance, including unmoved ones: mixed local frames
                # and native pattern followers must never silently change intent.
                for component in components:
                    name = str(component.Name2)
                    current = _explode_transform(component)
                    delta = tuple(current[i + 9] - baseline[name][i + 9] for i in range(3))
                    _telemetry.event(
                        "assembly.frame_explode.translation", step=label, component=name,
                        expected_mm=[value * 1000.0 for value in expected[name]],
                        actual_mm=[value * 1000.0 for value in delta],
                    )
                    if any(abs(delta[i] - expected[name][i]) > 1e-7 for i in range(3)):
                        raise RuntimeError(
                            f"{label}: {name} world translation mm "
                            f"{tuple(value * 1000.0 for value in delta)!r} != "
                            f"{tuple(value * 1000.0 for value in expected[name])!r}; "
                            f"direction={axis_name}, signed distance={distance * 1000.0:g} mm"
                        )
                    if any(abs(current[i] - baseline[name][i]) > 1e-9 for i in (*range(9), 12)):
                        raise RuntimeError(f"{label}: {name} presentation rotated or scaled")
    finally:
        primary_error = sys.exception()
        try:
            model.ClearSelection2(True)
            if not assembly.ShowExploded2(False, FRAME_EXPLODED) or not model.EditRebuild3():
                raise RuntimeError("FRAME_EXPLODED: failed to restore collapsed operational assembly")
            for component in components:
                name = str(component.Name2)
                current = _explode_transform(component)
                transform = _early_bound(component.Transform2, "IMathTransform")
                operational = tuple(float(value) for value in transform.ArrayData)
                if len(operational) != 16 or any(
                    abs(values[i] - baseline[name][i]) > 1e-9
                    for values in (current, operational) for i in range(16)
                ):
                    raise RuntimeError(f"FRAME_EXPLODED: collapse changed operational transform of {name}")
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"FRAME_EXPLODED: cleanup after authoring failure: {cleanup_error}")
    if int(configuration.GetNumberOfExplodeSteps()) != len(plans):
        raise RuntimeError("FRAME_EXPLODED: collapsed presentation lost authored steps")
    if tuple(assembly.GetExplodedViewNames2("Default") or ()) != (FRAME_EXPLODED,):
        raise RuntimeError("FRAME_EXPLODED: collapsed presentation lost named view")
    if str(assembly.GetExplodedViewConfigurationName(FRAME_EXPLODED)) != "Default":
        raise RuntimeError("FRAME_EXPLODED: named presentation is not owned by Default")
    _telemetry.success("FRAME_EXPLODED: 12 native steps verified in world space; all 29 instances restored")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    _part("rocker-arm-support")  # placed via place_component below; assert it exists
    _part("lag-screw")  # support hold-down; placed via place_component below
    _part("frame-cross-screw")  # eight casting/column retainers
    _part("gooseneck-set-screw")  # west-hub set screw; placed via place_component
    _part("fillister-screw")  # nameplate corner screws; placed via place_component
    _part("tube-frame-cap")  # four intact stock push-on caps
    top_frame_path = _part("top-frame")

    check("create_assembly", await adapter.create_assembly())

    # Base: first insert is auto-fixed by SolidWorks.
    res = await adapter.insert_component(InsertComponentParameters(file_path=base_path))
    check("insert_component harmonic-base (auto-fixed)", res)
    base_name = res.data["name"]
    if not res.data.get("fixed"):
        raise RuntimeError("base component was not auto-fixed")

    # Columns seat 25.4 into the four base sockets. Lowering the authored
    # origin from the deck to COLUMN_BOTTOM_Y preserves the previous exposed
    # span and every upper attachment station.
    column_target = [COLUMN_X, COLUMN_BOTTOM_Y, REAR_COLUMN_Z]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=column_path, position=column_target)
    )
    check(f"insert_component tube-frame @ {column_target}", res)
    column_name = res.data["name"]
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{column_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label=f"column {column_name} fixed to base",
    )
    assert_component_placed(adapter, column_name, column_target, IDENTITY)
    column_instances = await grid_component_pattern(
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
    # (build_rocker_arm_support.py), the faithful reproduction of the original
    # hand-built casting that REPLACES the unified rocker-arm-portal. Turned
    # +90deg about Y (SUPPORT_ROWS) so its big windowed faces point along
    # machine +/-X (face-on in the ch. 30 p008 side view), with local X (177.8
    # width) -> machine Z and the foot on the base top. Its origin is the casting
    # centre.
    #
    # Inserted on-solution (a single machine-handed casting) and locked to the
    # fixed base. Its authored transform places the physical foot on the base top.
    support_target = [SUPPORT_X, SUPPORT_SEAT_Y, SUPPORT_Z]
    support_name = await place_component(
        adapter,
        "rocker-arm-support",
        support_target,
        SUPPORT_EULER,
        SUPPORT_ROWS,
        ground=False,
        label="rocker-arm-support",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{support_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="rocker-arm-support fixed to base",
    )
    assert_component_placed(adapter, support_name, support_target, SUPPORT_ROWS)

    # Hold-down: four stock 1/4-20 hex-head screws install top-down through the
    # support foot's 5/16 clearance drills into the base's blind UNC-2B seats.
    # The authored support pose seats its foot exactly on the base top at the
    # derived machine stations. IDENTITY keeps each screw head above the foot,
    # its shank along -Y, and its vendor-modeled washer face on the support;
    # there is no underside counterbore. Each ungrounded seed uses one lock mate
    # to the fixed base; its exact transform carries physical coaxiality and head-seat
    # position, and the readback assertion proves the mate did not move it. One
    # real-mated seed and one native two-direction grid populate the other three
    # holes; both spacings derive from the same foot-pattern constants as the
    # base hole grid.
    bx, bz = LAG_SCREW_XZ[0]
    screw_target = [bx, LAG_SCREW_UNDER_HEAD_Y, bz]
    screw_name = await place_component(
        adapter,
        "lag-screw",
        screw_target,
        [0.0, 0.0, 0.0],
        IDENTITY,
        ground=False,
        label=f"lag-screw hold-down ({bx:.2f}, {bz:+.2f})",
    )
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{screw_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="lag-screw seed fixed to base",
    )
    assert_component_placed(adapter, screw_name, screw_target, IDENTITY)
    pattern_instances = await grid_component_pattern(
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

    # Top-frame casting clamped around the four columns, mid-plane y 1017.95.
    target = [0.0, TOP_FRAME_MID_Y, 0.0]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=top_frame_path, position=target)
    )
    check(f"insert_component top-frame @ {target}", res)
    name = res.data["name"]
    await lock_mate(
        adapter,
        named_ref(f"Right Plane@{name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="top-frame fixed to base",
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Four intact stock caps, opening at CAP_MOUTH_Y and crown toward +Y.
    # Their internal shoulders seat on the square tube ends; the top-frame
    # counterbores provide radial skirt clearance only.
    for tag, cx, cz in (
        ("rear west", -COLUMN_X, REAR_COLUMN_Z),
        ("rear east", COLUMN_X, REAR_COLUMN_Z),
        ("front west", -COLUMN_X, FRONT_COLUMN_Z),
        ("front east", COLUMN_X, FRONT_COLUMN_Z),
    ):
        cap_target = [cx, CAP_MOUTH_Y, cz]
        cap_name = await place_component(
            adapter,
            "tube-frame-cap",
            cap_target,
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,
            label=f"tube-frame-cap ({tag})",
        )
        await lock_mate(
            adapter,
            named_ref(f"Right Plane@{cap_name}", "PLANE"),
            named_ref(f"Right Plane@{base_name}", "PLANE"),
            label=f"tube-frame-cap ({tag}) fixed to base",
        )
        assert_component_placed(adapter, cap_name, cap_target, IDENTITY)

    # Maker's nameplate: laid flat on the base top, decorated face up, on the
    # EAST face, centred front-back between the two east columns (see
    # NAMEPLATE_POS / NAMEPLATE_ROWS). Cosmetic + rigid -> locked to the base.
    nameplate_name = await place_component(
        adapter,
        "nameplate",
        NAMEPLATE_POS,
        NAMEPLATE_EULER,
        NAMEPLATE_ROWS,
        ground=False,
        label="nameplate",
    )
    await lock_mate(
        adapter,
        named_ref(f"Top Plane@{nameplate_name}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="nameplate fixed to base",
    )
    assert_component_placed(adapter, nameplate_name, NAMEPLATE_POS, NAMEPLATE_ROWS)

    # Nameplate corner screws: one #4-40 brass fillister per corner, under-head
    # plane flush on the decorated face, shank down into the base tap (see
    # NAMEPLATE_SCREW_* constants). Rigid fasteners -> the same single-mate
    # fix-all treatment as the frame-side screws below.
    for nx, nz in NAMEPLATE_SCREW_STATIONS:
        tag = f"{'rear' if nz > 0 else 'front'} {'east' if nx > 200.0 else 'west'}"
        np_target = [nx, NAMEPLATE_FRONT_Y, nz]
        np_screw = await place_component(
            adapter,
            "fillister-screw",
            np_target,
            NAMEPLATE_SCREW_EULER,
            NAMEPLATE_SCREW_ROWS,
            ground=False,
            label=f"fillister-screw (nameplate {tag})",
        )
        await lock_mate(
            adapter,
            named_ref(f"Right Plane@{np_screw}", "PLANE"),
            named_ref(f"Right Plane@{base_name}", "PLANE"),
            label=f"fillister-screw (nameplate {tag}) fixed to base",
        )
        assert_component_placed(adapter, np_screw, np_target, NAMEPLATE_SCREW_ROWS)

    # Eight stock cross screws: four at the lower base sockets and four at the
    # top-frame bosses. Every under-head plane seats on its Ø9 spotface. Front
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
            cross_target = [sx, screw_y, sz]
            cross_screw = await place_component(
                adapter,
                "frame-cross-screw",
                cross_target,
                s_euler,
                s_rows,
                ground=False,
                label=f"frame-cross-screw ({joint} {tag})",
            )
            await lock_mate(
                adapter,
                named_ref(f"Right Plane@{cross_screw}", "PLANE"),
                named_ref(f"Right Plane@{base_name}", "PLANE"),
                label=f"frame-cross-screw ({joint} {tag}) fixed to base",
            )
            assert_component_placed(adapter, cross_screw, cross_target, s_rows)

    # Gooseneck set screw: 1/4-20 square head through the west-hub tapped rib
    # hole along +X at the hub centreline; tip 0.15 clear of the Ø16 post
    # (see SET_SCREW_* constants). Same fix-all treatment.
    set_target = [SET_SCREW_UNDER_HEAD_X, TOP_FRAME_MID_Y, GOOSENECK_HUB_Z]
    set_rows = rot_z_rows(90.0)
    set_screw = await place_component(
        adapter,
        "gooseneck-set-screw",
        set_target,
        [0.0, 0.0, 90.0],
        set_rows,
        ground=False,
        label="gooseneck-set-screw (west hub)",
    )
    await lock_mate(
        adapter,
        named_ref(f"Front Plane@{set_screw}", "PLANE"),
        named_ref(f"Right Plane@{base_name}", "PLANE"),
        label="gooseneck-set-screw fixed to base",
    )
    assert_component_placed(adapter, set_screw, set_target, set_rows)

    assert_components_fully_defined(adapter)
    check_no_interference(
        adapter,
        allowed_pairs=allowed_interference_pairs(ASM_NAME),
    )
    # Title-block identity for the assembly drawing (draw_frame_assembly.py):
    # assembly_title_properties supplies the Title/Generator and TOL_* cells
    # finalize_drawing requires without consulting the part registry;
    # released component drawing (the BOM has no material/finish columns).
    apply_custom_properties(
        adapter,
        {
            **assembly_title_properties(ASM_NAME),
            # MHA-A## = assembly-drawing ids, beside the parts' MHA-### range
            # (a longer number overflows the DWG. NO. title-block cell).
            "Number": "MHA-A04",
            "Revision Description": "Initial release",
            "Material": "SEE COMPONENT DRAWINGS",
            "Material Specification": "SEE COMPONENT DRAWINGS",
            "Finish": "SEE COMPONENT DRAWINGS",
            "Quantity": "1",
            "Drawn By": DRAWN_BY,
        },
    )
    # The PART cell resolves the document summary Title; "frame assembly" (not
    # the bare stem) so the sheet identifies itself as an assembly drawing.
    apply_summary_info(adapter, title=f"{ASM_NAME} assembly")
    _create_frame_explode(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
