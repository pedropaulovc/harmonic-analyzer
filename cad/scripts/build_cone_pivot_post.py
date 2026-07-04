r"""Reproduction script: cone pivot post + crank pedestal, ONE column.

The single green casting at the cone big end serving BOTH purposes
(user-confirmed vs v4_t00411/t00417 and ch12 p.18): the cone shaft's
big-end journal at BORE_HEIGHT, and the crank pedestal -- the crank
bore CRANK_BORE_Y higher, running along MACHINE z. It STANDS ON the
cone swing platform, so the whole crank rig (crankshaft, 16T pinion,
chain wheel, arm, handle) swings with the cone set as one unit and the
16T<->64T mesh survives the p1 disengage.

Cylindrical on purpose -- the assembly rotates it about Y (the shaft
incline, 12.52 deg) and a circular plan section reads the same at every
angle. Because the column rides the INCLINED plate, the crank bore is
OBLIQUE in the part: plan direction rotated +INCLINE from local z (=
machine z once placed), cut as a 360-degree REVOLVED cut about an
in-sketch centreline on a Top-offset plane (the is_cut revolve; the
straight extruded cut cannot make an angled bore without an angled
reference plane). The kinematic crank AXIS the crankshaft mates to
lives on the PLATFORM part ("crank axis"), not here -- this part
carries the casting geometry; the interference gate proves the shaft
fits the bore.

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (estimated;
heights re-read from the ch30 GT). BORE_HEIGHT + the platform's PLATE_T
must equal the drive height above the base top (54), and CRANK_BORE_Y
must equal Y_CRANK - Y_BASE_TOP - PLATE_T -- both asserted module-level
in build_drive_train_assembly.

Layout: cylinder standing on the Top plane, axis through the origin,
cone journal bore along Z at y = BORE_HEIGHT (the assembly rotates the
column about Y to align it with the cone axis), oblique crank bore at
y = CRANK_BORE_Y.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_pivot_post.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    define_polygon_chain,
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

PART_NAME = "cone-pivot-post"
MATERIAL = "Gray Cast Iron"  # ONE green casting: big-end journal + crank pedestal

BLOCK_DIA = 24.0  # round green column, p.18 top-down
BLOCK_HEIGHT = 100.5  # crank bore at 87.81 + 12.69 of material above (the old
# separate pedestal read ~110 above the BASE top = ~103.65 above the plate;
# this column ends just past the crank bore, video-plausible)
BORE_DIA = 0.375 * IN  # 9.525: cone shaft big-end diameter (ch. 12, legacy, med)
BORE_HEIGHT = 47.65  # + platform PLATE_T 6.35 = drive height 54 above base top
# (asserted in the assembly)

# Crank bore: same 3/8" as the crankshaft (ch. 11), running along MACHINE z
# once placed. The placement x-mirror conjugates directions, so the AUTHORED
# plan direction is (-sin I, +cos I) (see the bore feature's comment); it
# passes CRANK_BORE_DX east of the column axis (X_CRANK - ppost.x, asserted
# in the assembly).
INCLINE_DEG = 12.5182
CRANK_BORE_Y = 87.81  # Y_CRANK 144.96 - Y_BASE_TOP 50.8 - PLATE_T 6.35
CRANK_BORE_DX = 0.95  # machine X_CRANK 122.8 - ppost.x 121.85

BLOCK_RADIUS = BLOCK_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0
_SIN_I = math.sin(math.radians(INCLINE_DEG))
_COS_I = math.cos(math.radians(INCLINE_DEG))


def _bore_removed() -> float:
    """Material removed by the journal bore: a z-cylinder r=BORE_RADIUS crossing
    the O24 column -- z-chord 2*sqrt(R^2-x^2) integrated over the bore disc."""
    R, r = BLOCK_RADIUS, BORE_RADIUS
    n = 4000
    h = 2.0 * r / n

    def f(x: float) -> float:
        return 2.0 * math.sqrt(max(R * R - x * x, 0.0)) * 2.0 * math.sqrt(
            max(r * r - x * x, 0.0)
        )

    s = f(-r) + f(r)
    s += 4.0 * sum(f(-r + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-r + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block envelope and the journal
    # bore. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 24 =
    # 24 in, blowing the part up 25.4x). BoreDia carries the legacy 0.375" value
    # already reduced to mm.
    await set_global(adapter, "BlockDia", f"{BLOCK_DIA}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred circular footprint. Origin circle: only the diameter dim.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, BLOCK_RADIUS, "block circle", dims=block,
        names=("BlockCx", "BlockCz", "BlockDia"),
        drives=(None, None, '"BlockDia"'),
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
    v_block = math.pi * BLOCK_RADIUS**2 * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Big-end journal bore along Z at the drive height. On-axis in X (centre x 0,
    # a relation), so define_circle records only the centre-Z + diameter dims.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreX", "BoreZ", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_DIA + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JournalBore")
    v_bore = _bore_removed()
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Oblique crank bore: 360-degree revolved CUT about an in-sketch
    # centreline on a Top-offset plane at the crank height (proven live:
    # sketch (x, y) -> part (X, -Z)). The column is placed through the
    # x-MIRROR (bbox-"x", c=0), which CONJUGATES directions (R' = M R M):
    # an authored plan direction (sin I, cos I) lands 2*INCLINE off machine
    # z -- the exact two-lobe crankshaft interference signature the first
    # build produced. The MIRROR-COMPENSATED authoring is plan (-sin I,
    # +cos I) (sketch (-sin I, -cos I)) with the anchor at (DX*cos I,
    # -DX*sin I) sketch coords, which the conjugated placement maps to
    # machine z at DX east of the column axis. The removed volume equals
    # the straight-bore integral: the column is rotationally symmetric, and
    # the two bores are 40 apart (no boolean interaction).
    from solidworks_mcp.adapters.base import CreatePlaneParameters, RevolveParameters
    check(
        "create_plane CrankBorePlane",
        await adapter.create_plane(CreatePlaneParameters(
            mode="offset", base_plane="Top Plane", offset=CRANK_BORE_Y,
        )),
    )
    name_last_feature(adapter, "CrankBorePlane")
    check("create_sketch crank bore", await adapter.create_sketch("CrankBorePlane"))
    _dx, _dy = -_SIN_I, -_COS_I  # sketch direction (mirror-compensated, above)
    _nx, _ny = _COS_I, -_SIN_I  # in-sketch normal
    _cx, _cy = CRANK_BORE_DX * _COS_I, -CRANK_BORE_DX * _SIN_I  # axis plan point
    cbore = SketchDims()
    set_sketch_direct_db(adapter, True)
    _rect = [
        (_cx - 20.0 * _dx, _cy - 20.0 * _dy),
        (_cx + 20.0 * _dx, _cy + 20.0 * _dy),
        (_cx + 20.0 * _dx + BORE_RADIUS * _nx, _cy + 20.0 * _dy + BORE_RADIUS * _ny),
        (_cx - 20.0 * _dx + BORE_RADIUS * _nx, _cy - 20.0 * _dy + BORE_RADIUS * _ny),
    ]
    _rect_lines = await add_line_chain(adapter, _rect)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, _rect_lines, _rect, label="crank bore rect", dims=cbore,
        names=["CBAnchorX", "CBAnchorZ", "CBRunDx", "CBRunDy",
               "CBEndDx", "CBEndDy", "CBBackDx", "CBBackDy"],
        drives=[None] * 8,
    )
    # Revolve centreline: same endpoints as the rectangle's axis-side edge --
    # inference merges the endpoints, so the dimensioned rectangle fully
    # defines it (the crank-handle merged-in-centreline pattern).
    check("centreline crank bore", await adapter.add_centerline(
        _rect[0][0], _rect[0][1], _rect[1][0], _rect[1][1]))
    await ensure_fully_defined(adapter, "crank bore sketch")
    check("exit_sketch crank bore", await adapter.exit_sketch())
    name_last_feature(adapter, "CrankBoreProfile")
    check(
        "cut-revolve crank bore",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "CrankBore")
    volume = await volume_check(adapter, "crank bore", volume - v_bore, 0.01 * v_bore)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven post (equations neutral)", volume, 0.01 * v_bore)

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "journal axis")
    # Vertical centreline (Axis2), historically named "swing pivot". The p1
    # swing DOF now lives on the PLATFORM's own pivot axis (the post just rides
    # the plate); this axis remains the post's plan centreline, used by the
    # platform seat mates to locate the post on the plate.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "swing pivot")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
