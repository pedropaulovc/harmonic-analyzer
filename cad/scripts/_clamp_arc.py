r"""Shared builder for the two column-clamp semi-arc shells (book ch. 21/22).

The ch30 p005 quarter view shows each platen-bar clamp as a BLACK two-piece
collar: a FRONT arc (bar side) and a BACK arc, each wrapping half the Ø25.4
column, with ears flanking the column closed by two screws. The screw stack
runs bar -> front-arc ear -> back-arc ear (threaded), heads on the bar's
front face (ch30 p002). Both shells are one rectangular block with the
column's half-cylinder relieved from the mating face and two ear holes along
the clamp axis -- only the block depth, which side the relief opens, and the
ear-hole diameter (clearance vs thread) differ, so one builder takes the
deltas.

Local frame (inherited from the retired one-piece collar): clamp axis (screw line) along
X, column axis along Y through the origin, ears flanking at local z +-17.5;
the assembly rotates local +X to machine -Z. The FRONT arc spans local
x 0..DEPTH (relief opening -X, mating face on the column-axis plane), the BACK
arc spans x -DEPTH..-GRIP_OFFSET (relief opening +X): its mating face stops
``grip_offset`` short of the column axis so the two mating faces stay apart
when the screws close both half-bores onto the column (a split clamp whose
faces meet before the bores do cannot grip).
"""

from __future__ import annotations

import math
from typing import Any

from _appearance import PANEL_BLACK, apply_color, apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _document_units import apply_package_model_units
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _rebuild import force_rebuild
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _holes import HoleSpec, blind_cut_dia_mm, wizard_holes

ARC_WIDTH = 48.006  # 1.890: lateral (Z) span, ear tip to ear tip (old collar OD)
ARC_HALF_H = 8.001  # .315: .630 tall along the column, like the old one-piece collar
COLUMN_BORE = 25.6032  # 1.008: half-cylinder relief: slides on the Ø1.000 column
EAR_HOLE_Z = 17.5006  # .689: ear screw line flanks the column (ch30 p002 heads)
MATERIAL = "Gray Cast Iron"  # black casting (ch30 p005)

# Ear-hole placement contract, per ear ((x name, drive), (y name, drive)) in
# placement-sketch coordinates (x along model z, y along model y).  Both ears
# sit on the bar's centre plane (EAR_HOLE_Y = 0): wizard_holes ties a zero
# coordinate to the origin by a relation, never a dimension, so the two
# centres share ONE height, the one the ear-height reference below measures.
EAR_HOLE_Y = 0.0
EAR_PLACEMENT = (
    (("EarHole1Z", '"EarHoleZ"'), (None, None)),
    (("EarHole2Z", '"EarHoleZ"'), (None, None)),
)
# The prints locate both ears' height from the bottom face, which no feature
# dimension carries (see build_arc).  A hidden reference sketch on the Right
# plane (parallel to the split face both prints view it in; a Right-plane
# sketch maps (x, y) -> model (-z, y)) holds one construction centerline from
# the bottom face (the midplane block's -ArcHalfH) up to ear 1's centre: its
# length is the printed height, its station keeps the print's witness lines on
# that ear.
EAR_HEIGHT_REFERENCE = "EarHeightReference"
EAR_HEIGHT_DIMENSION = "EarHoleHeight"
EAR_HEIGHT_LINE = ((-EAR_HOLE_Z, -ARC_HALF_H), (-EAR_HOLE_Z, EAR_HOLE_Y))


