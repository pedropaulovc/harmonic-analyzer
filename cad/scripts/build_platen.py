r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar screwed to its back bottom edge and the two paper-clip
strips are separate parts (build_platen_rack.py / build_platen_clip.py).
M6.10 fasteners pass: four O3 x 3.5 sockets in the front face take the
clip fillister screws (through the clips' existing O3 end holes). The
sockets are authored MACHINE-handed: the platen's default "x" mirror
realizes as a pure translation (machine x = local - 42, machine y =
local + 305, machine front face z -142.9 = local z 0), so machine
socket targets (245/-27, y 320/429) pass straight through as local
(287/15, 15/124). The sockets are NOT symmetric about the plate centre
(the clips sit asymmetrically), which is fine precisely because the
realized transform never flips the part.

Dimensions: cad/DIMENSIONS.md "Chapter 22" — 140 mm height annotated
(p.55 callout, high); width ~300 from the front-photo aspect (~2.15:1)
and the p.54 inset vs the 460 mm frame (low; supersedes an earlier ~200
estimate); thickness ~4 from the p.55 top edge-on photo (low).

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

PART_NAME = "platen"
MATERIAL = "Brass"  # see _common.apply_material docstring

PLATE_WIDTH = 300.0  # DIMENSIONS.md ch22: photo aspect vs 140 mm (low)
PLATE_HEIGHT = 140.0  # DIMENSIONS.md ch22: p.55 callout (high)
PLATE_THICKNESS = 4.0  # DIMENSIONS.md ch22: p.55 edge-on photo (low)

# M6.10 clip-screw sockets (machine-handed locals, see docstring).
SOCKET_DIA = 3.0  # the fillister screws' O2.9 shanks thread in (low)
SOCKET_DEPTH = 3.5  # 0.5 web to the back face
SOCKET_XY = ((15.0, 15.0), (15.0, 124.0), (287.0, 15.0), (287.0, 124.0))


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
    print(f"  sockets removed {removed:.1f} mm^3 (analytic {v_sockets:.1f})")
    if abs(removed - v_sockets) > 0.02 * v_sockets:
        raise RuntimeError(f"sockets removed {removed:.1f}, expected {v_sockets:.1f}")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    v_final = v_plate - v_sockets
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
