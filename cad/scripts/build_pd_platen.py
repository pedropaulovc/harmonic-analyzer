r"""Reproduction script: platen plate (book ch. 22, pp. 54-55).

The heavy darkened-brass plate that carries the recording paper. The
toothed rack bar soft-soldered to its back bottom edge, the two paper-clip
strips, and the two back-side guide rails the platen hangs on are
separate parts (build_pd_platen_rack.py / build_pd_platen_clip.py /
build_pd_platen_guide.py). Fastener holes:

* four clip-screw #2-56 through receivers at the plate's extreme left/right
  edges (.170 in from each), matching the clips' .283-inset end holes, each
  tapped on through a Ø.28 boss on the back face for >= 1.5D engagement,
  each boss rounded into the face inside the title block's inside-corner limit;
* ten #4 loose (Ø.144) counterbored guide-screw through-holes in two rows
  of 5 (ch22 front photo) at the guide rail centrelines: bottom row y 13,
  top row y 47 (machine 318 / 352 with the plate at y 305).

Dimensions: the ch30-p002 Pose Studio fit sets the width to 269.64 mm and
the user-confirmed front-face proportion to height:width = 1:2, hence
134.82 mm high. Thickness: the p.55 edge-on-photo estimate (~4 mm), thinned
to 3.85 (R9-68) for disc-to-platen air. The sheet prints decimal inch
(#290); these three keep their millimetres (pd_platen_spec).

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
from _com import _early_bound, _read_member
from _dimensions import drive_dimension, name_dimensions, set_global
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _document_units import apply_package_model_units
from _drawing_precision import apply_drawing_precision
from _extrude import extrude_at_offset
from _feature_tree import _feature_by_name, name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_sketch,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _holes import HoleSpec, SharedCoordinate, blind_cut_dia_mm, wizard_holes
from _visibility import blank_reference_geometry
from pd_platen_spec import (
    CBORE_DEPTH,
    CBORE_DIA,
    CBORE_FLOOR,
    CBORE_FLOOR_REFERENCE_Y,
    CBORE_SECTION_PLANE,
    CBORE_SECTION_X,
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
    SOCKET_BOSS_FILLET_R,
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


def _plane_frame(adapter, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(rotation, origin mm) of a reference plane, read back from
    ``IRefPlane::Transform`` (build_pn_pen_v_block._plane_frame)."""
    feature = _early_bound(_feature_by_name(adapter, name), "IFeature")
    plane = _early_bound(feature.GetSpecificFeature2(), "IRefPlane")
    data = [
        float(v) for v in _read_member(_read_member(plane, "Transform"), "ArrayData")
    ]
    return tuple(data[0:9]), tuple(v * 1000.0 for v in data[9:12])


async def _cbore_section_plane(adapter) -> None:
    """Section A-A's cutting plane: the Right plane carried +X to the top row's
    middle guide hole.  Read back against the Right plane: the same rotation
    (so a sketch on it keeps the Right plane's (u, v) = model (-Z, Y)) and an
    origin shifted by exactly CBORE_SECTION_X along +X."""
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        f"create plane {CBORE_SECTION_PLANE}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Right Plane", offset=CBORE_SECTION_X
            )
        ),
    )
    name_last_feature(adapter, CBORE_SECTION_PLANE)
    right_rotation, right_origin = _plane_frame(adapter, "Right Plane")
    rotation, origin = _plane_frame(adapter, CBORE_SECTION_PLANE)
    shift = tuple(o - r for o, r in zip(origin, right_origin))
    if any(abs(a - b) > 1e-9 for a, b in zip(rotation, right_rotation)) or any(
        abs(s - e) > 1e-6 for s, e in zip(shift, (CBORE_SECTION_X, 0.0, 0.0))
    ):
        raise RuntimeError(
            f"{CBORE_SECTION_PLANE}: rotation {rotation} / origin shift {shift} mm, "
            f"expected the Right plane's {right_rotation} shifted "
            f"({CBORE_SECTION_X}, 0, 0)"
        )


