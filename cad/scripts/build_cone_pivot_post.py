r"""Reproduction script: cone pivot post (book ch. 12, p. 18).

Big-end journal post for the cone shaft. It STANDS ON the cone swing
platform (build_cone_swing_platform) near the wide south end: the p.18
top-down shows the round green post carrying the shaft's big end on the
dark wedge plate, and the whole plate -- post, shaft, cone set, tip
block -- swings horizontally about the platform's TIP-end pivot to
dis/engage the 16T from the 64T (video 4/4 stills). The post itself no
longer supplies the swing axis; it just rides the plate.

Cylindrical on purpose -- the assembly rotates it about Y (the shaft
incline, 12.52 deg) and a circular plan section reads the same at every
angle. "swing pivot" (Axis2) survives as the post's own centreline,
used by the platform seat mates.

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive supports" (estimated, low;
heights re-read from the ch30 GT). BORE_HEIGHT + the platform's PLATE_T
must equal the drive height above the base top (54) -- asserted
module-level in build_drive_train_assembly.

Layout: cylinder standing on the Top plane, axis through the origin,
journal bore along Z at y = BORE_HEIGHT (the assembly rotates the post
about Y to align the bore with the cone axis).

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
    apply_color,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "cone-pivot-post"
MATERIAL = "Gray Cast Iron"  # one green casting complex with the crank pedestal

BLOCK_DIA = 24.0  # round green post, p.18 top-down (low)
BLOCK_HEIGHT = 56.65  # journal at 47.65 + 9 of material above (low)
BORE_DIA = 0.375 * IN  # 9.525: cone shaft big-end diameter (ch. 12, legacy, med)
BORE_HEIGHT = 47.65  # + platform PLATE_T 6.35 = drive height 54 above base top
# (asserted in the assembly)

BLOCK_RADIUS = BLOCK_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0


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
