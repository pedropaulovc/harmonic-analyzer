r"""Reproduce the v2 cone pivot post and integrated crank pedestal.

``cone-pivot-post-v2.SLDPRT`` is a new casting, not a refinement of the old
O24 x 100.5 cylinder.  The exact feature dimensions were harvested from that
model.  Its 86 mm height was manually rederived from the second ch30 eight-view
(``references/albert-michelsons-harmonic-analyzer/ch30_images/page003_img01.png``);
the body/head/boss proportions were manually rederived from the two ch11 detail
photos (``ch11_images/page002_img05.jpeg`` and ``page002_img06.jpeg``).

The v2 coordinate frame is also authoritative: the body stands on Top at y=0,
the crank bore runs straight along +Z, and the cone journal itself is yawed
12.5182 degrees about the vertical body axis.  The part therefore wants identity
assembly placement.  Stable semantic references are emitted for downstream
mates: ``ConeShaftNormal``, ``journal axis``, ``swing pivot``, ``mount east``
and ``mount west``.

Run only with SolidWorks already open::

    uv run python cad\scripts\build_cone_pivot_post.py
"""

from __future__ import annotations

import math
import sys
from typing import Any

from _common import (
    CASTING_GREEN,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
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
from _holes import HoleSpec, wizard_holes
from cone_pivot_post_spec import (
    ATTACHMENT_CBORE_DEPTH,
    ATTACHMENT_CBORE_DIA,
    ATTACHMENT_SPACING,
    ATTACHMENT_THRU_DIA,
    ATTACHMENT_X,
    BLOCK_DIA,
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
    CONE_BOSS_DIA,
    CONE_BOSS_LENGTH,
    CRANK_BORE_DIA,
    CRANK_BORE_HEIGHT,
    CRANK_BOSS_DIA,
    CRANK_BOSS_LENGTH,
    CRANK_BOSS_START_Z,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    HARVESTED_VOLUME_MM3,
    HEAD_BASE_Y,
    HEAD_DIA,
    HEAD_HEIGHT,
    INCLINE_DEG,
)

PART_NAME = "cone-pivot-post"
MATERIAL = "Gray Cast Iron"

ATTACHMENT_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    "1/4",
    overrides_mm={
        "HoleDiameter": ATTACHMENT_THRU_DIA,
        "CounterBoreDiameter": ATTACHMENT_CBORE_DIA,
        "CounterBoreDepth": ATTACHMENT_CBORE_DEPTH,
    },
)

BLOCK_RADIUS = BLOCK_DIA / 2.0
HEAD_RADIUS = HEAD_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0
CRANK_BORE_RADIUS = CRANK_BORE_DIA / 2.0
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))