def _require_on_section_plane(adapter, sketch: str) -> None:
    """create_sketch falls back to a standard plane when a named one fails to
    select; the sketch's parents must name CBORE_SECTION_PLANE."""
    feature = _early_bound(_feature_by_name(adapter, sketch), "IFeature")
    parents = [
        str(_early_bound(parent, "IFeature").Name)
        for parent in (feature.GetParents() or ())
    ]
    if CBORE_SECTION_PLANE not in parents:
        raise RuntimeError(
            f"{sketch} is not on {CBORE_SECTION_PLANE}: parents {parents}"
        )


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    # #290: the row's inch calculation units, before the first global.
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

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
    await set_global(adapter, "SocketBossFilletR", f"{SOCKET_BOSS_FILLET_R}mm")
    # The counterbore depth the guide Hole Wizard override cuts; only the
    # drawing's floor reference reads it.
    await set_global(adapter, "CounterBoreDepth", f"{CBORE_DEPTH}mm")
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

    # Clip-screw receiver bosses: four Ø.28 integral bosses on the back face
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

    # Boss roots: each boss rounds into the back face inside the title
    # block's inside-corner limit (unprinted; pd_platen_spec), picked on its
    # root circle at +X (the only edge through that point).
    check(
        "fillet SocketBossFillets",
        await adapter.add_fillet(
            SOCKET_BOSS_FILLET_R,
            [[x + SOCKET_BOSS_DIA / 2.0, y, PLATE_THICKNESS] for x, y in SOCKET_XY],
        ),
    )
    name_last_feature(adapter, "SocketBossFillets")
    fillet_dim = name_dimensions(adapter, "SocketBossFillets", ["BossFilletsR"])
    drive_jobs += [(fillet_dim[0], '"SocketBossFilletR"')]
    # Pappus: the corner spandrel r^2 (1 - pi/4), its centroid r (10 - 3 pi) /
    # (3 (4 - pi)) out from the boss surface, revolved about each boss axis.
    spandrel = SOCKET_BOSS_FILLET_R**2 * (1.0 - math.pi / 4.0)
    spandrel_r = SOCKET_BOSS_DIA / 2.0 + SOCKET_BOSS_FILLET_R * (
        10.0 - 3.0 * math.pi
    ) / (3.0 * (4.0 - math.pi))
    v_fillets = len(SOCKET_XY) * 2.0 * math.pi * spandrel_r * spandrel
    await volume_check(
        adapter,
        "socket boss root fillets",
        v_plate + v_bosses + v_fillets,
        0.25 * v_fillets,
    )

    # Clip-screw receivers: ONE native Hole Wizard #2-56 through-tapped
    # feature (4 points) from the front face. The heads sit on the clip's flat
    # .032 sheet, so the plate plus the rear boss take the rest of the
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
    # #4 loose shanks pass through into the guide rails and the Ø.26 x .115
    # counterbores hold the stock heads exactly .008 sub-flush.
    # The through Ø (#4 loose) and the counterbore Ø.26 are
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

    # Drawing-only counterbore-floor reference (the user-accepted rule-17
    # exception, pd_platen_spec.CBORE_FLOOR): one construction line across the
    # floor, mid-annulus below the top row's middle guide hole, from the back
    # face to the counterbore's bottom.  It sits on section A-A's cutting
    # plane because the drawing's section through that hole prints it (a
    # reference sketch a derived view imports lies in its cut;
    # build_pn_pen_v_block).  Section plane (u, v) -> (-Z, Y), as Right.
    await _cbore_section_plane(adapter)
    floor = SketchDims()
    check(
        "create_sketch counterbore floor",
        await adapter.create_sketch(CBORE_SECTION_PLANE),
    )
    set_sketch_direct_db(adapter, True)
    floor_line = check(
        "counterbore floor reference line",
        await adapter.add_line(
            -PLATE_THICKNESS,
            CBORE_FLOOR_REFERENCE_Y,
            -CBORE_DEPTH,
            CBORE_FLOOR_REFERENCE_Y,
        ),
    )
    set_sketch_direct_db(adapter, False)
    segment = _early_bound(adapter._sketch_entities[floor_line], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("counterbore floor reference did not take construction flag")
    check(
        "counterbore floor reference horizontal",
        await adapter.add_sketch_constraint(floor_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter,
        f"{floor_line}.start",
        -PLATE_THICKNESS,
        CBORE_FLOOR_REFERENCE_Y,
        "counterbore floor reference at the back face",
    )
    floor.record("CboreFloorZ", '"PlateThickness"')
    floor.record("CboreFloorY", None)
    await dimension_between(
        adapter,
        f"{floor_line}.start",
        f"{floor_line}.end",
        "horizontal_distance",
        CBORE_FLOOR,
        "counterbore floor",
    )
    floor.record("CboreFloor", '"PlateThickness" - "CounterBoreDepth"')
    await ensure_fully_defined(adapter, "counterbore floor reference sketch")
    check("exit_sketch counterbore floor", await adapter.exit_sketch())
    name_last_feature(adapter, "CboreFloorReference")
    _require_on_section_plane(adapter, "CboreFloorReference")
    drive_jobs += floor.apply(adapter, "CboreFloorReference")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    v_final = v_plate + v_bosses + v_fillets - v_sockets - v_guide
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
        },
    )
    # The floor reference is construction-only: saved hidden so no assembly
    # renders it; the drawing shows it in section A-A through
    # _drawing_hidden_sketches to import the floor dimension.  Its cutting
    # plane is hidden too.
    blank_sketch(adapter, "CboreFloorReference")
    blank_reference_geometry(adapter, ((CBORE_SECTION_PLANE, "PLANE"),))
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
