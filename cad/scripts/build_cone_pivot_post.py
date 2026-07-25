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
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
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
    CRANK_BORE_OFFSET,
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

# Assembly compatibility names.  v2 puts the straight crank axis on the body
# centreline and bakes the cone incline into the journal.
CRANK_BORE_Y = CRANK_BORE_HEIGHT
CRANK_BORE_DX = CRANK_BORE_OFFSET

BLOCK_RADIUS = BLOCK_DIA / 2.0
HEAD_RADIUS = HEAD_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0
CRANK_BORE_RADIUS = CRANK_BORE_DIA / 2.0
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))


async def _revolved_cylinder(
    adapter: Any,
    *,
    plane_name: str,
    profile_name: str,
    feature_name: str,
    center_y: float,
    radius: float,
    half_length: float,
    is_cut: bool,
) -> None:
    """Create an exact finite cylinder around v2's inclined journal axis.

    A 360-degree revolved rectangle avoids the adapter's missing tangent-plane
    and up-to-surface extrusion modes while producing the same B-rep.  On a Top
    sketch, (u, v) maps to model (X, -Z), hence the sketch-axis direction below.
    """
    from solidworks_mcp.adapters.base import CreatePlaneParameters, RevolveParameters

    check(
        f"create plane {plane_name}",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=center_y
            )
        ),
    )
    name_last_feature(adapter, plane_name)
    check(
        f"create sketch {profile_name}",
        await adapter.create_sketch(plane_name),
    )

    axis_u, axis_v = _SIN_I, -_COS_I
    normal_u, normal_v = _COS_I, _SIN_I
    start = (-half_length * axis_u, -half_length * axis_v)
    end = (half_length * axis_u, half_length * axis_v)
    points = [
        start,
        end,
        (end[0] + radius * normal_u, end[1] + radius * normal_v),
        (start[0] + radius * normal_u, start[1] + radius * normal_v),
    ]
    lines = await add_line_chain(adapter, points)
    await define_polygon_chain(adapter, lines, points, label=profile_name)
    check(
        f"centreline {profile_name}",
        await adapter.add_centerline(start[0], start[1], end[0], end[1]),
    )
    await ensure_fully_defined(adapter, profile_name)
    check(f"exit sketch {profile_name}", await adapter.exit_sketch())
    name_last_feature(adapter, profile_name)
    check(
        f"revolve {feature_name}",
        await adapter.create_revolve(
            RevolveParameters(angle=360.0, is_cut=is_cut)
        ),
    )
    name_last_feature(adapter, feature_name)


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

    # 4. O17.2 flush pads and O12.2808 journal on the inclined v2 axis.
    await _revolved_cylinder(
        adapter,
        plane_name="ConeBossPlane",
        profile_name="ConeBossProfile",
        feature_name="ConeShaftBoss",
        center_y=BORE_HEIGHT,
        radius=CONE_BOSS_DIA / 2.0,
        half_length=CONE_BOSS_LENGTH / 2.0,
        is_cut=False,
    )
    await _revolved_cylinder(
        adapter,
        plane_name="JournalBorePlane",
        profile_name="JournalBoreProfile",
        feature_name="ConeShaftBore",
        center_y=BORE_HEIGHT,
        radius=BORE_RADIUS,
        half_length=BLOCK_DIA,
        is_cut=True,
    )

    # 5. Two exact Hole-Wizard-equivalent counterbores on the y=86 top face.
    check(
        "create AttachmentPlane",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=BLOCK_HEIGHT
            )
        ),
    )
    name_last_feature(adapter, "AttachmentPlane")
    mount_thru = SketchDims()
    check(
        "create sketch MountThruProfile",
        await adapter.create_sketch("AttachmentPlane"),
    )
    for side, x in (("West", ATTACHMENT_X), ("East", -ATTACHMENT_X)):
        await define_circle(
            adapter,
            x,
            0.0,
            ATTACHMENT_THRU_DIA / 2.0,
            f"mount {side.lower()} thru",
            dims=mount_thru,
            names=(f"Mount{side}X", f"Mount{side}Z", f"Mount{side}ThruDia"),
            drives=('"MountSpacing" / 2', None, '"MountThruDia"'),
        )
    await ensure_fully_defined(adapter, "MountThruProfile")
    check("exit sketch MountThruProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "MountThruProfile")
    drive_jobs += mount_thru.apply(adapter, "MountThruProfile")
    check(
        "cut MountThruHoles",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=BLOCK_HEIGHT + 1.0, reverse_direction=True
            )
        ),
    )
    name_last_feature(adapter, "MountThruHoles")

    mount_cbore = SketchDims()
    check(
        "create sketch MountCounterboreProfile",
        await adapter.create_sketch("AttachmentPlane"),
    )
    for side, x in (("West", ATTACHMENT_X), ("East", -ATTACHMENT_X)):
        await define_circle(
            adapter,
            x,
            0.0,
            ATTACHMENT_CBORE_DIA / 2.0,
            f"mount {side.lower()} counterbore",
            dims=mount_cbore,
            names=(f"Cbore{side}X", f"Cbore{side}Z", f"Cbore{side}Dia"),
            drives=('"MountSpacing" / 2', None, '"MountCboreDia"'),
        )
    await ensure_fully_defined(adapter, "MountCounterboreProfile")
    check("exit sketch MountCounterboreProfile", await adapter.exit_sketch())
    name_last_feature(adapter, "MountCounterboreProfile")
    drive_jobs += mount_cbore.apply(adapter, "MountCounterboreProfile")
    check(
        "cut AttachmentScrewHoles",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=ATTACHMENT_CBORE_DEPTH, reverse_direction=True
            )
        ),
    )
    name_last_feature(adapter, "AttachmentScrewHoles")

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
