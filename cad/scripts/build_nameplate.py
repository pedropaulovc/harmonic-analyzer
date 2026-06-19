r"""Reproduction script: maker's nameplate (book ch. 26, pp. 70-71).

The small brass plate screwed to the base near the platen that dates and
attributes the machine. From the p.71 macro: a rounded-corner brass plate with a
raised polished border, a fine pinstripe frame ringing a recessed blackened
field, and the engraving "Wm. Gaertner & Co / Chicago, U. S. A." split by a
scroll cartouche. The book states the plate is 100 mm x 55 mm (ch.26 p.70) --
the only hard provenance fact on the machine; the '2' stamped a few centimetres
away in the baseplate corner is a separate base feature, not modelled here.

The lettering, ornament and pinstripe are reproduced from the actual photo, not a
font: the polished engraving was traced off the p.71 macro into two vendored DXFs
in plate millimetres -- cad/assets/nameplate-engraving.dxf (smoothed letters +
cartouche, cut into the field floor) and cad/assets/nameplate-border.dxf (the
pinstripe frame, cut shallow on the raised border). This script imports each and
cuts it.

Dimensions: cad/DIMENSIONS.md ch.26 -- 100 x 55 stated (high); thickness, corner
radius, border, recess, pinstripe and screw inset are photo-plausible reads off
the p.71 macro (low). The engraving geometry IS the traced photo.

Layout: width along +X, height along +Y from the origin corner, decorated face on
the Front plane at z = 0, thickness extruded +Z (same scheme as build_platen).

NOTE: the DXF-import + cut path (import_dxf_to_sketch) is not yet exercised on the
SolidWorks COM seat -- first live run is the validation pass (raw-COM stopgap
posture).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_nameplate.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from _common import (
    add_line_chain,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    import_dxf_to_sketch,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    sketch_rounded_rect,
)

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

# Traced-photo engravings (cad/assets), authored in this script's plate frame.
ASSETS = Path(__file__).resolve().parent.parent / "assets"
LETTERING_DXF = str((ASSETS / "nameplate-engraving.dxf").resolve())
BORDER_DXF = str((ASSETS / "nameplate-border.dxf").resolve())

# Four corner mounting screws (the shared brass fillister part), in the border band.
SCREW_DIA = 2.6
SCREW_INSET = 4.5
SCREW_XY = (
    (SCREW_INSET, SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, SCREW_INSET),
    (SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
    (PLATE_WIDTH - SCREW_INSET, PLATE_HEIGHT - SCREW_INSET),
)


def _select_sketch(adapter, name: str) -> None:
    """Select an existing sketch by name as the next feature's profile (raw COM)."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    ok = model.Extension.SelectByID2(name, "SKETCH", 0, 0, 0, False, 0, null_callout(), 0)
    if not ok:
        raise RuntimeError(f"could not select imported sketch {name!r} for the cut")


async def _cut_dxf(adapter, dxf_path, depth, *, label):
    """Import a DXF to a sketch, select it, and both-directions cut it `depth`
    into the front face. Returns the volume removed (mm^3)."""
    from solidworks_mcp.adapters.base import ExtrusionParameters

    pre = await adapter.get_mass_properties()
    sketch = import_dxf_to_sketch(adapter, dxf_path, label=label)
    _select_sketch(adapter, sketch)
    check(
        f"cut {label}",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * depth, both_directions=True)
        ),
    )
    post = await adapter.get_mass_properties()
    removed = float(pre.data.volume) - float(post.data.volume)
    print(f"  {label} removed {removed:.1f} mm^3")
    if removed <= 0.0:
        raise RuntimeError(f"cut {label}: nothing removed (import/cut/plane -> live)")
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

    # Traced-photo engravings. Lettering + cartouche incise the recessed field
    # floor (cut clears the RECESS_DEPTH of air first, so reach = RECESS+ENGRAVE);
    # the pinstripe frame incises ENGRAVE_DEPTH on the raised border (front face).
    await _cut_dxf(adapter, LETTERING_DXF, RECESS_DEPTH + ENGRAVE_DEPTH, label="lettering")
    await _cut_dxf(adapter, BORDER_DXF, ENGRAVE_DEPTH, label="pinstripe")

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
