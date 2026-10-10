r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base dates and attributes the machine.
The ch.26 p.71 macro shows a rounded-corner brass plate, raised polished border,
fine notched pinstripe frame around a recessed blackened field, and engraving
"Wm. Gaertner & Co / Chicago, U. S. A." split by a scroll cartouche. The user
ruling of 2026-10-09 (ch.26 p.71; ch.30 p002/p003/p006) makes the traced OUTER
edge the plate outline at 100 mm wide, rather than surrounding the artwork
with the former 100 x 55 plate. Height is the measured DXF aspect ratio
(``fr_nameplate_spec``), about 45.33 mm. The nearby stamped '2' is a separate
base feature, not modelled here.

The lettering, ornament AND pinstripe are traced from the photo, not a font.
The original line-art was buffered into ~0.4 mm closed ribbons and unioned
offline (scratchpad ``generate_cut_dxf.py``: ezdxf resolve + shapely
buffer/union), producing 112 closed LWPOLYLINE contours, formerly baked 88 mm
wide and centred on a 100 x 55 plate.

The 2026-10-09 one-off ezdxf rebake uniformly scales every vertex by 100/88
after subtracting the measured outer-loop bbox origin
(6.0, 7.5538435420827525); it does NOT round the measured 39.8923129158345 mm
height. Units/header settings stay R2010 millimetres; ezdxf fixed metadata
makes the exports deterministic. The outer ribbon's OUTER edge is saved as
``fr-nameplate-outline.dxf`` and imported for the slab. Both loops of that
ribbon are removed from ``fr-nameplate-engraving.dxf`` (now 110 contours):
cutting a ribbon on the plate edge would nick the outline. Its edge is now
the plate boundary, not a decorative groove.

The pinstripe frame's INNER edge is copied unchanged into the single closed
``fr-nameplate-field.dxf`` contour. Cutting that notched field, rather than
a rectangular BorderW inset, leaves a raised border band with generous
corner lands under the screw heads. ``FIELD_AREA_MM2`` and
``OUTLINE_AREA_MM2`` are shoelace areas measured offline with shapely/ezdxf.
``CORNER_R`` is the least-squares circular radius of the traced lower-left
outer corner (maximum radial residual below 0.001 mm after scaling); the
imported contour, not a fitted rounded rectangle, defines the actual outline.

All three files are already in final plate-local mm. The Makers seat ignores
``IImportDxfDwgData::SetPosition`` and ``SetSheetScale`` for flat modelspace
DXFs, so every import uses scale=1, position=(0,0). The remaining engraving
cuts both directions to reach the field floor: lettering incises the sunk
field and the pinstripe incises the raised border. The SolidWorks-free
``test_fr_nameplate_geometry`` guards the files, field/outline areas, and
the coincidence of the clearance stations with the traced screw-head marks.

Mounting (2026-09-02 re-derive off ch26 p.71 ``page001_img01``): FOUR brass
slotted round-head screws, one per corner, heads riding the pinstripe corners
in the border band. They are the shared #4-40 brass ``vn-fillister-screw``
(``_fastener_catalog``; stock Ø2.8448 major diameter, Ø4.6482 head), so the plate carries
four #4 CLOSE clearance holes (wizard Ø3.048, the build_pd_guide_lock idiom) and
the harmonic base carries four blind #4-40 taps under them. The plate envelope,
the screw stations and the mount transform live in ``fr_nameplate_spec`` (pure
data) so ``build_fr_harmonic_base`` and ``build_fr_frame_assembly`` derive the tap
positions and the screw drops from ONE source without importing this build.

Layout: width along +X, height along +Y from the origin corner, decorated face on
the Front plane at z = 0. The body extrudes in -Z (``reverse_direction``) so the
decorated z=0 face is the EXPOSED FRONT face (outward normal +Z): the traced
artwork, drawn to read from +Z, then reads correctly on the face you actually
see, with no mirror. (build_pd_platen is untextured and extrudes +Z; only this
engraved plate needs the decorated face frontmost.)

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_save import save_part_and_images
from _paths import REFERENCES_DIR
from _rebuild import force_rebuild
from _session import run_build
from _holes import CLEARANCE_MM, HoleSpec, wizard_holes
from fr_nameplate_spec import (
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SCREW_XY,
)

import _telemetry

PART_NAME = "fr-nameplate"
MATERIAL = "Brass"  # bright cast/engraved brass plate (see _appearance.apply_material)

# Plate dimensions/stations live in the pure-data contract used by base and frame.
CORNER_R = 4.020278591487471  # mm; measured circular fit, not an outline driver
OUTLINE_DXF = REFERENCES_DIR / "fr-nameplate-outline.dxf"
OUTLINE_AREA_MM2 = 4519.182227599477

