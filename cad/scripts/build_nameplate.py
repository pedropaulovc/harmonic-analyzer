r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base near the platen that dates and
attributes the machine: raised polished lettering "WM. GAERTNER & CO /
CHICAGO, U.S.A." on a blackened (oxidised) recessed field, framed by a
raised polished border and pinned by four slotted corner screws (p.71
macro). The book states the plate is 100 mm x 55 mm (ch.26 p.70) -- the
only hard provenance fact on the machine, alongside the '2' stamped a few
centimetres away in the baseplate corner (a separate base feature, not
modelled here).

Geometry modelled (the photo-readable relief):
  * 100 x 55 plate slab;
  * a shallow rectangular recess (the darkened field) inset from the edge,
    leaving the raised perimeter border;
  * four corner through-holes for the mounting screws (the screws are the
    shared brass fillister part, placed at assembly).

The raised lettering + central scroll cartouche are a finish/appearance
detail, NOT geometry: there is no glyph primitive in the build toolkit and
the strokes sit far below the rectangle/circle modelling vocabulary -- the
same documented-simplification posture as the omitted fillister-screw slot.
The two-tone polished-border / blackened-field finish is likewise left to
appearance (deferred), so the part reads as a single brass body here.

Dimensions: cad/DIMENSIONS.md ch.26 -- 100 x 55 stated (high); thickness,
border width and screw inset are photo-plausible reads off the p.71 macro
(low).

Layout: width along +X, height along +Y from the origin corner, decorated
face on the Front plane at z = 0, thickness extruded +Z (same scheme as
build_platen / build_platen_paper).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "nameplate"
MATERIAL = "Brass"  # bright cast/engraved brass plate (see _common.apply_material)

PLATE_WIDTH = 100.0  # DIMENSIONS.md ch26: stated 100 mm (p.70, high)
PLATE_HEIGHT = 55.0  # DIMENSIONS.md ch26: stated 55 mm (p.70, high)
PLATE_THICKNESS = 1.5  # thin brass plate; p.71 edge read (low)

# Raised border framing the blackened field. Border width and recess depth are
# photo reads off the p.71 macro (low); the recess is what makes the polished
# perimeter stand proud of the sunk lettering field.
BORDER_W = 8.0
RECESS_DEPTH = 0.4

# Four corner mounting screws (the shared brass fillister part), centred in the
# border band so they clear the recessed field. Through-holes; the screws seat
# and thread into the base at assembly.
SCREW_DIA = 2.6
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Plate slab.
    check("create_sketch outline", await adapter.create_sketch("Front"))
    plate_rect = [
        (0.0, 0.0),
        (PLATE_WIDTH, 0.0),
        (PLATE_WIDTH, PLATE_HEIGHT),
        (0.0, PLATE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, plate_rect)
    await define_rectilinear_chain(adapter, lines, plate_rect, label="plate")
    await ensure_fully_defined(adapter, "plate outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICKNESS)),
    )
    v_slab = PLATE_WIDTH * PLATE_HEIGHT * PLATE_THICKNESS
    await volume_check(adapter, "plate slab", v_slab, 0.005 * v_slab)

    # Confirm the stated 100 x 55 footprint before sinking the field.
    await bbox_extent_check(adapter, "plate width (stated 100)", "x", PLATE_WIDTH)
    await bbox_extent_check(adapter, "plate height (stated 55)", "y", PLATE_HEIGHT)

    # Sink the central field (the blackened, lettered area), leaving the raised
    # border. A both-directions cut of 2x depth about the z=0 Front plane lands
    # exactly 0..RECESS_DEPTH in material (the -z half is air) -- the platen
    # socket trick (build_platen). Direct-db: the sketch plane is coplanar with
    # the front face, where inference picks misbehave live.
    field_w = PLATE_WIDTH - 2.0 * BORDER_W
    field_h = PLATE_HEIGHT - 2.0 * BORDER_W
    check("create_sketch field", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    field_rect = [
        (BORDER_W, BORDER_W),
        (BORDER_W + field_w, BORDER_W),
        (BORDER_W + field_w, BORDER_W + field_h),
        (BORDER_W, BORDER_W + field_h),
    ]
    field_lines = await add_line_chain(adapter, field_rect)
    await define_rectilinear_chain(adapter, field_lines, field_rect, label="field")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "field sketch")
    check("exit_sketch field", await adapter.exit_sketch())
    check(
        "cut field recess",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * RECESS_DEPTH, both_directions=True)
        ),
    )
    v_field = field_w * field_h * RECESS_DEPTH
    await volume_check(adapter, "after field recess", v_slab - v_field, 0.02 * v_field)

    # Four corner screw through-holes (both-directions 2x thickness clears the
    # full slab; the -z half is air).
    check("create_sketch screws", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for x, y in SCREW_XY:
        await define_circle(adapter, x, y, SCREW_DIA / 2.0, f"screw ({x:.1f}, {y:.1f})")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screws sketch")
    check("exit_sketch screws", await adapter.exit_sketch())
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PLATE_THICKNESS, both_directions=True)
        ),
    )
    v_holes = len(SCREW_XY) * math.pi * (SCREW_DIA / 2.0) ** 2 * PLATE_THICKNESS
    await volume_check(
        adapter, "after screw holes", v_slab - v_field - v_holes, 0.02 * v_holes
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