async def build(adapter: Any) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateAxisParameters,
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Retain the harvested reference topology, but give the vertical axis the
    # semantic name the assembly consumes instead of relying on Axis<N> order.
    await name_bore_axis(
        adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot"
    )
    name_last_feature(adapter, "swing pivot")
    check(
        "create ConeShaftNormal",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="angle",
                base_plane="Front Plane",
                angle=INCLINE_DEG,
                pivot_axis="swing pivot",
            )
        ),
    )
    name_last_feature(adapter, "ConeShaftNormal")

    # GUI-editable dimensional contract.  Explicit mm is load-bearing because
    # the project part template uses inch document units.
    globals_mm = {
        "MainBodyDia": BLOCK_DIA,
        "MainBodyHeight": BLOCK_HEIGHT,
        "HeadDia": HEAD_DIA,
        "HeadHeight": HEAD_HEIGHT,
        "CrankBossDia": CRANK_BOSS_DIA,
        "CrankBoreDia": CRANK_BORE_DIA,
        "CrankAxisY": CRANK_BORE_HEIGHT,
        "ConeBossDia": CONE_BOSS_DIA,
        "JournalBoreDia": BORE_DIA,
        "JournalAxisY": BORE_HEIGHT,
        "MountSpacing": ATTACHMENT_SPACING,
        "MountThruDia": ATTACHMENT_THRU_DIA,
        "MountCboreDia": ATTACHMENT_CBORE_DIA,
        "MountCboreDepth": ATTACHMENT_CBORE_DEPTH,
    }
    for name, value in globals_mm.items():
        await set_global(adapter, name, f"{value}mm")
    await set_global(adapter, "ConeIncline", f"{INCLINE_DEG}deg")

    drive_jobs: list[tuple[str, str]] = []

    # 1. Main O42.011 body, y=0..86.
    main = SketchDims()
    check("create sketch MainBodyProfile", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BLOCK_RADIUS,
        "main body",
        dims=main,
        names=("MainBodyCx", "MainBodyCz", "MainBodyDia"),
        drives=(None, None, '"MainBodyDia"'),
    )
    await ensure_fully_defined(adapter, "MainBodyProfile")
    check("exit sketch MainBodyProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "MainBodyProfile")
    drive_jobs += main.apply(adapter, "MainBodyProfile")
    check(
        "extrude MainBody",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "MainBody")
    main_depth = name_dimensions(adapter, "MainBody", ["MainBodyHt"])
    drive_jobs.append((main_depth[0], '"MainBodyHeight"'))
    body_volume = math.pi * BLOCK_RADIUS**2 * BLOCK_HEIGHT
    await volume_check(adapter, "v2 main body", body_volume, 0.001 * body_volume)

    # 2. Slightly larger O42.7506 head/collar over y=59.4..86.
    check(
        "create HeadBasePlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=HEAD_BASE_Y
            )
        ),
    )
    name_last_feature(adapter, "HeadBasePlane")
    head = SketchDims()
    check(
        "create sketch HeadProfile", await adapter.create_sketch("HeadBasePlane")
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        HEAD_RADIUS,
        "head collar",
        dims=head,
        names=("HeadCx", "HeadCz", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "HeadProfile")
    check("exit sketch HeadProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head.apply(adapter, "HeadProfile")
    check(
        "extrude Head",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_HEIGHT)),
    )
    name_last_feature(adapter, "Head")
    head_depth = name_dimensions(adapter, "Head", ["HeadHt"])
    drive_jobs.append((head_depth[0], '"HeadHeight"'))
    head_volume = body_volume + math.pi * (
        HEAD_RADIUS**2 - BLOCK_RADIUS**2
    ) * HEAD_HEIGHT
    await volume_check(adapter, "v2 head collar", head_volume, 0.001 * head_volume)

    # 3. Straight crank boss and bore along +Z from the head tangent plane.
    check(
        "create CrankInterfacePlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=CRANK_BOSS_START_Z,
            )
        ),
    )
    name_last_feature(adapter, "CrankInterfacePlane")
    crank_boss = SketchDims()
    check(
        "create sketch CrankBossProfile",
        await adapter.create_sketch("CrankInterfacePlane"),
    )
    await define_circle(
        adapter,
        0.0,
        CRANK_BORE_HEIGHT,
        CRANK_BOSS_DIA / 2.0,
        "crank boss",
        dims=crank_boss,
        names=("CrankBossX", "CrankAxisY", "CrankBossDia"),
        drives=(None, '"CrankAxisY"', '"CrankBossDia"'),
    )
    await ensure_fully_defined(adapter, "CrankBossProfile")
    check("exit sketch CrankBossProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBossProfile")
    drive_jobs += crank_boss.apply(adapter, "CrankBossProfile")
    check(
        "extrude CrankSprocketBoss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=CRANK_BOSS_LENGTH)
        ),
    )
    name_last_feature(adapter, "CrankSprocketBoss")

    crank_bore = SketchDims()
    check(
        "create sketch CrankBoreProfile",
        await adapter.create_sketch("CrankInterfacePlane"),
    )
    await define_circle(
        adapter,
        0.0,
        CRANK_BORE_HEIGHT,
        CRANK_BORE_RADIUS,
        "crank bore",
        dims=crank_bore,
        names=("CrankBoreX", "CrankBoreY", "CrankBoreDia"),
        drives=(None, '"CrankAxisY"', '"CrankBoreDia"'),
    )
    await ensure_fully_defined(adapter, "CrankBoreProfile")
    check("exit sketch CrankBoreProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBoreProfile")
    drive_jobs += crank_bore.apply(adapter, "CrankBoreProfile")
    check(
        "cut CrankBore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CRANK_BOSS_LENGTH)
        ),
    )
    name_last_feature(adapter, "CrankBore")

    # 4. O17.2 flush pads and O12.2808 journal on the inclined v2 axis.  Both
    # are mid-plane extrusions from the harvested ConeShaftNormal reference.
    # Do not substitute an on-axis revolve here: that SolidWorks topology is
    # known to make later Boolean features fail on this class of casting.
    cone_boss = SketchDims()
    check(
        "create sketch ConeBossProfile",
        await adapter.create_sketch("ConeShaftNormal"),
    )
    await define_circle(
        adapter,
        0.0,
        BORE_HEIGHT,
        CONE_BOSS_DIA / 2.0,
        "inclined cone boss",
        dims=cone_boss,
        names=("ConeBossX", "JournalAxisY", "ConeBossDia"),
        drives=(None, '"JournalAxisY"', '"ConeBossDia"'),
    )
    await ensure_fully_defined(adapter, "ConeBossProfile")
    check("exit sketch ConeBossProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "ConeBossProfile")
    drive_jobs += cone_boss.apply(adapter, "ConeBossProfile")
    check(
        "extrude ConeShaftBoss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=CONE_BOSS_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ConeShaftBoss")

    journal_bore = SketchDims()
    check(
        "create sketch JournalBoreProfile",
        await adapter.create_sketch("ConeShaftNormal"),
    )
    await define_circle(
        adapter,
        0.0,
        BORE_HEIGHT,
        BORE_RADIUS,
        "inclined journal bore",
        dims=journal_bore,
        names=("JournalBoreX", "JournalBoreY", "JournalBoreDia"),
        drives=(None, '"JournalAxisY"', '"JournalBoreDia"'),
    )
    await ensure_fully_defined(adapter, "JournalBoreProfile")
    check("exit sketch JournalBoreProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "JournalBoreProfile")
    drive_jobs += journal_bore.apply(adapter, "JournalBoreProfile")
    check(
        "cut ConeShaftBore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CONE_BOSS_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ConeShaftBore")

    # 5. Preserve the harvested attachment feature as ONE native ANSI-inch
    # Hole Wizard counterbore with two driven placement points.
    attachment_cut = wizard_holes(
        adapter,
        ATTACHMENT_HOLE_SPEC,
        [
            [ATTACHMENT_X, BLOCK_HEIGHT, 0.0],
            [-ATTACHMENT_X, BLOCK_HEIGHT, 0.0],
        ],
        (0.0, 1.0, 0.0),
        "mounting counterbores (1/4 fillister)",
        name="AttachmentScrewHoles",
        expect_dia_mm=ATTACHMENT_THRU_DIA,
        placement_dims=[
            (("MountWestX", '"MountSpacing" / 2'), (None, None)),
            (("MountEastX", '-"MountSpacing" / 2'), (None, None)),
        ],
    )
    drive_jobs += attachment_cut.placement_drive_jobs

    # Apply all neutral equations only after every referenced dimension exists.
    await force_rebuild(adapter)
    for dimension, expression in drive_jobs:
        await drive_dimension(adapter, dimension, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "v2 harvested final",
        HARVESTED_VOLUME_MM3,
        0.001 * HARVESTED_VOLUME_MM3,
    )

    # Semantic, name-selected assembly references.  The journal axis is taken
    # from its actual cylindrical wall; the three vertical axes are plane
    # intersections and therefore independent of screen projection.
    check(
        "create journal axis",
        await adapter.create_axis(
            CreateAxisParameters(
                mode="cylindrical_face",
                face_point=[0.0, BORE_HEIGHT + BORE_RADIUS, 0.0],
            )
        ),
    )
    name_last_feature(adapter, "journal axis")
    for label, x in (("mount west", ATTACHMENT_X), ("mount east", -ATTACHMENT_X)):
        await name_bore_axis(
            adapter, "Front Plane", 0.0, "Right Plane", x, label
        )
        name_last_feature(adapter, label)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
