r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base near the platen that dates and
attributes the machine. From the p.71 macro: a rounded-corner brass plate with a
raised polished border, a fine pinstripe frame ringing a recessed blackened
field, and the engraving "Wm. Gaertner & Co / Chicago, U. S. A." split by a
scroll cartouche. The book states the plate is 100 mm x 55 mm (ch.26 p.70) --
the only hard provenance fact on the machine; the '2' stamped a few centimetres
away in the baseplate corner is a separate base feature, not modelled here.

The lettering, ornament and pinstripe are reproduced from the actual photo, not a
font: the polished engraving was traced off the p.71 macro (originally into DXFs,
since retired) and is now drawn with native SolidWorks **sketch primitives**:

* the glyph + scroll-cartouche contours are drawn as closed line chains from the
  vendored ``_nameplate_geometry.LETTERING_LOOPS`` and cut into the field floor;
* the pinstripe frame is two concentric rounded rectangles (true corner arcs via
  :func:`sketch_rounded_rect`), cut shallow on the raised border.

``test_nameplate_geometry`` guards the vendored geometry against the golden analytic
targets the primitives were validated to (engraving 100%, pinstripe band 99.99%,
finished volume 100%).

Dimensions: cad/DIMENSIONS.md ch.26 -- 100 x 55 stated (high); thickness, corner
radius, border, recess, pinstripe and screw inset are photo-plausible reads off
the p.71 macro (low). The engraving geometry IS the traced photo.

Layout: width along +X, height along +Y from the origin corner, decorated face on
the Front plane at z = 0, thickness extruded +Z (same scheme as build_platen).

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
)
from _features import (
    sketch_polyline_loops,
    sketch_rounded_rect,
)
from _nameplate_geometry import BORDER_INNER, BORDER_OUTER, LETTERING_LOOPS

PART_NAME = "nameplate"
MATERIAL = "Brass"  # bright cast/engraved brass plate (see _common.apply_material)

PLATE_WIDTH = 100.0  # DIMENSIONS.md ch26: stated 100 mm (p.70, high)
PLATE_HEIGHT = 55.0  # DIMENSIONS.md ch26: stated 55 mm (p.70, high)
PLATE_THICKNESS = 1.5  # thin brass plate; p.71 edge read (low)
CORNER_R = 3.0  # rounded plate corners (p.71, low)

# Raised border framing the recessed field; pinstripe frame rides the border.
BORDER_W = 8.0
RECESS_DEPTH = 0.4
ENGRAVE_DEPTH = 0.3  # incise depth of letters / ornament / pinstripe

# Four corner mounting screws (the shared brass fillister part), in the border band.
SCREW_DIA = 2.6
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)


