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
the Front plane at z = 0. The body extrudes in -Z (``reverse_direction``) so the
decorated z=0 face is the EXPOSED FRONT face (outward normal +Z): the traced
lettering, drawn to read from +Z, then reads correctly on the face you actually
see, with no mirror. (build_platen is untextured and extrudes +Z; only this
engraved plate needs the decorated face frontmost.)

Run (SolidWorks already open)::

    uv run python cad\scripts\build_nameplate.py
"""

from __future__ import annotations

import math
import sys

from _common import (
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
    sketch_polyline_loops,
    sketch_rounded_rect,
)

import _telemetry
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
    Front plane, landing depth into the -z body (the +z half is air), same scheme
    as the field recess. ``expected_removed`` is the NEW volume this cut removes
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
    _telemetry.info(f"{label} removed {removed:.1f} mm^3 (analytic {expected_removed:.1f})")
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

    # Traced-photo engraving, drawn as native sketch line-loops (was a DXF import).
    # Lettering + cartouche incise the recessed field floor: the cut reaches
    # RECESS+ENGRAVE but the recess already cleared the first RECESS_DEPTH over the
    # field, so the NEW material removed is the engraving area x ENGRAVE_DEPTH.
    # The loops are traced to read from +Z; because the body extrudes -Z the
    # decorated z=0 face is the exposed front (outward normal +Z), so the loops
    # incise and read correctly drawn exactly as traced -- no mirror.
    # Engraving sketch = traced glyph/cartouche line-loops (sketch_polyline_loops):
    # an UNTOUCHED text/engraving feature -- no SketchDims, no recorded/driven dims
    # (the loops are the traced photo, not parametric geometry). Name only the cut.
    eng_area = _engraving_area()
    check("create_sketch lettering", await adapter.create_sketch("Front"))
    await sketch_polyline_loops(adapter, LETTERING_LOOPS, label="lettering")
    await _cut_region(
        adapter,
        RECESS_DEPTH + ENGRAVE_DEPTH,
        label="lettering",
        expected_removed=eng_area * ENGRAVE_DEPTH,
    )
    name_last_feature(adapter, "LetteringCut")

    # Pinstripe frame: two concentric rounded rectangles (even-odd -> thin band),
    # incised ENGRAVE_DEPTH on the raised border (front face).
    # Pinstripe = two concentric rounded rects drawn via sketch_rounded_rect (raw
    # lines + corner arcs, not a define_* helper): cosmetic, under-defined, no
    # recordable display dims -- like the plate outline, name only the cut.
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
    name_last_feature(adapter, "PinstripeCut")

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
