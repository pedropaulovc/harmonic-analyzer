r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar screwed to its back bottom edge, the two paper-clip
strips, and the two back-side guide rails the platen hangs on are
separate parts (build_platen_rack.py / build_platen_clip.py /
build_platen_guide.py). Fastener holes:

* four O3 x 3.5 clip-screw sockets in the front face at the plate's
  extreme left/right edges (x 6/276), the clips spanning local
  y 15..140 from the TOP edge down (ch22 front photo; holes at the
  clips' 8-inset end holes -> local y 23/132);
* ten O3 guide-screw through-holes in two rows of 5 (ch22 front photo)
  at the guide rail centrelines: bottom row y 13, top row y 47 (machine
  318 / 352 with the plate at y 305).

Dimensions: cad/DIMENSIONS.md "Chapter 22" — 140 mm height annotated
(p.55 callout, high); width 282 re-measured 2026-07-08 on the ch30 p002
front plate with a dual-anchored pixel scale (column span + paper width
agree on 1.27 px/mm; supersedes the aspect-derived ~300, whose vertical
reference mixed in the guide rails); thickness ~4 from the p.55 top
edge-on photo (low).

Layout: width along +X, height along +Y from the origin corner, thickness
extruded +Z.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    apply_color,
    PANEL_BLACK,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

import _telemetry

PART_NAME = "platen"
MATERIAL = "Brass"  # see _common.apply_material docstring

PLATE_WIDTH = 282.0  # re-measured 2026-07-08 on ch30 p002 (dual-anchored px
# scale: column span 394 AND paper 259.5 agree on 1.27 px/mm; board reads
# 358 px = 282, exposed margin beyond the paper ~11 mm/side). The former 300
# came from the front-photo aspect vs the 140 height (low) -- the vertical
# extent mixes in the guide rails, which is exactly what inflated it (med)
PLATE_HEIGHT = 140.0  # DIMENSIONS.md ch22: p.55 callout (high)
PLATE_THICKNESS = 4.0  # DIMENSIONS.md ch22: p.55 edge-on photo (low)

# Clip-screw sockets (machine-handed locals, see docstring).
SOCKET_DIA = 3.0  # the fillister screws' O2.9 shanks thread in (low)
SOCKET_DEPTH = 3.5  # 0.5 web to the back face
SOCKET_XY = ((6.0, 23.0), (6.0, 132.0), (276.0, 23.0), (276.0, 132.0))  # 6 in
# from each edge (mirrors with the width)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back).
GUIDE_HOLE_DIA = 3.0
GUIDE_HOLE_X = (21.0, 81.0, 141.0, 201.0, 261.0)  # 5 stations, 60 pitch,
# symmetric about the 282 width's centre (must match the rail's
# SCREW_STATION_X -- pinned by an assert in the assembly module)
GUIDE_HOLE_Y = (13.0, 47.0)  # bottom / top rail centrelines (machine 318 / 352)
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the guide-screw heads (O5.5 x 2.2 fillister)
# 0.2 below the front face so the recording paper lies FLAT on the platen --
# a proud head would pierce the rigid paper sheet (the interference gate
# caught exactly that, 11.9 mm^3 per head).
CBORE_DIA = 6.5  # 0.5 radial clearance around the O5.5 heads
CBORE_DEPTH = 2.4  # head 2.2 -> crown 0.2 sub-flush

# BACK-face relief where the sliding carriage rides over the four column-clamp
# screw heads (O8 x 2.5 proud of the support-bar front, build_paper_drive_
# assembly): flush against the bar front the heads would bury 2.5 into this
# board (interference gate: 125.66 mm^3 each at the ch30 park, which advances the
# carriage in front of the east column). A shallow blind pocket from the BACK
# lets the heads nest so the board slides clear. Stations are SYMMETRIC about the
# width centre (141) so the set is invariant under the assembly's part-centre
# mirror (see build_platen_guide.LOCK_STATION_X for the same trap) -- 55.5/226.5
# sit over the +-179.5 clamps, 20.5/261.5 over the +-214.5 clamps, whichever pair
# the carriage parks across. On the wear-band centreline (machine y 338.5 = local
# 33.5), clear of the guide-rail band and its screw rows (y 13/47).
CLAMP_RELIEF_DIA = 10.0  # 1.0 radial clearance around the O8 heads
CLAMP_RELIEF_DEPTH = 3.0  # 0.5 past the 2.5 head; leaves a 1.0 front web
CLAMP_RELIEF_XY = ((20.5, 33.5), (55.5, 33.5), (226.5, 33.5), (261.5, 33.5))


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the plate envelope and the socket
    # diameter. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 300 =
    # 300 in, blowing the part up 25.4x). SocketDepth has no sketch dim to drive
    # (it is the cut feature's depth, a feature parameter), but it is still an
    # editable knob here.
    await set_global(adapter, "PlateWidth", f"{PLATE_WIDTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "PlateThickness", f"{PLATE_THICKNESS}mm")
    await set_global(adapter, "SocketDia", f"{SOCKET_DIA}mm")
    await set_global(adapter, "SocketDepth", f"{SOCKET_DEPTH}mm")
    await set_global(adapter, "GuideHoleDia", f"{GUIDE_HOLE_DIA}mm")
    await set_global(adapter, "CboreDia", f"{CBORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Plate outline: a corner-anchored (origin) rectangle, NOT centred, so it
    # keeps define_rectilinear_chain. Emission order is the per-segment distance
    # dims skipping the last of each direction (width on L0, height on L1; L2/L3
    # supplied by closure), THEN the (0, 0) anchor (which emits no dims).
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    plate_rect = [
        (0.0, 0.0),
        (PLATE_WIDTH, 0.0),
        (PLATE_WIDTH, PLATE_HEIGHT),
        (0.0, PLATE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, plate_rect)
    await define_rectilinear_chain(
        adapter, lines, plate_rect, label="plate", dims=outline,
        names=["Width", "Height"],
        drives=['"PlateWidth"', '"PlateHeight"'],
    )
    await ensure_fully_defined(adapter, "plate outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "PlateProfile")
    drive_jobs += outline.apply(adapter, "PlateProfile")
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICKNESS)),
    )
    name_last_feature(adapter, "Plate")
    v_plate = PLATE_WIDTH * PLATE_HEIGHT * PLATE_THICKNESS
    await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Clip-screw sockets from the front face (local z 0): a both-directions
    # cut of 2x depth about the sketch plane lands exactly 0..3.5 in
    # material (the -z half is air).
    pre = await adapter.get_mass_properties()
    # Verify the annotated 140 mm front-face height BEFORE the socket cut
    # (the post-cut view broke the screen-projected face pick live).
    await bbox_extent_check(
        adapter, "plate height (annotated 140)", "y", PLATE_HEIGHT
    )

    # Direct-db: the sketch plane is coplanar with the plate's front face,
    # and inference against the face broke the second add_circle live.
    # Each socket is off-axis in both x and y, so define_circle emits THREE dims
    # (centre-x, centre-z, diameter). The socket centres are an asymmetric,
    # machine-handed layout with no single global knob (the clips sit
    # asymmetrically -- see docstring), so the position dims are named (for the
    # self-naming tree) but left undriven; only the diameter is driven by the
    # SocketDia global.
    sockets = SketchDims()
    check("create_sketch sockets", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, (x, y) in enumerate(SOCKET_XY):
        await define_circle(
            adapter, x, y, SOCKET_DIA / 2.0, f"socket ({x:.0f}, {y:.0f})",
            dims=sockets,
            names=(f"S{n}X", f"S{n}Z", f"S{n}Dia"),
            drives=(None, None, '"SocketDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "sockets sketch")
    check("exit_sketch sockets", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    drive_jobs += sockets.apply(adapter, "SocketProfile")
    check(
        "cut sockets",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * SOCKET_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Sockets")
    post = await adapter.get_mass_properties()
    v_sockets = len(SOCKET_XY) * math.pi * (SOCKET_DIA / 2.0) ** 2 * SOCKET_DEPTH
    removed = pre.data.volume - post.data.volume
    _telemetry.info(f"sockets removed {removed:.1f} mm^3 (analytic {v_sockets:.1f})")
    if abs(removed - v_sockets) > 0.02 * v_sockets:
        raise RuntimeError(f"sockets removed {removed:.1f}, expected {v_sockets:.1f}")

    # Guide-screw through-holes (2 rows of 5). Same direct-db rationale as the
    # sockets; positions are the guide layout (named, undriven), only the
    # diameter rides the global.
    guide_holes = SketchDims()
    check("create_sketch guide holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, (x, y) in enumerate(GUIDE_HOLE_XY):
        await define_circle(
            adapter, x, y, GUIDE_HOLE_DIA / 2.0, f"guide hole ({x:.0f}, {y:.2f})",
            dims=guide_holes,
            names=(f"G{n}X", f"G{n}Z", f"G{n}Dia"),
            drives=(None, None, '"GuideHoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "guide holes sketch")
    check("exit_sketch guide holes", await adapter.exit_sketch())
    name_last_feature(adapter, "GuideHoleProfile")
    drive_jobs += guide_holes.apply(adapter, "GuideHoleProfile")
    check(
        "cut guide holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PLATE_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "GuideHoles")
    v_guide_holes = (
        len(GUIDE_HOLE_XY) * math.pi * (GUIDE_HOLE_DIA / 2.0) ** 2 * PLATE_THICKNESS
    )
    await volume_check(
        adapter,
        "guide holes",
        v_plate - v_sockets - v_guide_holes,
        0.02 * v_guide_holes,
    )

    # Head counterbores from the front face (same both-directions trick as the
    # sockets: 2x depth about the z=0 sketch plane lands 0..CBORE_DEPTH in
    # material). Positions repeat the guide-hole stations (named, undriven);
    # only the diameter rides the global.
    cbores = SketchDims()
    check("create_sketch counterbores", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, (x, y) in enumerate(GUIDE_HOLE_XY):
        await define_circle(
            adapter, x, y, CBORE_DIA / 2.0, f"counterbore ({x:.0f}, {y:.2f})",
            dims=cbores,
            names=(f"Cb{n}X", f"Cb{n}Z", f"Cb{n}Dia"),
            drives=(None, None, '"CboreDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "counterbores sketch")
    check("exit_sketch counterbores", await adapter.exit_sketch())
    name_last_feature(adapter, "CboreProfile")
    drive_jobs += cbores.apply(adapter, "CboreProfile")
    check(
        "cut counterbores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * CBORE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Counterbores")
    # The O3 through-holes already removed their share of each counterbore.
    v_cbores = (
        len(GUIDE_HOLE_XY) * math.pi
        * ((CBORE_DIA / 2.0) ** 2 - (GUIDE_HOLE_DIA / 2.0) ** 2) * CBORE_DEPTH
    )
    await volume_check(
        adapter,
        "counterbores",
        v_plate - v_sockets - v_guide_holes - v_cbores,
        0.02 * v_cbores,
    )

    # Column-clamp head reliefs on the BACK face (blind pockets). Sketch on a
    # plane offset the full thickness off the front (= the back face), then the
    # same both-directions trick (2x depth) lands CLAMP_RELIEF_DEPTH into
    # material from the back, leaving a front web. A wrong-signed offset plane
    # would remove nothing -> the volume_check below fails loud.
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        "create_plane back face",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Front", offset=PLATE_THICKNESS,
        )),
    )
    back_plane = name_last_feature(adapter, "BackFace")
    reliefs = SketchDims()
    check("create_sketch clamp reliefs", await adapter.create_sketch(back_plane))
    set_sketch_direct_db(adapter, True)
    for n, (x, y) in enumerate(CLAMP_RELIEF_XY):
        await define_circle(
            adapter, x, y, CLAMP_RELIEF_DIA / 2.0, f"clamp relief ({x:.1f}, {y:.1f})",
            dims=reliefs,
            names=(f"Cr{n}X", f"Cr{n}Z", f"Cr{n}Dia"),
            drives=(None, None, None),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "clamp reliefs sketch")
    check("exit_sketch clamp reliefs", await adapter.exit_sketch())
    name_last_feature(adapter, "ClampReliefProfile")
    check(
        "cut clamp reliefs",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * CLAMP_RELIEF_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ClampReliefs")
    v_relief = (
        len(CLAMP_RELIEF_XY) * math.pi * (CLAMP_RELIEF_DIA / 2.0) ** 2
        * CLAMP_RELIEF_DEPTH
    )
    await volume_check(
        adapter,
        "clamp reliefs",
        v_plate - v_sockets - v_guide_holes - v_cbores - v_relief,
        0.02 * v_relief,
    )

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    v_final = v_plate - v_sockets - v_guide_holes - v_cbores - v_relief
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven platen (equations neutral)", v_final, 0.02 * v_sockets)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _common palette

    # Named slide axis (local X through the origin = Front Plane ∩ Top Plane) so
    # the platen runs as a prismatic joint along the rails in the M6 mated-DOF
    # assembly: collinear with an assembly axis at the slide line, an angle snap
    # kills the residual spin, an X distance snapshot pins the feed position.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "slide axis")

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
