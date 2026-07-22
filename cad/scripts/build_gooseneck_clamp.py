r"""Reproduction script: gooseneck clamp (book ch. 19, pp. 44-45).

The green cast block on the east end of the top frame that grips the
gooseneck post: a vertical O16.5 bore the O16 tube slides in (spring
tension adjustment), pinched by a square-head screw from the side --
"a square-head screw [that] pinches the post in its socket" (p. 45).
The 1/4-20 screw passage is cut through the front wall at the tap-drill
diameter (the drawing's DRILL + TAP note), and the screw itself is
merged into this part as just the square head seated over the passage
on the block face (simplification; the assembled tube does not
interfere).

Layout: origin at the block's base centre on the bore axis (machine
(197, 1040.7, 0) -- on the east rail/crossbar end). Block +Y, bore
along Y, screw along +Z. Dimensions: cad/DIMENSIONS.md ch. 19 (low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_gooseneck_clamp.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import TAP_DRILL_MM
from gooseneck_clamp_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
)

PART_NAME = "gooseneck-clamp"
MATERIAL = "Gray Cast Iron"  # green casting

BLOCK_HALF_X = 15.0  # DIMENSIONS.md ch19: clamp block (low)
BLOCK_HEIGHT = 29.0
BLOCK_HALF_Z = 12.0
BORE_DIA = 16.5  # slides on the O16 gooseneck (derived)
HEAD_HALF = 5.0  # square screw head 10 x 10 x 6 (low)
HEAD_Z = (12.0, 18.0)  # on the block face, seated over the tapped passage
SCREW_Y = 15.0
# 1/4-20 pinch-screw passage through the front wall (face z 12 down to the
# bore wall), cut at the tap drill so the native CAD carries the drawing's
# DRILL + TAP thru-to-bore requirement (codex review #361). A plain cut, not
# a Hole Wizard feature: the passage EXIT is the curved bore wall, and the
# entry face is covered by the merged screw head, so the geometric stand-in
# follows the output-fixture cross-hole precedent.
PASSAGE_DIA = TAP_DRILL_MM["1/4-20"]  # 5.105


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): block half-spans + height, bore
    # diameter, square head half-side, and the screw centre height. The mm
    # suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 29 = 29 in).
    # HEAD_Z is the head extrude's offset/depth (a feature parameter, not a
    # sketch dim), so it stays an inline constant with no global.
    await set_global(adapter, "BlockHalfX", f"{BLOCK_HALF_X}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockHalfZ", f"{BLOCK_HALF_Z}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "HeadHalf", f"{HEAD_HALF}mm")
    await set_global(adapter, "ScrewY", f"{SCREW_Y}mm")
    await set_global(adapter, "PassageDia", f"{PASSAGE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Block (Front sketch, mid-plane in Z). Centred in X, base on the origin
    # plane (y 0) -- NOT origin-centred, so a rectilinear chain (not
    # define_centered_rectangle). Emission order: the kept per-direction
    # distance dims (width seg0, height seg1; the closure supplies the other
    # horizontal + vertical), THEN the anchor (vertex 0 at (-HalfX, 0): x != 0
    # -> one anchor dim, y == 0 -> none).
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_HALF_X, 0.0),
        (BLOCK_HALF_X, 0.0),
        (BLOCK_HALF_X, BLOCK_HEIGHT),
        (-BLOCK_HALF_X, BLOCK_HEIGHT),
    ]
    outline = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter, outline, block_rect, label="block", dims=block,
        names=["Width", "Height", "AnchorX"],
        drives=['2 * "BlockHalfX"', '"BlockHeight"', '"BlockHalfX"'],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * BLOCK_HALF_Z, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    expected = 2.0 * BLOCK_HALF_X * BLOCK_HEIGHT * 2.0 * BLOCK_HALF_Z
    await volume_check(adapter, "block", expected, 0.005 * expected)

    # Vertical bore (on-axis circle at the origin: only the diameter is a dim;
    # the centre X/Z are origin relations, so define_circle records just Dia).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BLOCK_HEIGHT + 10.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    expected -= math.pi * (BORE_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    await volume_check(adapter, "bore", expected, 0.005 * expected)

    # 1/4-20 pinch-screw passage: blind cut INTO the front face (offset plane
    # at z 12, default cut direction opposite the plane normal -- the proven
    # no-reverse face-cut idiom) deep enough to pierce the curved bore wall
    # everywhere across the passage circle (wall z >= sqrt(R^2 - rc^2) = 7.85,
    # so 4.5 reaches z 7.5 < 7.85). Circle centred on the screw axis (0, ScrewY).
    passage_plane = check(
        "create_plane passage face",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=BLOCK_HALF_Z
            )
        ),
    )
    passage = SketchDims()
    check(
        "create_sketch passage",
        await adapter.create_sketch(getattr(passage_plane, "name", passage_plane)),
    )
    await define_circle(
        adapter, 0.0, SCREW_Y, PASSAGE_DIA / 2.0, "passage", dims=passage,
        names=("PassageCx", "PassageCy", "PassageDiaDim"),
        drives=(None, '"ScrewY"', '"PassageDia"'),
    )
    await ensure_fully_defined(adapter, "passage sketch")
    check("exit_sketch passage", await adapter.exit_sketch())
    name_last_feature(adapter, "PassageProfile")
    drive_jobs += passage.apply(adapter, "PassageProfile")
    check(
        "cut passage",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=4.5)),
    )
    name_last_feature(adapter, "ScrewPassage")
    # Removed volume: the front-wall band between the curved bore wall
    # z = sqrt(R^2 - x^2) and the face z 12, over the passage circle
    # (midpoint quadrature; the blind floor z 7.5 sits below the wall
    # everywhere, so it never truncates the integrand).
    rc, bore_r = PASSAGE_DIA / 2.0, BORE_DIA / 2.0
    steps = 400
    v_passage = 0.0
    for i in range(steps):
        x = -rc + (i + 0.5) * (2.0 * rc / steps)
        chord = 2.0 * math.sqrt(max(rc * rc - x * x, 0.0))
        v_passage += chord * (BLOCK_HALF_Z - math.sqrt(bore_r**2 - x * x))
    v_passage *= 2.0 * rc / steps
    expected -= v_passage
    await volume_check(adapter, "passage", expected, 0.005 * expected)

    # Square screw head (+Z face). Centred in X but offset to SCREW_Y in Y --
    # again not origin-centred, so a rectilinear chain. Emission order: width
    # seg0, height seg1 (closure supplies the rest), THEN the anchor (vertex 0
    # at (-HeadHalf, ScrewY - HeadHalf): both coords != 0 -> two anchor dims,
    # x then z).
    head = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Front"))
    head_rect = [
        (-HEAD_HALF, SCREW_Y - HEAD_HALF),
        (HEAD_HALF, SCREW_Y - HEAD_HALF),
        (HEAD_HALF, SCREW_Y + HEAD_HALF),
        (-HEAD_HALF, SCREW_Y + HEAD_HALF),
    ]
    head_lines = await add_line_chain(adapter, head_rect)
    await define_rectilinear_chain(
        adapter, head_lines, head_rect, label="head", dims=head,
        names=["HeadWidth", "HeadHeight", "HeadAnchorX", "HeadAnchorZ"],
        drives=['2 * "HeadHalf"', '2 * "HeadHalf"', '"HeadHalf"',
                '"ScrewY" - "HeadHalf"'],
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_Z[1] - HEAD_Z[0], HEAD_Z[0])
    name_last_feature(adapter, "ScrewHead")
    expected += (2.0 * HEAD_HALF) ** 2 * (HEAD_Z[1] - HEAD_Z[0])
    await volume_check(adapter, "head", expected, 0.005 * expected)

    # No shank feature: the head sits on the block face (z 12) and the bore
    # wall is at z 8.25, so the whole shank band lies inside solid block
    # material -- a shank extrude is a zero-volume no-op (caught live: the
    # +70.7 mm^3 expectation passed only via the 0.5% tolerance).

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven clamp (equations neutral)", expected, 0.005 * expected
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
