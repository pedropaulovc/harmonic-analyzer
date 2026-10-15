r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar soft-soldered to its back bottom edge, the two paper-clip
strips, and the two back-side guide rails the platen hangs on are
separate parts (build_pd_platen_rack.py / build_pd_platen_clip.py /
build_pd_platen_guide.py). Fastener holes:

* four clip-screw #2-56 through receivers at the resized plate's extreme
  left/right edges (x 4.5/265.14), matching the resized clips'
  7.1904-inset end holes at local y 29.6604/127.6296, each tapped on
  through a Ø7 x 1.70 boss on the back face for >= 1.5D engagement;
* ten #4 loose (Ø3.658) counterbored guide-screw through-holes in two rows
  of 5 (ch22 front photo) at the guide rail centrelines: bottom row y 13,
  top row y 47 (machine 318 / 352 with the plate at y 305).

Dimensions: the ch30-p002 Pose Studio fit sets the width to 269.64 mm and
the user-confirmed front-face proportion to height:width = 1:2, hence
134.82 mm high. Thickness: the p.55 edge-on-photo estimate (~4 mm), thinned
to 3.85 (R9-68) for disc-to-platen air.

Layout: width along +X, height along +Y from the origin corner, thickness
extruded +Z.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_platen.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material, apply_color, PANEL_BLACK
from _bore_axis import name_bore_axis
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_precision import apply_drawing_precision
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, add_line_chain, ensure_fully_defined
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _holes import HoleSpec, SharedCoordinate, blind_cut_dia_mm, wizard_holes
from pd_platen_spec import (
    BACK_VIEW_NOTE,
    CBORE_DEPTH,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GUIDE_HOLE_DIA,
    GUIDE_HOLE_FIT,
    GUIDE_HOLE_X,
    GUIDE_HOLE_XY,
    GUIDE_HOLE_Y,
    ISOMETRIC_VIEW_NOTE,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    RIGHT_VIEW_NOTE,
    SOCKET_BOSS_DIA,
    SOCKET_BOSS_H,
    SOCKET_SPEC,
    SOCKET_THREAD_ENGAGEMENT,
    SOCKET_XY,
)

import _telemetry

PART_NAME = "pd-platen"
MATERIAL = "Brass"  # see _appearance.apply_material docstring

# The plate envelope, the clip-screw receivers and the counterbored
# guide-screw through-holes live in pd_platen_spec.py, which the clip, the guide
# rails and the paper-drive assembly read without importing this builder.

