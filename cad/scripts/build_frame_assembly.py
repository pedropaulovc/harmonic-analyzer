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
  mount (channel.SLDASM, at machine z +101.6) and the rocker-pivot SHAFT runs
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
  Z -67.3..110.5 -- centred as far as the north pivot ball mount allows: its
  north face is flush with that mount's north edge (z 110.5; the mount sits at
  z +101.6, 17.8 deep), so the apex top edge fully seats it while reading nearly
  centred in the side views. Seat Y =
  base-top 50.8 + 88.9 (half-height) = 139.7. The pivot x = arbor 47.5 + 25.4
  rod lever = 72.9 (DIMENSIONS.md ch. 14 layout, M6.8-mirrored). Grounded at its
  measured transform (structure, like the columns/top-frame).
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic, so it is
  grounded at its measured transform (see NAMEPLATE_POS).

No hold-down fasteners are placed for the support: rocker-arm-support's
own mounting-hole pattern (4 holes at local X +/-60.32, Z +/-17.46) matches
neither the base's lag-screw sockets (X 41.15 / 104.65) nor the former portal
foot-rail bolt positions, and at the portal's lag-screw X/Z the screws would
drive into the solid foot. The portal-era M6.10 lag screws / hex bolts are
therefore dropped here; re-drilling the base to the new pattern is a separate,
out-of-frame change. The three plane-plane mates fully constrain the support on
their own.

Every component is fixed (base) or fully defined by three orthogonal
plane-plane mates against the base part's principal planes; distance-mate
flips are caught by reading back ``Transform2`` after each mate and
re-adding the mate flipped. Final asserts: every component fixed or
``swFullyConstrained``, and zero interferences (tangent/coincident contact
allowed).

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
    run_build,
)
from _assembly import (
    assert_component_placed,
    assert_components_fully_defined,
    check_no_interference,
    place_component,
    plane_distance_mate,
    save_assembly_and_images,
)
from _transforms import ROT_Y_POS90

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
COLUMN_Z = 112.0
SUPPORT_X = 72.9  # rocker pivot x: arbor 47.5 + 25.4 rod lever (M6.3, M6.8 mirror)
SUPPORT_Z = 101.6 + 8.9 - 88.9  # 21.6: centre the 177.8-deep (+/-88.9) turned
# wall as much as possible while its apex still fully seats the north pivot
# ball mount. That mount sits at z +101.6 and is 17.8 deep (z 92.7..110.5), so
# the support's north face is set flush with the mount's north edge (z 110.5):
# Zc = 110.5 - 88.9 = 21.6. Any more centred and the mount would overhang the
# wall's north face. Window centre then reads +21.6 (vs the base half-depth
# 133.35) -- nearly centred in the side views, matching the book's slight north
# offset, with the south face at -67.3 (clear of the base edge -133.35 and below
# the rocker bank, which pivots at y 253.8 well above the apex y 228.6).
SUPPORT_SEAT_Y = BASE_TOP_Y + 88.9  # 139.7: rocker-arm-support's origin is
# at the casting centre (bbox Y +/-88.9), so seating its foot on the base top
# lifts the origin by the 88.9 foot half-height.
# Turn the support +90deg about Y so its big windowed faces (local Z normal)
# point along machine +/-X (face-on in the ch. 30 p008 +X side view), matching
# the portal it replaces; local X (177.8 width) maps to machine Z.
SUPPORT_EULER = [0.0, 90.0, 0.0]
SUPPORT_ROWS = ROT_Y_POS90
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


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import InsertComponentParameters

    base_path = _part("harmonic-base")
    column_path = _part("tube-frame")
    _part("rocker-arm-support")  # placed via place_component below; assert it exists
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

    # Columns at the four top-plate corners.
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        target = [sx * COLUMN_X, BASE_TOP_Y, sz * COLUMN_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=column_path, position=target)
        )
        check(f"insert_component tube-frame @ {target}", res)
        name = res.data["name"]
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, COLUMN_X, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, COLUMN_Z, target
        )
        await plane_distance_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # Rocker-pivot support: the windowed trapezoidal NORTH support
    # (build_rocker_arm_support.py), the faithful reproduction of the original
    # hand-built casting that REPLACES the unified rocker-arm-portal. Turned
    # +90deg about Y (SUPPORT_ROWS) so its big windowed faces point along
    # machine +/-X (face-on in the ch. 30 p008 side view), with local X (177.8
    # width) -> machine Z and the foot on the base top. Its origin is the
    # casting centre, so the placed point is (SUPPORT_X, SUPPORT_SEAT_Y,
    # SUPPORT_Z) = (72.9, 139.7, 21.6). A single machine-handed structural
    # casting -> grounded at its measured transform (mirror=False), like the
    # nameplate. No hold-down fasteners (see module docstring).
    await place_component(
        adapter,
        "rocker-arm-support",
        [SUPPORT_X, SUPPORT_SEAT_Y, SUPPORT_Z],
        SUPPORT_EULER,
        SUPPORT_ROWS,
        ground=True,
        mirror=False,
        label="rocker-arm-support",
    )

    # Top-frame ring clamped around the four columns, mid-plane y 1020.2.
    target = [0.0, TOP_FRAME_MID_Y, 0.0]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=top_frame_path, position=target)
    )
    check(f"insert_component top-frame @ {target}", res)
    name = res.data["name"]
    await plane_distance_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, 0.0, target
    )
    await plane_distance_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, 0.0, target
    )
    await plane_distance_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, TOP_FRAME_MID_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Maker's nameplate: laid flat on the base top, decorated face up, on the EAST
    # face, centred front-back between the two east columns (see NAMEPLATE_POS /
    # NAMEPLATE_ROWS). Cosmetic + rigid -> grounded.
    await place_component(
        adapter,
        "nameplate",
        NAMEPLATE_POS,
        NAMEPLATE_EULER,
        NAMEPLATE_ROWS,
        ground=True,
        mirror=False,  # single handed part: NAMEPLATE_POS is the exact transform
        label="nameplate",
    )

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
