r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the two-plate cast base, four smooth
polished columns at the corners, the rocker-arm-support that carries the
rocker-pivot shaft, and the top-frame ring capping the columns
-- column tops flush with the ring's top face at 1040.7 (M6.8 8-view pass:
no stub above).

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28 cm
depth):

* harmonic-base fixed at the origin, top face at Y = 50.8.
* tube-frame x4 standing on the base top face near the top-plate corners,
  centres at (+/-197, +/-112) — 25.25/21.35 mm inset from the top-plate
  edges (eight views: columns sit at the extreme corners).
* rocker-arm-support x1 (the windowed trapezoidal NORTH support,
  build_rocker_arm_support.py) at (X, Z) = (+72.9, +44.45), foot seated on the
  base top. A 177.8 x 177.8 cast plate, 63.5 thick (tapering to 16.94 at the
  apex), with the central rounded window; its apex carries the north pivot ball
  mount (channel.SLDASM, at machine z +81.5) and the rocker-pivot SHAFT runs
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
  Z -88.9..88.9 -- centred on the base z-axis (origin z 0): the window reads
  centred in the +/-X side views. The north pivot ball mount (channel.SLDASM)
  now seats FULLY on the support: it was moved south to z +81.5 and its ball/base
  narrowed to O13 so its z-footprint [75.0, 88.0] clears the channel-19 amplitude
  bar (z +74.1) and stays inside the wall's north edge (88.9) -- no cantilever.
  Seat Y = base-top 50.8 + 88.9 (half-height) = 139.7. The pivot x = 72.9, the
  rocker seesaw's mid-span (ch30 GT arm-end triangulation midpoint +72.5; the
  rod-pin hole 127.37 out reaches the cam drum at -54.7, rods plumb; the old
  "arbor 47.5 + 25.4 rod lever" chain died with the ch30 re-anchor).
  Inserted at its exact authored transform and locked to the fixed base.
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic; constrained
  at its measured transform and locked to the fixed base (see NAMEPLATE_POS).

Hold-down: four 9/16-12 lag screws come up through the base into the support
foot's tapped holes. The base was re-drilled to the foot's pattern (4 holes at
local X +/-60.32, Z +/-17.46 -> machine x 55.44/90.36, z +/-60.32; see
build_harmonic_base.py HOLE_XZ) with O23 head counterbores on its underside, and
the lag screws (build_lag_screw.py, resized to the 9/16-12 foot tap) are
inserted at their exact authored transforms and locked to the fixed base. The
screws do NOT constrain the support. Every rigid frame member uses this same
single-mate strategy; transform readback remains the fail-loud placement
tripwire. Final asserts: every component fixed or ``swFullyConstrained``, and
zero interferences.

The 20-channel pitch stations live in the channel subassembly.

Dimensions: cad/DIMENSIONS.md ch. 6 (base/column), ch. 14 layout
(supports), "Channel & top-frame layout" (top frame); placements
photo-derived (med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_frame_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    OUT_SLDPRT,
    check,
    log,
    run_build,
)
from _assembly import (
    assert_component_placed,
    assert_components_fully_defined,
    assert_pattern_targets,
    check_no_interference,
    component_names,
    component_transform,
    delete_assembly_feature,
    linear_component_pattern,
    lock_mate,
    named_ref,
    PatternDirection,
    place_component,
    save_assembly_and_images,
)
from _transforms import ROT_Y_POS90
from solidworks_mcp.adapters.base import (
    ComponentLinearPatternParameters,
    CreateAxisParameters,
)

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
COLUMN_Z = 112.0
SUPPORT_X = 72.9  # rocker pivot x: the seesaw mid-span (ch30 GT arm-end
# triangulation midpoint +72.5; M6.8 mirror). Rod-side tip reaches the drum.
# The support's z position is NOT a constant: it is CENTRED on the base z-axis by
# a coincident mate of symmetry planes (see build()), so the window reads centred
# in the +/-X side views with no tuned offset. The north pivot ball mount
# (channel.SLDASM pivot-ball-mount) now seats fully on the wall: it was moved to
# z +81.5 and narrowed to O13 so its z-footprint [75.0, 88.0] clears the channel-
# 19 amplitude-bar (z +74.1) and stays inside the wall's north edge (88.9).
SUPPORT_SEAT_Y = BASE_TOP_Y + 88.9  # 139.7: rocker-arm-support's origin is
# at the casting centre (bbox Y +/-88.9), so seating its foot on the base top
# lifts the origin by the 88.9 foot half-height.
# Turn the support +90deg about Y so its big windowed faces (local Z normal)
# point along machine +/-X (face-on in the ch. 30 p008 +X side view), matching
# the portal it replaces; local X (177.8 width) maps to machine Z.
SUPPORT_EULER = [0.0, 90.0, 0.0]
SUPPORT_ROWS = ROT_Y_POS90