# Hole Wizard placement order and printed coordinates (pd_platen_spec
# .DRAWING_DIMENSIONS).  Sockets: the lower right one carries both coordinates
# (its X extension runs down clear of every other hole), the upper right one
# its own Y, the lower left one its own X; every other coordinate is a sketch
# relation to those.  Guide holes: y-major, the bottom row's five X and each
# row's first Y.
SOCKET_ORDER = (
    SOCKET_XY[2],  # (265.14, 58.5104)
    SOCKET_XY[3],  # (265.14, 127.6296)
    SOCKET_XY[0],  # (4.5, 58.5104)
    SOCKET_XY[1],  # (4.5, 127.6296)
)
SOCKET_PLACEMENT = [
    (("Socket1X", '"SocketX2"'), ("Socket1Y", '"SocketY1"')),
    (SharedCoordinate(0), ("Socket2Y", '"SocketY2"')),
    (("Socket3X", '"SocketX1"'), SharedCoordinate(0)),
    (SharedCoordinate(2), SharedCoordinate(1)),
]
GUIDE_PLACEMENT = [
    (
        (f"Guide{column + 1}X", f'"GuideX{column + 1}"')
        if row == 0
        else SharedCoordinate(column),
        (f"Guide{row * len(GUIDE_HOLE_X) + 1}Y", f'"GuideY{row + 1}"')
        if column == 0
        else SharedCoordinate(row * len(GUIDE_HOLE_X)),
    )
    for row in range(len(GUIDE_HOLE_Y))
    for column in range(len(GUIDE_HOLE_X))
]
if [(x, y) for y in GUIDE_HOLE_Y for x in GUIDE_HOLE_X] != list(GUIDE_HOLE_XY):
    raise AssertionError("guide-hole placement assumes the y-major GUIDE_HOLE_XY order")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the plate envelope. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 269.64 = 269.64 in, blowing the
    # part up 25.4x). (The old Socket/GuideHole/Cbore dia+depth knobs are gone:
    # the fastener holes are now native Hole Wizard features whose dimensions
    # come from the #2-56 / #4 standards + explicit artefact overrides, not
    # equation-driven sketch dims -- same as harmonic_base's FastenerHoles.)
    await set_global(adapter, "PlateWidth", f"{PLATE_WIDTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "PlateThickness", f"{PLATE_THICKNESS}mm")
    await set_global(adapter, "SocketBossDia", f"{SOCKET_BOSS_DIA}mm")
    await set_global(adapter, "SocketBossH", f"{SOCKET_BOSS_H}mm")
    # The printed hole stations (SOCKET_PLACEMENT / GUIDE_PLACEMENT).
    for index, value in enumerate(sorted({x for x, _ in SOCKET_XY}), start=1):
        await set_global(adapter, f"SocketX{index}", f"{value}mm")
    for index, value in enumerate(sorted({y for _, y in SOCKET_XY}), start=1):
        await set_global(adapter, f"SocketY{index}", f"{value}mm")
    for index, value in enumerate(GUIDE_HOLE_X, start=1):
        await set_global(adapter, f"GuideX{index}", f"{value}mm")
    for index, value in enumerate(GUIDE_HOLE_Y, start=1):
        await set_global(adapter, f"GuideY{index}", f"{value}mm")

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
    depth_dim = name_dimensions(adapter, "Plate", ["Depth"])
    drive_jobs += [(depth_dim[0], '"PlateThickness"')]
    v_plate = PLATE_WIDTH * PLATE_HEIGHT * PLATE_THICKNESS
    await volume_check(adapter, "plate", v_plate, 0.005 * v_plate)

    # Verify the user-confirmed 1:2 front-face height BEFORE cutting any holes
    # (the post-cut view broke the screen-projected face pick live).
    await bbox_extent_check(
        adapter, "plate height (1:2 front-face ratio)", "y", PLATE_HEIGHT
    )

    # Clip-screw receiver bosses: four Ø7 integral bosses on the back face
    # (z = PlateThickness), sketched on the front plane and extruded from that
    # offset, so the through taps below gain the boss height of thread.
    bosses = SketchDims()
    check("create_sketch socket bosses", await adapter.create_sketch("Front"))
    for index, (x, y) in enumerate(SOCKET_XY, start=1):
        await define_circle(
            adapter,
            x,
            y,
            SOCKET_BOSS_DIA / 2.0,
            f"socket boss {index}",
            dims=bosses,
            names=(f"Boss{index}X", f"Boss{index}Y", f"Boss{index}Dia"),
            drives=(None, None, '"SocketBossDia"'),
        )
    await ensure_fully_defined(adapter, "socket boss sketch")
    check("exit_sketch socket bosses", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketBossProfile")
    drive_jobs += bosses.apply(adapter, "SocketBossProfile")
    extrude_at_offset(adapter, SOCKET_BOSS_H, PLATE_THICKNESS)
    name_last_feature(adapter, "SocketBosses")
    # Offset bosses expose depth first and start offset second.
    boss_dims = name_dimensions(adapter, "SocketBosses", ["BossH", "BossOffset"])
    drive_jobs += [(boss_dims[0], '"SocketBossH"'), (boss_dims[1], '"PlateThickness"')]
    v_bosses = len(SOCKET_XY) * math.pi * (SOCKET_BOSS_DIA / 2.0) ** 2 * SOCKET_BOSS_H
    await volume_check(
        adapter, "plate with socket bosses", v_plate + v_bosses, 0.05 * v_bosses
    )

    # Clip-screw receivers: ONE native Hole Wizard #2-56 through-tapped
    # feature (4 points) from the front face. The heads sit on the clip's flat
    # 0.8 sheet, so the 3.85 plate plus the 1.70 rear boss take the rest of the
    # stock shank as thread and its tip finishes flush at the boss's rear face
    # rather than bottoming in a blind socket.
    pre = await adapter.get_mass_properties()
    sockets = wizard_holes(
        adapter, SOCKET_SPEC,
        [[x, y, 0.0] for x, y in SOCKET_ORDER],
        (0.0, 0.0, -1.0),
        "clip-screw through-tapped receivers (#2-56)", name="Sockets",
        placement_dims=SOCKET_PLACEMENT,
    )
    drive_jobs += sockets.placement_drive_jobs
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
    # #4 loose shanks pass through into the guide rails and the Ø6.5 x 2.9178
    # counterbores hold the stock heads exactly 0.2 sub-flush.
    # The through Ø (#4 loose) and the counterbore Ø6.5 artefact diameter are
    # explicit overrides; the depth follows the exact purchased head.
    pre = post
    guide_holes = wizard_holes(
        adapter,
        HoleSpec("counterbore_fillister", "#4", fit=GUIDE_HOLE_FIT, overrides_mm={
            "HoleDiameter": GUIDE_HOLE_DIA,
            "CounterBoreDiameter": CBORE_DIA,
            "CounterBoreDepth": CBORE_DEPTH,
        }),
        [[x, y, 0.0] for x, y in GUIDE_HOLE_XY],
        (0.0, 0.0, -1.0),
        "guide-screw counterbored holes (#4 loose)", name="GuideHoles",
        placement_dims=GUIDE_PLACEMENT,
    )
    drive_jobs += guide_holes.placement_drive_jobs
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
    v_final = v_plate + v_bosses - v_sockets - v_guide
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven platen (equations neutral)", v_final, 0.02 * v_sockets)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _appearance palette

    # Named slide axis (local X through the origin = Front Plane ∩ Top Plane) so
    # the platen runs as a prismatic joint along the rails in the M6 mated-DOF
    # assembly: collinear with an assembly axis at the slide line, an angle snap
    # kills the residual spin, an X distance snapshot pins the feed position.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "slide axis")

    # Manufacturing drawing support: every printed dimension's places live on
    # the model (drawing-simplicity-policy.md `How the repository implements
    # the guidelines`), then mark exactly the print's dimensions (the drawing
    # imports the marked set and must find every one) and stamp the view notes.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
            "Right View Note": RIGHT_VIEW_NOTE,
            "Back View Note": BACK_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
