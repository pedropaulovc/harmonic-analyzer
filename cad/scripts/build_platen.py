r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar screwed to its back bottom edge, the two paper-clip
strips, and the two back-side guide rails the platen hangs on are
separate parts (build_platen_rack.py / build_platen_clip.py /
build_platen_guide.py). Fastener holes:

* four clip-screw #4-40 through receivers at the resized plate's extreme
  left/right edges (x 5.3928/264.2472), matching the resized clips'
  7.1904-inset end holes at local y 29.6604/127.6296;
* ten O3 guide-screw through-holes in two rows of 5 (ch22 front photo)
  at the guide rail centrelines: bottom row y 13, top row y 47 (machine
  318 / 352 with the plate at y 305).

Dimensions: the ch30-p002 Pose Studio fit sets the width to 269.64 mm and
the user-confirmed front-face proportion to height:width = 1:2, hence
134.82 mm high. Thickness remains the p.55 edge-on-photo estimate (~4 mm).

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
    volume_check,
)
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes
from build_fillister_screw import HEAD_H as FILLISTER_HEAD_H

import _telemetry

PART_NAME = "platen"
MATERIAL = "Brass"  # see _common.apply_material docstring

PLATE_WIDTH = 269.64  # ch30-p002 Pose Studio: 300 * 0.8988 (user fit)
PLATE_HEIGHT = PLATE_WIDTH / 2.0  # user-confirmed front-face H:W = 1:2
PLATE_THICKNESS = 4.0  # DIMENSIONS.md ch22: p.55 edge-on photo (low)

# Clip-screw receivers: the stock 90114A511 shank reaches through the clip's
# integral seat and uses the platen's full 4-mm thickness as #4-40 engagement.
# These must be through taps: no blind receiver in this plate can accept the
# exact 6.35-mm under-head length without bottoming.
SOCKET_SPEC = HoleSpec("tapped", "#4-40")
SOCKET_THREAD_ENGAGEMENT = PLATE_THICKNESS
SOCKET_XY = (
    (5.3928, 29.6604), (5.3928, 127.6296),
    (264.2472, 29.6604), (264.2472, 127.6296),
)

# Guide-screw through-holes: 2 rows of 5 (heads on the front face, shanks
# into the guide rails on the back). ONE counterbored #4 fillister Hole
# Wizard feature; the artefact through/cbore dims are preserved as overrides.
GUIDE_HOLE_DIA = 3.0  # artefact through Ø (override); #4 fillister shank passes
GUIDE_HOLE_X = (26.964, 80.892, 134.82, 188.748, 242.676)
GUIDE_HOLE_Y = (13.0, 47.0)  # bottom / top rail centrelines (machine 318 / 352)
GUIDE_HOLE_XY = tuple((x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X)

# Front-face counterbores recess the stock 4.6482 x 2.7178 fillister heads
# exactly 0.2 below the front face so the recording paper lies flat.
# The Ø6.5 artefact override remains ample for the smaller stock head.
HEAD_RECESS = 0.2
CBORE_DIA = 6.5
CBORE_DEPTH = FILLISTER_HEAD_H + HEAD_RECESS


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the plate envelope. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 269.64 = 269.64 in, blowing the
    # part up 25.4x). (The old Socket/GuideHole/Cbore dia+depth knobs are gone:
    # the fastener holes are now native Hole Wizard features whose dimensions
    # come from the #4-40 / #4 standards + explicit artefact overrides, not
    # equation-driven sketch dims -- same as harmonic_base's FastenerHoles.)
    await set_global(adapter, "PlateWidth", f"{PLATE_WIDTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "PlateThickness", f"{PLATE_THICKNESS}mm")

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

    # Verify the user-confirmed 1:2 front-face height BEFORE cutting any holes
    # (the post-cut view broke the screen-projected face pick live).
    await bbox_extent_check(
        adapter, "plate height (1:2 front-face ratio)", "y", PLATE_HEIGHT
    )

    # Clip-screw receivers: ONE native Hole Wizard #4-40 through-tapped
    # feature (4 points) from the front face. The clip's integral outer bosses
    # consume the shank length not used by this plate, so all 4.0 mm of platen
    # thickness provide thread engagement and the stock screw tip finishes
    # flush at the back face rather than bottoming in a blind socket.
    pre = await adapter.get_mass_properties()
    wizard_holes(
        adapter, SOCKET_SPEC,
        [[x, y, 0.0] for x, y in SOCKET_XY],
        (0.0, 0.0, -1.0),
        "clip-screw through-tapped receivers (#4-40)", name="Sockets",
    )
    post = await adapter.get_mass_properties()
    v_sockets = (
        len(SOCKET_XY)
        * math.pi
        * (blind_cut_dia_mm(SOCKET_SPEC) / 2.0) ** 2
        * SOCKET_THREAD_ENGAGEMENT
    )
    removed = pre.data.volume - post.data.volume
    _telemetry.info(f"sockets removed {removed:.1f} mm^3 (analytic {v_sockets:.1f})")
    if abs(removed - v_sockets) > 0.02 * v_sockets:
        raise RuntimeError(f"sockets removed {removed:.1f}, expected {v_sockets:.1f}")

    # Guide-screw through-holes + head counterbores: ONE native Hole Wizard
    # counterbored #4 FILLISTER feature (10 points) from the front face. The
    # Ø3 shanks pass through into the guide rails and the Ø6.5 x 2.9178
    # counterbores hold the stock heads exactly 0.2 sub-flush.
    # The through Ø3 and counterbore Ø6.5 artefact diameters are preserved as
    # explicit overrides; only depth follows the exact purchased head.
    pre = post
    wizard_holes(
        adapter,
        HoleSpec("counterbore_fillister", "#4", overrides_mm={
            "HoleDiameter": GUIDE_HOLE_DIA,
            "CounterBoreDiameter": CBORE_DIA,
            "CounterBoreDepth": CBORE_DEPTH,
        }),
        [[x, y, 0.0] for x, y in GUIDE_HOLE_XY],
        (0.0, 0.0, -1.0),
        "guide-screw counterbored holes (#4)", name="GuideHoles",
    )
    post = await adapter.get_mass_properties()
    v_guide = len(GUIDE_HOLE_XY) * (
        math.pi * (GUIDE_HOLE_DIA / 2.0) ** 2 * PLATE_THICKNESS
        + math.pi * ((CBORE_DIA / 2.0) ** 2 - (GUIDE_HOLE_DIA / 2.0) ** 2) * CBORE_DEPTH
    )
    removed = pre.data.volume - post.data.volume
    _telemetry.info(f"guide holes removed {removed:.1f} mm^3 (analytic {v_guide:.1f})")
    if abs(removed - v_guide) > 0.02 * v_guide:
        raise RuntimeError(f"guide holes removed {removed:.1f}, expected {v_guide:.1f}")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    v_final = v_plate - v_sockets - v_guide
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