# Recess follows the notched inner edge of the traced pinstripe, keeping the
# screw heads on the raised border instead of sinking their bearing lands.
FIELD_DXF = REFERENCES_DIR / "fr-nameplate-field.dxf"
FIELD_AREA_MM2 = 3642.8558759658345
RECESS_DEPTH = 0.4
ENGRAVE_DEPTH = 0.3  # incise depth of the imported artwork below the field floor

# Final plate-local millimetres after the edge ribbon was retired. The reduced
# engraving bbox includes the four head marks, not the now-separate plate outline.
ENGRAVING_DXF = REFERENCES_DIR / "fr-nameplate-engraving.dxf"
ENGRAVING_RAW_BBOX = (
    1.8909717950481455,
    1.8910093518581388,
    98.10902819856861,
    43.441164909264316,
)
ENGRAVING_RAW_WIDTH = ENGRAVING_RAW_BBOX[2] - ENGRAVING_RAW_BBOX[0]
ENGRAVING_RAW_CENTER = (
    (ENGRAVING_RAW_BBOX[0] + ENGRAVING_RAW_BBOX[2]) / 2.0,
    (ENGRAVING_RAW_BBOX[1] + ENGRAVING_RAW_BBOX[3]) / 2.0,
)
ENGRAVING_TARGET_WIDTH = 96.21805640352047
ENGRAVING_SCALE = ENGRAVING_TARGET_WIDTH / ENGRAVING_RAW_WIDTH
ENGRAVING_CENTER = ENGRAVING_RAW_CENTER
ENGRAVING_POSITION = (0.0, 0.0)  # placement was baked; never re-centre the head marks

