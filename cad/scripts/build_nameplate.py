r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base near the platen that dates and
attributes the machine. From the p.71 macro: a rounded-corner brass plate with a
raised polished border, a fine pinstripe frame ringing a recessed blackened
field, and the engraving "Wm. Gaertner & Co / Chicago, U. S. A." split by a
scroll cartouche. The book states the plate is 100 mm x 55 mm (ch.26 p.70) --
the only hard provenance fact on the machine; the '2' stamped a few centimetres
away in the baseplate corner is a separate base feature, not modelled here.

The lettering, ornament AND pinstripe frame are reproduced from the actual photo,
not a font: the polished engraving was traced off the p.71 macro into a vector
DXF (``cad/references/nameplate-engraving.dxf``). This build **imports that DXF**
directly onto the decorated face and cuts the whole artwork as one feature --
lettering, scroll cartouche and pinstripe frame all come from the DXF (an earlier
revision re-traced the DXF into native ``LETTERING_LOOPS`` sketch primitives; that
is now retired in favour of importing the file at build time via
``IFeatureManager::InsertDwgOrDxfFile2`` -- see ``adapter.import_dxf_dwg``).

The import is placed on the Front plane, uniform-scaled so the traced artwork's
outer frame spans ``ENGRAVING_TARGET_WIDTH`` and centred on the plate centre, then
cut both-directions to reach the field floor (so the lettering incises the sunk
field and the pinstripe/frame incise the raised border).

``test_nameplate_geometry`` guards the vendored DXF's integrity (header units,
entity population and artwork extent) -- the source of truth is now the file.

Dimensions: cad/DIMENSIONS.md ch.26 -- 100 x 55 stated (high); thickness, corner
radius, border, recess and screw inset are photo-plausible reads off the p.71
macro (low). The engraving geometry IS the traced photo (the DXF).

Layout: width along +X, height along +Y from the origin corner, decorated face on
the Front plane at z = 0. The body extrudes in -Z (``reverse_direction``) so the
decorated z=0 face is the EXPOSED FRONT face (outward normal +Z): the traced
artwork, drawn to read from +Z, then reads correctly on the face you actually
see, with no mirror. (build_platen is untextured and extrudes +Z; only this
engraved plate needs the decorated face frontmost.)

Run (SolidWorks already open)::

    uv run python cad\scripts\build_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    REFERENCES_DIR,
    SketchDims,
    add_line_chain,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _features import (
    sketch_rounded_rect,
)

import _telemetry

PART_NAME = "nameplate"
MATERIAL = "Brass"  # bright cast/engraved brass plate (see _common.apply_material)

PLATE_WIDTH = 100.0  # DIMENSIONS.md ch26: stated 100 mm (p.70, high)
PLATE_HEIGHT = 55.0  # DIMENSIONS.md ch26: stated 55 mm (p.70, high)
PLATE_THICKNESS = 1.5  # thin brass plate; p.71 edge read (low)
CORNER_R = 3.0  # rounded plate corners (p.71, low)

# Raised border framing the recessed field; the imported pinstripe rides the border.
BORDER_W = 8.0
RECESS_DEPTH = 0.4
ENGRAVE_DEPTH = 0.3  # incise depth of the imported artwork below the field floor