# Rocker-support hold-down: four 9/16-12 lag screws (build_lag_screw.py)
# constrained coaxial with the base clearance holes (and the support foot's tapped
# holes above them) by concentric + seat mates -- see build(). The
# stations are the foot's tapped pattern in the machine frame: local X +/-60.32,
# Z +/-17.46 turned +90deg about Y -> machine x 72.9 -/+ 17.46 = 55.44/90.36,
# z +/-60.32 (these ARE the base HOLE_XZ machine positions). The screw is authored
# head-down at IDENTITY, so the placement point is the station and y is the under-
# head plane: machine y 6.5 (the base underside counterbore depth) sets the O22
# head recessed in the base underside, the O12 shank rising through the base into
# the O12.30 tapped foot hole. Placed on its exact machine transform (like the
# support); constrained by concentric + seat + spin-pin mates (see build()).
LAG_SCREW_XZ = ((55.44, 60.32), (55.44, -60.32), (90.36, 60.32), (90.36, -60.32))
LAG_SCREW_UNDER_HEAD_Y = 6.5

TOP_FRAME_MID_Y = 1020.2  # ring mid-plane: rails y 999.7..1040.7 (M6.3)

# Maker's nameplate (book ch. 26, pp. 70-71): the 100 x 55 brass plate lies FLAT
# on the base top, decorated side up, on the EAST (+X) face -- read off the in-situ
# photos (photogrammetry 195527397 / 195530756 / 195532820: the plate sits on the
# base top, centred between the two columns of one face, read by an operator
# standing at that face) and the ch. 30 eight views.
#
# The part's decorated face is its FRONT face (+Z local; build_nameplate extrudes
# the body in -Z so the engraving is frontmost and reads with no mirror).
# NAMEPLATE_ROWS (euler [-90,90,0]) lays it flat on the EAST face: local +Z
# (decorated front) -> +Y so the engraving faces up; local +Y (text height) -> -X
# so the text top faces the machine interior and reads upright to an east operator;
# local +X (text length, 100) -> -Z so the line runs front-back; the 1.5 body
# (local -Z) drops onto the base top. The placed point is the part origin CORNER
# (decorated face, x=0/y=0): Y 52.3 lays the decorated face on top with the 1.5
# body resting on the base top (50.8); Z 50 centres the 100 mm line at z 0 between
# the east columns (z +/-112); X 214.25 sets the plate's east edge ~8 mm in from
# the top-plate east edge (x 222.25), span x 159.25..214.25 -- east of the
# rocker-arm-support (x 28..117) and clear of the east columns (which sit at
# z +/-112, away from the plate's z -50..50), so it grounds 0-DOF, no interference.
NAMEPLATE_POS = [214.25, 52.3, 50.0]
NAMEPLATE_EULER = [-90.0, 90.0, 0.0]
NAMEPLATE_ROWS = [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]

IDENTITY = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _part(name: str) -> str:
    path = (OUT_SLDPRT / f"{name}.SLDPRT").resolve()
    if not path.exists():
        raise RuntimeError(f"missing part {path}; run build_{name.replace('-', '_')}.py first")
    return str(path)


def _instance_at(adapter, prefix: str, target: list[float]) -> str:
    """Name of the ``prefix`` instance whose origin sits at ``target`` (mm)."""
    for n in component_names(adapter):
        if n.rsplit("-", 1)[0] != prefix:
            continue
        a = component_transform(adapter, n)
        if all(abs(a[9 + k] * 1000.0 - target[k]) < 0.05 for k in range(3)):
            return n
    raise RuntimeError(f"no {prefix} instance at {target}")