def _shoelace(loop: list[tuple[float, float]]) -> float:
    """Signed polygon area (CCW positive)."""
    a = 0.0
    n = len(loop)
    for i in range(n):
        x1, y1 = loop[i]
        x2, y2 = loop[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def _engraving_area() -> float:
    """Even-odd filled area of the traced engraving (mm^2).

    The loops follow nesting parity -- outer glyph/ornament contours run CCW
    (positive), the 9 enclosed counters run CW (negative) -- so the signed-area
    sum is exactly the even-odd filled region the single cut removes.
    """
    return abs(sum(_shoelace(loop) for loop in LETTERING_LOOPS))


def _rrect_area(spec: tuple[float, float, float, float, float]) -> float:
    """Area of a rounded rectangle ``(cx, cy, w, h, r)``."""
    _cx, _cy, w, h, r = spec
    return w * h - (4.0 - math.pi) * r * r


def _rrect_to_args(spec: tuple[float, float, float, float, float]):
    """Reorder a ``(cx, cy, w, h, r)`` spec to sketch_rounded_rect's (w, h, r, cx, cy)."""
    cx, cy, w, h, r = spec
    return (w, h, r, cx, cy)


async def _cut_region(adapter, depth, *, label, expected_removed):
    """Exit the OPEN engraving/border sketch and both-directions cut it `depth`
    into the front face, asserting the analytically expected removed volume.

    ``depth`` is the half-reach; the cut runs 2*depth both ways about the z=0
    Front plane, landing 0..depth in material (-z half is air), same scheme as
    the field recess. ``expected_removed`` is the NEW volume this cut removes
    (overlap with the already-sunk recess excluded by the caller).
    """
    from solidworks_mcp.adapters.base import ExtrusionParameters

    pre = await adapter.get_mass_properties()
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * depth, both_directions=True)
        ),
    )
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    print(f"  {label} removed {removed:.1f} mm^3 (analytic {expected_removed:.1f})")
    if removed <= 0.0:
        raise RuntimeError(f"cut {label}: nothing removed (sketch/cut/plane -> live)")
    if abs(removed - expected_removed) > 0.02 * expected_removed:
        raise RuntimeError(
            f"cut {label}: removed {removed:.1f} mm^3, expected {expected_removed:.1f}"
        )
    return removed


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Rounded-corner plate slab (under-defined cosmetic outline -> no fully-defined gate).
    check("create_sketch outline", await adapter.create_sketch("Front"))
    await sketch_rounded_rect(
        adapter, PLATE_WIDTH, PLATE_HEIGHT, CORNER_R, PLATE_WIDTH / 2.0, PLATE_HEIGHT / 2.0
    )
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(ExtrusionParameters(depth=PLATE_THICKNESS)),
    )
    await bbox_extent_check(adapter, "plate width (stated 100)", "x", PLATE_WIDTH)
    await bbox_extent_check(adapter, "plate height (stated 55)", "y", PLATE_HEIGHT)

    # Sink the central field (raised border). Both-directions 2x depth about the
    # z=0 Front plane lands exactly 0..RECESS_DEPTH in material (-z half is air).
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
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    print(f"  field recess removed {removed:.1f} mm^3 (analytic {v_field:.1f})")
    if abs(removed - v_field) > 0.02 * v_field:
        raise RuntimeError(f"field recess removed {removed:.1f}, expected {v_field:.1f}")

    # Traced-photo engraving, drawn as native sketch line-loops (was a DXF import).
    # Lettering + cartouche incise the recessed field floor: the cut reaches
    # RECESS+ENGRAVE but the recess already cleared the first RECESS_DEPTH over the
    # field, so the NEW material removed is the engraving area x ENGRAVE_DEPTH.
    eng_area = _engraving_area()
    check("create_sketch lettering", await adapter.create_sketch("Front"))
    await sketch_polyline_loops(adapter, LETTERING_LOOPS, label="lettering")
    await _cut_region(
        adapter,
        RECESS_DEPTH + ENGRAVE_DEPTH,
        label="lettering",
        expected_removed=eng_area * ENGRAVE_DEPTH,
    )

    # Pinstripe frame: two concentric rounded rectangles (even-odd -> thin band),
    # incised ENGRAVE_DEPTH on the raised border (front face).
    band_area = _rrect_area(BORDER_OUTER) - _rrect_area(BORDER_INNER)
    check("create_sketch pinstripe", await adapter.create_sketch("Front"))
    await sketch_rounded_rect(adapter, *_rrect_to_args(BORDER_OUTER))
    await sketch_rounded_rect(adapter, *_rrect_to_args(BORDER_INNER))
    await _cut_region(
        adapter,
        ENGRAVE_DEPTH,
        label="pinstripe",
        expected_removed=band_area * ENGRAVE_DEPTH,
    )

    # Four corner screw through-holes (both-directions 2x thickness clears the slab).
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
    removed = float(pre.data.volume) - float((await adapter.get_mass_properties()).data.volume)
    print(f"  screw holes removed {removed:.1f} mm^3 (analytic {v_holes:.1f})")
    if abs(removed - v_holes) > 0.02 * v_holes:
        raise RuntimeError(f"screw holes removed {removed:.1f}, expected {v_holes:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