# Traced engraving, imported at build time. The whole artwork (lettering, scroll
# cartouche and pinstripe frame) is drawn in the vendored DXF; the build imports
# and cuts it as one feature (see module docstring).
ENGRAVING_DXF = REFERENCES_DIR / "nameplate-engraving.dxf"
# The DXF is millimetre-unit ($INSUNITS=4); its resolved artwork spans the WCS bbox
# below (NOT drawn around its own origin). Scale it so its outer frame fits the
# plate's border as ENGRAVING_TARGET_WIDTH (the historic 88 mm pinstripe-outer
# footprint). Placement uses swDwgEntitiesSpecifyPosition -- the position we pass is
# where the DXF's ORIGIN lands, so to centre the ARTWORK on the plate we offset by
# the scaled bbox centre: position = plate_centre - scale * bbox_centre. (A bare
# plate-centre would drop the far-from-origin bbox off the 100x55 plate.)
# NOTE: exact scale/position is calibrated against the live import on a SolidWorks
# seat -- these are the analytic values from the DXF's resolved extent.
ENGRAVING_RAW_BBOX = (199.469, 127.793, 478.041, 253.384)  # resolved WCS x0,y0,x1,y1 (mm)
ENGRAVING_RAW_WIDTH = ENGRAVING_RAW_BBOX[2] - ENGRAVING_RAW_BBOX[0]  # ~278.57 mm
ENGRAVING_RAW_CENTER = (
    (ENGRAVING_RAW_BBOX[0] + ENGRAVING_RAW_BBOX[2]) / 2.0,
    (ENGRAVING_RAW_BBOX[1] + ENGRAVING_RAW_BBOX[3]) / 2.0,
)
ENGRAVING_TARGET_WIDTH = 88.0  # mm, artwork outer frame footprint on the plate
ENGRAVING_SCALE = ENGRAVING_TARGET_WIDTH / ENGRAVING_RAW_WIDTH
ENGRAVING_CENTER = (PLATE_WIDTH / 2.0, PLATE_HEIGHT / 2.0)  # plate-mm
# Where the DXF origin must land so the scaled artwork bbox centres on the plate.
ENGRAVING_POSITION = (
    ENGRAVING_CENTER[0] - ENGRAVING_SCALE * ENGRAVING_RAW_CENTER[0],
    ENGRAVING_CENTER[1] - ENGRAVING_SCALE * ENGRAVING_RAW_CENTER[1],
)