async def build_arc(
    adapter: Any,
    *,
    part_name: str,
    depth: float,
    front: bool,
    hole_spec: HoleSpec,
    grip_offset: float = 0.0,
) -> None:
    """Build one semi-arc shell: ``front=True`` spans local x 0..depth (relief
    cut opening -X toward the column), ``front=False`` spans x
    -depth..-grip_offset. Each caller passes its own ear-hole ``HoleSpec`` (the
    back arc's ears are tapped for the clamp screw, the front arc's are
    clearance). ``grip_offset`` is the back arc's alone (the front's mating face
    stays on the column-axis plane), and it must be positive there. Both arcs
    name their height (``Height@Block``), ear-hole stations from the bore
    axis (``EarHole1Z``/``EarHole2Z@EarHoles``) and the ears' shared height
    from the bottom face (``EarHoleHeight@EarHeightReference``, a hidden
    reference sketch) for their prints. It leaves the
    part unsaved: each caller applies its drawing support (bands, places, marks,
    title-block properties) and then saves ONCE, like every other part builder."""
    if front and grip_offset != 0.0:
        raise ValueError("only the back arc's mating face is offset from the axis")
    if not front and not 0.0 < grip_offset < COLUMN_BORE / 2.0:
        raise ValueError(
            f"back arc grip offset {grip_offset} must lie inside the bore radius"
        )
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(part_name), label=part_name)

    # Editable knobs (Tools > Equations). mm suffix is load-bearing -- INCH
    # document, the equation manager reads bare numbers in document units.
    # (The old HoleDia knob is gone: the ear holes are now a native Hole Wizard
    # feature whose diameter comes from the ANSI-inch table, not a driven dim.)
    await set_global(adapter, "ArcDepth", f"{depth}mm")
    await set_global(adapter, "ArcWidth", f"{ARC_WIDTH}mm")
    await set_global(adapter, "ArcHalfH", f"{ARC_HALF_H}mm")
    await set_global(adapter, "ColumnBore", f"{COLUMN_BORE}mm")
    await set_global(adapter, "EarHoleZ", f"{EAR_HOLE_Z}mm")
    if not front:
        await set_global(adapter, "ArcGripOffset", f"{grip_offset}mm")

    drive_jobs: list[tuple[str, str]] = []

    x0, x1 = (0.0, depth) if front else (-depth, -grip_offset)

    # Block footprint on the Top plane (x depth, z lateral), extruded the
    # collar height about the bar's centre plane. Emission order (rectilinear
    # chain): seg0 depth, seg1 width, then the non-zero anchor coords. The
    # front anchors vertex 0 (x0, -W/2) on the column-axis plane (z only); the
    # back anchors vertex 1 (x1, -W/2) on its mating face, so the face's
    # offset from the column axis is one direct dimension (GripOffset), not
    # the difference of two others.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    rect = [
        (x0, -ARC_WIDTH / 2.0),
        (x1, -ARC_WIDTH / 2.0),
        (x1, ARC_WIDTH / 2.0),
        (x0, ARC_WIDTH / 2.0),
    ]
    lines = await add_line_chain(adapter, rect)
    if front:
        anchor = 0
        anchor_names = ["AnchorZ"]
        anchor_drives = ['"ArcWidth" / 2']
        depth_drive = '"ArcDepth"'
    else:
        anchor = 1
        anchor_names = ["GripOffset", "AnchorZ"]
        anchor_drives = ['"ArcGripOffset"', '"ArcWidth" / 2']
        depth_drive = '"ArcDepth" - "ArcGripOffset"'
    await define_rectilinear_chain(
        adapter, lines, rect, anchor, label="block", dims=block,
        names=["Depth", "Width", *anchor_names],
        drives=[depth_drive, '"ArcWidth"', *anchor_drives],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * ARC_HALF_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    drive_jobs.append(
        (name_dimensions(adapter, "Block", ["Height"])[0], '"ArcHalfH" * 2')
    )
    expected = (x1 - x0) * ARC_WIDTH * 2.0 * ARC_HALF_H
    await volume_check(adapter, "block", expected, 0.005 * expected)

    # Column relief: the Ø25.6 cylinder about the origin Y axis cut through.
    # The block sits on one side of the column-axis plane, so the circular
    # segment beyond the mating face leaves it: the half-disc for the front,
    # the segment past the chord grip_offset from the axis for the back.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, COLUMN_BORE / 2.0, "column bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"ColumnBore"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut column relief",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * ARC_HALF_H, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ColumnRelief")
    # Circular segment past the mating-face chord, `mating_d` from the axis.
    bore_r = COLUMN_BORE / 2.0
    mating_d = 0.0 if front else grip_offset
    segment_area = bore_r**2 * math.acos(mating_d / bore_r) - mating_d * math.sqrt(
        bore_r**2 - mating_d**2
    )
    expected -= segment_area * 2.0 * ARC_HALF_H
    await volume_check(adapter, "column relief", expected, 0.01 * expected)

    # Ear screw holes: ONE native Hole Wizard feature (2 instances) along the
    # clamp axis (local X) at z +-EAR_HOLE_Z, bar centre height, drilled
    # through the outer block face. The ears are outside the bore, so each
    # hole removes a full-length (block x1 - x0) cylinder at the ANSI-inch
    # table diameter. Placed while the body is still prismatic (block + bore
    # relief), before any face-exploding feature. The outward normal is the
    # block's outer X face: +X for the front arc (x 0..depth), -X for the back
    # arc (x -depth..-grip_offset). On either X face the placement sketch's x
    # runs along model z and its y along model y (build_fr_top_frame's
    # GooseneckTap on -X, build_dt_cone_tip_block's PinchBore on +X), so each
    # ear's station from the bore axis is a named sketch-x dimension; the
    # height stays the origin relation (the bar's centre plane), shared by
    # both ears (EAR_PLACEMENT).
    ear_normal = (1.0, 0.0, 0.0) if front else (-1.0, 0.0, 0.0)
    ear_face_x = depth if front else -depth
    ears = wizard_holes(
        adapter,
        hole_spec,
        [
            [ear_face_x, EAR_HOLE_Y, EAR_HOLE_Z],
            [ear_face_x, EAR_HOLE_Y, -EAR_HOLE_Z],
        ],
        ear_normal,
        f"clamp ear holes ({hole_spec.size} {hole_spec.kind})",
        name="EarHoles",
        placement_dims=list(EAR_PLACEMENT),
    )
    drive_jobs += ears.placement_drive_jobs
    ear_dia = blind_cut_dia_mm(hole_spec)
    expected -= 2.0 * math.pi * (ear_dia / 2.0) ** 2 * (x1 - x0)
    await volume_check(adapter, "ear holes", expected, 0.01 * expected)

    # REFERENCE sketch (drawing-simplicity-policy.md `How the repository
    # implements the guidelines`): both prints locate the ears' height from
    # the bottom face, yet no feature dimension carries it -- the placement
    # sketch holds both centres on the centre plane by an origin relation and
    # the midplane block puts the bottom face ArcHalfH below it.  One
    # construction centerline (EAR_HEIGHT_LINE) runs from the bottom face up
    # to ear 1's centre; its top end shares the origin's height, which both
    # ear centres hold, so its length is the height of both.  The station
    # dimension only keeps it under ear 1 (not printed).  Direct-to-DB keeps
    # creation-time inference from adding relations the explicit ones repeat.
    (bottom_x, bottom_y), (top_x, top_y) = EAR_HEIGHT_LINE
    height_ref = SketchDims()
    check("create_sketch ear height reference", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    height_line = check(
        "ear height reference line",
        await adapter.add_centerline(bottom_x, bottom_y, top_x, top_y),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "ear height reference vertical",
        await adapter.add_sketch_constraint(height_line, None, "vertical"),
    )
    await anchor_point_to_origin(
        adapter, f"{height_line}.end", top_x, top_y, "ear 1 centre height"
    )
    height_ref.record("EarHeightStation", '"EarHoleZ"')
    await dimension_between(
        adapter,
        f"{height_line}.start",
        f"{height_line}.end",
        "vertical_distance",
        top_y - bottom_y,
        "ear hole height",
    )
    height_ref.record(EAR_HEIGHT_DIMENSION, '"ArcHalfH"')
    await ensure_fully_defined(adapter, "ear height reference sketch")
    check("exit_sketch ear height reference", await adapter.exit_sketch())
    name_last_feature(adapter, EAR_HEIGHT_REFERENCE)
    drive_jobs += height_ref.apply(adapter, EAR_HEIGHT_REFERENCE)
    # Saved hidden so no part image or assembly renders it (#880); each print
    # shows it in its split-face view only (_drawing_hidden_sketches).
    blank_reference_sketches(adapter, (EAR_HEIGHT_REFERENCE,))

    # Deferred drive equations, then re-check neutrality (each evaluates to
    # the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, f"driven {part_name} (equations neutral)", expected, 0.01 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
