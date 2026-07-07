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
  Constrained (not grounded) by three orthogonal plane-plane mates against the
  base's principal planes, like the columns/top-frame.
* top-frame x1: the green ring at ring mid-plane Y = 1020.2 (rails 22 x
  41, y 999.7..1040.7), corner bosses bored around the four columns; its
  west rail seats the top-lever ball mounts (channel.SLDASM).
* nameplate x1: the maker's plate (book ch. 26), laid FLAT on the base top
  face on the EAST (+X) side, decorated side up, centred front-back between the
  two east columns and read by an operator at that face. Cosmetic; constrained
  at its measured transform by three orthogonal plane mates (see NAMEPLATE_POS).

Hold-down: four 9/16-12 lag screws come up through the base into the support
foot's tapped holes. The base was re-drilled to the foot's pattern (4 holes at
local X +/-60.32, Z +/-17.46 -> machine x 55.44/90.36, z +/-60.32; see
build_harmonic_base.py HOLE_XZ) with O23 head counterbores on its underside, and
the lag screws (build_lag_screw.py, resized to the 9/16-12 foot tap) are
CONSTRAINED coaxial with each (concentric to the hole axis + a head-seat
coincident + a spin pin). The screws do NOT constrain the support -- three
orthogonal mates already fully constrain it (one pivot-x offset-plane placement +
two flip-free coincident mates: the z-centring symmetry planes and the
FootSeat<->DeckTop datum seat) -- they are structure, constrained by their own
contacts like the columns.

