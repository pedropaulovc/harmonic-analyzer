r"""Reproduction script: cone tip block (book ch. 12, p. 18; video 4/4 stills).

The small clamp block at the thin end of the cone shaft. It stands on the
swing platform right beside the pivot and journals the shaft's 1/32" tip
stub, so the shaft is carried at BOTH ends -- big-end journal in the
pivot post, tip in this block -- and the whole set swings as one unit
about the platform's pivot axis (the block sits so close to the pivot
that its throw is millimetres).

Dimensions estimated from the p.18 top-down and the v4_t00393 still
(low). The bore height above the block base is BORE_HEIGHT; the platform
adds PLATE_T under the foot, and BORE_HEIGHT + PLATE_T must equal the
drive height above the base top (54) -- asserted module-level in
build_drive_train_assembly.

Layout: block standing on the Top plane, plan centred on the origin,
tip journal bore along Z at y = BORE_HEIGHT (the assembly rotates the
block about Y to align the bore with the cone axis). Named "journal
axis" for the view-independent coaxial mate to the shaft tip.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_block.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    PANEL_BLACK,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "cone-tip-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel, like the platform it rides

BLOCK_X = 14.0  # plan width across the shaft (low)
BLOCK_Z = 12.0  # plan depth along the shaft (low)
BLOCK_HEIGHT = 55.0  # bore at 47.65 + headroom for the pinch cross-bore (low)
BORE_DIA = 0.03125 * IN  # 0.79375: the shaft's 1/32" tip stub (ch. 12 SECTIONS)
BORE_HEIGHT = 47.65  # + platform PLATE_T 6.35 = drive height 54 above base top

BORE_RADIUS = BORE_DIA / 2.0

# --- adjuster + pinch lock (item 5, v4_t00471 / 7:49) ------------------------
ADJUSTER_BORE_DIA = 7.9  # threads the cone-tip-adjuster (line-to-line)
ADJUSTER_BORE_DEPTH = 8.0  # from the NORTH face; 1/32" journal lip stays south
SLIT_W = 1.2  # top slit width (the clamp flexure)
SLIT_DEPTH = 8.0  # top face down past the bore line (55.0 -> 47.0)
PINCH_BORE_DIA = 2.4  # pinch screw cross-bore, along local X
PINCH_BORE_Y = 53.2  # between the counterbore top (51.6) and the block top

# The pinch cross-bore must land wholly in the material band between the
# adjuster counterbore's top and the block top, and the slit must cross it.
if PINCH_BORE_Y - PINCH_BORE_DIA / 2.0 < BORE_HEIGHT + ADJUSTER_BORE_DIA / 2.0 + 0.25:
    raise AssertionError("pinch bore clips the adjuster counterbore")
if PINCH_BORE_Y + PINCH_BORE_DIA / 2.0 > BLOCK_HEIGHT - 0.25:
    raise AssertionError("pinch bore breaches the block top")
if BLOCK_HEIGHT - SLIT_DEPTH > PINCH_BORE_Y - PINCH_BORE_DIA / 2.0:
    raise AssertionError("top slit does not cross the pinch bore")


def _slit_removed() -> float:
    """Slit volume net of the bores it crosses (counterbore band + journal)."""
    r_cb, y_cb, y_bot = ADJUSTER_BORE_DIA / 2.0, BORE_HEIGHT, BLOCK_HEIGHT - SLIT_DEPTH
    h = SLIT_W / 400.0
    xs = [-SLIT_W / 2.0 + k * h for k in range(401)]

    def f(x: float) -> float:
        return (y_cb + math.sqrt(max(r_cb * r_cb - x * x, 0.0))) - y_bot

    simpson = f(xs[0]) + f(xs[-1]) + 4.0 * sum(f(x) for x in xs[1:-1:2]) \
        + 2.0 * sum(f(x) for x in xs[2:-1:2])
    a_cb = simpson * h / 3.0
    v = SLIT_W * BLOCK_Z * SLIT_DEPTH
    v -= a_cb * ADJUSTER_BORE_DEPTH  # counterbore band already void
    v -= math.pi * BORE_RADIUS**2 * (BLOCK_Z - ADJUSTER_BORE_DEPTH)  # journal band
    return v


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 14 = 14 in). BoreDia carries the legacy
    # 1/32" value already reduced to mm.
    await set_global(adapter, "BlockX", f"{BLOCK_X}mm")
    await set_global(adapter, "BlockZ", f"{BLOCK_Z}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")
    await set_global(adapter, "AdjusterBoreDia", f"{ADJUSTER_BORE_DIA}mm")
    await set_global(adapter, "SlitW", f"{SLIT_W}mm")
    await set_global(adapter, "PinchBoreY", f"{PINCH_BORE_Y}mm")
    await set_global(adapter, "PinchBoreDia", f"{PINCH_BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred rectangular footprint on the Top plane.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_X / 2.0, BLOCK_Z / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockX"',
        name_depth="Depth", drive_depth='"BlockZ"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BlockX" / 2', '"BlockZ" / 2'),
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_X * BLOCK_Z * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Tip journal bore along Z at the drive height. On-axis in X (centre x 0,
    # a relation), so define_circle records only the centre-Z + diameter dims.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreX", "BoreZ", "BoreDiaDim"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_Z + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JournalBore")
    v_bore = math.pi * BORE_RADIUS**2 * BLOCK_Z
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.5 * v_bore)

    # Adjuster counterbore (v4_t00471 / 7:49): O7.9 from the NORTH face, 8
    # deep -- the partially hollow slotted adjuster screw threads in here and
    # the shaft tip rests in its cup (axial end-play takeup). The 1/32"
    # journal lip survives at the south 4.
    check("create_plane NorthFace", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Front Plane",
                              offset=BLOCK_Z / 2.0)))
    name_last_feature(adapter, "NorthFace")
    cbore = SketchDims()
    check("create_sketch counterbore", await adapter.create_sketch("NorthFace"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, ADJUSTER_BORE_DIA / 2.0, "counterbore",
        dims=cbore, names=("CbX", "CbZ", "CbDia"),
        drives=(None, '"BoreHeight"', '"AdjusterBoreDia"'),
    )
    await ensure_fully_defined(adapter, "counterbore sketch")
    check("exit_sketch counterbore", await adapter.exit_sketch())
    name_last_feature(adapter, "CounterboreProfile")
    drive_jobs += cbore.apply(adapter, "CounterboreProfile")
    # A CUT's default direction is OPPOSITE the sketch normal (FeatureCut4
    # remarks), so from the north-face plane it already bores SOUTH into the block.
    check("cut counterbore", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=ADJUSTER_BORE_DEPTH)))
    name_last_feature(adapter, "AdjusterBore")
    v_cb = (math.pi * (ADJUSTER_BORE_DIA / 2.0) ** 2 - math.pi * BORE_RADIUS**2) \
        * ADJUSTER_BORE_DEPTH
    volume = await volume_check(adapter, "counterbore", volume - v_cb, 0.02 * v_cb)

    # Top slit + perpendicular pinch screw (the McMaster 61815K41 pattern,
    # locking the ADJUSTER's threads): 1.2-wide slit from the top down past
    # the bore line, and an O2.4 cross-bore above the counterbore for the
    # pinch screw that squeezes it closed.
    check("create_plane BlockTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane",
                              offset=BLOCK_HEIGHT)))
    name_last_feature(adapter, "BlockTop")
    slit = SketchDims()
    check("create_sketch slit", await adapter.create_sketch("BlockTop"))
    await define_centered_rectangle(
        adapter, SLIT_W / 2.0, BLOCK_Z / 2.0 + 1.0, "slit", dims=slit,
        name_width="SlitW", drive_width='"SlitW"',
        name_depth="SlitSpan", drive_depth=None,
        name_corner=("SlitCx", "SlitCz"), drive_corner=(None, None),
    )
    await ensure_fully_defined(adapter, "slit sketch")
    check("exit_sketch slit", await adapter.exit_sketch())
    name_last_feature(adapter, "SlitProfile")
    drive_jobs += slit.apply(adapter, "SlitProfile")
    check("cut slit", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=SLIT_DEPTH)))  # default cut dir = down into the block
    name_last_feature(adapter, "TopSlit")
    volume = await volume_check(
        adapter, "top slit", volume - _slit_removed(), 0.02 * _slit_removed()
    )

    pinch = SketchDims()
    check("create_sketch pinch bore", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, PINCH_BORE_Y, PINCH_BORE_DIA / 2.0, "pinch bore",
        dims=pinch, names=("PinchX", "PinchZ", "PinchDia"),
        drives=(None, '"PinchBoreY"', '"PinchBoreDia"'),
    )
    await ensure_fully_defined(adapter, "pinch bore sketch")
    check("exit_sketch pinch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "PinchBoreProfile")
    drive_jobs += pinch.apply(adapter, "PinchBoreProfile")
    check("cut pinch bore", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BLOCK_X + 4.0, both_directions=True)))
    name_last_feature(adapter, "PinchBore")
    v_pinch = math.pi * (PINCH_BORE_DIA / 2.0) ** 2 * (BLOCK_X - SLIT_W)
    volume = await volume_check(adapter, "pinch bore", volume - v_pinch, 0.05 * v_pinch)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", volume, 0.5 * v_bore)

    # Named bore axis for the view-independent coaxial mate: the shaft tip
    # positions this block (coaxial + axial distance), no face picks.
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "journal axis")
    # Second named axis (Axis2): the pinch-screw cross-bore, along local X at
    # the slit -- the assembly journals the pinch screw on it.
    await name_bore_axis(adapter, "Top Plane", PINCH_BORE_Y, "Front Plane", 0.0, "pinch axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