# Four corner mounting screws (the shared stock #4-40 brass fillister-screw,
# Ø2.8448 major diameter) at SCREW_XY in the border band: #4 CLOSE clearance
# (Ø3.048 -- the same HoleSpec build_pd_guide_lock cuts for the same screw;
# memory/fastener-policy-us-customary). History: the holes were #2-56 normal
# fit Ø2.591 from a "#2 screw" guess; the 2026-09-02 p.71 re-read sized the
# heads (~Ø5.5 on the 100 plate) to the catalog #4-40 fillister, whose Ø2.9
# nominal / Ø2.845 major would not pass a Ø2.591 hole.
SCREW_HOLE_SPEC = HoleSpec("clearance", "#4", fit="close")
SCREW_HOLE_DIA = CLEARANCE_MM[(SCREW_HOLE_SPEC.size, SCREW_HOLE_SPEC.fit)]  # 3.048


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        ExtrusionParameters,
        ImportDxfDwgParameters,
    )

    check("create_part", await adapter.create_part())

    # Only the screw-coordinate globals drive geometry. The imported outline and
    # field are fixed photo contours, not editable BorderW/FieldW/FieldH rectangles.
    # Explicit mm is load-bearing: this is an INCH document, so bare numbers would
    # evaluate in inches and move the placement sketch by a factor of 25.4.
    for n, (x, y) in enumerate(SCREW_XY):
        await set_global(adapter, f"Screw{n}X", f"{x}mm")
        await set_global(adapter, f"Screw{n}Y", f"{y}mm")

    # The Hole Wizard declares placement dim names + drive equations inline.
    # Collect its deferred drive jobs for one batch after the finished model's
    # rebuild, when every dimension target must resolve.
    drive_jobs: list[tuple[str, str]] = []

    # The slab's contour IS the original outer loop's outer edge, including the
    # traced corner curvature; importing it avoids approximating the photo with a
    # native rounded rectangle. Placement/scale are already baked into the file.
    if not OUTLINE_DXF.is_file():
        raise RuntimeError(f"outline DXF not found: {OUTLINE_DXF}")
    check(
        "import outline DXF",
        await adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(OUTLINE_DXF),
                plane="Front",
                scale=1.0,
                position=[0.0, 0.0],
                merge_points=True,
                import_hatch=False,
                import_dimensions=False,
                add_constraints=False,
            )
        ),
    )
    name_last_feature(adapter, "OutlineProfile")
    # A boss extrude takes its profile from the open or PRE-SELECTED sketch only
    # (unlike the cut path, it never looks up the last ProfileFeature), and the
    # DXF import leaves its sketch closed and unselected: farm leaf 2026-10-10
    # failed "Failed to create extrusion feature" right here without this select.
    check("select outline profile", await adapter.select_feature("OutlineProfile"))
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
    await bbox_extent_check(adapter, "plate width (traced outline)", "x", PLATE_WIDTH)
    await bbox_extent_check(adapter, "plate height (traced outline)", "y", PLATE_HEIGHT)
    await volume_check(
        adapter, "traced plate slab", OUTLINE_AREA_MM2 * PLATE_THICKNESS, 0.02
    )

    # Sink exactly the inner pinstripe edge, NOT a rectangular inset. Its corner
    # notches preserve the raised bearing lands around all four screw-head marks.
    # Both-directions 2x depth about z=0 lands RECESS_DEPTH into the -z body.
    if not FIELD_DXF.is_file():
        raise RuntimeError(f"field DXF not found: {FIELD_DXF}")
    pre = await adapter.get_mass_properties()
    check(
        "import field DXF",
        await adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(FIELD_DXF),
                plane="Front",
                scale=1.0,
                position=[0.0, 0.0],
                merge_points=True,
                import_hatch=False,
                import_dimensions=False,
                add_constraints=False,
            )
        ),
    )
    name_last_feature(adapter, "FieldProfile")
    check(
        "cut field recess",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * RECESS_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "FieldRecess")
    v_field = FIELD_AREA_MM2 * RECESS_DEPTH
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    _telemetry.info(f"field recess removed {removed:.1f} mm^3 (analytic {v_field:.1f})")
    if abs(removed - v_field) > 0.02 * v_field:
        raise RuntimeError(f"field recess removed {removed:.1f}, expected {v_field:.1f}")

    # Four corner screw through-holes: ONE native Hole Wizard clearance
    # feature (4 placement points) for the #4-40 brass fillister mounting
    # screws -- #4 CLOSE fit Ø3.048 (SCREW_HOLE_SPEC; memory/fastener-policy-
    # us-customary). Cut BEFORE the
    # engraving import: wizard_holes locates its face by enumerating every
    # face of the body (COM roundtrips per face), and the engraving cut
    # explodes the body into thousands of groove wall/floor faces -- placing
    # this feature after it measured >20 min of face-walk (both runs hung
    # here, front and back face alike). Before engraving only the outline/field
    # walls exist; the pristine back face at z=-PLATE_THICKNESS carries all four
    # stations and through-all is geometrically identical from either side.
    pre = await adapter.get_mass_properties()
    screw_drives = tuple((f'"Screw{n}X"', f'"Screw{n}Y"') for n in range(len(SCREW_XY)))
    screw_cut = wizard_holes(
        adapter,
        SCREW_HOLE_SPEC,
        [[x, y, -PLATE_THICKNESS] for x, y in SCREW_XY],
        (0.0, 0.0, -1.0),
        "mounting screw holes (#4 clearance, close)",
        name="ScrewHoles",
        expect_dia_mm=SCREW_HOLE_DIA,
        placement_dims=[
            ((f"S{n}X", dx), (f"S{n}Z", dy))
            for n, (dx, dy) in enumerate(screw_drives)
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    v_holes = len(SCREW_XY) * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * PLATE_THICKNESS
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    _telemetry.info(f"screw holes removed {removed:.1f} mm^3 (analytic {v_holes:.1f})")
    if abs(removed - v_holes) > 0.02 * v_holes:
        raise RuntimeError(f"screw holes removed {removed:.1f}, expected {v_holes:.1f}")

    # Traced-photo engraving, IMPORTED from the vendored DXF (was native line-loops).
    # The whole artwork -- lettering, scroll cartouche AND pinstripe frame -- comes
    # from cad/references/fr-nameplate-engraving.dxf as 110 closed-region contours
    # (edge ribbon omitted; see module docstring), imported and cut as one
    # feature. The artwork is traced to read from +Z; because the body extrudes -Z the
    # decorated z=0 face is the exposed front (outward normal +Z), so the import reads
    # correctly with no mirror.
    #
    # The cut reaches RECESS+ENGRAVE both-directions about z=0: over the sunk field
    # the lettering incises ENGRAVE_DEPTH into the floor (the recess already cleared
    # the first RECESS_DEPTH), while over the raised border the pinstripe/frame
    # incise the full RECESS+ENGRAVE. No analytic area exists for the traced ribbons,
    # so the removed volume is bounded-checked (something engraved, well short of
    # cutting through the slab) rather than matched to a closed form.
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
                # Final plate-local placement is already baked into the DXF.
                position=[ENGRAVING_POSITION[0], ENGRAVING_POSITION[1]],
                merge_points=True,   # weld coincident ribbon endpoints into regions
                import_hatch=False,  # file carries no hatches (closed ribbons only)
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
    slab_volume = OUTLINE_AREA_MM2 * PLATE_THICKNESS
    _telemetry.info(f"engraving cut removed {removed:.1f} mm^3 (imported DXF artwork)")
    if removed <= 0.0:
        raise RuntimeError("cut engraving: nothing removed (import/cut/plane -> live)")
    if removed > 0.5 * slab_volume:
        raise RuntimeError(
            f"cut engraving: removed {removed:.1f} mm^3 -- implausibly deep "
            f"(> half the {slab_volume:.1f} mm^3 slab); check import scale/position"
        )

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

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