Every component is fixed (base) or fully defined by three orthogonal mates
against the base part. Free-space placements (the corner/pivot offsets) go
through ``plane_distance_mate``: a SIGNED offset builds a reference plane on the
correct side of the base datum and the part is mated coincident to it, so it
lands in ONE solve with no flip and no delete-and-re-add recovery. The readback
of ``Transform2`` against each part's insertion pose stays as a fail-loud
tripwire. Final asserts: every component fixed or ``swFullyConstrained``, and
zero interferences (tangent/coincident contact allowed).

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
    coincident_mate,
    named_ref,
    parallel_mate,
    place_component,
    plane_distance_mate,
    save_assembly_and_images,
)
from _transforms import ROT_Y_POS90

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
# the O12.30 tapped foot hole. mirror=False (exact machine transform, like the
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

    # Columns at the four top-plate corners.
    column_names: list[str] = []
    for sx, sz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
        target = [sx * COLUMN_X, BASE_TOP_Y, sz * COLUMN_Z]
        res = await adapter.insert_component(
            InsertComponentParameters(file_path=column_path, position=target)
        )
        check(f"insert_component tube-frame @ {target}", res)
        name = res.data["name"]
        column_names.append(name)
        await plane_distance_mate(
            adapter, name, "Right Plane", "Right Plane", base_name, sx * COLUMN_X, target
        )
        await plane_distance_mate(
            adapter, name, "Front Plane", "Front Plane", base_name, sz * COLUMN_Z, target
        )
        # Foot seat: the column stands ON the base top -- a physical contact, so
        # coincident its foot (the column's Top Plane: it extrudes UPWARD from there,
        # so that default plane sits at the foot) to the base DeckTop datum, not a
        # measured distance. The Right/Front mates above are genuine free-space
        # corner offsets (the column touches nothing laterally); each is a SIGNED
        # offset plane (sx/sz carry the corner's side) with a coincident, so the
        # negative-side columns land in one solve with no flip recovery.
        await coincident_mate(
            adapter,
            named_ref(f"Top Plane@{name}", "PLANE"),
            named_ref(f"DeckTop@{base_name}", "PLANE"),
            label=f"column {name} foot seats on base top (Top Plane <-> DeckTop)",
            verify=(name, target),
        )
        assert_component_placed(adapter, name, target, IDENTITY)

    # Rocker-pivot support: the windowed trapezoidal NORTH support
    # (build_rocker_arm_support.py), the faithful reproduction of the original
    # hand-built casting that REPLACES the unified rocker-arm-portal. Turned
    # +90deg about Y (SUPPORT_ROWS) so its big windowed faces point along
    # machine +/-X (face-on in the ch. 30 p008 side view), with local X (177.8
    # width) -> machine Z and the foot on the base top. Its origin is the casting
    # centre.
    #
    # Inserted on-solution (mirror=False; single machine-handed casting) then
    # CONSTRAINED BY THREE ORTHOGONAL MATES against the base -- NOT grounded.
    # After the +90 turn the part's planes map onto the machine axes as:
    # local-Z-normal Front plane -> machine X, local-X-normal Right plane ->
    # machine Z, Top plane -> machine Y. So:
    #   Front@support <-> Right@base     distance SUPPORT_X  (72.9, pivot x)
    #   FootSeat@support <-> DeckTop@base COINCIDENT         (physical foot seat)
    #   Right@support <-> Front@base      COINCIDENT         (centres in z)
    # Two of the three are flip-free COINCIDENT mates between NAMED datum planes.
    # The z mate seats symmetry planes (the part's Right plane passes through the
    # casting's z-centre, the base's Front plane through the base z-centre) so the
    # wall is centred BY THE MATE with no tuned z offset. The foot mate seats the
    # support's FootSeat datum (on its foot bottom face) on the base's DeckTop
    # datum (on its top face) -- the actual contact -- a named datum on each part
    # built precisely to be mated here, so the seat is robust (no coordinate pick,
    # no face walk) and flip-free. The component is seeded on-solution (z 0, foot
    # at base top) so both coincident mates lock their DOF without moving; only
    # the pivot-x DISTANCE mate needs flip (see below). No hold-down fasteners.
    support_target = [SUPPORT_X, SUPPORT_SEAT_Y, 0.0]
    support_name = await place_component(
        adapter,
        "rocker-arm-support",
        support_target,
        SUPPORT_EULER,
        SUPPORT_ROWS,
        ground=False,  # defined by the three mates below (pivot-x distance + foot
                       # seat + z-centre), NOT grounded: a redundant fix on top of
                       # them over-defines on a cold re-mate, exactly like the
                       # nameplate did. Same idiom as every other frame part.
        mirror=False,
        label="rocker-arm-support",
    )
    # Pivot-x placement (x +72.9). A free-space offset with no physical contact,
    # so it needs an explicit side selector -- but the SIGNED offset plane is that
    # selector: +SUPPORT_X builds the datum on the near (+X) side and the support's
    # Front Plane is mated COINCIDENT to it, landing at x +72.9 in ONE solve. The
    # old distance mate resolved to the FAR side (x -72.9) because the +90 turn
    # inverts the support's Front-plane normal, so it leaned on the delete-and-re-add
    # flip recovery (a visible there-and-back jump); coincident-to-a-signed-plane
    # is immune -- the plane's position, not the part's plane normal, fixes the side.
    await plane_distance_mate(
        adapter, support_name, "Front Plane", "Right Plane", base_name,
        SUPPORT_X, support_target,
    )
    # Foot seat (y): a PHYSICAL coincident between two NAMED datum planes on the
    # contact -- the support's FootSeat (on its foot bottom face) and the base's
    # DeckTop (on its top face). Flip-free: the part is inserted on-solution (foot
    # already at base top) so the already-satisfied mate just locks the DOF.
    # Named datums make this robust with no coordinate pick and no face walk --
    # the datums exist in the parts precisely to be mated here.
    await coincident_mate(
        adapter,
        named_ref(f"FootSeat@{support_name}", "PLANE"),
        named_ref(f"DeckTop@{base_name}", "PLANE"),
        label="seat rocker-arm-support foot on base top (FootSeat <-> DeckTop)",
        verify=(support_name, support_target),
    )
    await coincident_mate(
        adapter,
        named_ref(f"Right Plane@{support_name}", "PLANE"),
        named_ref(f"Front Plane@{base_name}", "PLANE"),
        label="centre rocker-arm-support in z (symmetry planes)",
        verify=(support_name, support_target),
    )
    assert_component_placed(adapter, support_name, support_target, SUPPORT_ROWS)

    # Hold-down: four 9/16-12 lag screws coaxial with the support foot's tapped
    # holes (and the base clearance holes below them). The support's three mates
    # seat its foot exactly on the base top at the derived machine stations, so the
    # screw at each station rises through the base clearance hole -- its O22 head
    # recessed in the base underside counterbore -- into the O12.30 tapped foot
    # hole. Authored head-down (IDENTITY), mirror=False (exact machine transform),
    # mate-defined (ground=False), not grounded.
    # Each screw is CONSTRAINED (not grounded) by its two physical contacts plus a
    # spin pin -- no distance mate:
    #   coincident  ScrewAxis@screw <-> HoleAxis{i}@base  collinear axes => coaxial
    #               in the bore (concentric is for cylindrical FACES; two reference
    #               AXES take a coincident/collinear mate, which AddMate5 rejects as
    #               a concentric)
    #   coincident  Top Plane@screw <-> CboreSeat@base     under-head on the cbore
    #                                                       shoulder (the axial stop)
    # The screw is a solid of revolution, so those two leave its spin free; SW still
    # counts that as a DOF, so a single PARALLEL of the screw's Right plane to the
    # base's pins the (physically immaterial) spin -- the one non-contact mate, and
    # still distance-free. Each is satisfied at the on-solution insert pose, so it
    # locks without moving; the readback assert confirms the screw did not jump.
    # LAG_SCREW_XZ is in HOLE_XZ order, so screw i mates to HoleAxis{i}.
    for i, (bx, bz) in enumerate(LAG_SCREW_XZ):
        screw_target = [bx, LAG_SCREW_UNDER_HEAD_Y, bz]
        screw_name = await place_component(
            adapter,
            "lag-screw",
            screw_target,
            [0.0, 0.0, 0.0],
            IDENTITY,
            ground=False,  # defined by coaxial + under-head seat + spin pin below,
                           # NOT grounded (the redundant fix would over-define).
            mirror=False,
            label=f"lag-screw hold-down ({bx:.2f}, {bz:+.2f})",
        )
        await coincident_mate(
            adapter,
            named_ref(f"ScrewAxis@{screw_name}", "AXIS"),
            named_ref(f"HoleAxis{i}@{base_name}", "AXIS"),
            label=f"lag-screw {i} coaxial with base hole {i} (collinear axes)",
            verify=(screw_name, screw_target),
        )
        await coincident_mate(
            adapter,
            named_ref(f"Top Plane@{screw_name}", "PLANE"),
            named_ref(f"CboreSeat@{base_name}", "PLANE"),
            label=f"lag-screw {i} under-head seats on counterbore shoulder",
            verify=(screw_name, screw_target),
        )
        await parallel_mate(
            adapter,
            named_ref(f"Right Plane@{screw_name}", "PLANE"),
            named_ref(f"Right Plane@{base_name}", "PLANE"),
            label=f"lag-screw {i} anti-spin (immaterial; revolve symmetry)",
            verify=(screw_name, screw_target),
        )
        assert_component_placed(adapter, screw_name, screw_target, IDENTITY)

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
    # Vertical seat: the ring CAPS the columns -- its top face is flush with the
    # column top ends (docstring: column tops flush with the ring top at 1040.7).
    # Express that physical joint as a COINCIDENT of the ring's RingTop datum to a
    # column's TopEnd datum, NOT a measured distance from the base. One column pins
    # the ring's Y; the two d=0 plane mates above already pin x/z and keep it level.
    await coincident_mate(
        adapter,
        named_ref(f"RingTop@{name}", "PLANE"),
        named_ref(f"TopEnd@{column_names[0]}", "PLANE"),
        label="top-frame caps columns (ring top flush with column top end)",
        verify=(name, target),
    )
    assert_component_placed(adapter, name, target, IDENTITY)

    # Maker's nameplate: laid flat on the base top, decorated face up, on the EAST
    # face, centred front-back between the two east columns (see NAMEPLATE_POS /
    # NAMEPLATE_ROWS). Cosmetic + rigid -> constrained by datum mates (below).
    nameplate_name = await place_component(
        adapter,
        "nameplate",
        NAMEPLATE_POS,
        NAMEPLATE_EULER,
        NAMEPLATE_ROWS,
        ground=False,  # constrained by the three datum mates below, NOT grounded:
                       # a redundant fix on top of them over-defines the 3rd mate on
                       # a cold re-mate (AddMate5 rejects it). Same as every other
                       # frame part -- mate-defined, no fix.
        mirror=False,  # single handed part: NAMEPLATE_POS is the exact transform
        label="nameplate",
    )
    # CONSTRAINED (not grounded) by its physical seating plus one free-space offset:
    #   coincident  Underside@plate <-> DeckTop@base    plate rests on the base top
    #                                                    (defines y + both tilts)
    #   coincident  MidLength@plate <-> Front Plane@base 100 mm line centres on z 0
    #                                                    (defines the front-back z)
    #   distance    Top Plane@plate <-> Right Plane@base east-west placement, x =
    #                                                    214.25 -- a genuine free-
    #                                                    space offset (the plate
    #                                                    touches nothing east-west),
    #                                                    so a distance mate IS the
    #                                                    strictly-necessary knob here
    # Same shape as the rocker-arm-support: two coincident datum seats + one
    # signed free-space offset. The offset (+NAMEPLATE_POS[0]) builds the datum on
    # the +X side and the plate's Top Plane is mated coincident to it -- landing at
    # x 214.25 in one solve regardless of which way the plate's Top-plane normal
    # (local Y -> machine -X) points, so no flip and no recovery.
    await coincident_mate(
        adapter,
        named_ref(f"Underside@{nameplate_name}", "PLANE"),
        named_ref(f"DeckTop@{base_name}", "PLANE"),
        label="nameplate rests flat on base top (Underside <-> DeckTop)",
        verify=(nameplate_name, NAMEPLATE_POS),
    )
    await coincident_mate(
        adapter,
        named_ref(f"MidLength@{nameplate_name}", "PLANE"),
        named_ref(f"Front Plane@{base_name}", "PLANE"),
        label="nameplate length centres on base z-axis (MidLength <-> Front)",
        verify=(nameplate_name, NAMEPLATE_POS),
    )
    await plane_distance_mate(
        adapter, nameplate_name, "Top Plane", "Right Plane", base_name,
        NAMEPLATE_POS[0], NAMEPLATE_POS,
    )
    assert_component_placed(adapter, nameplate_name, NAMEPLATE_POS, NAMEPLATE_ROWS)

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
