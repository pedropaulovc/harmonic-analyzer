r"""Reproduction script: rocker-bank south thrust washer (MHA-CH-009; #743 PR2; 1 used).

The steel washer on the pivot shaft between rocker 0's hub and the south
pivot-bracket ear: cut from 1/16 in stock at the rocker hub's O.D., it stands
the ear off the ch0 amplitude bar (``ch_rocker_thrust_washer_spec``). The MHA-VN-053 preload
spring sits between it and the south ear (#948 ruling R; ``rocker_bank_layout``).

Layout: Front-plane annulus at the origin (OD, bore) extruded +Z by the
thickness. The channel assembly slips it on the shaft against hub 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_thrust_washer.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_deviations import deviations
from ch_rocker_thrust_washer_spec import (
    BORE_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    OD,
    THICKNESS,
)
from ch_rocker_thrust_washer_spec import BORE_DIA as BORE_DIA

PART_NAME = "ch-rocker-thrust-washer"
MATERIAL = "Plain Carbon Steel"  # 1/16 in 1008 cold-rolled sheet

DISC_DIA = OD
DISC_THICK = THICKNESS

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
        "shaft bore",
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
    disc_depth = name_dimensions(adapter, "Disc", ["DiscThick"])
    drive_jobs.append((disc_depth[0], '"DiscThick"'))
    await volume_check(adapter, "disc", V_DISC, 0.005 * V_DISC)

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven disc (equations neutral)", V_DISC, 0.005 * V_DISC
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "BoreDia", *deviations(BORE_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # No face finish (Main 2026-09-26): the faces are the 1/16 sheet's as
    # supplied, so a roughness callout could only force the facing the stock
    # ruling avoids.
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
