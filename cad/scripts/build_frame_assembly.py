r"""Reproduction script: frame subassembly (book ch. 6 / eight-views).

Static structure of the machine: the two-plate cast base, four smooth
polished columns at the corners, the rocker-arm-support PORTAL FRAME that
carries the rocker-pivot shaft, and the top-frame ring capping the columns
-- column tops flush with the ring's top face at 1040.7 (M6.8 8-view pass:
no stub above).

Layout (from the ch. 6 dimension photo and the ch. 30 eight views; assembly
axes follow the harmonic-base part: X = 46 cm length, Y = up, Z = 28 cm
depth):

* harmonic-base fixed at the origin, top face at Y = 50.8.
* tube-frame x4 standing on the base top face near the top-plate corners,
  centres at (+/-197, +/-112) — 25.25/21.35 mm inset from the top-plate
  edges (eight views: columns sit at the extreme corners).
* rocker-arm-portal x1 (single green cast WINDOWED PORTAL FRAME,
  build_rocker_arm_portal.py) at (X, Z) = (+72.9, +101.6) - the north
  frustum centre. Two tapered triangular uprights (north z +101.6, south
  z -111) tied by a top rail (under the ball-mount seats) and a foot rail
  (on the base), open window between. The north apex carries the north
  pivot ball mount and the south clevis the south ball mount (both
  channel.SLDASM); the CHANNEL AXIS runs along Z. This supersedes the
  former two-part split (rocker-arm-support frustum here + a-frame upright
  in the former output assembly) - one casting, re-derived from the ch30 side views
  (2026-06-19). The old arbor-clamp boss is GONE (the cone/arbor no longer
  rests on the support; the arbor is shortened to clear the solid portal and
  is carried by its south pedestal only, drive-train.SLDASM, with the north-end
  support deferred to the cone-position rework). The pivot x = arbor 47.5 + 25.4 rod lever = 72.9
  (DIMENSIONS.md ch. 14 layout, M6.8-mirrored).
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic, so it is
  grounded at its measured transform (see NAMEPLATE_POS).
* lag-screw x2 (M6.10 fasteners): the NORTH upright hold-downs, coming
  UP through the base from below -- heads recessed in the base underside's
  counterbores (y 0.5..4.5 in the O15 x 4.5 pockets), O7.8 shanks through
  the base's O8.2 holes and 19.7 into the support's O7.94 x 25 sockets
  (tips at y 70.5).
* hex-bolt x2 (M6.10 fasteners): the SOUTH foot-rail hold-downs (moved
  here from the former output assembly with the rails), at (X, Z) = (+74.75, -54 / +36),
  heads on the rail top (y 70.8), shanks descending into the base.

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

ASM_NAME = "frame"

BASE_TOP_Y = 50.8  # harmonic-base: 0.5 in bottom + 1.5 in top plate
COLUMN_X = 197.0  # column centres, from the ch. 6 / ch. 30 corner placement
COLUMN_Z = 112.0
SUPPORT_X = 72.9  # rocker pivot x: arbor 47.5 + 25.4 rod lever (M6.3, M6.8 mirror)
SUPPORT_Z = 133.35 - 63.5 / 2.0  # 101.6: outer face flush w/ top plate edge
LAG_SCREW_X = (SUPPORT_X - 31.75, SUPPORT_X + 31.75)  # 41.15 / 104.65: the
# support's mounting-hole pitch (base HOLE_XZ[2:] / counterbores match)
LAG_SCREW_Y = 4.5  # under-head face = counterbore top; head 0.5..4.5
# South foot-rail hold-down hex bolts (moved here from the former output assembly
# with the rails: the foot rail now belongs to rocker-arm-portal in this assembly).
# Heads on the rail top (y 70.8), Ø7.8 shanks descending into the base; authored
# machine-handed at x +74.75 (frame does NOT mirror), the bolt being x-symmetric.
HEX_BOLT_X = 74.75
HEX_BOLT_Y = 70.8
HEX_BOLT_Z = (-54.0, 36.0)  # rail quarter points (machine z)
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
# rocker-arm-portal (x 28..117) and clear of the east columns (which sit at
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
    support_path = _part("rocker-arm-portal")
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

    # Rocker-pivot support: the single windowed PORTAL FRAME (north + south
    # tapered uprights + top/foot rails, build_rocker_arm_portal.py). Authored
    # machine-handed with its local origin at the north frustum base centre, so
    # it inserts here at the SAME transform the former two-part split used:
    # apex/north centre at machine (x, z) = (+72.9, +101.6), feet on the base
    # top. Its north apex carries the north pivot ball mount and its south clevis
    # the south ball mount (both channel.SLDASM). The old arbor-clamp boss is
    # gone (the arbor is shortened to clear the solid portal, carried by its
    # south pedestal only; north-end support deferred to the cone rework).
    target = [SUPPORT_X, BASE_TOP_Y, SUPPORT_Z]
    res = await adapter.insert_component(
        InsertComponentParameters(file_path=support_path, position=target)
    )
    check(f"insert_component rocker-arm-portal @ {target}", res)
    name = res.data["name"]
    await plane_distance_mate(
        adapter, name, "Right Plane", "Right Plane", base_name, SUPPORT_X, target
    )
    await plane_distance_mate(
        adapter, name, "Front Plane", "Front Plane", base_name, SUPPORT_Z, target
    )
    await plane_distance_mate(
        adapter, name, "Top Plane", "Top Plane", base_name, BASE_TOP_Y, target
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Support hold-down lag screws (M6.10): authored axis +Y with the
    # under-head face on the part's Top plane, so the column-style
    # plane-mate triple pins them exactly.
    lag_path = _part("lag-screw")
    for lx in LAG_SCREW_X:
        target = [lx, LAG_SCREW_Y, SUPPORT_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=lag_path, position=target)
        )
        check(f"insert_component lag-screw @ {target}", res)
        name = res.data["name"]
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, lx, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, SUPPORT_Z, target
        )
        await plane_distance_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, LAG_SCREW_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # South foot-rail hold-down hex bolts (M6.10): heads on the rail top, axis
    # +Y, x-symmetric -> the column-style plane-mate triple pins them at
    # identity (same idiom as the lag screws).
    hex_path = _part("hex-bolt")
    for hz in HEX_BOLT_Z:
        target = [HEX_BOLT_X, HEX_BOLT_Y, hz]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=hex_path, position=target)
        )
        check(f"insert_component hex-bolt @ {target}", res)
        name = res.data["name"]
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, HEX_BOLT_X, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, hz, target
        )
        await plane_distance_mate(
            adapter, name, "Top Plane", "Top Plane", base_name, HEX_BOLT_Y, target
        )
        assert_component_placed(adapter, name, target, IDENTITY)

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