# Four corner mounting screws (the shared brass fillister part), in the border band.
SCREW_DIA = 2.6
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        ImportDxfDwgParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the plate envelope, border band, screw
    # pattern and incise depths. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units, so an
    # unsuffixed "100" would evaluate as 100 inches and blow the part up 25.4x. The
    # depth/radius knobs (PlateThickness, CornerR, RecessDepth, EngraveDepth) are
    # editable too even though no SKETCH dim drives them -- thickness/recess are
    # feature (extrude/cut) parameters, the corner radius rides the cosmetic
    # rounded-rect arcs, and the engraving incises the traced loops; none lands in
    # drive_jobs. FieldW/FieldH are the recessed-field span, derived from the
    # envelope minus the border so the field re-centres when a knob changes.
    await set_global(adapter, "PlateWidth", f"{PLATE_WIDTH}mm")
    await set_global(adapter, "PlateHeight", f"{PLATE_HEIGHT}mm")
    await set_global(adapter, "PlateThickness", f"{PLATE_THICKNESS}mm")
    await set_global(adapter, "CornerR", f"{CORNER_R}mm")
    await set_global(adapter, "BorderW", f"{BORDER_W}mm")
    await set_global(adapter, "RecessDepth", f"{RECESS_DEPTH}mm")
    await set_global(adapter, "EngraveDepth", f"{ENGRAVE_DEPTH}mm")
    await set_global(adapter, "ScrewDia", f"{SCREW_DIA}mm")
    await set_global(adapter, "ScrewInset", f"{SCREW_INSET}mm")
    await set_global(adapter, "FieldW", '"PlateWidth" - 2 * "BorderW"')
    await set_global(adapter, "FieldH", '"PlateHeight" - 2 * "BorderW"')

    # Each sketch declares its dim names + drive equations inline; a per-sketch
    # SketchDims records each dim in the order the helper emits it, count-asserts
    # in apply(), and the drive equations are collected here for one deferred batch
    # at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Rounded-corner plate slab (under-defined cosmetic outline -> no fully-defined
    # gate). The rounded rect is raw lines + corner arcs (sketch_rounded_rect), not
    # a define_* helper, so it carries NO recordable display dims -- name the sketch
    # and feature, but record no dims (CornerR is exposed as a global knob above).
    check("create_sketch outline", await adapter.create_sketch("Front"))
    await sketch_rounded_rect(
        adapter, PLATE_WIDTH, PLATE_HEIGHT, CORNER_R, PLATE_WIDTH / 2.0, PLATE_HEIGHT / 2.0
    )
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "OutlineProfile")
    check(
        "extrude plate",
        # Extrude the body in -Z so the decorated z=0 face (where the field recess,
        # lettering and pinstripe incise) is the EXPOSED FRONT face (normal +Z),
        # not buried behind the body -- the traced lettering then reads correctly
        # with no mirror.
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_THICKNESS, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "PlateSlab")
    await bbox_extent_check(adapter, "plate width (stated 100)", "x", PLATE_WIDTH)
    await bbox_extent_check(adapter, "plate height (stated 55)", "y", PLATE_HEIGHT)

    # Sink the central field (raised border). Both-directions 2x depth about the
    # z=0 Front plane lands exactly RECESS_DEPTH into the -z body (+z half is air).
    field_w = PLATE_WIDTH - 2.0 * BORDER_W
    field_h = PLATE_HEIGHT - 2.0 * BORDER_W
    pre = await adapter.get_mass_properties()
    field = SketchDims()
    check("create_sketch field", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    field_rect = [
        (BORDER_W, BORDER_W),
        (BORDER_W + field_w, BORDER_W),
        (BORDER_W + field_w, BORDER_W + field_h),
        (BORDER_W, BORDER_W + field_h),
    ]
    field_lines = await add_line_chain(adapter, field_rect)
    # Not origin-centred (corner anchored at (BorderW, BorderW)), so it stays a
    # define_rectilinear_chain rather than define_centered_rectangle. Emission
    # order: the two kept span dims in line order (horizontal field_w on L0, then
    # vertical field_h on L1; the last segment of each direction is supplied by
    # closure), THEN the anchor dims (x then z, both non-zero). Both anchor coords
    # are +BorderW -- unsigned distances, positive, so they drive directly.
    await define_rectilinear_chain(
        adapter, field_lines, field_rect, label="field", dims=field,
        names=["FieldWidth", "FieldDepth", "FieldX", "FieldZ"],
        drives=['"FieldW"', '"FieldH"', '"BorderW"', '"BorderW"'],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "field sketch")
    check("exit_sketch field", await adapter.exit_sketch())
    name_last_feature(adapter, "FieldProfile")
    drive_jobs += field.apply(adapter, "FieldProfile")
    check(
        "cut field recess",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * RECESS_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FieldRecess")
    v_field = field_w * field_h * RECESS_DEPTH
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    _telemetry.info(f"field recess removed {removed:.1f} mm^3 (analytic {v_field:.1f})")
    if abs(removed - v_field) > 0.02 * v_field:
        raise RuntimeError(f"field recess removed {removed:.1f}, expected {v_field:.1f}")

    # Traced-photo engraving, IMPORTED from the vendored DXF (was native line-loops).
    # The whole artwork -- lettering, scroll cartouche AND pinstripe frame -- comes
    # from cad/references/nameplate-engraving.dxf, inserted on the Front plane as one
    # sketch and cut as one feature. The artwork is traced to read from +Z; because
    # the body extrudes -Z the decorated z=0 face is the exposed front (outward
    # normal +Z), so the import reads correctly with no mirror.
    #
    # The cut reaches RECESS+ENGRAVE both-directions about z=0: over the sunk field
    # the lettering incises ENGRAVE_DEPTH into the floor (the recess already cleared
    # the first RECESS_DEPTH), while over the raised border the pinstripe/frame
    # incise the full RECESS+ENGRAVE. No analytic area exists for the imported
    # splines, so the removed volume is bounded-checked (something engraved, well
    # short of cutting through the slab) rather than matched to a closed form.
    if not ENGRAVING_DXF.is_file():
        raise RuntimeError(f"engraving DXF not found: {ENGRAVING_DXF}")
    pre = await adapter.get_mass_properties()
    check(
        "import engraving DXF",
        await adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(ENGRAVING_DXF),
                plane="Front",
                scale=ENGRAVING_SCALE,
                # DXF origin placement (SpecifyPosition) that centres the scaled
                # artwork on the plate -- see ENGRAVING_POSITION.
                position=[ENGRAVING_POSITION[0], ENGRAVING_POSITION[1]],
                merge_points=True,   # close the traced contours so they cut
                import_hatch=False,  # hatch fills are not cuttable profiles
                import_dimensions=False,
                add_constraints=False,
            )
        ),
    )
    name_last_feature(adapter, "EngravingImport")
    check(
        "cut engraving",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (RECESS_DEPTH + ENGRAVE_DEPTH), both_directions=True
            )
        ),
    )
    name_last_feature(adapter, "EngravingCut")
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    slab_volume = (PLATE_WIDTH * PLATE_HEIGHT - (4.0 - math.pi) * CORNER_R**2) * PLATE_THICKNESS
    _telemetry.info(f"engraving cut removed {removed:.1f} mm^3 (imported DXF artwork)")
    if removed <= 0.0:
        raise RuntimeError("cut engraving: nothing removed (import/cut/plane -> live)")
    if removed > 0.5 * slab_volume:
        raise RuntimeError(
            f"cut engraving: removed {removed:.1f} mm^3 -- implausibly deep "
            f"(> half the {slab_volume:.1f} mm^3 slab); check import scale/position"
        )

    # Four corner screw through-holes (both-directions 2x thickness clears the slab).
    # Every centre is off-axis (both coords non-zero), so define_circle emits three
    # dims per circle -- centreX, centreZ, diameter -- all UNSIGNED distances from
    # the origin. Each coord is positive (the pattern sits in the +X/+Y quadrant),
    # so the drives evaluate positive directly: the near edge is "ScrewInset", the
    # far edge "PlateWidth"/"PlateHeight" minus it. Drives align to SCREW_XY order.
    screw_drives = (
        ('"ScrewInset"', '"ScrewInset"'),
        ('"PlateWidth" - "ScrewInset"', '"ScrewInset"'),
        ('"ScrewInset"', '"PlateHeight" - "ScrewInset"'),
        ('"PlateWidth" - "ScrewInset"', '"PlateHeight" - "ScrewInset"'),
    )
    screws = SketchDims()
    pre = await adapter.get_mass_properties()
    check("create_sketch screws", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, ((x, y), (dx, dz)) in enumerate(zip(SCREW_XY, screw_drives, strict=True)):
        await define_circle(
            adapter, x, y, SCREW_DIA / 2.0, f"screw ({x:.1f}, {y:.1f})",
            dims=screws,
            names=(f"S{n}X", f"S{n}Z", f"S{n}Dia"),
            drives=(dx, dz, '"ScrewDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screws sketch")
    check("exit_sketch screws", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewProfile")
    drive_jobs += screws.apply(adapter, "ScrewProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PLATE_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_holes = len(SCREW_XY) * math.pi * (SCREW_DIA / 2.0) ** 2 * PLATE_THICKNESS
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    _telemetry.info(f"screw holes removed {removed:.1f} mm^3 (analytic {v_holes:.1f})")
    if abs(removed - v_holes) > 0.02 * v_holes:
        raise RuntimeError(f"screw holes removed {removed:.1f}, expected {v_holes:.1f}")

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so geometry must not move. This part has no single analytic-total
    # volume_check (its incremental cuts are asserted in place above), so the
    # neutrality proof captures the as-built volume and re-asserts it unchanged.
    final_volume = float((await adapter.get_mass_properties()).data.volume)
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven nameplate (equations neutral)", final_volume, 1e-3 * final_volume
    )

    # Assembly datums -- frame.SLDASM seats the plate flat on the base distance-free:
    #  * Underside: the plate's BACK face. The body extrudes -Z (reverse_direction)
    #    so it occupies z in [-PlateThickness, 0]; the back/contact face is at
    #    z = -PlateThickness, an offset from the Front plane along its -Z normal.
    #    Mated COINCIDENT to the base DeckTop so the plate physically rests on the
    #    base top (defines the up-axis + both tilts).
    #  * MidLength: the plate's mid-plane along its 100 mm length (local x = w/2),
    #    offset from the Right plane. Mated COINCIDENT to the base Front plane so the
    #    100 mm line centres on the base z-axis (defines the front-back position).
    # Only the east-west placement is then a single free-space distance mate.
    from solidworks_mcp.adapters.base import CreatePlaneParameters

    check(
        "create_plane Underside (Front Plane, -thickness)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Front Plane",
                offset=-PLATE_THICKNESS,
            )
        ),
    )
    name_last_feature(adapter, "Underside")
    check(
        "create_plane MidLength (Right Plane, +width/2)",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset",
                base_plane="Right Plane",
                offset=PLATE_WIDTH / 2.0,
            )
        ),
    )
    name_last_feature(adapter, "MidLength")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
