r"""Reproduction script: magnifying-wheel drum (MHA-MG-010; 1 used).

The brass ring the lever wire wraps (book ch. 21, p.53 shows the wheel's brass
hub drum): pressed on the wheel's Ø14.5 spigot up to the boss, its front face
never proud of the spigot's (``mg_magnifying_wheel_geom.DRUM_RECESS``). Its
wire-centre radius sets the wheel's magnification (``mg_wheel_drum_geom``).

Layout: Front-plane annulus at the origin, extruded mid-plane (the drum's own
mid-plane on the Front plane); the assembly places it at the wheel's
``DRUM_MID_Z``.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_mg_wheel_drum.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _bore_axis import name_bore_axis
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
from mg_wheel_drum_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    DRUM_BORE,
    DRUM_BORE_BAND,
    DRUM_LEN,
    DRUM_LEN_BAND,
    DRUM_OD,
    DRUM_OD_BAND,
)

PART_NAME = "mg-wheel-drum"
MATERIAL = "Brass"  # C36000 free-machining brass bar

V_DRUM = math.pi * ((DRUM_OD / 2.0) ** 2 - (DRUM_BORE / 2.0) ** 2) * DRUM_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units.
    await set_global(adapter, "DrumOd", f"{DRUM_OD}mm")
    await set_global(adapter, "DrumBore", f"{DRUM_BORE}mm")
    await set_global(adapter, "DrumLen", f"{DRUM_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Annulus: OD + bore in ONE sketch (both on-axis circles -> only the two
    # diameter dims emit), extruded once.
    ring = SketchDims()
    check("create_sketch ring", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        DRUM_OD / 2.0,
        "drum OD",
        dims=ring,
        names=("OdCx", "OdCz", "DrumOd"),
        drives=(None, None, '"DrumOd"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        DRUM_BORE / 2.0,
        "drum bore",
        dims=ring,
        names=("BoreCx", "BoreCz", "DrumBore"),
        drives=(None, None, '"DrumBore"'),
    )
    await ensure_fully_defined(adapter, "ring sketch")
    check("exit_sketch ring", await adapter.exit_sketch())
    name_last_feature(adapter, "RingProfile")
    drive_jobs += ring.apply(adapter, "RingProfile")
    check(
        "extrude drum",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=DRUM_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Drum")
    drum_depth = name_dimensions(adapter, "Drum", ["DrumLen"])
    drive_jobs.append((drum_depth[0], '"DrumLen"'))
    await volume_check(adapter, "drum", V_DRUM, 0.005 * V_DRUM)

    # Axis1: the drum axis, model Z (Top Plane x Right Plane); the assembly
    # mates it coaxial with the wheel.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "drum axis")

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven drum (equations neutral)", V_DRUM, 0.005 * V_DRUM
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "DrumOd", *deviations(DRUM_OD_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "RingProfile", "DrumBore", *deviations(DRUM_BORE_BAND)
    )
    set_dimension_bilateral_tolerance(
        adapter, "Drum", "DrumLen", *deviations(DRUM_LEN_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(adapter, PART_NAME, {"Manufacturing Notes": DRAWING_NOTES})
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
