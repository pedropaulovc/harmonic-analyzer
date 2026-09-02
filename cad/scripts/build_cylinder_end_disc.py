r"""Reproduction script: cylinder end disc (book ch. 13 pp. 22-25, ch. 25 p. 67; 2 used).

The plain brass disc that closes each end of the cylinder-gear sandwich: ch13
page002_img01 ("back side") and page002_img03 ("front side") both show a
toothless brass washer, a shade smaller than the 120T gears, sitting on the
arbor between the outermost station and the arbor pedestal; ch25
page001_img02 shows the back one edge-on next to the pedestal strap. It gives
the gear/rod stack a flat face to bear on at each end (the "notch" label on
p. 25 sits on the toothed gear behind it, not on this disc).

Layout: Front-plane annulus at the origin (OD DISC_DIA, bore BORE_DIA) extruded
+Z by DISC_THICK. The drive-train assembly seats one 0.5 inboard of each
pedestal strap on the cylinder arbor and locks it to the arbor.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cylinder_end_disc.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
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

PART_NAME = "cylinder-end-disc"
MATERIAL = "Brass"  # ch13 p.23/25: same bright brass as the gears

DISC_DIA = 55.0  # ch13 page002_img01 reads ~0.9 of the 62.2 gear OD (photo-scaled,
# low); capped so the north disc clears the cone-tip bushing beside gear 19 by
# 1.0 (a O60 disc grazed it -- drive-train interference gate, 2026-09)
DISC_THICK = 3.0  # ch25 page001_img02 edge-on: a gear-face-thick washer (low)
BORE_DIA = 9.6  # slips on the O9.525 (3/8 in) cylinder arbor

V_DISC = math.pi * ((DISC_DIA / 2.0) ** 2 - (BORE_DIA / 2.0) ** 2) * DISC_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "DiscDia", f"{DISC_DIA}mm")
    await set_global(adapter, "DiscThick", f"{DISC_THICK}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: OD + bore in ONE sketch (both on-axis circles -> only the two
    # diameter dims emit), extruded once.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        DISC_DIA / 2.0,
        "disc OD",
        dims=ring,
        names=("OdCx", "OdCz", "DiscDia"),
        drives=(None, None, '"DiscDia"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_DIA / 2.0,
        "arbor bore",
        dims=ring,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude ring",
        await adapter.create_extrusion(ExtrusionParameters(depth=DISC_THICK)),
    )
    name_last_feature(adapter, "Disc")
    drive_jobs.append(("D1@Disc", '"DiscThick"'))
    await volume_check(adapter, "disc", V_DISC, 0.005 * V_DISC)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven disc (equations neutral)", V_DISC, 0.005 * V_DISC)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
