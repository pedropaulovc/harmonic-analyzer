r"""Reproduction script: connecting rod (book ch. 13 pp. 22-25 / ch. 14 p. 29; 20 used).

Black rough-finished rod converting each cam's rotation into the rocker arm's
see-saw: a full ring riding the Ø30.6 eccentric cam, a 1.0 mm flat shank, and a
photo-backed two-prong clevis around the rocker's reduced tongue.  Each 1.0 mm
D-shaped cheek is 8 mm wide by 12 mm high around the retained #47 pin axis; a
2.9 mm slot gives the 2.5 mm tongue 0.20 mm nominal clearance per face.

The ring and shank remain on the cam plane.  The clevis is offset to local
Z=-4.05 mm so the assembly's Ry180 places it on the rocker plane.  A shallow
U-bottom web joins both cheeks, while a separate narrow neck overlaps the
centred shank and near cheek; the resulting part is one connected solid.
Centre distance 163.10103 mm preserves the photographed plumb rod / level arm
closure and the existing J2 mates.

Dimensions: cad/config/dimensions.yaml, Chapter 13.  The clevis topology and
offset sign are fixed by the ch14 end views and page002_img02; its occluded
prong, slot, and transition dimensions are photo-bounded nominals.

Layout: ring centre at the origin, shank rising +Y to the clevis root; ring and
shank straddle local Z=0, while every clevis boss uses an explicit negative-Z
offset extrusion.  The strap bore is cut after the bosses so it also trims the
shank sliver that overlaps the ring.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_connecting_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    extrude_at_offset,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    name_dimensions,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _holes import HoleSpec, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from connecting_rod_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from connecting_rod_notes import DRAWING_DIMENSIONS
from connecting_rod_spec import (
    CENTER_DISTANCE,
    CLEVIS_CENTER_Z_LOCAL,
    CLEVIS_CROWN_CENTER_Y,
    CLEVIS_ROOT_OVERLAP,
    CLEVIS_ROOT_Y,
    CLEVIS_SLOT_WIDTH,
    CLEVIS_WEB_BOTTOM_Y,
    CLEVIS_WEB_HEIGHT,
    CLEVIS_WEB_TOP_Y,
    CLEVIS_Z_MAX,
    CLEVIS_Z_MIN,
    FAR_PRONG_Z_MAX,
    FAR_PRONG_Z_MIN,
    NEAR_PRONG_Z_MAX,
    NEAR_PRONG_Z_MIN,
    OFFSET_NECK_HEIGHT,
    OFFSET_NECK_PRONG_OVERLAP,
    OFFSET_NECK_SHANK_OVERLAP,
    OFFSET_NECK_Z_MAX,
    OFFSET_NECK_Z_MIN,
    PRONG_CROWN_CENTER_ABOVE_PIN,
    PRONG_CROWN_RADIUS,
    PRONG_HEIGHT,  # noqa: F401 -- re-exported for the spec/build contract test
    PRONG_ROOT_BELOW_PIN,
    PRONG_THICKNESS,
    PRONG_WIDTH_X,
    RING_BORE_DIA,
    RING_BORE_DIA_BAND,
    RING_THICKNESS,
    RING_WALL,
    SHANK_END_Y,
    SHANK_THICKNESS,
    SHANK_WIDTH,
    SURFACE_FINISHES,
)

import _telemetry

PART_NAME = "connecting-rod"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Cam ring centre -> rocker pin, vertical rod.  The retained pin sits directly
# above the phased cam lobe in the level pose; build_channel_assembly imports
# the same pure-data CENTER_DISTANCE contract.
THROUGH_CUT_DEPTH = 20.0  # > the complete 4.9 mm clevis outside envelope

RING_OUTER_RADIUS = RING_BORE_DIA / 2.0 + RING_WALL
SHANK_START_Y = RING_BORE_DIA / 2.0 - 0.5  # overlaps the strap annulus


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable primitives and derived envelope equations.  Units are explicit
    # because this is an inch document and bare equation values are inches.
    await set_global(adapter, "CenterDistance", f"{CENTER_DISTANCE}mm")
    await set_global(adapter, "RingBoreDia", f"{RING_BORE_DIA}mm")
    await set_global(adapter, "RingWall", f"{RING_WALL}mm")
    await set_global(adapter, "RingThickness", f"{RING_THICKNESS}mm")
    await set_global(adapter, "ShankWidth", f"{SHANK_WIDTH}mm")
    await set_global(adapter, "ShankThickness", f"{SHANK_THICKNESS}mm")
    await set_global(adapter, "ProngWidth", f"{PRONG_WIDTH_X}mm")
    await set_global(adapter, "ProngCrownRadius", f"{PRONG_CROWN_RADIUS}mm")
    await set_global(
        adapter,
        "ProngCrownCenterAbovePin",
        f"{PRONG_CROWN_CENTER_ABOVE_PIN}mm",
    )
    await set_global(adapter, "ProngRootBelowPin", f"{PRONG_ROOT_BELOW_PIN}mm")
    await set_global(adapter, "ProngThickness", f"{PRONG_THICKNESS}mm")
    await set_global(adapter, "ClevisSlotWidth", f"{CLEVIS_SLOT_WIDTH}mm")
    await set_global(adapter, "ClevisCenterZ", f"{CLEVIS_CENTER_Z_LOCAL}mm")
    await set_global(adapter, "ClevisRootOverlap", f"{CLEVIS_ROOT_OVERLAP}mm")
    await set_global(adapter, "ClevisWebHeight", f"{CLEVIS_WEB_HEIGHT}mm")
    await set_global(adapter, "OffsetNeckHeight", f"{OFFSET_NECK_HEIGHT}mm")
    await set_global(
        adapter,
        "OffsetNeckProngOverlap",
        f"{OFFSET_NECK_PRONG_OVERLAP}mm",
    )
    await set_global(
        adapter,
        "OffsetNeckShankOverlap",
        f"{OFFSET_NECK_SHANK_OVERLAP}mm",
    )
    # The #47 diameter is owned by Hole Wizard, not a duplicate equation knob.
    await set_global(adapter, "RingOuterRadius", '"RingBoreDia" / 2 + "RingWall"')
    await set_global(adapter, "ShankStartY", '"RingBoreDia" / 2 - 0.5mm')
    await set_global(
        adapter,
        "ClevisOutsideWidth",
        '2 * "ProngThickness" + "ClevisSlotWidth"',
    )
    await set_global(
        adapter,
        "ClevisZMin",
        '"ClevisCenterZ" - "ClevisOutsideWidth" / 2',
    )
    await set_global(
        adapter,
        "ClevisZMax",
        '"ClevisCenterZ" + "ClevisOutsideWidth" / 2',
    )
    await set_global(
        adapter,
        "SlotZMin",
        '"ClevisCenterZ" - "ClevisSlotWidth" / 2',
    )
    await set_global(
        adapter,
        "SlotZMax",
        '"ClevisCenterZ" + "ClevisSlotWidth" / 2',
    )
    await set_global(adapter, "FarProngZMin", '"ClevisZMin"')
    await set_global(adapter, "FarProngZMax", '"SlotZMin"')
    await set_global(adapter, "NearProngZMin", '"SlotZMax"')
    await set_global(adapter, "NearProngZMax", '"ClevisZMax"')
    await set_global(
        adapter,
        "OffsetNeckZMin",
        '"NearProngZMax" - "OffsetNeckProngOverlap"',
    )
    await set_global(
        adapter,
        "OffsetNeckZMax",
        '-"ShankThickness" / 2 + "OffsetNeckShankOverlap"',
    )
    await set_global(
        adapter,
        "ClevisRootY",
        '"CenterDistance" - "ProngRootBelowPin"',
    )
    await set_global(adapter, "ShankEndY", '"ClevisRootY"')
    await set_global(
        adapter,
        "ClevisCrownCenterY",
        '"CenterDistance" + "ProngCrownCenterAbovePin"',
    )
    await set_global(
        adapter,
        "ClevisTopY",
        '"ClevisCrownCenterY" + "ProngCrownRadius"',
    )
    await set_global(
        adapter,
        "ClevisWebTopY",
        '"ClevisRootY" + "ClevisRootOverlap"',
    )
    await set_global(
        adapter,
        "ClevisWebBottomY",
        '"ClevisWebTopY" - "ClevisWebHeight"',
    )

    # Each sketch records its dim names + drive equations into a per-sketch
    # SketchDims in helper emission order; the drives are collected and applied in
    # one deferred batch at the end (every target resolves against the finished
    # model).
    drive_jobs: list[tuple[str, str]] = []

    # Ring disc (bore is cut last so it also trims the shank sliver). On-axis
    # circle: only the diameter is a dim (centre is a coincident relation).
    ring_disc = SketchDims()
    check("create_sketch ring disc", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        RING_OUTER_RADIUS,
        "ring outer",
        dims=ring_disc,
        names=("RingCx", "RingCz", "RingOuterDia"),
        drives=(None, None, '2 * "RingOuterRadius"'),
    )
    await ensure_fully_defined(adapter, "ring disc sketch")
    check("exit_sketch ring disc", await adapter.exit_sketch())
    name_last_feature(adapter, "RingDiscProfile")
    drive_jobs += ring_disc.apply(adapter, "RingDiscProfile")
    check(
        "extrude ring disc",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingDisc")

    # Shank: flat bar from the strap to the clevis root.  The offset neck below
    # overlaps its rear (-Z) face; the shank itself does not intrude into the slot.
    shank_sd = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    shank_rect = [
        (-SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_START_Y),
        (SHANK_WIDTH / 2.0, SHANK_END_Y),
        (-SHANK_WIDTH / 2.0, SHANK_END_Y),
    ]
    shank = await add_line_chain(adapter, shank_rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter,
        shank,
        shank_rect,
        label="shank",
        dims=shank_sd,
        names=["ShankWidthDim", "ShankLength", "ShankCornerX", "ShankCornerZ"],
        drives=[
            '"ShankWidth"',
            '"ShankEndY" - "ShankStartY"',
            '"ShankWidth" / 2',
            '"ShankStartY"',
        ],
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_sd.apply(adapter, "ShankProfile")
    check(
        "extrude shank",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SHANK_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Shank")

    @_telemetry.traced("connecting_rod.bridge", label_param="stem")
    async def add_bridge(
        stem: str,
        *,
        bottom_y: float,
        top_y: float,
        z_min: float,
        z_max: float,
        height_drive: str,
        bottom_drive: str,
        depth_drive: str,
        offset_drive: str,
    ) -> None:
        """Add a rectangular transition boss toward negative local Z."""
        if not z_min < z_max <= 0.0:
            raise ValueError(
                f"{stem} local-Z envelope must satisfy z_min < z_max <= 0"
            )
        dims = SketchDims()
        check(f"create_sketch {stem}", await adapter.create_sketch("Front"))
        set_sketch_direct_db(adapter, True)
        rect = [
            (-PRONG_WIDTH_X / 2.0, bottom_y),
            (PRONG_WIDTH_X / 2.0, bottom_y),
            (PRONG_WIDTH_X / 2.0, top_y),
            (-PRONG_WIDTH_X / 2.0, top_y),
        ]
        entities = await add_line_chain(adapter, rect)
        set_sketch_direct_db(adapter, False)
        await define_rectilinear_chain(
            adapter,
            entities,
            rect,
            label=stem,
            dims=dims,
            names=[
                f"{stem}Width",
                f"{stem}Height",
                f"{stem}CornerX",
                f"{stem}BottomY",
            ],
            drives=[
                '"ProngWidth"',
                height_drive,
                '"ProngWidth" / 2',
                bottom_drive,
            ],
        )
        await ensure_fully_defined(adapter, f"{stem} sketch")
        check(f"exit_sketch {stem}", await adapter.exit_sketch())
        profile_name = f"{stem}Profile"
        name_last_feature(adapter, profile_name)
        drive_jobs.extend(dims.apply(adapter, profile_name))
        extrude_at_offset(adapter, z_max - z_min, -z_max, flip=True)
        name_last_feature(adapter, stem)
        depth_dim, offset_dim = name_dimensions(
            adapter, stem, [f"{stem}Depth", f"{stem}Offset"]
        )
        drive_jobs.extend(((depth_dim, depth_drive), (offset_dim, offset_drive)))

    # The narrow neck is first because it overlaps the existing centred shank.
    # The U-bottom web then overlaps the neck and spans only the 4.9 mm clevis
    # outside envelope.  Both reach 0.5 mm above the D-cheek roots.
    await add_bridge(
        "OffsetNeck",
        bottom_y=CLEVIS_WEB_TOP_Y - OFFSET_NECK_HEIGHT,
        top_y=CLEVIS_WEB_TOP_Y,
        z_min=OFFSET_NECK_Z_MIN,
        z_max=OFFSET_NECK_Z_MAX,
        bottom_drive='"ClevisWebTopY" - "OffsetNeckHeight"',
        height_drive='"OffsetNeckHeight"',
        depth_drive='"OffsetNeckZMax" - "OffsetNeckZMin"',
        offset_drive='-"OffsetNeckZMax"',
    )
    await add_bridge(
        "ClevisWeb",
        bottom_y=CLEVIS_WEB_BOTTOM_Y,
        top_y=CLEVIS_WEB_TOP_Y,
        z_min=CLEVIS_Z_MIN,
        z_max=CLEVIS_Z_MAX,
        bottom_drive='"ClevisWebBottomY"',
        height_drive='"ClevisWebHeight"',
        depth_drive='"ClevisOutsideWidth"',
        offset_drive='-"ClevisZMax"',
    )

    @_telemetry.traced("connecting_rod.prong", label_param="stem")
    async def add_prong(stem: str, z_min: float, z_max: float) -> None:
        """Add one fully-defined 8 x 12 D-shaped cheek toward negative local Z."""
        if not z_min < z_max <= 0.0:
            raise ValueError(
                f"{stem} local-Z envelope must satisfy z_min < z_max <= 0"
            )
        dims = SketchDims()
        half = PRONG_WIDTH_X / 2.0
        check(f"create_sketch {stem}", await adapter.create_sketch("Front"))
        set_sketch_direct_db(adapter, True)
        bottom = check(
            f"{stem} bottom",
            await adapter.add_line(-half, CLEVIS_ROOT_Y, half, CLEVIS_ROOT_Y),
        )
        right = check(
            f"{stem} right side",
            await adapter.add_line(half, CLEVIS_ROOT_Y, half, CLEVIS_CROWN_CENTER_Y),
        )
        crown = check(
            f"{stem} crown",
            await adapter.add_arc(
                0.0,
                CLEVIS_CROWN_CENTER_Y,
                half,
                CLEVIS_CROWN_CENTER_Y,
                -half,
                CLEVIS_CROWN_CENTER_Y,
            ),
        )
        left = check(
            f"{stem} left side",
            await adapter.add_line(-half, CLEVIS_CROWN_CENTER_Y, -half, CLEVIS_ROOT_Y),
        )
        set_sketch_direct_db(adapter, False)
        check(
            f"{stem} bottom horizontal",
            await adapter.add_sketch_constraint(bottom, None, "horizontal"),
        )
        for label, entity in (("right", right), ("left", left)):
            check(
                f"{stem} {label} vertical",
                await adapter.add_sketch_constraint(entity, None, "vertical"),
            )
        await anchor_point_to_origin(
            adapter,
            f"{crown}.center",
            0.0,
            CLEVIS_CROWN_CENTER_Y,
            f"{stem} crown centre",
        )
        dims.record(f"{stem}CrownCenterY", '"ClevisCrownCenterY"')
        check(
            f"{stem} crown radius",
            await adapter.add_sketch_dimension(
                crown, None, "radial", PRONG_CROWN_RADIUS
            ),
        )
        dims.record(f"{stem}CrownRadius", '"ProngCrownRadius"')
        for end in ("start", "end"):
            check(
                f"{stem} crown {end} level",
                await adapter.add_sketch_constraint(
                    f"{crown}.{end}", f"{crown}.center", "horizontal_points"
                ),
            )
        check(
            f"{stem} root height",
            await adapter.add_sketch_dimension(
                f"{bottom}.start",
                "origin",
                "vertical_distance",
                CLEVIS_ROOT_Y,
            ),
        )
        dims.record(f"{stem}RootY", '"ClevisRootY"')
        await ensure_fully_defined(adapter, f"{stem} sketch")
        check(f"exit_sketch {stem}", await adapter.exit_sketch())
        profile_name = f"{stem}Profile"
        name_last_feature(adapter, profile_name)
        drive_jobs.extend(dims.apply(adapter, profile_name))
        extrude_at_offset(adapter, z_max - z_min, -z_max, flip=True)
        name_last_feature(adapter, stem)
        depth_dim, offset_dim = name_dimensions(
            adapter, stem, [f"{stem}Thickness", f"{stem}Offset"]
        )
        offset_drive = (
            '-"NearProngZMax"' if stem == "NearProng" else '-"FarProngZMax"'
        )
        drive_jobs.extend(
            ((depth_dim, '"ProngThickness"'), (offset_dim, offset_drive))
        )

    # Two separated D-cheeks.  At nominal local Z:
    # near -2.60..-1.60, slot -5.50..-2.60, far -6.50..-5.50.
    await add_prong("NearProng", NEAR_PRONG_Z_MIN, NEAR_PRONG_Z_MAX)
    await add_prong("FarProng", FAR_PRONG_Z_MIN, FAR_PRONG_Z_MAX)
    res = await adapter.get_mass_properties()
    _telemetry.info(f"volume after connected clevis bosses: {res.data.volume:.1f} mm^3")

    # Strap bore - rides the eccentric cam. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        RING_BORE_DIA / 2.0,
        "strap bore",
        dims=bore_sd,
        names=("StrapBoreCx", "StrapBoreCz", "StrapBoreDia"),
        drives=(None, None, '"RingBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapBoreProfile")
    drive_jobs += bore_sd.apply(adapter, "StrapBoreProfile")
    check(
        "cut strap bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StrapBore")

    # One native #47 through-all starts on the near prong's outer (+Z) face.
    # Its inward drill direction crosses the near cheek, open 2.9 mm slot, and
    # far cheek while preserving one coaxial Axis2 for the existing J2 mate.
    pin_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[0.0, CENTER_DISTANCE, NEAR_PRONG_Z_MAX]],
        (0.0, 0.0, 1.0),
        "rocker pin hole (#47)",
        name="PinHole",
        placement_dims=[((None, None), ("PinCz", '"CenterDistance"'))],
    )
    drive_jobs += pin_cut.placement_drive_jobs
    res = await adapter.get_mass_properties()
    v_built = float(res.data.volume)
    _telemetry.info(f"volume after cuts: {v_built:.1f} mm^3")
    # bore now -2234 (r 15.4 x 3) - sliver - pin; Phase 3 rebuild confirms

    # Named bore axes for assembly mates (view-independent name selection):
    # Axis1 = strap bore on the cam; Axis2 = retained clevis/rocker pin axis.
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "strap bore")
    await name_bore_axis(
        adapter,
        "Right Plane",
        0.0,
        "Top Plane",
        CENTER_DISTANCE,
        "rod pin bore",
        drive_b='"CenterDistance"',
        drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value (the
    # rod's volume has no tidy closed form, so the neutrality gate asserts the
    # post-drive volume equals the captured as-built volume): geometry must not
    # move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven connecting rod (equations neutral)", v_built, 0.001 * v_built
    )
    set_dimension_bilateral_tolerance(
        adapter,
        "StrapBoreProfile",
        "StrapBoreDia",
        *deviations(RING_BORE_DIA_BAND),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
