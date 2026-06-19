r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base near the platen that dates and
attributes the machine: "WM. GAERTNER & CO / CHICAGO, U.S.A." split by a
central scroll cartouche, on a recessed field framed by a raised border and
pinned by four slotted corner screws (p.71 macro). The book states the plate
is 100 mm x 55 mm (ch.26 p.70) -- the only hard provenance fact on the
machine, alongside the '2' stamped a few centimetres away in the baseplate
corner (a separate base feature, not modelled here).

Geometry modelled:
  * 100 x 55 plate slab;
  * a shallow rectangular recess (the darkened field) inset from the edge,
    leaving the raised perimeter border;
  * the two engraved text lines + an oval cartouche, incised into the field
    floor (SketchText, via the new _common.insert_sketch_text / add_ellipse
    raw-COM helpers -- see below);
  * four corner through-holes for the mounting screws (the screws are the
    shared brass fillister part, placed at assembly).

SketchText: the lettering is real cut geometry now, drawn with
``IModelDoc2::InsertSketchText`` reached through the adapter (the MCP wrapper
exposes no text primitive) -- the same raw-COM route :func:`insert_helix`
uses. Engraved INTO the field rather than raised proud of it (the photo shows
raised polished letters): an incise is unambiguous to build from the z=0 sketch
plane, where raised glyphs would need the field cut around them as islands. The
scroll flourishes are simplified to the central oval. The polished-border /
blackened-field two-tone finish stays appearance-level (deferred).

Dimensions: cad/DIMENSIONS.md ch.26 -- 100 x 55 stated (high); thickness,
border, recess, screw inset, the engraving heights and the rough text centring
are photo-plausible reads off the p.71 macro (low). The text x-centring uses an
average-glyph-advance estimate and wants a tuning pass on the live seat.

Layout: width along +X, height along +Y from the origin corner, decorated face
on the Front plane at z = 0, thickness extruded +Z (same scheme as
build_platen).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_ellipse,
    add_line_chain,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    insert_sketch_text,
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
# perimeter (and the lettering) stand against the sunk field.
BORDER_W = 8.0
RECESS_DEPTH = 0.4

# Engraving: glyphs + cartouche incised into the field floor. The cut is taken
# from the z=0 Front plane, so it must pass the RECESS_DEPTH of air over the
# field before biting ENGRAVE_DEPTH into the floor (see the cut below).
ENGRAVE_DEPTH = 0.3
TITLE = "WM. GAERTNER & CO"
SUBTITLE = "CHICAGO, U.S.A."
TITLE_H = 7.0   # cap height (low)
SUB_H = 6.0
# Average glyph advance ~= 0.62 * cap height for this condensed sans; used only
# to left-anchor each line near plate-centre (InsertSketchText ignores the
# centre alignment without a guide curve). Refine live.
_ADVANCE = 0.62
TITLE_BASELINE_Y = 33.0
SUB_BASELINE_Y = 11.0
ORNAMENT_CY = 27.5          # between the two lines
ORNAMENT_RX = 9.0           # oval half-width
ORNAMENT_RY = 2.2           # oval half-height


def _centre_left_x(text: str, height: float) -> float:
    """Left-anchor x that centres ``text`` on the plate (advance estimate)."""
    return PLATE_WIDTH / 2.0 - (len(text) * _ADVANCE * height) / 2.0


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


async def _removed(adapter, pre_vol: float) -> float:
    post = await adapter.get_mass_properties()
    return pre_vol - float(post.data.volume)


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
    await bbox_extent_check(adapter, "plate width (stated 100)", "x", PLATE_WIDTH)
    await bbox_extent_check(adapter, "plate height (stated 55)", "y", PLATE_HEIGHT)

    # Sink the central field (raised border). A both-directions cut of 2x depth
    # about the z=0 Front plane lands exactly 0..RECESS_DEPTH in material (the
    # -z half is air) -- the platen socket trick. Direct-db: the sketch plane is
    # coplanar with the front face, where inference picks misbehave live.
    field_w = PLATE_WIDTH - 2.0 * BORDER_W
    field_h = PLATE_HEIGHT - 2.0 * BORDER_W
    pre = await adapter.get_mass_properties()
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
    removed = await _removed(adapter, float(pre.data.volume))
    print(f"  field recess removed {removed:.1f} mm^3 (analytic {v_field:.1f})")
    if abs(removed - v_field) > 0.02 * v_field:
        raise RuntimeError(f"field recess removed {removed:.1f}, expected {v_field:.1f}")

    # Engrave the two lines + the cartouche oval into the field floor. The cut
    # starts at z=0 and must clear the RECESS_DEPTH of air over the field before
    # cutting ENGRAVE_DEPTH into the floor, so its +z reach is RECESS+ENGRAVE
    # (both-directions => 2x). Glyph area is not analytic, so this is gated by a
    # loose sanity bound (something was cut, but not the whole field) rather than
    # an exact volume.
    pre = await adapter.get_mass_properties()
    check("create_sketch engraving", await adapter.create_sketch("Front"))
    insert_sketch_text(
        adapter, TITLE, _centre_left_x(TITLE, TITLE_H), TITLE_BASELINE_Y,
        height_mm=TITLE_H, label="title",
    )
    insert_sketch_text(
        adapter, SUBTITLE, _centre_left_x(SUBTITLE, SUB_H), SUB_BASELINE_Y,
        height_mm=SUB_H, label="subtitle",
    )
    add_ellipse(adapter, PLATE_WIDTH / 2.0, ORNAMENT_CY, ORNAMENT_RX, ORNAMENT_RY,
                label="cartouche")
    check("exit_sketch engraving", await adapter.exit_sketch())
    check(
        "cut engraving",
        await adapter.create_cut_extrude(
            ExtrusionParameters(
                depth=2.0 * (RECESS_DEPTH + ENGRAVE_DEPTH), both_directions=True
            )
        ),
    )
    removed = await _removed(adapter, float(pre.data.volume))
    field_cap = field_w * field_h * ENGRAVE_DEPTH
    print(f"  engraving removed {removed:.1f} mm^3 (0 < x < field cap {field_cap:.1f})")
    if not (0.0 < removed < field_cap):
        raise RuntimeError(
            f"engraving removed {removed:.1f} mm^3, outside (0, {field_cap:.1f}) -- "
            "expected some glyph area, less than the whole field incised"
        )

    # Four corner screw through-holes (both-directions 2x thickness clears the
    # full slab; the -z half is air). They sit in the full-thickness border, so
    # the removed volume is the clean cylinder analytic.
    pre = await adapter.get_mass_properties()
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
    removed = await _removed(adapter, float(pre.data.volume))
    print(f"  screw holes removed {removed:.1f} mm^3 (analytic {v_holes:.1f})")
    if abs(removed - v_holes) > 0.02 * v_holes:
        raise RuntimeError(f"screw holes removed {removed:.1f}, expected {v_holes:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
