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
from _holes import (
    DRILL_POINT_H,
    HoleSpec,
    blind_cut_dia_mm,
    blind_hole_volume_mm3,
    wizard_holes,
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
# Adjuster interface: native 5/16-18 blind TAPPED hole from the NORTH face --
# the Ø6.2 cone-tip-adjuster threads in. NOTE: the old bore was Ø7.9
# line-to-line; the 5/16-18 tap drill is Ø6.528, so the cup narrows 7.9 ->
# 6.528 (per fastener policy we take the true tap-drill, NOT an override to the
# artefact Ø). ADJUSTER_BORE_DIA is the tap-drill, used by the slit + interlock
# geometry below (NOT imported by the assembly, so the shrink is self-contained).
ADJUSTER_BORE_DEPTH = 8.0  # from the NORTH face; 1/32" journal lip stays south
ADJUSTER_BORE_SPEC = HoleSpec(
    "tapped", "5/16-18", end="blind", depth_mm=ADJUSTER_BORE_DEPTH)
ADJUSTER_BORE_DIA = blind_cut_dia_mm(ADJUSTER_BORE_SPEC)  # 6.528 tap drill
SLIT_W = 1.2  # top slit width (the clamp flexure)
SLIT_DEPTH = 8.0  # top face down past the bore line (55.0 -> 47.0)
# Pinch screw cross-bore, along local X: native #3-48 TAPPED hole -- the Ø1.7
# cone-tip-pinch-screw threads in (build_cone_tip_pinch_screw SHANK_DIA = 1.7 =
# 1.994 - 0.3; the drive-train assembly asserts bore - shank in [0.15, 0.45],
# which needs this Ø1.994 tap-drill, not the old Ø2.4). PINCH_BORE_DIA is
# imported by the assembly as TIP_PINCH_BORE_DIA.
PINCH_BORE_SPEC = HoleSpec("tapped", "#3-48")
PINCH_BORE_DIA = blind_cut_dia_mm(PINCH_BORE_SPEC)  # 1.994 tap drill
PINCH_BORE_Y = 53.2  # between the counterbore top and the block top

# The pinch cross-bore must land wholly in the material band between the
# adjuster counterbore's top and the block top, and the slit must cross it.
if PINCH_BORE_Y - PINCH_BORE_DIA / 2.0 < BORE_HEIGHT + ADJUSTER_BORE_DIA / 2.0 + 0.25:
    raise AssertionError("pinch bore clips the adjuster counterbore")
if PINCH_BORE_Y + PINCH_BORE_DIA / 2.0 > BLOCK_HEIGHT - 0.25:
    raise AssertionError("pinch bore breaches the block top")
if BLOCK_HEIGHT - SLIT_DEPTH > PINCH_BORE_Y - PINCH_BORE_DIA / 2.0:
    raise AssertionError("top slit does not cross the pinch bore")


def _slit_removed() -> float:
    """Slit volume net of the already-void bores it crosses: the adjuster
    counterbore band, its blind-tap 118-degree DRILL-POINT cone past the
    shoulder (the term whose omission failed the first wizard build by
    +4.1 mm^3), and the 1/32" journal -- the cone and journal are concentric,
    so each z-slice subtracts the UNION circle (max radius), never both."""
    r_cb, y_cb, y_bot = ADJUSTER_BORE_DIA / 2.0, BORE_HEIGHT, BLOCK_HEIGHT - SLIT_DEPTH
    x_half = SLIT_W / 2.0

    def a_void(r: float) -> float:
        """In-slit void area of a concentric circle of radius r at bore height:
        integral over |x| < min(x_half, r) of (circle top - max(slit bottom,
        circle bottom)), Simpson."""
        if r <= 0.0:
            return 0.0
        lim = min(x_half, r)
        h = lim / 200.0
        xs = [-lim + k * h for k in range(401)]

        def f(x: float) -> float:
            s = math.sqrt(max(r * r - x * x, 0.0))
            return max((y_cb + s) - max(y_bot, y_cb - s), 0.0)

        simpson = f(xs[0]) + f(xs[-1]) + 4.0 * sum(f(x) for x in xs[1:-1:2]) \
            + 2.0 * sum(f(x) for x in xs[2:-1:2])
        return simpson * h / 3.0

    point_h = r_cb * DRILL_POINT_H  # 118-degree point height past the shoulder
    v = SLIT_W * BLOCK_Z * SLIT_DEPTH
    v -= a_void(r_cb) * ADJUSTER_BORE_DEPTH  # counterbore band already void
    # Past the shoulder the void slice is max(cone, journal) -- trapezoid in z.
    n_z = 400
    dz = (BLOCK_Z - ADJUSTER_BORE_DEPTH) / n_z
    acc = 0.0
    for k in range(n_z + 1):
        z = k * dz  # 0 at the shoulder
        r_cone = r_cb * max(1.0 - z / point_h, 0.0)
        a = a_void(max(r_cone, BORE_RADIUS))
        acc += a * (0.5 if k in (0, n_z) else 1.0)
    v -= acc * dz
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
    # (The old AdjusterBoreDia/PinchBoreDia knobs are gone: both are now native
    # Hole Wizard TAPPED features whose diameters come from the ANSI-inch tap
    # tables, not driven dims.)
    await set_global(adapter, "SlitW", f"{SLIT_W}mm")
    await set_global(adapter, "PinchBoreY", f"{PINCH_BORE_Y}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred rectangular footprint on the Top plane.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_X / 2.0, BLOCK_Z / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockX"',
        name_depth="Depth", drive_depth='"BlockZ"',
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

    # Adjuster interface (v4_t00471 / 7:49): ONE native Hole Wizard blind
    # 5/16-18 TAPPED hole from the NORTH face (z = +BLOCK_Z/2), concentric with
    # the journal, ADJUSTER_BORE_DEPTH deep -- the partially hollow Ø6.2 slotted
    # adjuster screw threads in here and the shaft tip rests in its (own) cup
    # (axial end-play takeup). Drilled while the body is still simple (block +
    # journal). Removed = the blind tap-drill cylinder + drill point MINUS the
    # journal already void within that envelope (the journal runs straight
    # through it). The 1/32" journal survives at the south.
    adjuster_cut = wizard_holes(
        adapter, ADJUSTER_BORE_SPEC,
        [[0.0, BORE_HEIGHT, BLOCK_Z / 2.0]],
        (0.0, 0.0, 1.0), "adjuster tapped hole (5/16-18 blind)", name="AdjusterBore",
        placement_dims=[((None, None), ("CbZ", '"BoreHeight"'))],
    )
    drive_jobs += adjuster_cut.placement_drive_jobs
    _adj_point = (ADJUSTER_BORE_DIA / 2.0) * DRILL_POINT_H
    v_cb = blind_hole_volume_mm3(ADJUSTER_BORE_DIA, ADJUSTER_BORE_DEPTH) \
        - math.pi * BORE_RADIUS**2 * (ADJUSTER_BORE_DEPTH + _adj_point)
    volume = await volume_check(adapter, "adjuster bore", volume - v_cb, 0.03 * v_cb)

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

    # Pinch screw cross-bore: ONE native Hole Wizard #3-48 TAPPED hole through
    # along local X at (y = PINCH_BORE_Y, z = 0), drilled from the +X block face
    # (a clean planar rectangle -- the top slit only removes the |x|<SLIT_W/2
    # centre). The top slit splits it into two solid halves, so a through-all
    # cut removes the tap-drill cylinder over (BLOCK_X - SLIT_W) of solid.
    pinch_cut = wizard_holes(
        adapter, PINCH_BORE_SPEC,
        [[BLOCK_X / 2.0, PINCH_BORE_Y, 0.0]],
        (1.0, 0.0, 0.0), "pinch tapped hole (#3-48)", name="PinchBore",
        placement_dims=[((None, None), ("PinchZ", '"PinchBoreY"'))],
    )
    drive_jobs += pinch_cut.placement_drive_jobs
    v_pinch = math.pi * (PINCH_BORE_DIA / 2.0) ** 2 * (BLOCK_X - SLIT_W)
    volume = await volume_check(adapter, "pinch bore", volume - v_pinch, 0.05 * v_pinch)

    # Named bore axis for the view-independent coaxial mate: the shaft tip
    # positions this block (coaxial + axial distance), no face picks.
    await name_bore_axis(
        adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "journal axis",
        drive_a='"BoreHeight"', drive_jobs=drive_jobs,
    )
    # Second named axis (Axis2): the pinch-screw cross-bore, along local X at
    # the slit -- the assembly journals the pinch screw on it.
    await name_bore_axis(
        adapter, "Top Plane", PINCH_BORE_Y, "Front Plane", 0.0, "pinch axis",
        drive_a='"PinchBoreY"', drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations after the model + reference axes exist,
    # then re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", volume, 0.5 * v_bore)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