async def _pattern_pair(
    adapter, seeds: list[str], axis_name: str, spacing: float,
    prefix: str, targets: list[list[float]],
) -> None:
    """Replicate the real-mated ``seeds`` ONCE along ``axis_name`` by a local
    linear component pattern and verify each copy landed on its expected
    machine position (the channel ``_pattern_bank`` idiom): the axis fixes
    only the LINE, SolidWorks infers the sign, and the inference is not
    contractual -- a flipped pattern is deleted whole and re-created with
    ``FlipDir1``, deterministic in at most two solves.

    Flip seed TRUE: both frame patterns measured FLIPPED on their first solve
    (Top ∩ Right resolves +Z, the copies go -Z; Top ∩ Front resolves -X, the
    copies go +X), so ``FlipDir1=True`` lands in ONE solve; the untried value
    stays as the verified retry (the channel ``_pattern_bank`` philosophy)."""
    for attempt, flip in enumerate((True, False)):
        tag = " (flip retry)" if attempt else ""
        feature = check(
            f"linear-pattern {prefix} pair{tag}",
            await adapter.pattern_components_linear(
                ComponentLinearPatternParameters(
                    components=seeds, count=2, spacing=spacing,
                    direction_name=axis_name, flip_direction=flip,
                )
            ),
        )
        try:
            for target in targets:
                _instance_at(adapter, prefix, target)
            return
        except RuntimeError as exc:
            if attempt:
                raise
            log(f"!! {prefix} pattern sense flipped -- deleting + flip retry ({exc})")
            delete_assembly_feature(adapter, feature.name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    _part("rocker-arm-support")  # placed via place_component below; assert it exists
    _part("lag-screw")  # support hold-down; placed via place_component below
    top_frame_path = _part("top-frame")

    check("create_assembly", await adapter.create_assembly())

    # Base: first insert is auto-fixed by SolidWorks.
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=base_path)
    )
    check("insert_component harmonic-base (auto-fixed)", res)
    base_name = res.data["name"]
    if not res.data.get("fixed"):
        raise RuntimeError("base component was not auto-fixed")

    # Columns at the four top-plate corners: the two +Z corners are REAL-mated
    # seeds; ONE local linear component pattern replicates the pair to the -Z
    # corners (2 inserts + 6 mates + 1 pattern replace 4 inserts + 12 mates).
    # The pattern instances are positioned rigidly by the feature -- they read
    # fully defined (the channel bushing-bank precedent) and spacing 2*COLUMN_Z
    # lands them exactly on the old mate-solved corners, so the top-frame ring
    # bores and every render are unchanged. Sense handling in _pattern_pair.
    column_names: list[str] = []
    for sx in (1, -1):
        target = [sx * COLUMN_X, BASE_TOP_Y, COLUMN_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=column_path, position=target)
        )
        check(f"insert_component tube-frame @ {target}", res)
        name = res.data["name"]
        column_names.append(name)
        await lock_mate(
            adapter,
            named_ref(f"Right Plane@{name}", "PLANE"),
            named_ref(f"Right Plane@{base_name}", "PLANE"),
            label=f"column {name} fixed to base",
        )
        assert_component_placed(adapter, name, target, IDENTITY)
    # Direction reference: EXPLICIT geometry (Top ∩ Right = the machine Z line),
    # not a face/edge pick whose inference flipped the channel banks (#8 era).
    frame_z = check(
        "axis FrameZ (Top ∩ Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    ).name
    await _pattern_pair(
        adapter, column_names, frame_z, 2.0 * COLUMN_Z, "tube-frame",
        [[sx * COLUMN_X, BASE_TOP_Y, -COLUMN_Z] for sx in (1, -1)],
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
    support_target = [SUPPORT_X, SUPPORT_SEAT_Y, 0.0]
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

    # Hold-down: four 9/16-12 lag screws coaxial with the support foot's tapped
    # holes (and the base clearance holes below them). The authored support pose
    # seats its foot exactly on the base top at the derived machine stations, so the
    # screw at each station rises through the base clearance hole -- its O22 head
    # recessed in the base underside counterbore -- into the O12.30 tapped foot
    # hole. Authored head-down (IDENTITY) on its exact machine transform,
    # not grounded. Each seed uses one lock mate to the fixed base; its exact
    # transform carries the physical coaxiality and head-seat position, and the
    # readback assertion proves the mate did not move it. Only the two x-55.44
    # screws are real-mated seeds; ONE local linear component pattern
    # replicates the pair to the x-90.36 stations -- faithful because the pattern
    # spacing and the base hole grid derive from the SAME foot-pattern constants,
    # so the instances land coaxial in holes 2/3 by construction.
    screw_names: list[str] = []
    for i, (bx, bz) in enumerate(LAG_SCREW_XZ[:2]):
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
            label=f"lag-screw {i} fixed to base",
        )
        assert_component_placed(adapter, screw_name, screw_target, IDENTITY)
        screw_names.append(screw_name)
    screw_targets = [
        [bx, LAG_SCREW_UNDER_HEAD_Y, bz] for bx, bz in LAG_SCREW_XZ[2:]
    ]
    pattern_instances = await linear_component_pattern(
        adapter,
        screw_names,
        axis="x",
        spacing_mm=LAG_SCREW_XZ[2][0] - LAG_SCREW_XZ[0][0],
        instances=2,
        direction=PatternDirection.REVERSE,
        label="lag-screw hold-down pattern",
    )
    assert_pattern_targets(
        adapter,
        pattern_instances,
        screw_targets,
        IDENTITY,
        "lag-screw hold-down pattern",
    )

    # Top-frame ring clamped around the four columns, mid-plane y 1020.2.
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

    # Maker's nameplate: laid flat on the base top, decorated face up, on the EAST
    # face, centred front-back between the two east columns (see NAMEPLATE_POS /
    # NAMEPLATE_ROWS). Cosmetic + rigid -> locked to the base.
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

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
